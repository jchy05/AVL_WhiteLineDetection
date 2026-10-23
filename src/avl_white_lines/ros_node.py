"""ROS 2 adapter. Installed ROS supplies rclpy/cv_bridge, never pip substitutes."""
import json
import time
import math
import cv2
import struct
import numpy as np
from .config import load_config
from .detector import STAGES,Detector,render
from .components import component_dict
from .tracking import Tracker

def depth_metres(array,encoding):
    import numpy as np
    if encoding not in ('32FC1','16UC1'): raise ValueError('Depth must be 32FC1 metres or 16UC1 millimetres')
    result=np.asarray(array,dtype=np.float32)
    if encoding=='16UC1': result=result*.001
    result=result.copy(); result[~np.isfinite(result)|(result<=0)]=np.nan
    return result


def ground_cloud_points(tracks, require_depth=True):
    """Only fresh confirmed metric tracks may feed the optional costmap cloud."""
    return [(float(x),float(y),0.) for t in tracks
            if t.get('valid') and t.get('backend')=='marvin_ridge' and (not require_depth or t.get('depth_confirmed'))
            for x,y in t.get('centerline_ground',[])]


def fresh_stamp(stamp,now,max_age):
    return all(math.isfinite(x) for x in (stamp,now,max_age)) and stamp>0 and -.05<=now-stamp<=max_age

def main(argv=None):
    try:
        import rclpy
        from rclpy.node import Node
        from rclpy.qos import QoSProfile,ReliabilityPolicy,HistoryPolicy
        from sensor_msgs.msg import Image, PointCloud2, PointField
        from std_msgs.msg import String, Header
        from cv_bridge import CvBridge
    except ImportError as exc:
        raise SystemExit('Source ROS 2 and use the robot venv with system site packages. See docs/ROBOT_SETUP.md.') from exc

    class WhiteLines(Node):
        def __init__(self):
            super().__init__('avl_white_lines')
            self.declare_parameter('camera_name','front')
            self.declare_parameter('image_topic','')
            self.declare_parameter('config_path','')
            self.declare_parameter('mode','')
            self.declare_parameter('ground_frame_id','')
            self.declare_parameter('costmap_require_depth',True)
            self.declare_parameter('depth_topic','')
            self.declare_parameter('depth_sync_seconds',.03)
            self.declare_parameter('debug_stage','final')
            self.declare_parameter('process_hz',30.0)
            self.cfg=load_config(self.get_parameter('config_path').value or None)
            if self.get_parameter('mode').value: self.cfg.mode=self.get_parameter('mode').value
            self.cfg.validate()
            hz=float(self.get_parameter('process_hz').value)
            if not 0<hz<=120: raise ValueError('process_hz must be in (0,120]')
            camera=self.get_parameter('camera_name').value
            topic=self.get_parameter('image_topic').value or f'/zed_{camera}/zed_node/rgb/color/rect/image'
            qos=QoSProfile(history=HistoryPolicy.KEEP_LAST,depth=1,reliability=ReliabilityPolicy.BEST_EFFORT)
            self.pub=self.create_publisher(String,'~/detections',qos)
            self.debug=self.create_publisher(Image,'~/debug',qos)
            self.bridge=CvBridge(); self.tracker=Tracker(self.cfg); self.detector=Detector(self.cfg)
            self.depth_packet=None
            depth_topic=self.get_parameter('depth_topic').value
            if depth_topic: self.depth_sub=self.create_subscription(Image,depth_topic,self.receive_depth,qos)
            self.mask_pub=self.create_publisher(Image,'~/mask',qos)
            self.cloud_pub=self.create_publisher(PointCloud2,'~/ground_lines',qos)
            self.last_header=None; self.last_size=None
            self.pending=None; self.last_received=None; self.last_geometry=None
            self.sub=self.create_subscription(Image,topic,self.receive,qos)
            self.timer=self.create_timer(1/hz,self.tick)
            self.get_logger().info(f'Listening on {topic}; outputs {self.pub.topic_name}; config {self.cfg.mode}')

        def publish_cloud(self,tracks,header=None):
            frame_id=self.get_parameter('ground_frame_id').value
            if not frame_id: return
            header=Header(stamp=header.stamp if header else self.get_clock().now().to_msg(),frame_id=frame_id)
            points=ground_cloud_points(tracks,self.get_parameter('costmap_require_depth').value)
            data=b''.join(struct.pack('<fff',*p) for p in points)
            cloud=PointCloud2(header=header,height=1,width=len(points),is_bigendian=False,
                fields=[PointField(name=name,offset=i*4,datatype=PointField.FLOAT32,count=1) for i,name in enumerate(('x','y','z'))],
                point_step=12,row_step=12*len(points),data=data,is_dense=True)
            self.cloud_pub.publish(cloud)

        def receive_depth(self,msg):
            self.depth_packet=msg

        def receive(self,msg):
            now=time.monotonic()
            self.pending=(msg,now); self.last_received=now

        def publish(self,payload):
            payload['schema_version']=1
            self.pub.publish(String(data=json.dumps(payload,allow_nan=False)))

        def invalidate(self,reason):
            self.tracker.reset(); self.detector=Detector(self.cfg)
            self.publish_cloud([])
            if self.last_header is not None and self.mask_pub.get_subscription_count()>0:
                import numpy as np
                blank=self.bridge.cv2_to_imgmsg(np.zeros(self.last_size,np.uint8),encoding='mono8')
                blank.header=Header(stamp=self.get_clock().now().to_msg(),frame_id=self.last_header.frame_id)
                self.mask_pub.publish(blank)
            self.publish({'status':reason,'detected':False,'tracks':[],
                          'published_stamp_sec':self.get_clock().now().nanoseconds/1e9,
                          'valid_for_seconds':0})

        def tick(self):
            packet=self.pending; self.pending=None
            if packet is None:
                if self.last_received is None or time.monotonic()-self.last_received>self.cfg.max_frame_age_seconds:
                    self.invalidate('no_fresh_frame')
                return
            msg,received=packet
            stamp=msg.header.stamp.sec+msg.header.stamp.nanosec/1e9
            now_ros=self.get_clock().now().nanoseconds/1e9
            age=now_ros-stamp
            if not fresh_stamp(stamp,now_ros,self.cfg.max_frame_age_seconds) or time.monotonic()-received>self.cfg.max_frame_age_seconds:
                self.invalidate('stale_or_invalid_stamp'); return
            try:
                frame=self.bridge.imgmsg_to_cv2(msg,desired_encoding='bgr8')
                geometry=(msg.header.frame_id,frame.shape)
                if geometry!=self.last_geometry: self.tracker.reset(); self.detector=Detector(self.cfg); self.last_geometry=geometry
                stage=self.get_parameter('debug_stage').value
                want_debug=self.debug.get_subscription_count()>0
                depth=None
                dm=self.depth_packet
                if dm is not None:
                    ds=dm.header.stamp.sec+dm.header.stamp.nanosec/1e9
                    if abs(ds-stamp)<=float(self.get_parameter('depth_sync_seconds').value) and fresh_stamp(ds,now_ros,self.cfg.max_frame_age_seconds):
                        depth=depth_metres(self.bridge.imgmsg_to_cv2(dm,desired_encoding='passthrough'),dm.encoding)
                result=self.detector.detect(frame,debug=want_debug and stage!='final',depth=depth)
                tracks=self.tracker.update(result.observations,stamp)
                if 'Tracked components' in result.stages: result.stages['Tracked components']=render(result,tracks)
            except Exception as exc:
                self.get_logger().error(f'Frame rejected: {exc}')
                self.invalidate('processing_error'); return
            age=max(self.get_clock().now().nanoseconds/1e9-stamp,time.monotonic()-received)
            if age>self.cfg.max_frame_age_seconds:
                self.invalidate('processing_deadline_missed'); return
            self.last_header=msg.header; self.last_size=(msg.height,msg.width)
            self.publish_cloud(tracks,msg.header)
            self.publish({'status':'ok','source_stamp_sec':stamp,'frame_id':msg.header.frame_id,
                          'published_stamp_sec':self.get_clock().now().nanoseconds/1e9,
                          'frame_age_seconds':age,'valid_for_seconds':max(0,self.cfg.max_frame_age_seconds-age),
                          'image_size':[msg.width,msg.height],'mode':self.cfg.mode,
                          'processing_image_size':[result.original.shape[1],result.original.shape[0]],'backend':result.backend,'ground_estimate':result.ground_estimate,
                          'components':[component_dict(o,i+1) for i,o in enumerate(result.observations)],
                          'processing_ms':result.processing_ms,'detected':any(t['valid'] for t in tracks),'tracks':tracks})
            if self.mask_pub.get_subscription_count()>0:
                mask=result.mask if result.mask is not None else np.zeros(frame.shape[:2],np.uint8)
                out=self.bridge.cv2_to_imgmsg(cv2.resize(mask,(msg.width,msg.height),interpolation=cv2.INTER_NEAREST),encoding='mono8'); out.header=msg.header; self.mask_pub.publish(out)
            if want_debug:
                picture=render(result,tracks) if stage in ('final','Tracked components') else result.stages.get(stage)
                if picture is None:
                    self.get_logger().error(f'Unknown debug_stage: {stage}. Options: final or {STAGES}')
                    return
                out=self.bridge.cv2_to_imgmsg(picture,encoding='mono8' if picture.ndim==2 else 'bgr8')
                out.header=msg.header; self.debug.publish(out)

    rclpy.init(args=argv)
    node=None
    try:
        node=WhiteLines(); rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None: node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()

if __name__=='__main__': main()

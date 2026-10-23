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
from .navigation import navigation_output,populate_navigation_stages
from .calibration import camera_from_rectified_info,depth_registration_reason

def depth_metres(array,encoding):
    import numpy as np
    if encoding not in ('32FC1','16UC1'): raise ValueError('Depth must be 32FC1 metres or 16UC1 millimetres')
    result=np.asarray(array,dtype=np.float32)
    if encoding=='16UC1': result=result*.001
    result=result.copy(); result[~np.isfinite(result)|(result<=0)]=np.nan
    return result


def ground_cloud_points(tracks, require_depth=True):
    """Legacy track-geometry sampler, not navigation approval.

    Robot outputs use navigation_output and measured depth points instead.
    """
    return [(float(x),float(y),0.) for t in tracks
            if t.get('valid') and not t.get('quality_flags') and t.get('backend')=='marvin_ridge' and (not require_depth or t.get('depth_confirmed'))
            for x,y in t.get('centerline_ground',[])]


def fresh_stamp(stamp,now,max_age):
    return all(math.isfinite(x) for x in (stamp,now,max_age)) and stamp>0 and -.05<=now-stamp<=max_age

def main(argv=None):
    try:
        import rclpy
        from rclpy.node import Node
        from rclpy.qos import QoSProfile,ReliabilityPolicy,HistoryPolicy
        from sensor_msgs.msg import Image, PointCloud2, PointField, CameraInfo
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
            self.declare_parameter('camera_info_topic','')
            self.declare_parameter('depth_sync_seconds',.03)
            self.declare_parameter('debug_stage','final')
            self.declare_parameter('process_hz',30.0)
            self.cfg=load_config(self.get_parameter('config_path').value or None)
            if self.get_parameter('mode').value: self.cfg.mode=self.get_parameter('mode').value
            frame_override=self.get_parameter('ground_frame_id').value
            if frame_override:
                if self.cfg.calibration_verified and frame_override!=self.cfg.ground_frame_id:
                    raise ValueError('Ground frame override differs from verified profile; update and reverify the profile')
                self.cfg.ground_frame_id=frame_override
            self.cfg.validate()
            if not self.get_parameter('costmap_require_depth').value: raise ValueError('Navigation outputs require registered depth; RGB-only output is inspection-only')
            hz=float(self.get_parameter('process_hz').value)
            if not 0<hz<=120: raise ValueError('process_hz must be in (0,120]')
            camera=self.get_parameter('camera_name').value
            topic=self.get_parameter('image_topic').value or f'/zed_{camera}/zed_node/rgb/color/rect/image'
            qos=QoSProfile(history=HistoryPolicy.KEEP_LAST,depth=1,reliability=ReliabilityPolicy.BEST_EFFORT)
            self.pub=self.create_publisher(String,'~/detections',qos)
            self.navigation_pub=self.create_publisher(String,'~/navigation_detections',qos)
            self.navigation_mask_pub=self.create_publisher(Image,'~/navigation_mask',qos)
            self.debug=self.create_publisher(Image,'~/debug',qos)
            self.bridge=CvBridge(); self.tracker=Tracker(self.cfg); self.detector=Detector(self.cfg)
            self.depth_packet=None; self.camera_info=None
            self.camera_info_topic=self.get_parameter('camera_info_topic').value
            if self.camera_info_topic: self.info_sub=self.create_subscription(CameraInfo,self.camera_info_topic,self.receive_info,qos)
            depth_topic=self.get_parameter('depth_topic').value
            if depth_topic: self.depth_sub=self.create_subscription(Image,depth_topic,self.receive_depth,qos)
            self.mask_pub=self.create_publisher(Image,'~/mask',qos)
            self.cloud_pub=self.create_publisher(PointCloud2,'~/ground_lines',qos)
            self.last_header=None; self.last_size=None
            self.pending=None; self.last_received=None; self.last_geometry=None; self.last_source_stamp=None
            self.sub=self.create_subscription(Image,topic,self.receive,qos)
            self.timer=self.create_timer(1/hz,self.tick)
            self.get_logger().info(f'Listening on {topic}; outputs {self.pub.topic_name}; config {self.cfg.mode}')

        def receive_info(self,msg):
            self.camera_info=msg

        def publish_cloud(self,navigation,header=None):
            frame_id=self.cfg.ground_frame_id
            if not frame_id: return
            header=Header(stamp=header.stamp if header else self.get_clock().now().to_msg(),frame_id=frame_id)
            points=navigation.points if navigation is not None else []
            data=b''.join(struct.pack('<fff',*p) for p in points)
            cloud=PointCloud2(header=header,height=1,width=len(points),is_bigendian=False,
                fields=[PointField(name=name,offset=i*4,datatype=PointField.FLOAT32,count=1) for i,name in enumerate(('x','y','z'))],
                point_step=12,row_step=12*len(points),data=data,is_dense=True)
            self.cloud_pub.publish(cloud)

        def publish_navigation(self,navigation,header=None,reason=None):
            if navigation is not None and header is not None:
                check_stamp=header.stamp.sec+header.stamp.nanosec/1e9
                if not fresh_stamp(check_stamp,self.get_clock().now().nanoseconds/1e9,self.cfg.max_frame_age_seconds):
                    self.invalidate('stale_at_publish'); return False
            payload=navigation.payload() if navigation is not None else dict(eligible=False,detected=False,tracks=[],reasons=[reason],calibration_id=self.cfg.calibration_id,ground_frame_id=self.cfg.ground_frame_id)
            now=self.get_clock().now().nanoseconds/1e9
            stamp=header.stamp.sec+header.stamp.nanosec/1e9 if header else None
            payload.update(schema_version=1,status='ok' if payload['eligible'] else 'blocked',published_stamp_sec=now,
                           output_role='navigation_evidence_not_a_driving_authorization',source_stamp_sec=stamp,
                           frame_id=header.frame_id if header else (self.last_header.frame_id if self.last_header else ''),
                           valid_for_seconds=max(0,self.cfg.max_frame_age_seconds-max(0,now-stamp)) if payload['eligible'] and stamp else 0)
            self.navigation_pub.publish(String(data=json.dumps(payload,allow_nan=False)))
            self.publish_cloud(navigation,header)
            if self.last_size is not None:
                mask=navigation.mask if navigation is not None else np.zeros(self.last_size,np.uint8)
                image=self.bridge.cv2_to_imgmsg(cv2.resize(mask,(self.last_size[1],self.last_size[0]),interpolation=cv2.INTER_NEAREST),encoding='mono8')
                image.header=header if header else Header(stamp=self.get_clock().now().to_msg(),frame_id=self.last_header.frame_id)
                self.navigation_mask_pub.publish(image)
            return True

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
            self.publish_navigation(None,reason=reason)
            if self.last_header is not None and self.mask_pub.get_subscription_count()>0:
                import numpy as np
                blank=self.bridge.cv2_to_imgmsg(np.zeros(self.last_size,np.uint8),encoding='mono8')
                blank.header=Header(stamp=self.get_clock().now().to_msg(),frame_id=self.last_header.frame_id)
                self.mask_pub.publish(blank)
            self.publish({'status':reason,'output_role':'inspection_candidates','detected':False,'tracks':[],
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
            if self.last_source_stamp is not None and stamp<=self.last_source_stamp:
                self.last_source_stamp=stamp
                self.invalidate('nonmonotonic_source_stamp'); return
            if self.last_source_stamp is not None and stamp-self.last_source_stamp>self.cfg.reset_gap_seconds:
                self.tracker.reset(); self.detector=Detector(self.cfg)
            self.last_source_stamp=stamp
            try:
                frame=self.bridge.imgmsg_to_cv2(msg,desired_encoding='bgr8')
                self.last_header=msg.header; self.last_size=frame.shape[:2]
                geometry=(msg.header.frame_id,frame.shape)
                if geometry!=self.last_geometry: self.tracker.reset(); self.detector=Detector(self.cfg); self.last_geometry=geometry
                if self.camera_info_topic:
                    info=self.camera_info
                    if info is None:
                        self.invalidate('awaiting_camera_info'); return
                    if not info.header.frame_id or info.header.frame_id!=msg.header.frame_id or (info.height,info.width)!=frame.shape[:2]:
                        self.invalidate('camera_info_geometry_mismatch'); return
                    camera=camera_from_rectified_info(self.cfg.camera,info.width,info.height,info.p,
                        (info.binning_x,info.binning_y),(info.roi.x_offset,info.roi.y_offset,info.roi.width,info.roi.height))
                    if camera!=self.cfg.camera:
                        self.cfg.camera=camera; self.cfg.validate(); self.detector=Detector(self.cfg); self.tracker.reset()
                stage=self.get_parameter('debug_stage').value
                want_debug=self.debug.get_subscription_count()>0
                depth=None; depth_status='missing_depth'
                dm=self.depth_packet
                if dm is not None:
                    ds=dm.header.stamp.sec+dm.header.stamp.nanosec/1e9
                    if abs(ds-stamp)<=float(self.get_parameter('depth_sync_seconds').value) and fresh_stamp(ds,now_ros,self.cfg.max_frame_age_seconds):
                        candidate=depth_metres(self.bridge.imgmsg_to_cv2(dm,desired_encoding='passthrough'),dm.encoding)
                        depth_status=depth_registration_reason(frame.shape,candidate.shape,msg.header.frame_id,dm.header.frame_id)
                        if depth_status is None: depth=candidate; depth_status='registered_pair'
                    else: depth_status='stale_or_unsynchronized_depth'
                result=self.detector.detect(frame,debug=want_debug and stage!='final',depth=depth)
                result.diagnostics['depth_input_status']=depth_status
                result.diagnostics['calibration_source']='camera_info' if self.camera_info_topic else 'json_or_preset'
                tracks=self.tracker.update(result.observations,stamp)
                if 'Tracked components' in result.stages: result.stages['Tracked components']=render(result,tracks)
            except Exception as exc:
                self.get_logger().error(f'Frame rejected: {exc}')
                self.invalidate('processing_error'); return
            age=max(self.get_clock().now().nanoseconds/1e9-stamp,time.monotonic()-received)
            if age>self.cfg.max_frame_age_seconds:
                self.invalidate('processing_deadline_missed'); return
            self.last_header=msg.header; self.last_size=(msg.height,msg.width)
            navigation=navigation_output(result,tracks,self.cfg,frame_age_seconds=age)
            populate_navigation_stages(result,navigation)
            if not self.publish_navigation(navigation,msg.header): return
            self.publish({'status':'ok','output_role':'inspection_candidates','navigation':{'eligible':bool(navigation.tracks),'reasons':navigation.reasons},'source_stamp_sec':stamp,'frame_id':msg.header.frame_id,
                          'published_stamp_sec':self.get_clock().now().nanoseconds/1e9,
                          'frame_age_seconds':age,'valid_for_seconds':max(0,self.cfg.max_frame_age_seconds-age),
                          'image_size':[msg.width,msg.height],'mode':self.cfg.mode,
                          'processing_image_size':[result.original.shape[1],result.original.shape[0]],'backend':result.backend,'ground_estimate':result.ground_estimate,'diagnostics':result.diagnostics,
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

"""ROS 2 adapter. Installed ROS supplies rclpy/cv_bridge, never pip substitutes."""
import json
import time
import math
from .config import load_config
from .detector import STAGES,detect,render
from .tracking import Tracker

def fresh_stamp(stamp,now,max_age):
    return all(math.isfinite(x) for x in (stamp,now,max_age)) and stamp>0 and -.05<=now-stamp<=max_age

def main(argv=None):
    try:
        import rclpy
        from rclpy.node import Node
        from rclpy.qos import QoSProfile,ReliabilityPolicy,HistoryPolicy
        from sensor_msgs.msg import Image
        from std_msgs.msg import String
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
            self.bridge=CvBridge(); self.tracker=Tracker(self.cfg)
            self.pending=None; self.last_received=None; self.last_geometry=None
            self.sub=self.create_subscription(Image,topic,self.receive,qos)
            self.timer=self.create_timer(1/hz,self.tick)
            self.get_logger().info(f'Listening on {topic}; outputs {self.pub.topic_name}; config {self.cfg.mode}')

        def receive(self,msg):
            now=time.monotonic()
            self.pending=(msg,now); self.last_received=now

        def publish(self,payload):
            payload['schema_version']=1
            self.pub.publish(String(data=json.dumps(payload,allow_nan=False)))

        def invalidate(self,reason):
            self.tracker.reset()
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
                if geometry!=self.last_geometry: self.tracker.reset(); self.last_geometry=geometry
                stage=self.get_parameter('debug_stage').value
                want_debug=self.debug.get_subscription_count()>0
                result=detect(frame,self.cfg,debug=want_debug and stage!='final')
                tracks=self.tracker.update(result.observations,stamp)
            except Exception as exc:
                self.get_logger().error(f'Frame rejected: {exc}')
                self.invalidate('processing_error'); return
            age=max(self.get_clock().now().nanoseconds/1e9-stamp,time.monotonic()-received)
            if age>self.cfg.max_frame_age_seconds:
                self.invalidate('processing_deadline_missed'); return
            self.publish({'status':'ok','source_stamp_sec':stamp,'frame_id':msg.header.frame_id,
                          'published_stamp_sec':self.get_clock().now().nanoseconds/1e9,
                          'frame_age_seconds':age,'valid_for_seconds':max(0,self.cfg.max_frame_age_seconds-age),
                          'image_size':[msg.width,msg.height],'mode':self.cfg.mode,
                          'processing_ms':result.processing_ms,'detected':any(t['valid'] for t in tracks),'tracks':tracks})
            if want_debug:
                picture=render(result,tracks) if stage=='final' else result.stages.get(stage)
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

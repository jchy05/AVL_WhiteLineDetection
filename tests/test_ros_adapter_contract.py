"""Exercise ROS adapter callbacks with message doubles; not a transport/hardware test."""
import json
import sys
import time
from types import ModuleType,SimpleNamespace as NS
from dataclasses import asdict
import numpy as np
import pytest
from test_ridge import CAM,render,ground_depth,W,H
from avl_white_lines.config import Config,save_config
from avl_white_lines import ros_node


def test_navigation_topics_block_missing_inputs_and_clear_after_stale(tmp_path,monkeypatch):
    cfg=Config(backend='marvin_ridge',camera=asdict(CAM),processing_width=480,ground_live=False,max_frame_age_seconds=5,
               calibration_verified=True,calibration_id='synthetic-test',ground_frame_id='test_ground')
    path=tmp_path/'camera.json';save_config(cfg,path)
    parameters={'config_path':str(path),'image_topic':'/rgb','depth_topic':'/depth','camera_info_topic':'/info'}
    publications={};state={'now':100.}
    class Header:
        def __init__(self,stamp=None,frame_id=''):
            self.stamp=stamp or NS(sec=0,nanosec=0);self.frame_id=frame_id
    def stamp(t):
        sec=int(t);return NS(sec=sec,nanosec=round((t-sec)*1e9))
    class Clock:
        def now(self):return NS(nanoseconds=round(state['now']*1e9),to_msg=lambda:stamp(state['now']))
    class Publisher:
        def __init__(self,name):self.topic_name=name;publications[name]=[]
        def publish(self,msg):publications[self.topic_name].append(msg)
        def get_subscription_count(self):return 0 if self.topic_name=='~/debug' else 1
    class Node:
        def __init__(self,name):self.parameters={}
        def declare_parameter(self,name,default):self.parameters[name]=parameters.get(name,default)
        def get_parameter(self,name):return NS(value=self.parameters[name])
        def create_publisher(self,cls,name,qos):return Publisher(name)
        def create_subscription(self,*args):return NS()
        def create_timer(self,*args):return NS()
        def get_clock(self):return Clock()
        def get_logger(self):return NS(info=lambda *a:None,error=lambda *a:None)
        def destroy_node(self):pass
    class Message:
        def __init__(self,**kw):self.__dict__.update(kw)
    class PointField(Message):FLOAT32=7
    class Bridge:
        def imgmsg_to_cv2(self,msg,desired_encoding):return msg.array
        def cv2_to_imgmsg(self,array,encoding):return Message(array=array,encoding=encoding)
    def module(name,**attrs):
        m=ModuleType(name);m.__dict__.update(attrs);monkeypatch.setitem(sys.modules,name,m);return m
    module('rclpy.node',Node=Node)
    module('rclpy.qos',QoSProfile=lambda **kw:NS(**kw),ReliabilityPolicy=NS(BEST_EFFORT=1),HistoryPolicy=NS(KEEP_LAST=1))
    module('sensor_msgs');module('sensor_msgs.msg',Image=Message,PointCloud2=Message,PointField=PointField,CameraInfo=Message)
    module('std_msgs');module('std_msgs.msg',String=Message,Header=Header)
    module('cv_bridge',CvBridge=Bridge)
    image,_=render();depth=ground_depth()
    def image_message(array,encoding='bgr8',frame='left_optical'):
        return Message(array=array,encoding=encoding,header=Header(stamp(state['now']),frame),height=array.shape[0],width=array.shape[1])
    def nav():return json.loads(publications['~/navigation_detections'][-1].data)
    def spin(node):
        # Configured CameraInfo is mandatory; nothing is guessed while waiting.
        node.receive(image_message(image));node.tick()
        assert not nav()['eligible'] and nav()['reasons']==['awaiting_camera_info']
        K=CAM.K_for(W,H);P=np.column_stack([K,np.zeros(3)]).ravel().tolist()
        info=Message(header=Header(stamp(state['now']),'left_optical'),width=W,height=H,p=P,
                     binning_x=0,binning_y=0,roi=NS(x_offset=0,y_offset=0,width=0,height=0))
        node.receive_info(info)
        # Good synchronized depth + confirmed observations can publish measured points.
        for _ in range(3):
            state['now']+=1/30;node.receive_depth(image_message(depth,'32FC1'));node.receive(image_message(image));node.tick()
        assert nav()['eligible'] and nav()['frame_id']=='left_optical' and publications['~/ground_lines'][-1].width>0
        assert publications['~/navigation_mask'][-1].array.any()
        # Equal-sized depth in a different optical frame is not accepted as registered.
        state['now']+=1/30;node.receive_depth(image_message(depth,'32FC1','right_optical'));node.receive(image_message(image));node.tick()
        assert not nav()['eligible'] and publications['~/ground_lines'][-1].width==0
        assert not publications['~/navigation_mask'][-1].array.any()
        candidate=json.loads(publications['~/detections'][-1].data)
        assert candidate['output_role']=='inspection_candidates'
        assert candidate['diagnostics']['depth_input_status']=='depth_frame_id_mismatch'
        # Correct depth can recover. A duplicate RGB stamp clears navigation.
        for _ in range(3):
            state['now']+=1/30;node.receive_depth(image_message(depth,'32FC1'));node.receive(image_message(image));node.tick()
        assert nav()['eligible']
        node.receive(image_message(image));node.tick()
        assert not nav()['eligible'] and nav()['reasons']==['nonmonotonic_source_stamp']
        # Stream timeout publishes empty cloud and zero navigation mask.
        node.last_received=time.monotonic()-10;node.tick()
        assert not nav()['eligible'] and nav()['reasons']==['no_fresh_frame']
        assert publications['~/ground_lines'][-1].width==0
        assert not publications['~/navigation_mask'][-1].array.any()
        # If processing becomes stale immediately before publication, both
        # navigation and candidate summaries must be invalidated consistently.
        original_publish=node.publish_navigation
        def delayed_publish(navigation,header=None,reason=None):
            if navigation is not None:state['now']+=6
            return original_publish(navigation,header,reason)
        node.publish_navigation=delayed_publish
        state['now']+=1/30;node.receive_depth(image_message(depth,'32FC1'));node.receive(image_message(image));node.tick()
        assert nav()['reasons']==['stale_at_publish'] and not nav()['eligible']
        assert json.loads(publications['~/detections'][-1].data)['status']=='stale_at_publish'
        node.publish_navigation=original_publish
        # Wrong CameraInfo frame invalidates the whole pair before processing.
        state['now']+=1/30;info.header.frame_id='other_camera';node.receive(image_message(image));node.tick()
        assert nav()['reasons']==['camera_info_geometry_mismatch']
    module('rclpy',init=lambda **kw:None,spin=spin,ok=lambda:True,shutdown=lambda:None)
    ros_node.main([])
    parameters['ground_frame_id']='unverified_other_frame'
    with pytest.raises(ValueError,match='Ground frame override'):
        ros_node.main([])

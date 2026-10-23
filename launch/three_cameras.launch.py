"""One calibrated profile per camera; start one camera before measuring all three."""
from pathlib import Path
from launch import LaunchDescription
from launch.actions import ExecuteProcess


def generate_launch_description():
    root=Path(__file__).resolve().parents[1]
    exe=root/'.venv/bin/avl-lines-ros'
    processes=[]
    for camera in ('front','left','right'):
        config=root/'config/local'/(camera+'.json')
        if not config.is_file(): raise FileNotFoundError(f'Missing {config}; copy config/robot_templates and read docs/ROBOT_SETUP.md')
        z=f'/zed_{camera}/zed_node/'
        processes.append(ExecuteProcess(cmd=[str(exe),'--ros-args','-r',f'__node:=white_lines_{camera}',
            '-p',f'camera_name:={camera}','-p',f'config_path:={config}',
            '-p','image_topic:='+z+'rgb/color/rect/image',
            '-p','camera_info_topic:='+z+'rgb/color/rect/camera_info',
            '-p','depth_topic:='+z+'depth/depth_registered'],output='screen'))
    return LaunchDescription(processes)

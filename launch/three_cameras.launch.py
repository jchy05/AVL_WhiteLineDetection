"""Run with: ros2 launch ./launch/three_cameras.launch.py

Source ROS and activate .venv first. Each process has independent tracking state.
"""
from pathlib import Path
from launch import LaunchDescription
from launch.actions import ExecuteProcess

def generate_launch_description():
    root=Path(__file__).resolve().parents[1]
    exe=root/'.venv/bin/avl-lines-ros'
    return LaunchDescription([
        ExecuteProcess(cmd=[str(exe),'--ros-args','-r',f'__node:=white_lines_{cam}',
                            '-p',f'camera_name:={cam}'],output='screen')
        for cam in ('front','left','right')
    ])

#!/usr/bin/env bash
set -u
echo '=== OS / architecture ==='
uname -sm
test ! -f /etc/os-release || cat /etc/os-release
echo '=== NVIDIA release (if installed) ==='
test ! -f /etc/nv_tegra_release || head -n 1 /etc/nv_tegra_release
echo "=== ROS_DISTRO=${ROS_DISTRO:-not sourced} ==="
python3 --version
python3 -c 'import cv2,numpy; print("OpenCV",cv2.__version__,"NumPy",numpy.__version__)' || true
if command -v ros2 >/dev/null; then
  echo '=== Image topics; names only, no image recording ==='
  ros2 topic list -t | grep -E 'sensor_msgs/msg/(Image|CompressedImage|CameraInfo)|avl_white' || true
fi
echo 'Confirm actual camera topics with ros2 topic info <topic> -v'

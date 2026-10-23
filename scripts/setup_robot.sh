#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -z "${ROS_DISTRO:-}" ]]; then
  echo "Source your installed ROS first: source /opt/ros/<distro>/setup.bash"; exit 1
fi
if ! python3 -c 'import cv2, numpy, rclpy, cv_bridge' >/dev/null 2>&1; then
  echo "Missing system dependencies. Install for your installed ROS distribution:"
  echo "sudo apt install python3-venv python3-pip python3-opencv python3-numpy ros-${ROS_DISTRO}-cv-bridge"
  exit 1
fi
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -c 'import cv2, numpy, rclpy, cv_bridge; print("ROS/OpenCV imports passed")'
echo "Environment installed. Copy and measure config/robot_templates, then run: bash scripts/run_camera.sh front. See docs/ROBOT_SETUP.md."

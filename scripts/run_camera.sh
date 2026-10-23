#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
camera="${1:-front}"
case "$camera" in front|left|right) ;; *) echo 'Use front, left, or right'; exit 1;; esac
config_path="${2:-config/local/${camera}.json}"
if [[ ! -f "$config_path" ]]; then
  echo "Missing $config_path. Copy config/robot_templates/${camera}.json into config/local/ and follow docs/ROBOT_SETUP.md."
  exit 1
fi
image_topic="${AVL_IMAGE_TOPIC:-/zed_${camera}/zed_node/rgb/color/rect/image}"
info_topic="${AVL_CAMERA_INFO_TOPIC:-/zed_${camera}/zed_node/rgb/color/rect/camera_info}"
depth_topic="${AVL_DEPTH_TOPIC:-/zed_${camera}/zed_node/depth/depth_registered}"
exec .venv/bin/avl-lines-ros --ros-args -r "__node:=white_lines_${camera}"   -p "camera_name:=${camera}" -p "config_path:=${config_path}"   -p "image_topic:=${image_topic}" -p "camera_info_topic:=${info_topic}" -p "depth_topic:=${depth_topic}"

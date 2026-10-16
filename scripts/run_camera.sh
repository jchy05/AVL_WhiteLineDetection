#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
camera="${1:-front}"
case "$camera" in front|left|right) ;; *) echo 'Use front, left, or right'; exit 1;; esac
exec .venv/bin/avl-lines-ros --ros-args -r "__node:=white_lines_${camera}" -p "camera_name:=${camera}"

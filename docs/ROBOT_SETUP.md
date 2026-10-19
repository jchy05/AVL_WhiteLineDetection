# Transfer and run on MARVIN

**This guide runs the rewritten tracked detector, not the restored original viewer.** For matching the original results first, use [Original program](ORIGINAL_PROGRAM.md). The ROS adapter remains untested on the physical robot.

The bookmarked AVROS repository documents Jetson Orin / JetPack 6, ZED X cameras and ROS 2 Jazzy/Humble. That is evidence about the project, not a live inventory of your robot. Verify the installed distro and topics before running. No SSH or robot connection was available during development.

## 1. Get the repository

The repository is public. Clone it on the robot without GitHub authentication:

```bash
git clone https://github.com/jchy05/AVL_WhiteLineDetection.git
cd AVL_WhiteLineDetection
```

Alternatively, copy and unzip the supplied source archive. It contains the same code and configuration; no recordings are needed to run live. Authentication is only needed for operations that require write access, such as pushing changes.

## 2. Discover the installation

```bash
ls /opt/ros
source /opt/ros/humble/setup.bash  # substitute the installed distribution
bash scripts/probe_robot.sh
```

If the existing ZED driver runs from a workspace, source its `install/setup.bash` too. Keep the team's existing sensor bringup running; this package does not launch or reconfigure cameras.

```bash
ros2 topic list -t
ros2 topic info /zed_front/zed_node/rgb/color/rect/image -v
ros2 topic hz /zed_front/zed_node/rgb/color/rect/image
```

The current bookmarked perception code uses `/zed_{front,left,right}/zed_node/rgb/color/rect/image`. Older ZED wrappers may use `rgb/image_rect_color`; discover actual names rather than assuming them.

## 3. Install without replacing Jetson ROS libraries

If the setup script reports missing packages:

```bash
sudo apt install python3-venv python3-pip python3-opencv python3-numpy ros-${ROS_DISTRO}-cv-bridge
```

Then:

```bash
bash scripts/setup_robot.sh
bash scripts/run_camera.sh front
```

Use `.venv` with system site packages so `cv_bridge` sees the ROS-compatible NumPy/OpenCV. Do not install desktop/headless OpenCV wheels into this robot environment. The script only installs this package into its local venv.

## 4. Verify detections

In another sourced terminal:

```bash
ros2 topic echo /white_lines_front/detections --qos-reliability best_effort
ros2 run rqt_image_view rqt_image_view
```

Select `/white_lines_front/debug` in the image viewer, with best-effort QoS if offered. Debug images are computed only when someone subscribes. If `rqt_image_view` is not installed, install the matching ROS distro package. These debug images retain the source header stamp, but may be resized to the configured processing width.

Inspect a particular stage:

```bash
ros2 param set /white_lines_front debug_stage 'Article white mask'
ros2 param set /white_lines_front debug_stage 'Accepted segments'
ros2 param set /white_lines_front debug_stage final
```

## 5. Override topics or settings

```bash
cp src/avl_white_lines/default.json front.json
.venv/bin/avl-lines-ros --ros-args \
  -r __node:=white_lines_front \
  -p camera_name:=front \
  -p config_path:="$(pwd)/front.json" \
  -p image_topic:=/actual/front/image/topic \
  -p mode:=article_hsl_white \
  -p process_hz:=30.0
```

Only `debug_stage` is read dynamically. Restart after changing other node parameters/config. Match input timestamps and ROS clock; for bag playback use `-p use_sim_time:=true` and a `/clock` publisher. Invalid, zero, future, old or duplicate/nonmonotonic stamps cannot sustain confirmed tracking. A stopped camera results in `detected=false` with empty tracks after the freshness timeout.

## 6. Run three cameras

Start with one camera and measure load before enabling all three:

```bash
ros2 launch ./launch/three_cameras.launch.py
```

Or run these in separate sourced terminals:

```bash
bash scripts/run_camera.sh front
bash scripts/run_camera.sh left
bash scripts/run_camera.sh right
```

Outputs are `/white_lines_front/{detections,debug}`, `/white_lines_left/{detections,debug}`, and `/white_lines_right/{detections,debug}`. IDs are per camera; do not interpret them as shared identities. Different camera pitch/yaw can require different ROI/threshold settings. The launch example uses default configuration for each; use separate manual commands with `config_path` to tune each.

## 7. Measure actual freshness

- Check input image rate, output rate, `processing_ms`, `frame_age_seconds` and deadline rejections.
- Default processing width is 960. Reduce it (for example to 640) if end-to-end frame age is too high. Pixel-valued blur/Hough lengths may need retuning at the new resolution.
- Keep debug subscribers closed for normal timing. Display, recording and three-camera load change performance.
- Inspect masks under shadows, glare, exposure transitions, turning, barrels and missing paint. The bookmarked team's notes describe auto-exposure interacting with fixed thresholds. Change exposure only through the team's driver configuration and after checking the tradeoff in shadows.
- Disconnect/pause a camera and verify invalid output. Resume and verify reconfirmation; old lines must not remain valid.
- Record short input/detection bags for review using your team's normal recording process; camera logs can be large.

The downstream consumer must check `status`, per-track `valid`, source age, and its own watchdog. Best-effort transport can drop a notification. It must not continue using the last valid result indefinitely after the publisher stops. No motor/control topic is published by this package.

## 8. Update later

Keep local settings outside tracked source files, then:

```bash
git pull --ff-only
bash scripts/setup_robot.sh
```

Stop/restart the perception process to load the new version. Add service startup only after camera topics and configurations are verified on the actual robot.

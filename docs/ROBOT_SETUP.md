# Robot setup: measured geometry and registered depth

This guide runs the current tracked ridge version. The original viewer is separate. Software unit/callback tests have passed; actual Jetson/ROS/ZED/TF/navigation transport remains untested in this development environment. The project sources describe Jetson Orin, JetPack 6, ZED X and ROS Humble/Jazzy; verify the actual robot installation rather than treating that as a live inventory.

## 1. Install and discover

```bash
git clone https://github.com/jchy05/AVL_WhiteLineDetection.git
cd AVL_WhiteLineDetection
ls /opt/ros
source /opt/ros/humble/setup.bash  # substitute the installed distribution
# Source the existing ZED workspace's install/setup.bash if needed.
bash scripts/probe_robot.sh
bash scripts/setup_robot.sh
```

The setup script uses a venv with system site packages. Use the robot's ROS-compatible OpenCV/NumPy/cv_bridge; do not replace those with pip OpenCV wheels. It does not launch/reconfigure cameras, install services or send control commands. For offline desktop setup see [Quick start](QUICK_START.md).

Discover actual topics and inspect their headers, dimensions, rates and encoding:

```bash
ros2 topic list -t
ros2 topic info /zed_front/zed_node/rgb/color/rect/image -v
ros2 topic echo /zed_front/zed_node/rgb/color/rect/camera_info --once
ros2 topic hz /zed_front/zed_node/rgb/color/rect/image
```

The current defaults follow the upstream Marvin integration: `/zed_<camera>/zed_node/rgb/color/rect/image`, `rgb/color/rect/camera_info`, and `depth/depth_registered`. Older wrappers may differ. Check the registered depth header and size against RGB. Topic names alone do not prove registration.

## 2. Create a local measured profile

```bash
mkdir -p config/local
cp config/robot_templates/front.json config/local/front.json
```

Edit the local file, not the shipped template:

- Replace example camera intrinsics and reference dimensions with measured rectified values. With `camera_info_topic` configured, runtime intrinsics are taken from CameraInfo `P`; a change resets detector/tracker state. The current implementation rejects unsupported skew, right-camera baseline projection and unadjusted crop/binning rather than guessing.
- Measure `height_m` and downward `pitch_deg` for the actual mount. Rectify images upstream. The model assumes no unmodeled roll and a locally flat ground plane. Live depth fitting can smooth height/pitch within bounded priors; it cannot certify an arbitrary mount or terrain.
- Set `ground_frame_id` to a measured TF frame whose origin is on the ground directly below that camera, X forward in that camera's horizontal direction, Y left, Z up. Verify yaw/translation to `base_link`/map. This package does not invent or publish that transform.
- Record a meaningful `calibration_id`. Set `calibration_verified=true` only after those measurements/TF and the RGB/depth alignment have been checked. This is an operator assertion, not automatic verification. Preset strings cannot be marked verified; explicit camera fields are required.
- Keep `image_roi=[]` initially for the robot. The recording-review crop is not transferable calibration.

Local JSON under `config/local/` is ignored by Git. It survives repository updates and is not accidentally committed. Templates stay explicitly unverified and navigation stays blocked until required evidence is present.

## 3. Start one camera and inspect

```bash
bash scripts/run_camera.sh front
```

The script supplies that camera's config, rectified image, CameraInfo and registered depth topics. Override discovered topic names through `AVL_IMAGE_TOPIC`, `AVL_CAMERA_INFO_TOPIC`, `AVL_DEPTH_TOPIC`, or provide a second argument for a different config path. Example:

```bash
AVL_DEPTH_TOPIC=/actual/registered/depth bash scripts/run_camera.sh front config/local/front.json
```

To run manually:

```bash
.venv/bin/avl-lines-ros --ros-args -r __node:=white_lines_front \
  -p config_path:=config/local/front.json \
  -p image_topic:=/zed_front/zed_node/rgb/color/rect/image \
  -p camera_info_topic:=/zed_front/zed_node/rgb/color/rect/camera_info \
  -p depth_topic:=/zed_front/zed_node/depth/depth_registered
```

CameraInfo supplies intrinsics, not height/pitch or TF. If its topic is configured but unavailable/mismatched, outputs are invalidated. Matching RGB/depth size and nonempty optical frame IDs are required; stale or unsynchronized depth becomes unavailable for navigation. `32FC1` is metres, `16UC1` is millimetres and converted once. NaN/zero/Inf are invalid. The API expects optical-axis Z, not radial range or disparity.

## 4. Consume the dedicated outputs

```bash
ros2 topic echo /white_lines_front/navigation_detections --qos-reliability best_effort
ros2 run rqt_image_view rqt_image_view
```

Inspect `/white_lines_front/navigation_mask` and `/white_lines_front/debug`. Set `debug_stage` to `Navigation overlay` for on-image block reasons; `Navigation mask` for gated evidence; `Final mask` for raw candidates; `Configured image region` for any pixel crop. Only `debug_stage` is dynamic; restart for other config changes.

`/detections` and `/mask` retain **inspection candidates** for compatibility. Do not connect them to steering/costmaps. `/navigation_detections`, `/navigation_mask`, and `/ground_lines` are conservative gated evidence, not driving authorization. [Exact contract and watchdog requirements](NAVIGATION_OUTPUTS.md).

## 5. Verify before navigation integration

With actuation disabled, verify painted ground, trees/fences/people/barrels, curves, shadows, exposure transitions and missing paint. Inspect actual registered depth on each candidate. Check source/ROS clocks, depth alignment and end-to-end frame age. Withhold/disconnect depth, pause RGB, send a duplicate/backward timestamp, and stop the node: navigation evidence must expire, and the consumer watchdog must handle a publisher that cannot send a final invalidation.

Check the TF/RViz placement of measured ground points. Configure costmap observation persistence and clearing: an empty cloud does not erase historical marked cells automatically. The point cloud is ground-boundary evidence with Z=0, not a full obstacle cloud. Do not infer a traversable corridor from one line or an empty mask.

No physical validation results are available here. Complete the team's stationary/replay and controlled robot tests before connecting autonomous navigation.

## 6. Three cameras and updates

Copy/measure separate templates for left and right. First measure one-camera load with debug subscribers closed; then:

```bash
ros2 launch ./launch/three_cameras.launch.py
```

The launch file requires `config/local/{front,left,right}.json` and supplies all three topic pairs. Tracking IDs are per camera and are not fused. Actual simultaneous throughput, dropped frames, thermals and acquisition latency must be measured on the Jetson. `process_hz` is a requested processing rate, not a performance guarantee.

For updates, keep local calibration files and use:

```bash
git pull --ff-only
bash scripts/setup_robot.sh
```

Restart perception to load changes. [Current validation](GROUND_IMPROVEMENT.md) separates measurements from unfinished hardware work.

[Official interface references](HARDWARE_SOURCES.md#current-interface-cross-check-2026-10-23) support the default topic and message conventions. A ROS parameter cannot silently replace the ground-frame name in a verified profile; update/reverify the profile if the measured frame changes.

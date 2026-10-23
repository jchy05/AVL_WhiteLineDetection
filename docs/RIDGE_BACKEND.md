# Calibrated ridge backend

Use `marvin_ridge` for the proposed production pipeline **after camera calibration and robot validation**. `legacy_hough` preserves the earlier tracked HSL/HSV + Canny + Hough computation. The original `lane_pipeline_viewer.py` and its checked-in examples are unchanged.

The packaged default remains `legacy_hough` so an existing installation does not silently adopt guessed camera geometry. Start a calibrated deployment with `config/marvin_ridge.json`, replace its explicit preset with your measured camera object, and keep a separate config per camera.

## Run each backend

From the repository root, after `python -m pip install -e ".[desktop,test]"`:

```bash
python -m avl_white_lines.cli --images examples/raw --backend legacy_hough
python -m avl_white_lines.cli --video recording.mp4 --config config/marvin_ridge.json
python -m avl_white_lines.cli --video recording.mp4 --config config/hybrid_fallback.json
```

The ridge/hybrid example configs explicitly select Marvin's **front** preset. That is an example mount, not proof of calibration for the five old images or your robot today. Override with `--camera-model measured_camera.json`. An explicit preset name such as `--camera-model marvin_right` is also supported. Set `processing_width` to 480 initially; legacy retains its historical 960 default. `M` and `R` affect Hough only; `I/O` cycles the active backend's stages. Image browsing resets tracking. `T` resets track state; `A/D`, Space, `S`, and `Q/Esc` retain their meanings.

For a headless environment use `.[headless,test]` and:

```bash
python -m avl_white_lines.cli --images examples/raw --config config/marvin_ridge.json --headless --export-dir results/ridge --jsonl results/ridge.jsonl --benchmark results/timing.json
python -m avl_white_lines.cli --images consecutive_frames --config config/marvin_ridge.json --depth-dir registered_depth --headless --jsonl results/depth.jsonl
```

`registered_depth/frame_000000.npy` matches the RGB file's stem. Images and depth must have identical dimensions before resizing. Float depth is optical-axis Z in **metres**, not radial range, uint16 millimetres, disparity, or an unregistered second camera. Zero/NaN/Inf are invalid. Missing files mean RGB-only detection and `depth_confirmed=false`. An available but all-invalid depth image cannot confirm ground and usually rejects detections with the default confirmation gate.

## Calibration

A camera JSON object has `fx`, `fy`, `cx`, `cy`, `ref_width`, `ref_height`, `height_m`, `pitch_deg`. Intrinsics refer to the rectified reference image; resize uses pixel-centre scaling. Pitch is positive down. Camera optical coordinates are right/down/forward. Output ground coordinates are **X forward, Y left, Z up**, in metres, in a camera-local level ground frame. These are not automatically `base_link`, map coordinates, or the optical frame. Supply measured yaw/translation and TF before feeding a robot costmap.

The horizon is `cy - fy*tan(pitch)`. Rays intersect a flat ground plane; width/range gates depend on height and pitch. For lens distortion, rectify upstream. Presets are attributed upstream measurements at specific historical mounts, not automatic calibration. Live fitting estimates height and pitch only; roll, slopes, steps, and non-planar terrain remain limitations.

## Detection and tracking

Log linear-light luminance → multiscale Hessian ridges → ground/range/width gates → darker sides and local chroma/shade checks → hysteresis/physical length → optional depth votes → connected component centerlines → AVL tracking.

Components have a sampled metric centerline rather than only a straight fit. The adapter adds direct half-prominence cross-strip width measurement, since coarse Hessian scales can overestimate thin strips. Width uses the better-resolved portion of each component. Local quadratic smoothing suppresses pixel-grid jitter, and strips consistent with straight geometry within a width-scaled tolerance retain straight sampled centerlines. PCA orders component samples; crossing strips, loops/hairpins and merged branches can be ambiguous. Curved open strips work; this is not a general lane topology solver.

Metric association gates center distance, bidirectional centerline distance/overlap, orientation and length, with confidence in the ranking. Matching remains one-to-one. Centerlines and image polylines use time-based smoothing; confirmation still needs three consecutive hits. Held tracks decay and remain invalid; expiry, backward timestamps and long-gap resets retain AVL behavior. There is no ego-motion compensation, global identity guarantee or multi-camera fusion.

`hybrid_fallback` calls Hough only when ridge has no observation above `min_confidence`. Fallback confidence is multiplied by 0.5, backend is `legacy_hough_fallback`, and it cannot associate into a ridge track. Confirmation is therefore interrupted when the backend switches. Fallback may reintroduce bright-object false positives and has no metric/depth confirmation. Hough is not equivalent evidence to ridge.

Confidence is a heuristic of ridge response and support length, discounted without depth; it is **not** a probability or measured correctness. `depth_confirmed` records component ground evidence, not track validity. Physical gate defaults: 2.5–15 cm width, 30 cm length, 12 m range; high/low response .22/.10, side-log contrast .10, 4 cm object height, depth ground ratio .5, above-ground vote .3.

## Depth and live ground

Depth gate rejects components with too many above-floor votes and requires enough symmetric agreement with expected ground depth. Farther-than-floor depth does not count as confirmation. An isolated bad sample does not decide the whole component. Live RANSAC samples valid depth below the expected horizon, rejects implausible normals/heights/inlier counts, takes a five-fit median and then smooths the estimated height/pitch. It does not recover arbitrarily wrong calibration: mount height must be within 35 cm and pitch within the fit's angular window. Fitting defaults to every 15 frames.

## Stages

I/O displays Original, Log luminance, Ground region, Ridge response, Selected ridge scale, Ridge orientation, Width gate, Side-darkness gate, Color gate, Length gate, Depth/object gate, Connected components, Tracked components, Final mask, Final overlay. Float maps are normalized for inspection, not additional thresholds. Gate maps show individual pixel evidence; Length includes hysteresis and upstream shade/length filtering; Depth/object also reflects final physical component checks. Connected components show accepted cores. Tracked components show the tracked overlay. Final mask/overlay show single-frame segmentation, which can exist while tracks are still tentative.

## ROS

```bash
avl-lines-ros --ros-args -p config_path:=/absolute/path/front.json -p image_topic:=/zed_front/zed_node/rgb/color/rect/image -p depth_topic:=/registered/depth
```

RGB and depth must be registered. Depth accepts `32FC1` metres or `16UC1` millimetres; the node converts once, pairs within `depth_sync_seconds` (default .03), and rejects stale depth. Intrinsics are supplied through JSON; there is no automatic CameraInfo replacement. Missing/out-of-sync depth uses RGB-only mode. `~/detections` retains freshness-aware JSON; `~/mask` publishes native-image-size mono8 segmentation; `~/debug` accepts the stage names above or `final`. Latest-frame buffering and missed-deadline invalidation are retained. The mask is single-frame evidence, not confirmed tracked occupancy; consumers must enforce timestamps. Optional `~/ground_lines` publishes XYZ PointCloud2 samples for costmap consumers when `ground_frame_id` is explicitly configured. Define that frame in TF from the measured mount (origin under the camera at the ground, X forward/Y left). Only current valid ridge tracks are included; default `costmap_require_depth=true` also requires depth confirmation. Empty clouds and zero masks are published on invalidation. Configure the Nav2 obstacle source, ground-height acceptance and expiry/clearing policy yourself: an empty cloud does not erase old marked costmap cells. There is no automatic transform, clearing policy, or steering integration in this change.

## Validation

Run `python -m pytest tests -q`, `python scripts/check_original_reference.py --strict-bytes`, and `python scripts/benchmark_backends.py --repeat 3`. See [validation measurements](../validation/backend_benchmark.json).

Synthetic labels measure pixel precision/recall including dilation borders, component precision/recall, false components/frame and centerline errors. They are a small construction-label check, not a representative test set. The stricter boundary criterion is **<10 px and <2 degrees**. Real frames 0/410/474/710/1077 have no reviewed labels or verified camera model: their results are smoke/timing only. No real-world accuracy improvement, moving-sequence ID-switch rate, GPU/Jetson FPS, ROS transport/depth synchronization or robot navigation safety has been established. Memory is Python-traced peak, not total process/GPU memory. Three-camera timing uses independent serial detector instances on duplicate streams, not physical cameras.

Upstream source and tests are attributed in `src/avl_white_lines/MARVIN_PROVENANCE.md`. Upstream has no license file; attribution does not establish redistribution rights.

## Python streaming API

```python
from avl_white_lines.config import load_config
from avl_white_lines.detector import Detector
from avl_white_lines.tracking import Tracker
cfg = load_config("config/marvin_ridge.json")
detector, tracker = Detector(cfg), Tracker(cfg)  # keep these per camera
# On each fresh frame:
result = detector.detect(bgr, depth=registered_depth_m)
tracks = tracker.update(result.observations, source_stamp_seconds)
```

The old functional `detect(frame, cfg)` API remains available for stateless calls. Use a persistent `Detector` for live ground history and cached geometry. Reset/recreate detector and tracker when camera geometry changes.

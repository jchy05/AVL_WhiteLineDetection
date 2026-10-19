# AVL_WhiteLineDetection

White-line perception for MARVIN, with two explicitly separate programs:

- **Original viewer (start here):** the working frame-by-frame detector from this chat, with the same grouping/fitting, native image resolution, three filters and 17 stages.
- **Experimental tracked version:** a rewritten detector with independent line hypotheses, persistent IDs and a ROS 2 adapter. Its results differ from the original.

The initial upload omitted the original viewer. It is now restored; see the [handoff correction](docs/ORIGINAL_PROGRAM.md) for exactly what changed. Runs on CPU with OpenCV; no neural-network weights or GPU setup required.

## Your five raw frames and their results

**[View frames 0, 410, 474, 710 and 1077, with all three filter results](examples/README.md).** The repository now includes those five original raw JPEGs unchanged, fifteen full-resolution final PNGs, and all 17 stage previews. The rest of the 1,078-frame recording is still excluded.

Open `examples/gallery.html` from a downloaded copy for an offline interactive comparison (A/D images, I/O stages, M filters). Or run the original viewer directly on the included frames:

```bash
python lane_pipeline_viewer.py examples/raw
```

On Windows, **Show Sample Frames.cmd** opens those five included frames directly after desktop dependencies are installed.

These results use the restored original detector at native input resolution, not the rewritten tracked pipeline. The example page displays failures as well as successful fits.

## Run the original program

After installing desktop dependencies (`python -m pip install -e ".[desktop]"`), run:

```bash
python lane_pipeline_viewer.py /path/to/original_raw_frames
```

On Windows, double-click **Start Lane Viewer.cmd** and select the raw-image folder. With an installed package, `avl-lines-original /path/to/images` does the same. The original detector is unchanged; input/output locations are portable. `--export` saves all stages of the first frame.

For the **experimental tracked ROS adapter**, use [Robot setup](docs/ROBOT_SETUP.md). That adapter is not the original detector and has not been tested on the physical Jetson/ZED X. The code publishes perception only. Image-coordinate lines are not steering commands or ground-plane lane boundaries.

## On the robot

Clone this private repository using your GitHub credentials, then:

```bash
cd AVL_WhiteLineDetection
source /opt/ros/humble/setup.bash  # use jazzy instead if that is what is installed
bash scripts/setup_robot.sh
bash scripts/run_camera.sh front
```

The installer uses the robot's existing ROS, NumPy, OpenCV and cv_bridge. It tells you what is missing instead of replacing Jetson/ROS libraries with pip wheels. See the setup guide for topic discovery, three cameras, debug viewing and recording.

## On a personal computer

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[desktop]"
python lane_pipeline_viewer.py /path/to/raw_frames
```

For the separate tracked version, use `avl-lines-tracked --images /path/to/raw_frames --play` (or `python -m avl_white_lines.cli`). Manual A/D browsing resets tracking because skipped/reversed images do not represent a continuous camera stream. Initial detections are tentative until observed three consecutive times. That behavior differs from the original viewer, which draws per-frame fits immediately.

```bash
python -m avl_white_lines.cli --video recording.mp4
python -m avl_white_lines.cli --camera 0
python -m avl_white_lines.cli --images /path/to/raw_frames --headless \
  --jsonl results/detections.jsonl --benchmark results/timing.json
```

ZED X GMSL cameras should use the existing ZED ROS driver, rather than assuming they are USB camera index 0. Headless installations can use `.[headless]` instead of `.[desktop]`; install only one OpenCV wheel variant. On the robot use the system OpenCV and plain `-e .`.

## Tracked-version controls

| Key | Action |
| --- | --- |
| I / O | Previous / next inspection stage |
| M | Article HSL white → Previous HSV defaults → Saved HSL |
| R | Rectangle starting 40% from top / article trapezoid |
| A / D, arrows | Previous / next image, reset temporal history |
| Space | Play/pause image sequences |
| T | Reset tracking |
| S | Save comparison, selected stage and effective configuration to `results/` |
| Q / Esc | Quit |

The final panel uses tracked lines. Colored lines are current confirmed estimates; gray dashed lines are tentative or briefly held, and are **invalid** in machine-readable output. The fitted-line inspection stage shows unsmoothed frame estimates, so you can inspect the effect of tracking.

## Exactly the requested stages

1. Original
2. HSV saturation
3. HSV value
4. HSL lightness (HSV has value, not lightness)
5. HSL saturation
6. Article white mask
7. Previous HSV mask
8. Saved HSL mask
9. Active color mask
10. Filtered original
11. Grayscale
12. Gaussian blur
13. Canny edges
14. ROI edges
15. Raw Hough segments
16. Accepted segments
17. Fitted line mask

The article mask keeps HSL lightness 200–255 with any hue/saturation. Previous HSV uses H=0–180, S=0–30, V=195–255. Saved HSL uses H=0–36, L=59–205, S=0–40. OpenCV calls HSL `HLS`, with channel order H,L,S. Hue is encoded at half-degrees (normally 0–179); upper bound 180 includes all encoded hues.

The active mask is the chosen one of those three. The filtered original keeps the original pixels inside that mask, then becomes grayscale, Gaussian blur (11×11), Canny (50/150), and ROI-limited edges. These feed Hough segments.

## What changed for streaming

- Separate line hypotheses are extracted with length-supported geometric consensus. No fixed left/center/right bins assign a lane identity.
- Up to four independent line hypotheses can be tracked; IDs follow position and angle over their common observed height. IDs are local to a camera and process session.
- One-to-one association, three consecutive hits before confirmation, and time-based smoothing reduce unstable reassignment.
- Brief misses are shown as held for at most 0.15 seconds, with falling confidence and `valid=false`. Old or discontinuous timestamps reset tracking; a 0.5-second gap resets all tracks.
- Live camera capture uses one latest-frame slot. ROS uses best-effort depth-one image subscription and a processing timer. Old images and missed processing deadlines produce invalid results.
- Headless mode skips channel preview and overlay allocations. Processing width, thresholds, ROI, timeouts and tracker settings live in one JSON file.

Accepted segments are a **geometric heuristic**, not semantic recognition. Short/flat segments are rejected. Each potential line votes for nearby aligned segments; the strongest qualifying set is fitted and removed, then the process repeats. Foreground reach and vertical span reject small isolated bright objects. The tracker then associates these hypotheses across frames.

## Configuration and outputs

The authoritative bundled file is [`src/avl_white_lines/default.json`](src/avl_white_lines/default.json). Copy it to customize:

```bash
mkdir -p config
cp src/avl_white_lines/default.json config/front.json
python -m avl_white_lines.cli --images /path/to/images --config config/front.json
```

Use independent settings and tracker instances for each camera. The retained Saved HSL preset includes mid-gray pixels and can select asphalt; it is a comparison preset, not an automatically optimal default.

The JSON `color_bounds` contains editable lower/upper channel bounds for all three modes. Article/Saved HSL use H,L,S order; Previous HSV uses H,S,V. These ship with the exact values above. If you change them for a camera, save that camera's JSON alongside its deployment settings.

See [Output contract](docs/OUTPUT_SCHEMA.md), [validation](docs/VALIDATION.md), and [hardware/source notes](docs/HARDWARE_SOURCES.md). Apart from the five explicitly included sample frames and their generated results, recordings, machine-specific paths, credentials and runtime logs are excluded from Git.

## Limits and next deployment step

This release fits straight lines over supported image height. It does not model tight curves, infer a drivable corridor, calibrate pixels into meters, fuse cameras, or compensate for vehicle motion. Tracking reduces flicker but cannot restore paint lost by a color threshold. ZED auto-exposure can change threshold coverage; validate the mask on live images and configure the existing camera driver deliberately.

Core tests and recorded-frame timing run on the development computer. ROS transport, Jetson end-to-end latency and camera-specific accuracy require the on-robot checks in the setup guide. There are no labeled lane annotations here, so no accuracy score is claimed.

## Provenance

The per-frame sequence follows [Eddie Forson's lane-line article](https://medium.com/computer-car/udacity-self-driving-car-nanodegree-project-1-finding-lane-lines-9cd6a846c58c) and its [notebook](https://github.com/kenshiro-o/CarND-LaneLines-P1). This is a new implementation with normalized geometry and tracking, not a copy of the notebook. The prior filters are the user's earlier MARVIN presets.

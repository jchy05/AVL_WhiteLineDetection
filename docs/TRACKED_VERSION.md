# Experimental tracked version

Use this after trying the [original viewer](START_HERE.md). This is a rewritten detector, not a behavior-preserving real-time port. Its grouping, fitting, processing resolution and temporal behavior can produce different results. The physical Jetson/ROS camera path remains unverified.

## Run

After desktop installation, use your local environment's Python:

```bash
python -m avl_white_lines.cli --images examples/raw --play
python -m avl_white_lines.cli --video recording.mp4
python -m avl_white_lines.cli --camera 0
```

`avl-lines-tracked` is the installed command for the same CLI. The older `avl-lines` alias also selects this version. ZED X GMSL cameras should use the team's ZED ROS driver and the [ROS adapter](ROBOT_SETUP.md), rather than assuming a USB camera index.

For headless replay and timing:

```bash
python -m avl_white_lines.cli --images examples/raw --headless \
  --jsonl results/detections.jsonl --benchmark results/timing.json
```

For a dedicated standalone headless environment, install `.[headless]` instead of `.[desktop]`. Install only one OpenCV wheel variant. The robot setup guide uses the existing system ROS/OpenCV libraries instead.

## Controls

| Key | Action |
| --- | --- |
| I / O | Previous / next inspection stage |
| M | Next of the three filter modes |
| R | Rectangle / article trapezoid |
| A / D or arrows | Previous / next image; resets tracking |
| Space | Play/pause image sequences |
| T | Reset tracking |
| S | Save comparison, stage, final image, metadata and effective settings to `results/` |
| Q / Esc | Quit |

Use sequential playback to evaluate tracking. Manual A/D browsing resets history, so detections become tentative again. Default confirmation requires three consecutive observations. The checked-in samples are widely separated frames and are useful for mask inspection; playing just those five does not represent a continuous real-time recording.

### Why the five samples can all report `detected: false`

`detected` means at least one **confirmed, freshly measured, sufficiently supported track**, not that the frame contained no white pixels or line segments. A run over just frames 0, 410, 474, 710 and 1077 may produce five successful JSONL rows with `detected: false` throughout. Large changes between these scenes can prevent three matching consecutive observations. Inspect `tracks`, their `status`/`hits`, and the original viewer's masks for per-frame evidence. No confirmed track does not by itself mean the CLI failed.

To evaluate tracking, supply your own consecutive frames, a real recording via `--video`, or live camera input. A synthetic sequential-video test checks the confirmation mechanism in the test suite, but does not establish performance on the robot. Do not lower confirmation thresholds just to make the five separated samples report success.

The final panel uses tracked estimates. Colored lines are freshly measured and confirmed; gray dashed lines are tentative or briefly held and marked invalid. The fitted-line inspection stage shows the unsmoothed per-frame estimate.

## Settings

The authoritative defaults are in [`src/avl_white_lines/default.json`](../src/avl_white_lines/default.json). Copy that file for each camera rather than editing the packaged defaults. Then pass `--config path/to/front.json`, or `config_path` in ROS.

Settings cover processing width, ROI, color bounds, blur/Canny/Hough values, candidate limits, matching, smoothing, confirmation and expiry. `color_bounds` uses H,L,S for Article/Saved HSL and H,S,V for Previous HSV. These JSON settings do **not** configure the original viewer.

## Streaming behavior and limits

- Length-supported consensus extracts up to four independent line hypotheses per frame; there are no fixed lane-position IDs.
- One-to-one position/angle matching over shared observed height maintains session-local IDs.
- Time-based smoothing defaults to 0.08 seconds. Confirmation defaults to three consecutive observations.
- Missing tracks are held for at most 0.15 seconds, with falling confidence and `valid=false`. Timestamp discontinuities or a gap over 0.5 seconds reset history.
- Camera input uses one latest-frame slot; ROS uses a depth-one image subscription and rejects old input or missed deadlines.

The detector still fits straight lines, not curved ground-plane lanes. It does not infer a drivable corridor, convert pixels to meters, fuse cameras, or publish steering commands. Smoothing introduces delay and cannot fix incorrect color selection. Use [Validation](VALIDATION.md) for measured development timing and outstanding robot checks, and [Output schema](OUTPUT_SCHEMA.md) before consuming detections.

## Metric and curved tracking

The description above covers the legacy Hough/original paths. The calibrated ridge backend adds physical components, sampled curves, metric tracking, optional registered depth and live ground estimation. See [ridge backend](RIDGE_BACKEND.md) for commands, stages and limits, and [benchmark data](../validation/backend_benchmark.json) for measured synthetic checks and unlabeled real smoke tests. Existing defaults and original reference images remain unchanged in behavior.

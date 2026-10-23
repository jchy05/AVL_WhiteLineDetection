# Tracking and streaming behavior

Use the [quick start](QUICK_START.md) for installation and the [configuration guide](../config/README.md) to select a backend. The original `lane_pipeline_viewer.py` is a separate frame-by-frame baseline; it has no temporal tracker and its saved outputs remain unchanged.

## Run

```bash
python -m avl_white_lines.cli --images examples/raw --config config/recording_review.json
python -m avl_white_lines.cli --video recording.mp4 --config config/marvin_ridge.json
python -m avl_white_lines.cli --images consecutive_frames --config config/marvin_ridge.json --headless --jsonl results/candidates.jsonl
```

The recording-review profile is a scene-specific crop for inspection. The full-frame ridge profile requires an explicit camera model/preset; robot templates need measured data. ZED X input uses the [ROS adapter](ROBOT_SETUP.md), not an assumed USB index.

## What tracking does

`marvin_ridge` extracts sampled curved components in camera-local ground coordinates. Metric association checks common geometric support, centerline similarity, position, orientation, length and confidence. Expensive pairwise distances are evaluated after cheap impossible-match rejection. Greedy matching remains one-to-one; a component cannot update two tracks in the same frame. Each camera owns independent IDs and calibration history.

`legacy_hough` preserves the earlier tracked straight `x=a*y+b` hypotheses and normalized image-space matching. `hybrid_fallback` uses ridge first, then explicitly tagged/discounted Hough when necessary; Hough fallback cannot match into a ridge track or qualify navigation.

Time-based smoothing defaults to 0.08 seconds. Ridge tracks smooth sampled metric/image centerlines; legacy tracks smooth line coefficients. Physical metadata and frame-local component labels refer to the current measurement. A `component_label` is not a persistent tracking ID.

## Track lifecycle

| State/field | Meaning |
| --- | --- |
| Tentative | Fewer than the required consecutive matching observations |
| Measured | Confirmed and observed this frame; candidate `valid` also requires minimum confidence |
| Held | Previously confirmed but currently missing; explicitly invalid and confidence decays |
| Expired | Missing beyond the hold period; removed |

Confirmation defaults to **three consecutive hits**. Hold defaults to **0.15 seconds**. A backward/nonadvancing timestamp or gap over **0.5 seconds** resets tracker history; IDs are not recycled as if they were an old observation. ROS additionally invalidates duplicate/backward input before publication and resets detector history across gaps. Manual A/D browsing resets tracking. An interrupted camera cannot leave a measured track valid indefinitely.

The five checked-in frames (0, 410, 474, 710, 1077) are far apart. A successful five-row replay may report candidate `detected=false` because objects do not match across three consecutive frames. That is not the same as an empty segmentation mask. Use consecutive recording playback to evaluate continuity.

## Candidate validity is not navigation eligibility

Tracking can make a tree detection stable. It does not establish paint semantics, calibration correctness or a drivable corridor. Additional width/length estimates are diagnostics by default; flagged components remain visible as evidence but do not qualify the navigation outputs.

The viewer's tracked panel and legacy JSON `tracks`/`detected` remain **inspection candidates**. Separate navigation evidence requires verified calibration provenance, matching registered depth and fresh confirmed unflagged metric components. Missing inputs give empty/blocked navigation output, which means unknown rather than clear road. [Exact contract and receiver watchdog](NAVIGATION_OUTPUTS.md).

## Controls and streaming

I/O selects the inspection stage, A/D or arrows changes images, Space plays/pauses, T resets tracking, S saves and Q/Esc quits. M/R affect Hough settings only. The current ridge viewer has 18 stages, including configured image region and navigation mask/overlay; the original viewer keeps its 17 stages.

Camera capture uses one latest-frame slot; ROS uses depth-one subscriptions and rejects stale inputs/missed deadlines. Debug rendering, export, logging and multiple cameras affect throughput. End-to-end source age and the receiver watchdog matter more than a detector-only FPS number.

There is no ego-motion compensation, global identity guarantee, multi-camera fusion, drivable-corridor inference or steering output. Curves are represented by sampled centerlines; branches/crossings/hairpins remain difficult. [Current measured validation and unfinished hardware work](GROUND_IMPROVEMENT.md) and [output fields](OUTPUT_SCHEMA.md) describe practical limits.

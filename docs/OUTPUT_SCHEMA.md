# Detection output, schema version 1

ROS publishes JSON in `std_msgs/msg/String` on the node-private `~/detections` topic. This avoids custom-message compilation and is intended as an inspectable integration interface. Standalone `--jsonl` uses the same track fields. Parse JSON; never depend on string formatting or field order.

Each track has:

| Field | Meaning |
| --- | --- |
| `id` | Persistent session-local ID; separate namespace per camera |
| `a`, `b` | Normalized straight line: x = a*y + b |
| `y_min`, `y_max` | Normalized observed vertical support, not inferred horizon |
| `confidence` | Support/residual heuristic in [0,1], not a probability or measured accuracy |
| `status` | `tentative`, `measured`, or `held` |
| `valid` | True only for confirmed, freshly measured, sufficiently supported tracks |
| `age_seconds` | Time since this track was last observed |
| `hits` | Total matched observations in this track's lifetime |

Coordinates: x goes right; y goes down. Convert to source pixels with `x_pixel=(a*y_norm+b)*(width-1)` and `y_pixel=y_norm*(height-1)`. Points outside [0,1] are outside the image, not metric coordinates. Do not infer heading in the ground plane from image slope. Camera intrinsics/extrinsics, ground-plane projection and controller design are separate work.

ROS envelopes contain `source_stamp_sec`, `frame_id`, `published_stamp_sec`, `frame_age_seconds`, `valid_for_seconds`, original `image_size=[width,height]`, `mode`, `processing_ms`, `detected`, and `tracks`. `detected` means at least one valid track, not both corridor boundaries. Expiry is based on source age; receiving a packet later does not make its lines fresh again.

Invalid ROS statuses (`no_fresh_frame`, `stale_or_invalid_stamp`, `processing_deadline_missed`, `processing_error`) always have `detected=false`, `tracks=[]`, `valid_for_seconds=0`. Track IDs increase for the process lifetime and are not reused on a tracker reset. They restart when the process restarts.

Standalone timestamps: image/video replay uses frame index divided by supplied/inferred FPS, not wall time; camera mode uses monotonic arrival time at `read()`. This cannot prove the sensor itself is not buffering. ROS uses the actual image header and ROS clock; replay must use a consistent clock.

Held tracks are for debugging/short visual continuity and always invalid. Even a `measured` track can have `valid=false` if confidence falls. A downstream consumer should use an explicit source-time deadline and clear state on invalid messages or missing output. Output delivery is best effort with depth one.

## Additive ridge fields (schema version 1 retained)

Existing keys retain their meaning. Consumers should ignore unknown keys. Frame output adds `backend`, `processing_image_size`, `ground_estimate`, and `components`. Component IDs are frame-local; track IDs remain session-local. Components are single-frame evidence; `detected` still requires a confirmed current valid track. Components do not acquire track validity implicitly.

Components and tracks add `backend`, `centerline_ground` (list of [X forward, Y left] metres), `centerline_image` (normalized [x,y] samples), `length_m`, `width_m`, `heading_rad` (overall chord heading from forward toward left), and `depth_confirmed`. `local_headings_rad` contains one tangent heading per sampled centerline point. `a,b` remain the best straight approximation in normalized image coordinates and cannot represent the curve. Legacy/fallback centerlines are empty, physical lengths/widths are zero (unavailable), and depth confirmation is false. Fallback is tagged `legacy_hough_fallback` and its confidence is halved.

`ground_estimate` provides height, downward pitch, live-estimate state, whether this frame accepted a fit, and depth availability/gating state. It is not a robot/map transform. Binary masks are available from the Python FrameResult and ROS mono8 topic, not embedded in JSON. Python masks have processing dimensions; ROS resizes to native source size. Track fields/centerline_image are resolution independent.

Stale input/deadline failures still publish invalid empty tracks with zero validity duration in ROS. CLI camera deadline failures clear tracks and set `processing_deadline_missed`. Held tracks are never current valid measurements. Consumers of standalone mask topics must enforce header freshness as well. See [ridge backend](RIDGE_BACKEND.md).

## Component policy and diagnostics

`component_policy` defaults to `diagnostic`. The ridge mask keeps upstream segmentation, while additional component width/length estimates flag uncertain measurements and multiply their confidence by .75. `strict` opts into secondary component rejection. Both retain the upstream ridge/width/shade/color/length/depth gates.

Frames add `diagnostics` with `component_policy` and per-component label, pixel count, processing-size bounding box, estimated width/length, flags and rejection state when available. `quality_flags` propagates through observations and tracks. A flagged track can be freshly measured/confirmed; that is not an assertion that its physical dimensions are reliable. Optional costmap point clouds exclude flagged tracks even when `valid=true` and depth-confirmed. Legacy tracks have an empty flag list. The final segmentation mask and tracked geometry remain separate outputs.

## Current navigation contract

Existing CLI/ROS candidate fields are retained and labeled `output_role=inspection_candidates`. CLI adds `navigation` with eligible tracks and explicit reasons. Dedicated ROS `~/navigation_detections` has `eligible`, `detected`, `tracks`, `reasons`, calibration/ground-frame identifiers, source/publication timestamps and `valid_for_seconds`; blocked evidence has empty tracks and zero validity. `~/navigation_mask` and `~/ground_lines` follow the same gates. Ground points are sampled from measured registered depth; they are not RGB-only line extrapolations. See [exact checks and consumer watchdog](NAVIGATION_OUTPUTS.md).

Current components/tracks include frame-local `component_label` for matching current depth evidence; it is not a persistent identity. Frame diagnostics include ROI removal counts, navigation reasons, and ROS calibration/depth input status. The optional `image_roi` is an explicit inspection constraint, not depth confirmation. Current calibration provenance fields are documented in [configuration guide](../config/README.md).

## Ridge rejection diagnostics

`diagnostics.gate_pixels` counts candidate pixels inside the configured image region after each cumulative filter: `ridge_candidates`, `side_darkness`, `color`, `width`, `hysteresis`, `shade`, `length`, and `depth`. These counts decrease or stay equal in that order. `width` is the combined ridge-core mask after width filtering, not the independent width-only debug view. `final_dilated` counts the final displayed mask and may increase because of dilation, or decrease under strict component policy.

Connected-component shade/length decisions still run before the image crop. Counts describe retained evidence in the crop; they do not mean each filter was recomputed on cropped components. They are processing-resolution pixels, not native pixels, confidence probabilities or accuracy measurements. The legacy Hough backend does not supply these ridge-specific fields.

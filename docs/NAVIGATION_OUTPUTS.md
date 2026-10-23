# Inspection candidates and navigation evidence

The detector can find bright strips on trees, fences and objects. An image crop reduces some of these candidates but does not establish that remaining pixels lie on the ground. Stable tracking also does not establish correctness.

## Outputs

| Output | Meaning | Robot consumer |
| --- | --- | --- |
| ROS `~/detections`, CLI `tracks`/`detected` | Existing candidate/track contract; `output_role=inspection_candidates` | Inspection only |
| ROS `~/mask`, debug `Final mask` | Single-frame candidate segmentation | Inspection only |
| ROS `~/navigation_detections`, CLI `navigation` | Eligible metric/depth evidence or an explicit blocked result | Enforce freshness and your own watchdog |
| ROS `~/navigation_mask` | Only currently eligible component pixels with confirming ground depth | Enforce header freshness |
| ROS `~/ground_lines` | Bounded samples of measured registered-depth points in the configured local ground frame | Requires correct TF and costmap configuration |

The old candidate names remain for compatibility. They are not navigation authorization. New integrations should consume only the dedicated navigation outputs. Nothing in this package publishes steering or motor commands.

## Eligibility rules

Navigation outputs stay empty unless **all** checks pass:

1. Current status is OK and source timestamps meet the frame-age limit. ROS duplicate/backward timestamps clear outputs and reset state; long gaps reset history. Freshness is checked again at navigation publication.
2. Backend is `marvin_ridge`; Hough and hybrid Hough fallback never qualify.
3. `calibration_verified=true`, a nonempty `calibration_id`, explicit measured camera fields, and a configured `ground_frame_id`. A preset name cannot be marked verified. The verification flag is an operator assertion, not an automatic certificate.
4. Registered optical-axis depth in metres is supplied and its ground gate is active. ROS requires matching image size, matching nonempty optical frame names, and timestamps within the sync/freshness bounds. These checks cannot prove physical registration; use the driver's registered topic.
5. Track is confirmed, freshly measured and valid. Tentative/held tracks and component quality flags are excluded.
6. The current component has confirming ground depth and finite measured points within `maximum_range_m`.

Navigation mask pixels must also intersect the actual current candidate mask and per-pixel ground-confirmation mask. Point-cloud X/Y comes from measured optical depth plus the mount rotation, not from projecting unverified image pixels onto a guessed floor. Z is emitted as zero in the measured local ground frame because this output represents ground boundaries. It is not a generic obstacle cloud or a global map.

`costmap_require_depth=false` is rejected by the ROS node. Missing depth is allowed for inspection; it cannot enable navigation. A recording-specific ROI never substitutes for calibration/depth.

## Blocked and stale behavior

`navigation.eligible=false`, empty tracks/points, zero navigation mask, `valid_for_seconds=0`, and reason strings are expected when inputs are absent or fail checks. Examples: `calibration_not_verified`, `ground_frame_not_configured`, `no_registered_depth_gate`, `no_current_confirmed_ground_tracks`, `awaiting_camera_info`, `camera_info_geometry_mismatch`, `nonmonotonic_source_stamp`, `stale_at_publish`.

Source interruption, stale frames, processing errors and missed deadlines publish empty navigation evidence. The downstream subscriber still needs its own watchdog: a crashed process cannot send an invalidation, and best-effort ROS delivery can drop messages. Use source timestamps/validity duration at consumption time. An empty point cloud does not erase prior marked Nav2 cells; configure observation persistence and clearing behavior explicitly.

## Limits

These checks are conservative software gates, not proof of safe autonomous driving. Calibration/TF can be wrong despite a verification flag. Bad stereo, synchronization, non-flat terrain, roll, glare and depth bleeding can defeat assumptions. CameraInfo supplies rectified intrinsics; it does not measure mount height, pitch, yaw or translation. The ROS callback contract is tested with message doubles; actual ROS transport, ZED registration, TF and the physical robot remain untested here.

## Consumer watchdog helper

`avl_white_lines.navigation.navigation_message_available(message, ros_now_seconds, receipt_age_monotonic_seconds, max_frame_age)` validates the dedicated ROS navigation payload's role, status, nonempty eligible tracks, source age, publication TTL and local receipt timeout. Call it on a timer as well as on message receipt. A process crash or dropped invalidation then expires availability even without another message.

A `False` result means **unavailable/unknown**, not clear road. The actual planner/controller must pause or choose its validated sensor fallback accordingly. This package does not stop an already moving robot or install a planner safety interlock. That integration requires the actual robot stack and remains outstanding. The offline CLI's inspection JSON is not a live navigation watchdog message.

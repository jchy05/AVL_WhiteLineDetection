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

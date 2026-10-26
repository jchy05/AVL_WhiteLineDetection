# Choose a configuration

| File | Purpose | Navigation |
| --- | --- | --- |
| `legacy_hough.json` | Tracked color/Hough comparison | Ineligible |
| `marvin_ridge.json` | Full-frame Marvin RGB reference; no image crop | Blocked until calibration/depth/track checks pass |
| `recording_review.json` | Fast recording inspection at 480 px; lower 45% crop | Unverified example; blocked |
| `recording_detail.json` | Slower 960 px inspection of the same recording; same filters and crop | Unverified example; blocked |
| `hybrid_fallback.json` | Explicit discounted Hough fallback comparison | Fallback is ineligible |
| `marvin_ridge_strict.json` | Optional secondary width/length experiment | Same navigation checks; can reject real paint with wrong calibration |
| `robot_templates/{front,left,right}.json` | Example camera mounts/intrinsics to replace on robot | Unverified and blocked |

Copy robot templates to `config/local/` and edit measured values. Local JSON is ignored by Git so updates do not replace or publish your camera settings. `calibration_verified=true` is an operator assertion requiring an explicit camera object, a nonempty `calibration_id`, and a measured TF `ground_frame_id`; it is not automatic certification. CameraInfo can supply rectified intrinsics, not mount height/pitch or TF. See [robot setup](../docs/ROBOT_SETUP.md).

The original `lane_pipeline_viewer.py` does not use these JSON configurations. The package default remains legacy Hough for compatibility.

The detail profile is an explicit offline inspection choice. It recovers paint missed at 480 px in investigated frames, but does not establish higher general accuracy or real-time robot speed. See the [detail investigation](../docs/DETECTION_DETAIL_REVIEW.md) for evidence, remaining false detections and reproducible comparison commands.

# Change log

## Evaluation tooling — 2026-10-26

- Full 1,078-frame continuity/runtime review, per-frame numerical records and a 24-frame diverse review queue.
- Raw-image centerline editor with explicit reviewer/negative state, edit invalidation, export and reload.
- Reviewed-only native-pixel boundary scoring with <10 px / <2 degree thresholds, bidirectional coverage, one-to-one matching, image identity checks and frozen predictions.
- No production detection or navigation algorithm changes and no invented real ground truth.

## 0.2.0 — ground-region and navigation improvements — 2026-10-23

- Optional explicit image polygon; separate `recording_review` profile crops this recording's upper background while preserving the full-frame reference profile.
- Inspection outputs labeled as candidates. Separate navigation JSON/mask/point cloud require measured calibration provenance, registered depth, fresh confirmed unflagged metric tracks and current per-pixel ground evidence.
- Point cloud samples measured depth rather than extrapolating an RGB-only ground projection. Missing inputs, stale/duplicate/backward frames and processing errors clear navigation output.
- Rectified CameraInfo support with geometry validation and tracker reset on calibration changes; wrong-size/frame depth is rejected for navigation.
- Early metric-association rejection reduces unnecessary pairwise distance work. Three-camera launch/scripts use per-camera local configs and supply image/CameraInfo/depth topics.
- Current documentation map, quick start, navigation contract, configuration guide, local-config protection, sparse image audit, sequential smoke report and callback-contract tests.

## Previous milestones (historical measurements)

1. Original AVL viewer restored with unchanged raw samples and saved reference outputs.
2. Initial Marvin ridge integration added curved metric components, tracking and depth support.
3. Direct comparisons exposed over-aggressive secondary width rejection and thicker dilation.
4. Segmentation fix restored exact full-frame RGB mask parity with Marvin; secondary component checks became diagnostics by default, with strict rejection opt-in.

See [documentation map](docs/INDEX.md) for current guides and the dated comparison records. Original viewer behavior and saved references remain the baseline.

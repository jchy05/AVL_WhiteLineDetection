# AVL_WhiteLineDetection

Inspect white-line candidates, track curved ground components, and keep uncertain image detections separate from navigation evidence. The original AVL viewer and its saved results remain available unchanged.

**Start with the [quick start](docs/QUICK_START.md).** The [documentation map](docs/INDEX.md) lists current guides and separates them from historical experiments.

## Run the five-image review

After installing in a virtual environment with `.[desktop,test]`:

```bash
python -m avl_white_lines.cli --images examples/raw --config config/recording_review.json
```

**I/O** changes the inspection stage; **A/D** changes images; **Space** plays; **T** resets tracking; **S** saves; **Q/Esc** quits. This profile crops the upper 55% of this recording, reducing background candidates. It can also remove distant paint and is not robot calibration. [Installation and headless export](docs/QUICK_START.md).

The five raw images are frames **0, 410, 474, 710, 1077**. Their original comparisons and 17-stage previews are in [examples](examples/README.md). The full recording is not distributed.

## Understand the outputs

| Output | Use |
| --- | --- |
| Candidate mask and tracked candidates | Inspection; bright trees/fences can still resemble paint |
| Navigation JSON, mask and measured-depth point cloud | Requires calibration provenance, matching registered depth, fresh confirmed unflagged metric tracks |
| Blocked/empty navigation evidence | Unknown/unavailable input, not a clear road or permission to drive |

The sample recording has no verified calibration/depth, so navigation is **expected to stay blocked**. The actual planner must enforce eligibility, timestamps and its own watchdog. This package does not stop or steer a robot. [Navigation contract](docs/NAVIGATION_OUTPUTS.md).

## Choose the right configuration

| Profile/program | Purpose |
| --- | --- |
| `lane_pipeline_viewer.py examples/raw` | Original AVL native-resolution baseline, unchanged |
| `config/marvin_ridge.json` | Full-frame Marvin-compatible RGB comparison |
| `config/recording_review.json` | Recording-specific road-region inspection at 480 px |
| `config/recording_detail.json` | Slower inspection at 960 px, recovering paint missed in investigated frames |
| `config/legacy_hough.json` | Tracked HSL/HSV + Hough comparison |
| `config/hybrid_fallback.json` | Explicit discounted Hough fallback; fallback never qualifies for navigation |
| `config/robot_templates/` | Per-camera templates to replace with measured robot data |

The package default remains legacy Hough for compatibility; use an explicit profile for the current ridge path. [All configuration choices](config/README.md).

## Current evidence and remaining work

[Current validation report](docs/GROUND_IMPROVEMENT.md) includes the five-frame sparse audit, 120-frame sequential smoke, test coverage, CPU timings and known limits. These are not representative real-world precision/recall or robot performance claims. Full-frame RGB parity with Marvin and all original reference outputs remain regression checks.

Physical ROS/ZED registration, TF placement, the downstream planner interlock, Jetson load and controlled robot operation still require hardware validation. [Robot setup](docs/ROBOT_SETUP.md) uses separate local camera files and image/CameraInfo/depth topics.

For the known missed-paint frames, see the [detailed detection investigation](docs/DETECTION_DETAIL_REVIEW.md). The slower detail profile changes resolution only; it is not a calibrated robot profile.

## Measure the next improvement

The [full-recording review](docs/FULL_RECORDING_REVIEW.md) covers all 1,078 local frames and identifies output gaps for inspection. A [label editor and scorer](docs/EVALUATION_WORKFLOW.md) now support reviewed paint centerlines, the <10 px / <2 degree criterion, and frozen prediction comparisons. Unreviewed drafts never count as accuracy ground truth.

[Compare available versions](docs/AVAILABLE_VERSIONS.md) reproduces actual historical code and current profiles on the same images, with no invented results.

## Find the code and history

- `src/avl_white_lines/`: detector, camera/region geometry, depth/component metadata, tracking, navigation gates, CLI and ROS adapter.
- `config/`: named review/reference profiles and robot templates; `config/local/*.json` is ignored by Git.
- [tests/](tests/README.md): regression and software-contract test map.
- [scripts/](scripts/README.md): task-based command catalog for checks, review, scoring, comparisons and robot helpers.
- `examples/`: unchanged five-frame originals, saved stages and offline original gallery.
- [validation/](validation/README.md): current numerical evidence and frozen historical measurements.
- [docs/](docs/INDEX.md): current guides; [docs/history/](docs/history/README.md) holds earlier reports and [docs/images/](docs/images/README.md) holds illustrations.
- `results/`, `recordings/`, `data/`, `config/local/`: local work, recordings and calibration; ignored by Git.

[Change log](CHANGELOG.md) · [Repository guide](docs/REPOSITORY_GUIDE.md) · [Original program record](docs/history/ORIGINAL_PROGRAM.md).

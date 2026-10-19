# Where things live

You only need the examples and original viewer for a first run. The source package and ROS files are for development or experimental streaming.

```text
AVL_WhiteLineDetection/
├── README.md                     Start page and quick run commands
├── lane_pipeline_viewer.py        Original viewer entry point
├── Show Sample Frames.cmd        Windows: open the five included images
├── Start Lane Viewer.cmd          Windows: choose your own image folder
├── examples/
│   ├── README.md                 Static comparison page for GitHub
│   ├── gallery.html              Offline interactive results gallery
│   ├── raw/                      Five unchanged original JPEGs
│   ├── generated/                Final PNGs, stage previews, comparisons
│   └── manifest.json             Frame hashes, stage paths and run metadata
├── docs/                         Setup, explanations and validation
├── src/avl_white_lines/           Python implementation
├── scripts/                      Robot helpers and example generation
├── launch/                       Experimental three-camera ROS launch
├── tests/                        Automated checks
├── .github/workflows/            Linux test automation
└── pyproject.toml                Package/dependency/command definitions
```

`results/`, `.venv/`, cache files and the full recording are local runtime files, not checked-in source. Only the five requested raw images and their generated example results are deliberately included.

## Which source file should I read?

| File under `src/avl_white_lines/` | Responsibility |
| --- | --- |
| `original_viewer.py` | The original detector, three preset masks, 17 stages, viewer and keyboard handling. Read this to understand the reproduced results. |
| `detector.py` | The experimental rewritten per-frame detector. It is not the original implementation. |
| `tracking.py` | Persistent IDs, matching, smoothing, confirmation and expiry for the experimental version. |
| `cli.py` | Experimental image/video/camera viewer and JSONL output. |
| `capture.py` | Latest-frame camera reader used by the experimental CLI. |
| `ros_node.py` | Experimental ROS adapter using `detector.py` and `tracking.py`. |
| `config.py`, `default.json` | Experimental settings and validation. The original viewer does not read these settings. |

The small root `lane_pipeline_viewer.py` imports the original viewer; it is an entry point, not a second copy of the detection algorithm.

## Command names

| Command | Implementation |
| --- | --- |
| `python lane_pipeline_viewer.py …` | Original viewer; recommended starting point |
| `avl-lines-original …` | Installed alias for the same original viewer |
| `avl-lines-tracked …` | Experimental tracked CLI |
| `avl-lines …` | Older alias for the experimental tracked CLI; prefer the explicit name above |
| `avl-lines-ros …` | Experimental ROS adapter |

These names do not select interchangeable detectors. Changing the original viewer's mask/fitting code changes the baseline; changing `default.json` affects only the experimental path.

## Documentation map

| Page | Read it when… |
| --- | --- |
| [Start here](START_HERE.md) | Running for the first time |
| [Pipeline explained](PIPELINE.md) | Learning what each mask/stage means |
| [Tracked version](TRACKED_VERSION.md) | Trying tracking, video, camera input or custom JSON settings |
| [Robot setup](ROBOT_SETUP.md) | Testing ROS on the actual robot |
| [Output schema](OUTPUT_SCHEMA.md) | Writing a consumer of tracked/ROS detections |
| [Validation](VALIDATION.md) | Checking what was actually tested and what remains unverified |
| [Hardware sources](HARDWARE_SOURCES.md) | Finding the evidence for the Jetson/ZED assumptions |
| [Original transfer record](ORIGINAL_PROGRAM.md) | Understanding the earlier rewrite and baseline restoration |

## Reproduce examples or run tests

From the repository root, using your environment's Python:

```bash
python scripts/generate_examples.py
python -m pip install -e ".[test]"
python -m pytest -q
```

Example generation uses the original detector and the five checked-in raw images; it does not download data. It overwrites generated examples and their metadata. Tests cover both implementations, but do not establish that the two implementations produce the same detections.

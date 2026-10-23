# Run the current version

From the repository folder, use Python 3.10+ and a virtual environment. Install one OpenCV variant. The example below uses a graphical desktop:

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[desktop,test]"
.\.venv\Scripts\python.exe -m avl_white_lines.cli --images examples/raw --config config/recording_review.json
```

Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[desktop,test]"
.venv/bin/python -m avl_white_lines.cli --images examples/raw --config config/recording_review.json
```

For later commands, activate that environment or keep using its full Python path. Windows activation: `.venv\Scripts\Activate.ps1`; Linux/macOS: `source .venv/bin/activate`.

The window shows raw input, selected inspection stage and tracked **candidates**. I/O changes stages; A/D or arrows changes images; Space plays; T resets tracking; S saves; Q/Esc quits. M/R affect Hough only. The current ridge path has 18 stages, including configured image region and separate navigation mask/overlay. The original viewer still has its original 17 stages and controls.

## Know which view you are running

| Command/profile | What it demonstrates |
| --- | --- |
| `lane_pipeline_viewer.py examples/raw` | Original AVL program, unchanged native-resolution results |
| `--config config/marvin_ridge.json` | Full-frame Marvin-compatible RGB segmentation baseline |
| `--config config/recording_review.json` | Recording-specific lower-45% crop to suppress upper background candidates |
| `--config config/marvin_ridge_strict.json` | Extra component rejection experiment; can lose paint under wrong calibration |

The recording crop deliberately drops far-field image content, including distant paint. It is not ground recognition and is not the robot profile. The example camera model is unverified for the recording. Candidate lines can exist while **navigation is blocked**, which is expected without measured calibration and registered depth. Tracking three hits does not make a tree into a road boundary.

## Headless export

In a separate headless environment install `.[headless,test]` instead of `.[desktop,test]`. Then:

```bash
python -m avl_white_lines.cli --images examples/raw --config config/recording_review.json --headless --export-dir results/review --jsonl results/review.jsonl --benchmark results/timing.json
```

Open the exported PNGs. `final_mask` is image evidence; `navigation_mask` stays zero without the required inputs. Read `navigation.reasons` in JSON for the reason, rather than treating the zero navigation mask as a broken detector.

For a gallery and measurements:

```bash
python scripts/audit_ground_outputs.py --output results/ground_audit
```

Open `results/ground_audit/index.html`. The five samples are widely separated; they do not measure real tracking stability. Use consecutive footage for playback. [Current measured report](GROUND_IMPROVEMENT.md).

## Next steps

[Navigation contract](NAVIGATION_OUTPUTS.md) explains what a robot should consume. [Robot setup](ROBOT_SETUP.md) covers measured intrinsics/mounts and depth. [Documentation map](INDEX.md) separates current guidance from the history.

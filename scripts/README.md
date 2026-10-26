# Script guide

Run commands from the repository root with its Python environment active. Start with the [quick start](../docs/QUICK_START.md) to install dependencies. Use `--help` on a Python script for its full arguments.

## Routine verification

```bash
python -m pytest tests -q
python scripts/check_docs.py
python scripts/check_original_reference.py --strict-bytes
python -m compileall -q src scripts launch
```

The strict byte check protects the saved original outputs on the reference environment; CI also checks pixel equality across environments. The documentation checker skips local generated results and dependency folders.

## Current recording review and accuracy evaluation

| Tool | Purpose |
| --- | --- |
| `audit_ground_outputs.py` | Sparse candidate/navigation audit and sequential smoke measurements |
| `review_recording.py` | Review a recording and export selected raw images plus a labeling gallery |
| `label_editor/index.html`, `label_editor/editor.js` | Editor template copied into each generated review set |
| `score_boundaries.py` | Score reviewed centerlines and save/re-score frozen predictions |

Follow the [labeling workflow](../docs/EVALUATION_WORKFLOW.md) for exact commands, reviewed-label rules and metric definitions. Use a new `results/` folder for each experiment. Existing labels are personal review work; the recording-review script refuses to overwrite a folder containing labels.

## Reference and historical comparisons

| Tool | Purpose |
| --- | --- |
| `check_original_reference.py` | Verify original viewer results against saved outputs |
| `generate_examples.py` | Explicitly regenerate original example assets; not part of routine processing |
| `benchmark_backends.py` | Synthetic backend comparison; defaults to ignored `results/backend_benchmark.json` |
| `compare_marvin_avl.py` | Direct comparison with a separately supplied Marvin checkout |
| `compare_three_versions.py` | Compare Marvin, the original viewer and the tracked implementation |

Comparison fixtures need the test extra. Read the [historical reports](../docs/history/README.md) for the settings and limits of past runs; their checked-in JSON records are frozen snapshots.

## Robot helpers

| Tool | Purpose |
| --- | --- |
| `setup_robot.sh` | Robot environment setup helper |
| `probe_robot.sh` | Inspect available robot software/devices |
| `run_camera.sh` | Run one camera with its own configuration/topics |

Follow [robot setup](../docs/ROBOT_SETUP.md) before using these helpers. Templates do not replace measured calibration, registered depth, TF or physical validation. The ROS launch entry point lives in `launch/`.

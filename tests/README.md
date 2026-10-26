# Test guide

From the repository root, install the test extra and run:

```bash
python -m pytest tests -q
```

| Area | Test modules |
| --- | --- |
| Original viewer, controls and saved assets | `test_original_viewer.py`, `test_viewer_controls.py`, `test_examples.py` |
| Detection and Marvin mask parity | `test_detector.py`, `test_ridge.py`, `test_segmentation_parity.py` |
| Tracking and timestamps | `test_tracking.py`, `test_freshness.py` |
| Navigation and integration contracts | `test_navigation.py`, `test_physical_integration.py`, `test_ros_adapter_contract.py` |
| CLI and exports | `test_cli.py` |
| Reviewed labels and boundary scoring | `test_evaluation.py` |

`fixtures/marvin_rgb_reference.json` stores reference data used by regression checks. Keep the original saved results in [examples](../examples/README.md) intact; use [script checks](../scripts/README.md) to verify them.

Synthetic scenes and mocked ROS messages exercise software contracts. They do not prove physical calibration, middleware/device compatibility, robot speed or representative detection accuracy. Accuracy evaluation requires [reviewed real labels](../docs/EVALUATION_WORKFLOW.md); unreviewed drafts never count as ground truth. See the [validation records](../validation/README.md) for measured evidence and limits.

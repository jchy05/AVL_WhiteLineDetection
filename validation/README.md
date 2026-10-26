# Validation records

| Record | Meaning |
| --- | --- |
| `full_recording_summary.json`, `full_recording_frames.jsonl` | Full 1,078-frame output/runtime review; selective review queue, no accuracy labels |
| `ground_improvement.json` | Current five-image sparse audit and 120-frame sequential runtime smoke; no reviewed full-frame accuracy labels |
| `segmentation_fix.json` | Previous fix restoring Marvin RGB masks after extra filtering/dilation regressions |
| `three_version_comparison.json` | Historical Marvin / original AVL / initial new AVL comparison |
| `marvin_vs_avl.json` | Historical same-resolution upstream versus first integration comparison |
| `backend_benchmark.json` | First backend integration's synthetic and unlabeled runtime record |
| `INTEGRATION_REPORT.md` | First integration summary at its recorded source revision |

Read [current validation](../docs/GROUND_IMPROVEMENT.md) before interpreting old numbers. Reports retain settings, source/image hashes and limitations where available. A stable ID count is not identity-switch accuracy. A zero upper-band count after cropping is not semantic ground detection. Original reference outputs remain in `examples/generated/`.

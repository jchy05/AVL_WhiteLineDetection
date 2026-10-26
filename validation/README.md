# Validation records

These checked-in records preserve measurements and source provenance. New experiments write to ignored `results/` or a separate chosen output folder; do not overwrite a historical record to run a benchmark.

## Current review evidence

| Record | Meaning |
| --- | --- |
| [Detail-profile summary](detail_review_summary.json) and [per-frame trace](detail_review_frames.jsonl) | Same 1,078 frames at 480/960 px, gate losses and CPU timings; not labeled accuracy |
| [Full-recording summary](full_recording_summary.json) and [per-frame trace](full_recording_frames.jsonl) | All 1,078 local frames; runtime/output gaps and selected review queue, no reviewed accuracy labels |
| [Ground improvement audit](ground_improvement.json) | Five-image sparse audit and 120-frame sequential smoke |

Read the [detail-profile investigation](../docs/DETECTION_DETAIL_REVIEW.md), [full-recording report](../docs/FULL_RECORDING_REVIEW.md), [ground improvement report](../docs/GROUND_IMPROVEMENT.md) and [labeling workflow](../docs/EVALUATION_WORKFLOW.md) to interpret these records.

## Historical snapshots

| Record | Meaning |
| --- | --- |
| [Segmentation correction](segmentation_fix.json) | Restored Marvin RGB masks after extra filtering/dilation regressions |
| [Three versions](three_version_comparison.json) | Marvin / original AVL / initial new AVL |
| [Marvin versus AVL](marvin_vs_avl.json) | Same-resolution upstream versus first integration |
| [Initial backend benchmark](backend_benchmark.json) | First integration's synthetic and unlabeled runtime record |
| [Initial integration report](../docs/history/INITIAL_INTEGRATION.md) | Narrative summary at its recorded source revision |

JSON filenames remain stable for existing consumers. Historical narratives are indexed in [docs/history](../docs/history/README.md). A stable ID count is not identity-switch accuracy; cropping out an upper band is not semantic ground detection. Original saved reference outputs remain in [examples](../examples/README.md).

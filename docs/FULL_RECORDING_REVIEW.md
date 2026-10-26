# Full-recording review — 2026-10-26

The review now covers **all 1078 frames**, rather than only the first 120. The production detector/navigation code was not changed by this tooling step. It uses the existing `recording_review` crop profile, the same unverified camera preset and no depth; this is runtime/output-continuity inspection, not real accuracy validation.

## What the run found

- **1018/1078 frames** contained at least one confirmed image candidate.
- **32 frames** had empty candidate masks, in intervals **386–409, 775–776, 814–817, 820, 823**.
- Visual inspection of **386** and **814** shows visible road paint that the candidate mask misses. These are useful regression cases; the entire set of empty masks has not been labeled as false negatives.
- **31 distinct session IDs** appeared. This is not a labeled identity-switch score; camera motion/scene changes can create legitimate new tracks.
- Navigation-eligible frames: **0**, as expected without measured calibration and registered depth. No autonomous driving validation was performed.
- Local compute mean **55.0 ms/frame**, p95 **66.6 ms**, including detection/tracking/gating but excluding decode, GUI, actual capture/ROS and depth fitting. Wall time includes loading/export. A nominal 30Hz replay clock was used, not original acquisition timestamps. These numbers do not establish robot throughput.

[Summary/settings/source hashes](../validation/full_recording_summary.json) · [Every frame's numerical record](../validation/full_recording_frames.jsonl).

## Prepared review set

The tool selected **24 raw frames**, mixing the five familiar examples, uniform coverage and spaced high-change frames. It includes the dropout regions. The raw-only editor starts with **zero reviewed labels**. Additional image copies/previews and the interactive local gallery remain local; this repository adds only the numerical recording records and reusable tools, not the full recording or extra raw footage.

Per-frame review priorities combine adjacent-mask overlap change, candidate area change, disappearance of confirmed candidates and new IDs. They prioritize inspection and do not prove detection errors. The queue is intentionally selective and cannot serve as a representative held-out accuracy benchmark.

## New evaluation workflow

[Labeling and scoring guide](EVALUATION_WORKFLOW.md) explains how to draw visible paint centerlines, explicitly mark human-reviewed positives/negatives, save labels, score per-frame predictions and re-score frozen predictions later. The scorer enforces **<10 px and <2 degrees**, sufficient bidirectional coverage and one-to-one matching. Unreviewed drafts cannot produce accuracy metrics.

The original AVL fitted-line baseline and current AVL profiles can be evaluated against the same reviewed centerlines. Standalone Marvin's mask API is not silently treated as equivalent centerlines. Both old/new scoring smoke runs currently return `needs_reviewed_labels`; no accuracy winner is claimed.

## Verification

- **141 tests pass locally**, including new evaluator tests for strict position/angle limits, curved/reversed polylines, partial coverage/unsupported extensions, duplicate predictions, maximum-cardinality matching, explicit negatives, invalid review states, source hash/dimension/path validation and unreviewed exclusion.
- Original output reference check: **15/15 pixel- and PNG-byte-identical locally**.
- The browser editor was exercised for point drawing/finishing, reviewer requirement, review-state changes, automatic invalidation after edits and A/D browsing. Temporary UI test labels were discarded and not exported as ground truth. Real dataset remains entirely unreviewed.
- Actual new/old prediction export and frozen re-scoring were exercised on the 24-frame local dataset. Reports correctly have zero reviewed frames and null accuracy metrics.

The next algorithm work should address the newly visible misses using reviewed cases and correct calibration, not another undocumented threshold adjustment. [Robot/navigation requirements](NAVIGATION_OUTPUTS.md) still apply; these tools do not connect a planner or move the robot.

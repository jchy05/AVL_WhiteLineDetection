# Label and score visible paint boundaries

This workflow turns the existing recording into a reviewable evaluation dataset without inventing ground truth. Detection/navigation algorithms are unchanged by this tooling update. The full-recording review is [documented here](FULL_RECORDING_REVIEW.md).

## 1. Generate a review set

With the repository's Python environment active:

```bash
python scripts/review_recording.py --images /path/to/consecutive_jpg_frames --output results/review_01 --review-count 24
```

For a small demo using only the five distributed images:

```bash
python scripts/review_recording.py --images examples/raw --output results/label_demo --review-count 5
```

The five demo images are far apart, so its temporal counts do not describe a continuous recording. The script inspects every supplied JPG, saves per-frame change proxies, and selects a mix of known/uniform/high-change frames. High change is a **review priority**, not a proven failure; motion and exposure can cause legitimate changes. The selected set is not a representative random accuracy benchmark.

Open `index.html` for raw/candidate comparisons and `labeling/index.html` for raw-only annotation. The latter copies native images so coordinates remain in original pixels. A fresh output directory is required when an existing labels file would be overwritten.

## 2. Mark the target consistently

Label the **center of visible white painted boundary segments**. Exclude trees, fences, barrel stripes and unrelated white objects. Follow each segment in order; split dashed gaps/occluded portions into separate segments rather than drawing through missing paint. Trace curves with enough points and zoom in when needed. Label uncertainty and inter-reviewer agreement still matter, especially for the strict angle threshold.

| Editor action | Control |
| --- | --- |
| Add a point | Click raw image |
| Finish current segment/start next | Enter or N / finish button |
| Undo point or reopen last segment | Backspace / undo button |
| Remove unfinished/last segment | Remove last line |
| Previous/next image | A/D or buttons |
| Confirm human review | Reviewer initials + Mark reviewed |
| Confirm no target paint | Explicit Reviewed negative button, with no labels |
| Save/resume | Download labels / Load labels |

Annotations live in browser memory. **Download regularly** and save the JSON next to the exported `images/` folder (keep a backup of existing labels). Reloading the page starts from the initial dataset; use Load labels to resume your saved work. Drafts remain unreviewed. Editing clears review status. The scorer excludes every unreviewed frame, and reviewed negatives must explicitly say `negative=true`.

The dataset records native dimensions, relative image paths, SHA-256 image identity, reviewer, condition tag and boundary points. Files cannot reference images outside the dataset directory. The scorer verifies image hashes/dimensions before evaluating.

## 3. Score and preserve predictions

```bash
python scripts/score_boundaries.py --labels results/review_01/labeling/labels.json --config config/recording_review.json --output results/review_01/score_new.json
python scripts/score_boundaries.py --labels results/review_01/labeling/labels.json --config config/marvin_ridge.json --output results/review_01/score_full_frame.json
python scripts/score_boundaries.py --labels results/review_01/labeling/labels.json --original --original-mode 0 --output results/review_01/score_original.json
```

Use distinct output names for each algorithm/version. Each run saves native-pixel centerline predictions next to its report. Re-score frozen predictions after more labels are reviewed without rerunning/changing the algorithm:

```bash
python scripts/score_boundaries.py --labels results/review_01/labeling/labels.json --predictions results/review_01/score_new_predictions.json --output results/review_01/rescored_new.json
```

Frozen predictions must match every dataset frame ID, image hash and dimensions. This prevents comparing labels against another set of images. The report includes a hash of the labels file.

New AVL uses per-frame component centerlines **before temporal confirmation**. Original AVL's fitted-line raster is converted into native-image centerlines; its unsupported fitted extensions can therefore be penalized. Standalone Marvin's public API returns a mask, not equivalent centerlines: this scorer does not automatically rank its raw mask as if it were the same output. Full-frame AVL RGB parity with Marvin does not imply identical centerline metadata. Existing three-version image comparisons remain useful inspection evidence.

## Metric definition

Each truth centerline is sampled uniformly in image arc length. Distances are measured to predicted **segments**, not just sparse vertices. Angle error compares the local segment tangent, modulo 180 degrees because a paint strip has no arrow direction.

A pair is correct only when:

- Mean truth-to-prediction distance is **strictly <10 native pixels**.
- Mean local tangent error is **strictly <2 degrees**.
- At least **60%** of both truth and prediction arc samples lie within the position threshold. This prevents a tiny correct fragment or a long unsupported extension from counting as a full match.

Maximum-cardinality one-to-one matching counts correct boundaries. Deterministic error-ordered augmenting paths resolve associations. Duplicate predictions count as false positives; unmatched truth counts as missed boundaries. Reports include boundary precision/recall/F1, false positives per reviewed frame, matched position/angle means and all per-pair errors, with condition breakdowns. Means over matched pairs exclude misses; inspect FP/FN and the pair records as well.

These are **boundary-component metrics**, not pixel-mask precision/recall, lane-side correctness, drivable-corridor accuracy or identity-switch scoring. Undefined rates are null. With zero reviewed frames, status is `needs_reviewed_labels` and metrics are null—never fabricated accuracy numbers.

## Before claiming an improvement

Review selected failures, then test a held-out set and other recordings/conditions. Do not tune on these 24 selected frames and present the resulting score as general accuracy. Existing navigation gates and real calibration/depth/TF requirements still apply. [Current robot/navigation contract](NAVIGATION_OUTPUTS.md).

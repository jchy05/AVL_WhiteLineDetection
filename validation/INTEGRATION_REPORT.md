# Ridge integration report — 2026-10-23

Implemented in the requested Oct 23 AVL checkout, based on AVL `e23345a857f58eff29bff91e1cd820df839b4539` and Marvin `d6aa919877a853511518f556b56d0bec62a4676f`. The upstream Marvin checkout was read and tested, not modified. The original viewer and checked-in sample outputs were not changed.

## Delivered

Three backend choices; calibrated physical ridge segmentation; curved sampled metric/image centerlines; direct physical width and length checks; metric one-to-one association and smoothing; preserved AVL confirmation/hold/expiry/reset behavior; registered-depth component votes and symmetric ground confirmation; live plane estimation and smoothing; 15 ridge debug stages alongside the final tracked overlay; headless stage export; additive JSON metadata; ROS mask, debug and optional depth-confirmed costmap PointCloud2 output.

## Verification

- Before edits: AVL 35/35 tests passed; upstream Marvin 6/6 passed.
- After edits: AVL **60/60 tests passed**, including all original 35. New coverage includes shadow edges, dark joints/cracks, narrow/oversize strips, curves, raised bright objects, invalid/missing depth, wrong mount height/live correction, metric smoothing/association, backend isolation/fallback, coordinate projection, costmap filtering, headless export and additive output contract. Original timestamp/freshness tests remain present.
- Original viewer: **15/15 final references remain pixel- and PNG-byte-identical** locally, covering all five frames and three modes.
- `compileall` and `git diff --check` passed. Live GUI key delivery and ROS hardware transport were not exercised. All 15 ridge stage panels were composed without a display in tests.
- The synthetic straight and curved strips meet the requested **<10 px AND <2 degrees** criterion, with at least 60% centerline coverage in the benchmark. Construction-label results:

- tape: mean centerline error 0.321 px, mean local heading error 0.768 degrees; strict boundary match: True.
- curve: mean centerline error 0.263 px, mean local heading error 1.312 degrees; strict boundary match: True.

These two positive fixtures are regression checks, not held-out accuracy validation. On this seven-scene fixture set, ridge matched both positives and produced no components on the five negative scenes. Hough produced no components on these fixtures with its retained Article/Hough defaults at the shared processing width; that is not a general comparison across lighting, camera mounts or tuned settings. Exact pixel precision is lower than 100% because the returned mask includes border dilation; inspect the per-scene values in the JSON.

## Local CPU benchmark

All comparisons use 480-pixel processing width, no depth, warmed frames, three timed repeats per frame, separate memory profiling, and no GUI/capture/ROS. The real set is frames 0, 410, 474, 710 and 1077. The fixture camera model is known; the real camera calibration is **not verified**. Do not interpret real output as labeled accuracy.

| Backend | Synthetic mean ms | Real mean ms | Real p95 ms | Three-stream serial aggregate FPS (real) | Python-traced peak MiB (real) |
| --- | ---: | ---: | ---: | ---: | ---: |
| legacy_hough | 3.4 | 8.1 | 9.1 | 146.3 | 1.9 |
| marvin_ridge | 54.9 | 136.0 | 170.4 | 5.8 | 18.7 |
| hybrid_fallback | 46.6 | 130.3 | 147.8 | 6.7 | 18.7 |

The three-stream figure uses separate detector instances on duplicate streams. It is aggregate throughput, not FPS per camera, and excludes acquisition/ROS/depth fitting. Python-traced peak excludes some native allocations and is not total RSS/GPU memory. Timings vary with CPU load and scene complexity. The ridge path does **not** establish a 30 FPS, three-camera robot budget here. [Full measured data and source/image hashes](backend_benchmark.json).

## Visual and hardware limits

The five real images have no reviewed masks/centerlines or verified intrinsics/mount geometry. Visual inspection of frame 1077 with the example front-camera preset and no depth shows false hits on off-road fence/vegetation/background features. Real-world improvement is therefore unproven. Depth helps reject raised surfaces only when registered and sufficiently valid. No labeled moving-sequence ID-switch rate, Jetson thermals, acquisition latency, live CameraInfo/TF integration, depth synchronization or physical navigation test is available.

Flat ground and zero-roll geometry are assumed. Live fitting adjusts height/pitch within bounded priors, not arbitrary remounts or non-planar terrain. Branches/crossings/hairpins can confuse PCA-ordered components. No ego-motion compensation or camera fusion is implemented. Confidence is heuristic. Missing depth lowers confidence but still permits RGB-only observations; default costmap output requires positive depth confirmation. Costmap consumers must set TF, source expiry and clearing behavior; empty clouds do not automatically erase old cells.

Upstream files have source attribution; upstream does not include a license file, so redistribution licensing remains unspecified.

## Recommended configuration and commands

Use **`config/marvin_ridge.json` as the calibrated production candidate**: processing width 480; width .025–.15 m; length .30 m; range 12 m; ridge thresholds .22/.10; side-log .10; depth confirmation .5; depth/live ground/tracking enabled. Replace its explicit example `marvin_front` model with your measured camera JSON. Presets are not universal robot calibration. The package compatibility default remains `legacy_hough` with its earlier 960-pixel setting.

```bash
python -m avl_white_lines.cli --images examples/raw --config config/marvin_ridge.json --headless --export-dir results/ridge --jsonl results/ridge.jsonl
python -m avl_white_lines.cli --images examples/raw --config config/legacy_hough.json
python -m avl_white_lines.cli --images examples/raw --config config/hybrid_fallback.json
```

Add `--camera-model measured_camera.json` for calibrated ridge/hybrid runs, `--video recording.mp4` instead of `--images` for sequential tracking, and `--depth-dir registered_depth` for image-aligned float-metre `.npy` depth. Interactive runs need a desktop; use `--headless` on SSH/sandbox sessions. I/O changes the inspected stage, A/D changes images, Space plays, T resets, S saves, Q/Esc quits. M/R configure only Hough.

[Full backend, calibration, ROS and schema guide](../docs/RIDGE_BACKEND.md).

## Files changed

- `.github/workflows/tests.yml`
- `README.md`
- `config/hybrid_fallback.json`
- `config/legacy_hough.json`
- `config/marvin_ridge.json`
- `docs/OUTPUT_SCHEMA.md`
- `docs/PIPELINE.md`
- `docs/RIDGE_BACKEND.md`
- `docs/TRACKED_VERSION.md`
- `docs/VALIDATION.md`
- `pyproject.toml`
- `scripts/benchmark_backends.py`
- `scripts/check_original_reference.py`
- `src/avl_white_lines/MARVIN_PROVENANCE.md`
- `src/avl_white_lines/camera.py`
- `src/avl_white_lines/cli.py`
- `src/avl_white_lines/components.py`
- `src/avl_white_lines/config.py`
- `src/avl_white_lines/default.json`
- `src/avl_white_lines/detector.py`
- `src/avl_white_lines/ground.py`
- `src/avl_white_lines/physical.py`
- `src/avl_white_lines/ridge.py`
- `src/avl_white_lines/ros_node.py`
- `src/avl_white_lines/tracking.py`
- `tests/test_physical_integration.py`
- `tests/test_ridge.py`
- `validation/backend_benchmark.json`

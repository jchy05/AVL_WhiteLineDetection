# Validation performed

Development date: 2026-10-16. See [machine-readable timing](development_benchmark.json).

## Functional checks

- 28 automated tests passed locally: exact mask selection, filtered pixels, ROI exclusion, independent nearby markings, blank input, geometric ID continuity across old bin boundaries, one-to-one matching, confirmation, missed-frame invalidation, expiry, smoothing on known injected jitter, timestamp resets/freshness, latest-frame overwrite, video decode, JSONL schema and frame limits.
- All three modes replayed over all 1,078 original 1280×720 raw images: 3,234 processed real frames. Replay used nominal 30 FPS timestamps, not actual sensor stamps.
- A generated 40-frame MJPEG video decoded successfully and produced at least two valid tracks on every frame after the three-frame confirmation period.
- Python source and ROS launch files compiled. The ROS entry point fails with a useful setup message when ROS is unavailable.
- Compared debug views on straight/turning portions of the recorded sequence. This is visual inspection, not a labeled accuracy test.
- The GitHub workflow runs the core suite on Linux with Python 3.10 and 3.12. Its live status is visible in the repository Actions tab; local results do not imply ROS was tested there.

## Local recorded-frame timing

Windows development computer, Python 3.14, OpenCV 4.13.0, NumPy 2.4.6. Processing width 960; no debug rendering. Runs were separate, with normal background workload rather than controlled hardware benchmarking.

| Mode | Mean detection + tracking | 95th percentile | Full replay throughput |
| --- | ---: | ---: | ---: |
| Article HSL white | 24.68 ms | 43.12 ms | 24.41 frames/s |
| Previous HSV defaults | 16.75 ms | 25.78 ms | 38.45 frames/s |
| Saved HSL | 19.01 ms | 28.10 ms | 35.19 frames/s |

Compute time excludes image decoding, disk JSONL writes and display; full replay throughput includes decoding/logging/loop overhead. Neither measurement includes camera acquisition or ROS transport. Individual slow frames and three-camera contention matter; average compute rate alone is not a 30 Hz deadline guarantee. Saved HSL being faster does not mean it is more accurate.

## Not yet measured

- Jetson runtime, ROS 2 message delivery, live ZED hardware and disconnected-camera behavior on the actual robot.
- True acquisition-to-output latency and timestamp/clock consistency.
- Live three-camera CPU load, thermal effects or frame drops.
- Labeled precision/recall, curve accuracy, tracking identity errors and effect on downstream navigation.
- Camera exposure stability and per-camera thresholds in actual field conditions.

Tracking reduces injected jitter in a controlled test. This is not a claim that flicker is eliminated on all recorded scenes. The detector still uses fixed color thresholds and straight local fits. Use the robot setup guide to complete live validation before integrating with a controller.

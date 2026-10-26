# Documentation map

Read the **current guides** first. Earlier comparison reports are preserved as dated evidence, not current setup instructions.

## Start here

1. [Quick start and controls](QUICK_START.md): run the five images, understand inspection versus navigation.
2. [Configuration choices](../config/README.md): reference, recording crop, strict experiment, and robot templates.
3. [Navigation output contract](NAVIGATION_OUTPUTS.md): exact eligibility rules and why an output is empty.
4. [Robot setup](ROBOT_SETUP.md): CameraInfo, measured mount/TF, registered depth, topics, watchdogs.
5. [Current validation report](GROUND_IMPROVEMENT.md): measured results, sparse audit limits, sequential smoke run and outstanding hardware work.

## Evaluation and next improvements

- [Available version comparison](AVAILABLE_VERSIONS.md): actual reruns of original presets, historical implementations, Marvin and current profiles, with source verification.

- [Detailed detection review](DETECTION_DETAIL_REVIEW.md): why the 480 px profile misses paint, a slower 960 px option, and full-recording comparisons.

- [Full 1,078-frame review](FULL_RECORDING_REVIEW.md): output gaps, review queue and current limits.
- [Raw-image labeling and scoring](EVALUATION_WORKFLOW.md): human-reviewed centerlines, strict thresholds, frozen predictions and comparison policy.

## How the code works

- [Pipeline](PIPELINE.md): original color/Hough stages and current calibrated ridge stages.
- [Ridge details](RIDGE_BACKEND.md): camera conventions, component metadata, depth and live fitting.
- [Tracking](TRACKED_VERSION.md): confirmation, smoothing, held/expired states and timestamp resets.
- [JSON schema](OUTPUT_SCHEMA.md): compatibility fields and current navigation additions.
- [Repository guide](REPOSITORY_GUIDE.md): where implementation, tests, profiles and reports live.
- [Original viewer setup](START_HERE.md) and [five-frame original results](../examples/README.md).

## Historical evidence

The [archive index](history/README.md) explains the report sequence. [Script commands](../scripts/README.md), [test map](../tests/README.md) and [numerical validation records](../validation/README.md) have their own indexes.

- [Original transfer verification](history/ORIGINAL_PROGRAM.md).
- [First integration report](history/INITIAL_INTEGRATION.md).
- [Marvin versus initial AVL integration](history/MARVIN_VS_AVL.md).
- [Marvin / original AVL / initial new AVL](history/THREE_VERSION_COMPARISON.md).
- [Restoring exact Marvin RGB segmentation](history/SEGMENTATION_FIX.md).
- [Earlier validation record](history/VALIDATION.md) and [hardware source notes](HARDWARE_SOURCES.md).

[Change log](../CHANGELOG.md) records what changed and why. Do not interpret an older timing table or example preset as calibration for a new robot mount.

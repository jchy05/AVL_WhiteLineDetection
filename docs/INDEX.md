# Documentation map

Read the **current guides** first. Earlier comparison reports are preserved as dated evidence, not current setup instructions.

## Start here

1. [Quick start and controls](QUICK_START.md): run the five images, understand inspection versus navigation.
2. [Configuration choices](../config/README.md): reference, recording crop, strict experiment, and robot templates.
3. [Navigation output contract](NAVIGATION_OUTPUTS.md): exact eligibility rules and why an output is empty.
4. [Robot setup](ROBOT_SETUP.md): CameraInfo, measured mount/TF, registered depth, topics, watchdogs.
5. [Current validation report](GROUND_IMPROVEMENT.md): measured results, sparse audit limits, sequential smoke run and outstanding hardware work.

## How the code works

- [Pipeline](PIPELINE.md): original color/Hough stages and current calibrated ridge stages.
- [Ridge details](RIDGE_BACKEND.md): camera conventions, component metadata, depth and live fitting.
- [Tracking](TRACKED_VERSION.md): confirmation, smoothing, held/expired states and timestamp resets.
- [JSON schema](OUTPUT_SCHEMA.md): compatibility fields and current navigation additions.
- [Repository guide](REPOSITORY_GUIDE.md): where implementation, tests, profiles and reports live.
- [Original viewer setup](START_HERE.md) and [five-frame original results](../examples/README.md).

## Historical evidence

- [Original transfer verification](ORIGINAL_PROGRAM.md).
- [First integration report](../validation/INTEGRATION_REPORT.md).
- [Marvin versus initial AVL integration](MARVIN_VS_AVL.md).
- [Marvin / original AVL / initial new AVL](THREE_VERSION_COMPARISON.md).
- [Restoring exact Marvin RGB segmentation](SEGMENTATION_FIX.md).
- [Earlier validation record](VALIDATION.md) and [hardware source notes](HARDWARE_SOURCES.md).

[Change log](../CHANGELOG.md) records what changed and why. Do not interpret an older timing table or example preset as calibration for a new robot mount.

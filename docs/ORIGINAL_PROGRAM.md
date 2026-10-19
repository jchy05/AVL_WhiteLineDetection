# Original program and the October 19 handoff correction

The first repository upload was a rewrite, not a complete transfer of the working image viewer. That distinction was not stated clearly enough.

The rewrite changed detection by resizing frames to width 960, replacing fixed-position grouping with independent hypotheses, changing consensus selection and fit weighting, restricting extrapolation, and adding confirmation/smoothing. Those changes can alter accepted segments and final line locations even when the color-filter names match. Passing headless tests did not establish equivalence with the original detector or validate live robot behavior.

## Restored original baseline

`src/avl_white_lines/original_viewer.py` preserves the latest working viewer from this chat, including its detector, all 17 stages, explanatory footer, three filters, I/O and A/D controls, ROI toggle, full stage export and separate final-image saving. It processes native-resolution input without temporal tracking, just like the working program.

Only startup/output plumbing was changed: the personal absolute image-folder path was removed, an optional folder picker was added, and exports now go to a portable `results/original/` directory (or `--output-dir`). The detection functions and state/keyboard behavior were copied without algorithm changes.

The transfer was checked against the working original: all six detection/display/state definitions match, and all 17 stage images plus final output were pixel-identical in 72 real-frame/mode/ROI comparisons. See [verification details](original_transfer_verification.json). This comparison used identical input files and the same OpenCV runtime; it does not compare the original with the rewritten detector.

Run from the repository root:

```bash
python lane_pipeline_viewer.py /path/to/the/same/raw_images
```

On Windows, double-click `Start Lane Viewer.cmd` and choose the original raw-image folder. It uses a local `.venv` if one exists. Install desktop dependencies first if needed: `python -m pip install -e ".[desktop]"`. Folder selection requires Tkinter; passing the folder explicitly avoids that dependency.

For a GUI-free first-frame export:

```bash
python lane_pipeline_viewer.py /path/to/raw_images --export --output-dir results/original
```

Use identical source files, filter mode, ROI setting, and OpenCV version for an exact comparison. Raw images remain excluded from Git; altered/compressed input images can also change detections.

## Rewritten tracked version remains separate

`avl-lines-tracked` (and the older `avl-lines` alias) explicitly run the rewritten pipeline. `avl-lines-ros` also uses that rewritten pipeline. They are not equivalent ports of the original frame-by-frame detector. The ROS adapter has not been run on the physical robot. Do not use the existence of a working original viewer as proof that the ROS path matches its output.

The tracked viewer's missing uppercase controls, stage descriptions, image labels and separate final-image saving were corrected during this audit. UI tests now exercise stage/mode changes, browsing and snapshots through mocked desktop events, in addition to the headless tests. These tests do not replace real desktop or ROS hardware checks.

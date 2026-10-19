# AVL_WhiteLineDetection

Find white road markings and inspect each processing stage beside the original image and the final detection. Start with the **original image viewer** below. It uses native-resolution images, three filters, and 17 processing stages.

## Choose a starting point

| I want to… | Start here |
| --- | --- |
| See the images and results without installing anything | [Five-frame comparisons](examples/README.md) |
| Run the original program on my computer | [Beginner setup](docs/START_HERE.md) |
| Understand the masks and processing steps | [Pipeline explained](docs/PIPELINE.md) |
| Find or edit the code | [Repository guide](docs/REPOSITORY_GUIDE.md) |
| Try temporal tracking or video/camera input | [Experimental tracked version](docs/TRACKED_VERSION.md) |
| Test the ROS 2 adapter on MARVIN | [Robot setup — experimental](docs/ROBOT_SETUP.md) |

## See the included examples

The repo includes your unchanged raw frames **0, 410, 474, 710 and 1077**, results for all three filters, and all 17 stage previews. The full 1,078-frame recording is not included.

- On GitHub, open [the comparisons page](examples/README.md).
- After downloading/cloning the repo, open **`examples/gallery.html`** in your browser. No Python installation is needed for this offline gallery.

## Run the original viewer

Requires Python 3.10 or newer. Run these commands from the repository folder. For download instructions or troubleshooting, use [Beginner setup](docs/START_HERE.md).

**Windows PowerShell:**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[desktop]"
.\.venv\Scripts\python.exe lane_pipeline_viewer.py examples/raw
```

**Linux/macOS:**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[desktop]"
.venv/bin/python lane_pipeline_viewer.py examples/raw
```

The window shows **original → selected stage → final detection**. On Windows, subsequent launches can use **Show Sample Frames.cmd** for the five examples or **Start Lane Viewer.cmd** to choose another image folder.

| Key | Original viewer action |
| --- | --- |
| A / D or left/right arrows | Previous / next image |
| I / O | Previous / next processing stage |
| M | Article HSL white → Previous HSV defaults → Saved HSL |
| R | Rectangular ROI / article trapezoid |
| S | Save the comparison, selected stage and final image |
| Q / Esc | Quit |

Saved images go to `results/original/saved/`. The rectangular region starts **40% down from the top**, retaining the bottom 60%.

## Original and tracked versions are different

| Program | Purpose and validation |
| --- | --- |
| Original viewer | Reproduces the working frame-by-frame program. Verified pixel-identical in 72 comparisons on the same inputs/runtime. |
| Tracked version | Experimental rewrite with different grouping/fitting and temporal tracking. Its detections can differ. |
| ROS 2 adapter | Runs the experimental tracked version. Not tested on the physical robot; publishes perception, not steering. |

Do not use the tracked or ROS commands when checking whether the original results match. The JSON configuration belongs to the tracked version; it does **not** change the original viewer.

See [validation and timing](docs/VALIDATION.md), [output fields](docs/OUTPUT_SCHEMA.md), and the [original transfer record](docs/ORIGINAL_PROGRAM.md) for supporting details.

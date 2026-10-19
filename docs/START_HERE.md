# Start here: original image viewer

This is the recommended first run for a new person. You do not need ROS, a robot, a GPU, or the full camera recording.

## 1. Get the files

The repository is private, so your GitHub account needs access. On GitHub choose **Code → Download ZIP**, unzip it, and open the extracted folder. Or clone it:

```bash
git clone https://github.com/jchy05/AVL_WhiteLineDetection.git
cd AVL_WhiteLineDetection
```

The correct folder contains `README.md`, `lane_pipeline_viewer.py`, `pyproject.toml`, and `examples/`. Open a terminal in that folder. If you downloaded a ZIP, its folder name may end in `-main`; the commands below still work from inside it.

## 2. See the results before installing

Open `examples/gallery.html` in your browser. It includes frames 0, 410, 474, 710 and 1077, all three filter results, and all 17 stages.

Click outside the dropdowns before using keyboard shortcuts: **A/D** changes image, **I/O** changes stage, **M** changes filter. You can also use the dropdowns and buttons. Raw JPEGs and full-resolution final PNGs are linked below the panels. The static [examples page](../examples/README.md) works directly on GitHub.

## 3. Install and run the original Python program

Use Python 3.10 or newer with desktop window support. Check `python --version` on Windows or `python3 --version` on Linux/macOS. The following commands create a local environment, so there is no need to activate it or change PowerShell's execution policy.

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[desktop]"
.\.venv\Scripts\python.exe lane_pipeline_viewer.py examples/raw
```

After this first setup, double-click **Show Sample Frames.cmd** to reopen the five samples. Double-click **Start Lane Viewer.cmd** to select a different image folder.

### Linux/macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[desktop]"
.venv/bin/python lane_pipeline_viewer.py examples/raw
```

These desktop instructions are for a computer with a display. For the Jetson's ROS environment, use [Robot setup](ROBOT_SETUP.md) instead of installing desktop OpenCV wheels over ROS libraries.

## 4. Check what you see

The first image is `frame_000000.jpg`. The three panels show the raw image, the selected processing stage, and the final overlay. The program initially selects **Article HSL white** and **Active color mask**. The final result does not change when you only cycle through inspection stages.

Click the viewer window to give it keyboard focus:

| Key | Action |
| --- | --- |
| A / D or arrows | Previous / next image |
| I / O | Previous / next of 17 stages |
| M | Next of the three filters |
| R | Switch region of interest |
| S | Save comparison, stage and final image |
| Q / Esc | Close |

The sample results use the rectangular ROI, starting 40% down the image. Changing the ROI or filter changes detection. The original viewer processes each frame independently; there is no play/pause or temporal smoothing in this program.

## 5. Use your own raw images

Replace `examples/raw` with your image folder. Quote paths that contain spaces. For example, on Windows:

```powershell
.\.venv\Scripts\python.exe lane_pipeline_viewer.py "C:\path\to\raw images"
```

The repo contains five samples, not the entire recording. Use the same image files, filter, ROI and OpenCV runtime when comparing to earlier results. Edited, compressed or resized inputs may change detections.

## 6. Find saved output

- Press **S**: files appear under `results/original/saved/`.
- Add `--export`: all 17 stages of the first image, its final overlay, comparison and detection counts appear under `results/original/preview/`.
- Add `--output-dir "path/to/output"` to choose another location.

GUI-free example export:

```bash
python lane_pipeline_viewer.py examples/raw --export
```

Use the local environment's Python executable from step 3 if it is not activated. Saved runtime output is ignored by Git; checked-in sample results live under `examples/generated/`.

## Common first-run problems

| Symptom | What to check |
| --- | --- |
| `python` is not found or opens the Store | Install/configure Python first, then reopen the terminal. |
| `No module named cv2` or `numpy` | Run the install command with the same `.venv` Python you use to launch. |
| Window/GUI support error | Use a desktop installation. Do not install both `opencv-python` and `opencv-python-headless` in the same environment; a fresh desktop `.venv` is the easiest starting point. |
| Folder picker is unavailable | Pass the image folder explicitly; the picker optionally uses Tkinter. |
| No images found | Check the path and current folder; `examples/raw` is relative to the repository root. |
| Keys do nothing | Click the image window first. Space/T belong to the tracked version, not this viewer. |
| Results look different | Check that you launched `lane_pipeline_viewer.py`, not `avl-lines`/`avl-lines-tracked`; compare the same raw file, mode and ROI. |

Next: [understand the stages](PIPELINE.md) or [find the source code](REPOSITORY_GUIDE.md). Tracking/video and robot work have [separate experimental instructions](TRACKED_VERSION.md).

# Available version comparison

This comparison reruns preserved source code. No historical detector is approximated with current thresholds, no missing result is drawn by hand, and no temporal history or accuracy score is invented. It is frozen at the detection sources listed below; later documentation-only commits are not new detector versions.

## Actual sources used

| Available version/preset | Source commit | Processing/output |
| --- | --- | --- |
| Original AVL: Article HSL white | `e23345a` | Native 1280x720 original final rendering and fitted-line mask |
| Original AVL: Previous HSV | `e23345a` | Same original program, actual HSV preset |
| Original AVL: Saved HSL | `e23345a` | Same original program, actual saved HSL preset |
| Early tracked AVL: Hough | `e23345a` | Package defaults at 960 px; per-frame fitted lines before tracking |
| Standalone Marvin | Upstream `d6aa919` | Actual standalone package; 480 px, `marvin_front`, no depth |
| Initial AVL ridge integration | `8fb2b5e` | That revision's `config/marvin_ridge.json`, including its original secondary filtering |
| Corrected full-frame AVL ridge | `ea94083` | That revision's diagnostic-policy full-frame profile at 480 px |
| Current road-region profile | `67b53a9` | `config/recording_review.json`, 480 px, lower-45% crop |
| Newest compared detailed profile | `67b53a9` | `config/recording_detail.json`, 960 px, same crop/filter thresholds |

These are nine real configurations across the available detection milestones, not nine independent trained models. The three original modes and two current resolution profiles share code. All ridge camera presets are unverified for this recording. Depth, live ground fitting and temporal tracking are absent from this still-image comparison.

## Frames and verification

The first five frames are the user's original **0, 410, 474, 710 and 1077**. Additional available local frames **386, 814, 419, 422 and 423** expose known misses and resolution regressions. All versions receive the identical native JPEG for each frame. Sources are extracted with Git archive into the generated output folder and loaded in separate Python processes to prevent imports leaking between revisions.

- All **15 original sample outputs** match the saved original references pixel-for-pixel before export. The extra five frames have no saved original references and are not claimed to have them.
- Standalone Marvin and the corrected full-frame AVL mask match on all **10** compared frames in this environment.
- The [checked comparison manifest](../validation/available_versions.json) records exact source revisions, input hashes, availability and verification results.

Lossless PNG overlays/masks, source copies and per-version provenance JSON remain in the local gallery. Raw JPEGs are copied byte-for-byte and verified by SHA-256. Contact sheets are JPEG previews; click a gallery card for its lossless output. Original AVL keeps its original colored fits/ROI; other overlays use cyan to visualize actual masks or fitted-line rasters. Straight fitted extensions are estimates, not segmented paint pixels.

These are reruns with the currently installed Python/OpenCV, not a claim to reproduce the exact historical execution environment. No reviewed accuracy ranking follows from the pictures. Additional raw frames and their galleries are local outputs, not added to the public repository.

## Reproduce and browse

The repository needs its full history and a separate upstream Marvin checkout. Missing/unrunnable versions are explicitly listed as unavailable and omitted rather than substituted. Existing output directories are refused to protect saved results.

```bash
python scripts/compare_available_versions.py --marvin-repo ../Marvin_White_Line --output results/available_versions_01
```

This default uses only the five distributed images. To include all ten locally available frames:

```bash
python scripts/compare_available_versions.py --marvin-repo ../Marvin_White_Line --images /path/to/consecutive_jpg_frames --frames 0,410,474,710,1077,386,814,419,422,423 --output results/available_versions_10
```

Open the generated `index.html`. A/D or arrows changes frames; I/O switches mask/overlay; the Layout menu switches all versions or any two selected versions. The pair view defaults to raw versus the newest compared profile. Click any image for native resolution, or open the full labeled contact sheet. The page works offline; an ordinary local HTTP server can also serve its directory.

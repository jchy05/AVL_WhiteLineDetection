# Pipeline explained

Current entry points: [quick start](QUICK_START.md), [navigation contract](NAVIGATION_OUTPUTS.md), and [current validation](GROUND_IMPROVEMENT.md). Earlier Hough-only limitations and timing below describe the legacy path or historical experiments. The current ridge path has an optional explicit image ROI and separate gated navigation outputs.

Both viewers expose the same stage names, but their segment grouping and final fitting differ. The checked-in example images use the **original viewer**. Changing the inspected stage does not change the active detection pipeline; changing the filter or ROI does.

## Filters

| Filter | OpenCV channel bounds |
| --- | --- |
| Article HSL white | H=0–180, L=200–255, S=0–255 |
| Previous HSV defaults | H=0–180, S=0–30, V=195–255 |
| Saved HSL | H=0–36, L=59–205, S=0–40 |

OpenCV calls HSL `HLS` and stores its channels as H,L,S. HSV stores H,S,V. Hue normally runs 0–179 in these 8-bit OpenCV conversions; an upper bound of 180 includes all encoded hues. HSV has **value**; HSL has **lightness**.

The article mask comes from the [article's notebook](https://github.com/kenshiro-o/CarND-LaneLines-P1). It selects high lightness, not a semantic concept of white paint, so bright non-lane objects can pass. Saved HSL includes mid-gray pixels and may select asphalt; it is a retained comparison preset, not a universal best setting.

## The 17 stages

| Stage | What you see |
| --- | --- |
| Original | The raw input image |
| HSV saturation | Color intensity; white/gray pixels tend to have low saturation |
| HSV value | Brightness channel |
| HSL lightness | Lightness channel |
| HSL saturation | HSL's saturation channel, which differs from HSV saturation |
| Article white mask | Binary pixels that pass the article's lightness bounds |
| Previous HSV mask | Binary pixels that pass the earlier HSV preset |
| Saved HSL mask | Binary pixels that pass the saved HSL preset |
| Active color mask | A copy of whichever of the three masks M selected |
| Filtered original | Original colors kept where the active mask is white; black elsewhere |
| Grayscale | Filtered original converted to one brightness channel |
| Gaussian blur | 11×11 smoothing before edge detection |
| Canny edges | Edges using thresholds 50 and 150 |
| ROI edges | Canny edges retained inside the region of interest |
| Raw Hough segments | Straight segments proposed from those edges |
| Accepted segments | Segments that survive the current detector's geometry/grouping rules |
| Fitted line mask | Straight line estimates fitted from accepted segments |

Channel and grayscale views are images, not binary masks. The final panel overlays the detector's result on the original. A fitted extension is an estimate, not proof that every pixel along it contains paint.

## Original segment selection

The original detector rejects short/flat segments, projects remaining segments toward the image bottom, and places them in fixed left/center/right groups. With the article trapezoid it uses slope-based left/right groups instead. Within each group, it keeps the length-supported set aligned with a candidate line, requires vertical extent and foreground support, then fits x as a function of y. The fit can extend toward the ROI boundary and image bottom.

This fixed grouping can reassign markings or combine unrelated evidence, especially during turns. A straight fit cannot trace a tight curve. These limitations are preserved in the original baseline so it reproduces the earlier results.

## Experimental differences

The tracked detector resizes input to a configured width (default 960), extracts independent line hypotheses without those fixed bins, uses a different fit/extension policy, and associates hypotheses across frames. Confirmed current tracks are colored; tentative or held tracks are gray dashed and invalid in machine-readable output. Manual image browsing resets that temporal history.

Tracking can reduce jitter but cannot restore pixels rejected by a color threshold. Shadows, glare and camera auto-exposure can change masks. There are no labeled lane annotations in this repo, so examples and confidence scores are not measured accuracy.

For tracking settings, see [Tracked version](TRACKED_VERSION.md). For the robot's required live checks, see [Robot setup](ROBOT_SETUP.md).

## Calibrated physical pipeline

The description above covers the legacy Hough/original paths. The calibrated ridge backend adds physical components, sampled curves, metric tracking, optional registered depth and live ground estimation. See [ridge backend](RIDGE_BACKEND.md) for commands, stages and limits, and [benchmark data](../validation/backend_benchmark.json) for measured synthetic checks and unlabeled real smoke tests. Existing defaults and original reference images remain unchanged in behavior.

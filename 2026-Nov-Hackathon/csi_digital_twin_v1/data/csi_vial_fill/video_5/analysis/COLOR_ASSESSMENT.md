# Video 5 color-only assessment

- Source video: `C:\Development\2026-Nov-Hackathon\csi_digital_twin_v1\data\csi_vial_fill\video_5\video\vial_fill_video_5.mp4` (50942 frames at 30 fps).
- Black-collar signal detector: 30 disappearance runs, mapped in sequence to the 30 source recipe rows.
- Detection settings: grayscale `<60` fraction in ROI x=255:390, y=190:255; disappearance below 0.04.
- Each color sample is the frame immediately before a sustained 10% collar-signal drop, using a preceding stable baseline.
- Color measurement: median masked HSV and OpenCV 8-bit Lab values in ROI x=278:350, y=275:425; this is image-derived, not calibrated physical color.
- The first vial in each 3-vial recipe group is retained for timing but excluded from clean color references.
- Exploratory leave-one-vial-out nearest-centroid check: 16/20 clean candidate frames assigned to the correct recipe.
- Misclassifications: vial 3 (recipe 5 -> 9), vial 5 (recipe 6 -> 12), vial 11 (recipe 8 -> 9), vial 29 (recipe 14 -> 10).

## Interpretation

Color is useful for coarse recipe grouping, but these measurements do not support reliable unique identification of all 10 recipes. The leave-one-out check has only two candidate vials per recipe, uses one remaining vial as the comparison reference, and is sensitive to lighting, reflections, glass, liquid level, and the fixed ROI. It is exploratory, not a validated classifier.

Recipes 5 and 8 have the same T100:T200:T400 proportions (10:10:10 mL versus 20:20:20 mL) and the same dispense order. Their mixed-liquid color is therefore expected to be indistinguishable by color alone; their total volume/fill height is a useful additional cue. The observed candidate samples also show overlap among recipes 5, 8, and 9, and between recipes 6 and 12.

For robust recipe identification, combine settled liquid color with fill height and the ordered nozzle-stream colors. The source recipe labels remain authoritative for recipe IDs; this image analysis does not rewrite them.

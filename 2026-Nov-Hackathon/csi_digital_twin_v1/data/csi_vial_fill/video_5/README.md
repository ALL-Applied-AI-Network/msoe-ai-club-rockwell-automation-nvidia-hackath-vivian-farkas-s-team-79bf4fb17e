# Video 5 vial-fill data

This folder contains the vial-fill camera data for Video 5 only, selected from
the supplied `csi-vial-fill-dataset` ZIP. Other videos and the cap-seal and
tank-level camera data are stored separately.

## Contents

- `video/vial_fill_video_5.mp4`: source vial-fill video.
- `images/`: all 845 JPG frames whose source image index assigns them to video 5.
- `labels/source/video5_vial_recipes.csv` and `.json`: original per-vial recipe
  labels, one record for each of the 30 vials.
- `labels/source/video5_frame_labels.csv`: original labels mapped to sampled
  frames.
- `labels/source/README.md`: source dataset documentation and recipe legend.
- `labels/image_index_video5.csv`: source image index filtered to video 5.
- `labels/video5_frame_manifest.csv`: derived join of the frame labels and
  image index, keyed by exact filename, with image paths and reliability flags.
- `labels/review_frames.csv`: exploratory early, middle, and late sampled-frame
  picks from vial positions 2 and 3 of each recipe. These are starting points
  for review, not confirmed final-state frames or complete stream sequences.
- `analysis/`: reproducible black-collar transition detections, selected
  full-frame samples, image-derived color measurements, and the color-only
  assessment. Regenerate these with `python tools/analyze_video5_colors.py`
  from the project root (requires Python packages `numpy` and `opencv-python`).
- `analysis/nozzle/`: full-frame nozzle activity/color measurements, grouped
  color phases, pauses between different observed colors, and an analysis
  report. Regenerate these for Videos 4 and 5 with
  `python tools/analyze_nozzle_streams.py` from the project root.
- `analysis/colored_streams/`: a separate orange/blue-only Video 5 analysis.
  Regenerate it with `python tools/analyze_colored_streams.py` from the project
  root. It does not attempt to classify clear flow.
- `analysis/meniscus/`: first-pass manual meniscus-height intervals measured
  from the existing last-stable frames; see `MENISCUS_HEIGHT_ANALYSIS.md`.
- `analysis/combined_cues/`: per-vial join of stream, final-color, and meniscus
  cues. Regenerate it with `python tools/combine_video5_recipe_cues.py` from
  the project root; see `COMBINED_CUE_ANALYSIS.md` for the combined findings.

## Label alignment and recipe coverage

Video 5 has 30 vials: 10 recipe groups (IDs 5-14), with 3 vials per recipe.
The frame-label CSV and the video-5-filtered image index have an exact
one-to-one filename match across all 845 frames. Each image in the manifest
therefore links to its frame label and capture timestamp by filename; `video_s`
is the label's time relative to the start of the source video.

The original dataset labels tank volumes, dispense order, vial number, recipe
ID, and sampled fill-window frames. Its recipe legend says T100 is clear,
T200 is orange, and T400 is blue. It does not provide calibrated RGB values for
the mixed liquid or stream, nor image-measured fill heights. The descriptive
color/purpose field is blank for recipes 11-14. Those visual properties still
need to be reviewed and measured against the images/video before they are used
as target values for Isaac Sim.

## Carryover handling

The source labels do not contain a contamination flag. Based on the user's
process note, the first vial in each three-vial recipe group is marked as a
carryover/transition suspect in `video5_frame_manifest.csv` and is not included
in the provisional reference-frame list. Vial 1 is the beginning of the clip,
so its preceding machine state is unknown; the source recipe note also says
"swapped in". Treat it as uncertain and do not use it as a clean reference
without further review. Vials in positions 2 and 3 are candidates, not
automatically verified clean samples.

The reference-frame picks are late frames *within* the labeled fill window.
They may still show the dispensing stream, so use the full labeled sequence
and source video when distinguishing stream color from final vial color or
estimating the settled liquid level.

## Full-frame nozzle analysis

`tools/analyze_nozzle_streams.py` measures a narrow region immediately below
the nozzle on every frame within each Video 5 recipe window. It records
frame-level stream-detection scores and approximate HSV/Lab colors, groups
observations into color phases, and records only visible stream-off intervals
between different measured phases. Same-color pauses are not listed as
between-color pauses. The first vial after each recipe switch remains in the
timing output but is flagged as carryover-suspect.

Video 4 is analyzed separately as an unlabeled example; its six vial intervals
are inferred from collar departures, not recipe labels. The Video 5 dispense
order is used only as a cross-check after visual measurements. A low-saturation
phase can be marked as a candidate T100 phase when it occurs in the expected
order, but disagreements are preserved.

These are exploratory computer-vision measurements, not calibrated fluid
colors or validated flow boundaries. The liquid stream may be faint or nearly
clear, and reflections or nozzle motion can affect both detection and color.
Review the source footage before using exact phase boundaries, colors, or
timings as simulation targets. See `analysis/nozzle/NOZZLE_ANALYSIS.md` for
the method and output summaries.

The current automated pass produced 93 candidate color phases and 7
between-color pauses across 30 recipe windows. Of the phases that could be
compared to the expected dispense order, 45 were classified as visual-order
disagreements. Treat this as a signal that the automatic color assignment is
not yet reliable enough for recipe targets; retain the raw per-frame
measurements and verify phase labels against the footage.

## Video-first transition and color analysis

`tools/analyze_video5_colors.py` scans the full video for low-black-signal runs
in the fixed collar region, then maps the 30 detected vial events to the source
recipe rows by sequence. It samples the last frame before a sustained collar
signal drop, retaining each first-after-switch vial for timing while excluding
it from clean color references. The script writes per-vial timing and color
CSVs, a recipe summary, sample frames, and `analysis/COLOR_ASSESSMENT.md`.

The initial analysis detects 30 collar-disappearance runs, matching the
30 source vials. Its image-derived color-only nearest-centroid check is
exploratory rather than validated: it matched 16 of 20 clean candidate frames,
with errors among recipes 5/9, 6/12, 8/9, and 14/10. There are only two clean
candidate vials per recipe, and the measured colors are affected by lighting,
reflections, glass, liquid level, and the fixed image region. Color is useful
for coarse grouping but is not sufficient to reliably distinguish all 10
recipes.
Recipes 5 and 8 have the same T100:T200:T400 proportions and dispense order,
but different total volumes; fill height is needed to tell those recipes apart.
Combine liquid color with fill height and the ordered nozzle-stream colors for
stronger identification. These derived measurements do not alter source labels.

## Orange/blue-only stream analysis

`tools/analyze_colored_streams.py` measures candidate orange and blue stream
phases in the full Video 5 footage, using the labeled recipe windows only to set
the measurement intervals and compare observed colors with the known T200 then
T400 order. Its approximate hue references are anchored to the same-camera
single-color examples (recipe 6, clean vial 5 for T200; recipe 7, clean vials
8-9 for T400). It does not infer clear flow from an absent color signal.

The current output is diagnostic, not recipe-identification evidence: it finds
57 candidate phases across 30 vials, but only 8 complete candidate sequences
exactly match the recipe's expected visible colored order. Other records contain
missing phases, unexpected colors, or apparent reversals. These may reflect
measurement errors, mixing/reflections, or actual visual discrepancies; review
the source video before drawing process conclusions. See
`analysis/colored_streams/ORANGE_BLUE_ANALYSIS.md` for the method and output
details.

## Meniscus-height review

`analysis/meniscus/meniscus_measurements.csv` records first-pass image-coordinate
ranges for all 30 vial samples. Visible menisci are measured as ranges; if the
holder hides the meniscus, the row contains a broad interval covering the
obscured band. The sampled frames are late-stationary candidates, not proven
fully settled states. Pixel heights are not milliliters: volume conversion
requires physical calibration. The current view shows lower levels in the first
six vials, while the menisci for the other 24 are obscured, limiting comparison
among high-fill recipes.

## Initial spot-check and suggested review

An initial spot-check found that some sampled frames late in a labeled fill
window show a vial moving away or little/no stream. Do not treat the last
`in_fill` sample as a final-state image automatically. For example, sampled
frames of vial 29 (recipe 14, around video seconds 1626.751-1640.843) appear
orange/brown in both the vial and the visible stream, while the source recipe
and tank-color legend imply T400 (blue) followed by T100 (clear). This is an
unresolved visual/label discrepancy, not a corrected label; verify it against
the full video and neighboring vials before using it as recipe ground truth.

Recommended review:

1. Compare the early, middle, and late samples for both candidate vials
   (positions 2 and 3) in each recipe.
2. Review the full source video around each dispense window to identify the
   T200/T400/T100 phases and distinguish the stream from the mixed vial color.
3. Inspect the vial after dispensing for a stable color and fill-height
   observation, excluding the transition vial as noted above.
4. Record manually derived color/height measurements separately from original
   labels, citing image filename/video time, method, and confidence.

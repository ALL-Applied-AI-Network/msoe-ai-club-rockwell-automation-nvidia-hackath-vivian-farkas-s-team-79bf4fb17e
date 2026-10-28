# Video 5 combined recipe cues

This report joins the nozzle-stream analysis, final-vial color measurements, and meniscus-height review by vial. Source recipe labels are retained as reference labels, not inferred results.

## Overall result

- Joined records: 30 vials.
- Final-color exploratory leave-one-out assignments: 16/20 clean candidate vials; this is a small, exploratory check, not validated accuracy.
- Automated stream sequences exactly matched the expected sequence for 8/30 vials; the detector is not reliable enough to use this as a process or recipe score.
- Meniscus visible below the holder in 6/30 selected frames; hidden in 24/30.
- No combined classifier or confidence score is reported: the stream detector and many height intervals are not sufficiently reliable.

## Manually reviewed stream evidence

- Vial 2 (recipe 5): blue, then a mixed blue-orange appearance; not confirmed as a separate orange phase.
- Vial 3 (recipe 5): green until 1:36, then green-brown until 1:59; tank colors remain ambiguous.
- Vial 10 (recipe 8): blue through 7:23, no visible stream until 7:35, then light blue fading toward clear until 7:41.
- Vials 11 and 12 (recipe 8): orange to green to blue, with no visible stop. This agrees qualitatively with the expected orange-to-blue order; green is treated as a transition color, not a third tank.
- These five user-reviewed vials are the only manual stream observations included here. For other vials, the automated color sequence remains unverified.

## What the three cues suggest

### Recipes 5 and 8: same proportions, different total volume

Their clean candidate final-color hues are close (recipe 5: 44; recipe 8: 45.5 in OpenCV hue units), consistent with their equal component ratios. Recipe 5 samples have visible 70–96 px height ranges; recipe 8 menisci are hidden in a broad 137–195 px range. That suggests a coarse low-versus-higher fill distinction, but it does not provide calibrated volume or a trustworthy exact level measurement.

### Recipes 7 and 14: both total 70 mL, blue-heavy versus clear-heavy

The clean recipe 7 samples are strongly blue in the image (hues 98 and 99); recipe 14 samples are more variable (hues 66 and 80). Both have the same broad holder-obscured height interval, and both are expected to show blue then clear, so level and stream order do not separate them. Final-vial color may help, but the two recipe 14 samples are not consistent enough for a dependable automatic decision.

### Recipes 11 and 12: same total, contrasting colored proportions

Both are labeled 70 mL and share the same obscured height interval. Their clean final-vial colors differ strongly in the image: recipe 11 has median hue 88, versus 11 for recipe 12; the exploratory color-only check assigned 2/2 and 2/2 clean candidates correctly. This is a promising visual distinction in this clip, but it is based on only two clean vials per recipe and is not validated. Automated stream output often misses one of the expected colors.

### Remaining comparisons

All source-labeled 60–80 mL cases have the same broad obscured level interval in this first pass. Their separation therefore depends mostly on final-vial color and, potentially, stream phase durations. The current stream detector does not measure those reliably. Recipe 6 and recipe 12 both look orange-heavy but have different totals; color alone can confuse them, while height only gives a coarse lower-versus-higher cue. Recipe 12 and recipe 13 also look similar in the current final color measurements despite different component mixtures.

## Conclusion

Combining the cues improves the qualitative picture but does not yet identify every recipe reliably. The strongest current use is coarse grouping: low versus higher fill for some comparisons, and visibly different final colors for recipes such as 11 versus 12. The manual stream checks help interpret transitions, but the automated stream labels should not be treated as ground truth. For dependable recipe identification, the meniscus needs a clearer view and height-to-volume calibration; stream phases need additional manual checks or a better detector.

See `combined_recipe_cues.csv` for every joined vial record and its source measurements.

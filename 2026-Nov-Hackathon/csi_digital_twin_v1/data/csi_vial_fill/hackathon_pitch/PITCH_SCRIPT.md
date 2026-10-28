# Hackathon pitch: Recipe Fingerprint Explorer

## 2–3 minute talk track

“Can fill-line video help us narrow down which recipe went into each vial? We tested three visual methods against ten labeled reference recipes from Video 5: finished-liquid color, liquid level, and the orange/blue stream sequence.

First, color: each vial is compared in Lab color space with clean reference examples. In a small leave-one-vial-out test on Video 5, color ranked the right recipe first for 16 of 20 clean repeats, and in the top two for 18. This is the strongest single cue, but not a probability or cross-run accuracy. Recipe profiles can look similar—for example, an R14 sample had R7 as its next color match, and R12/R13 can appear as alternatives. Lighting, glass reflections, fill amount, and mixing all shift the image.

Second, level: the volume chart and vial photos show how fill height could separate mixtures with similar colors. But only 4 of 20 clean Video 5 holdout vials had visible menisci; among those, top-1 was 2 of 4 and top-2 was 4 of 4. In our 34 unlabeled Videos 1–4 samples, only three looked possibly low; the other 31 were obscured or uncertain. These are not calibrated milliliters.

Third, stream sequence: the detector finds orange/blue-looking phases, but reflections, short phases, clear flow, and missed intervals make the labels noisy. In the separate Video 5 holdout, stream ranked only 4 of 20 first and 10 of 20 in the top two. Treat it as process context—not tank identity.

Putting the evidence together, an exploratory equal-weight rank fusion reached 13 of 20 top-1 and 18 of 20 top-2 on the same small Video 5 test. For Videos 1–4, we show the nearest color candidate and runner-up alongside stream and level observations for every one of the 34 vials. Because those videos have no recipe labels, we cannot calculate their accuracy. The result is a transparent shortlist, not confirmed recipe IDs.”

## Demo sequence

1. Show the ten labeled Video 5 vial photos as the comparison library.
2. Color: show all 34 vial photos, the nearest color candidate and the runner-up; explain that Lab distance is not probability.
3. Level: use the recipe volume bars and example vial images; point out that three of 34 unlabeled vials are only qualitative low-level candidates and 31 are obscured/uncertain.
4. Stream: play the annotated Video 4 clip and explain that phase colors are heuristic appearances, not verified tank identities.
5. Finish on the all-34 table. The listed recipe is a color-led candidate, qualified by stream and level evidence; it is not a scored fusion or confirmed label.

## Evidence boundary

- Videos 1–4 have no authoritative recipe IDs in the provided dataset.
- Video 5 contains the labeled reference recipes (5, 6, 7, 8, 9, 10, 11, 12, 13, 14).
- The color, level, stream, and equal-weight fusion scores are a small within-Video-5 leave-one-vial-out exercise, not cross-day or production validation.
- Stream-phase classes are heuristic; a detected color name does not identify a tank or confirm dispensing order.
- Most meniscus observations are obscured and none have pixel-to-volume calibration.
- Color distances are relative rankings, not probabilities. Do not describe any Videos 1–4 candidate ID as ground truth.

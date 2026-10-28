# Candidate recipe patterns in unlabeled Videos 1-4

Videos 1-4 do not have recipe labels. Candidate IDs below are exploratory similarities to Video 5's clean final-vial color references, not verified recipe assignments. The color-only cross-validation on Video 5 matched 16/20 clean samples, and the stream detector also produces false or missing phases.

## Processing and evidence limits

- Vial order is inferred from black-collar disappearance events and checked against the source-documented vial counts: 19, 3, 6, and 6.
- Video 2 had four low-collar runs; the first began at frame 0 and was treated as a likely empty-startup signal, leaving three vial departures.
- Final-vial color is compared in image Lab space with two clean Video 5 samples per recipe. The nearest recipes are ranked only; lighting, mixing, glass, sample timing, and level affect the color.
- Nozzle phases are heuristic appearance labels and are not confirmed tank dispense phases. They are reported per vial in `stream_phases.csv`.
- Meniscus positions are hidden or uncertain in most review frames. Video 3 vials 4-6 visibly appear to have liquid only near the lower vial, but those rough observations are not calibrated volumes.
- First vial/recipe transitions cannot be located reliably in these unlabeled clips, so no vials were excluded as carryover-suspect.

## Per-video patterns

### Video 1

- Source vial count: 19; detected and analyzed: 19; 30 fps.
- Candidate interpretation: Vials 1-5 are consistently vivid blue; their nearest-color result is Recipe 7 for all five. Vials 7-10 and 16-19 are orange-dominant; their nearest-color results alternate between Recipes 6 and 12, which are plausible orange-rich candidates. The remaining dark green/teal vials have nearest-color results among Recipes 5, 8, 9, 10, and 11. These suggest Recipe 7, one or more orange-rich recipes (6/12), and one or more dark mixture recipes, but do not establish exact IDs or group boundaries.

### Video 2

- Source vial count: 3; detected and analyzed: 3; 30 fps. Startup adjustment: ignored leading low-collar run beginning at frame 0.
- Candidate interpretation: Three vial departures are supported after ignoring the frame-0 startup signal. All three are closest in final color to Recipe 11; vials 2 and 3 have a notably dark blue-green appearance and orange/blue stream candidates. Recipe 11 is the leading hypothesis, but an unlabeled first vial could include carryover, and the stream classifier is not reliable enough to confirm the assignment.

### Video 3

- Source vial count: 6; detected and analyzed: 6; 30 fps.
- Candidate interpretation: The six vials do not form a reliable match to the known recipes. The color-only nearest result is Recipe 10 for vial 1 and Recipe 14 for vials 2-6, but the latter frames look pale/clear and vials 4-6 appear to contain only a small amount near the bottom. Those nearest-color results are likely confounded by low color signal, partial fills, or a process state unlike the Video 5 reference. Recipe 14 is only a weak possibility, not an assignment.

### Video 4

- Source vial count: 6; detected and analyzed: 6; 30 fps.
- Candidate interpretation: Two repeated visual families are apparent: vials 1-3 are vivid blue; their color-nearest results are Recipe 11 for vial 1 (Recipe 7 is second) and Recipe 7 for vials 2-3. Vials 4-6 are consistently dark green/teal; vials 4-5 are nearest Recipe 11 and vial 6 is nearest Recipe 9, with Recipe 11 a close second. The first group is most consistent with Recipe 7; the second is a Recipe 9/11 candidate. These recipes have similar mixed-color references, and the hidden level prevents separating their 80 mL versus 70 mL totals. This is the clearest two-family candidate in the four clips, but it is not confirmed.

## Overall conclusion

Video 4 provides the clearest two-family candidate: a blue-dominant group consistent with Recipe 7, followed by a dark blue-green/orange-mix group that could be Recipe 9 or 11. Vials 4-5 are nearest Recipe 11 in color; vial 6 is nearest Recipe 9, with Recipe 11 a close second. The hidden level prevents separating their 80 mL versus 70 mL totals, so the exact second recipe is unresolved. Video 2 also points toward Recipe 11, though this needs confirmation. Video 1 appears to include a Recipe 7-like blue family, orange-rich candidates (Recipes 6/12), and dark mixed-color candidates (Recipes 5/8/9/10/11); exact IDs are unresolved. Video 3 cannot be matched reliably; Recipe 14 is a weak color-only possibility, but the apparent low/clear fills conflict with that interpretation.

No absolute recipe IDs can be confirmed for Videos 1-4 without labels or additional independent evidence (for example tank levels, batch scheduler records, or manually verified stream/meniscus observations). Use `unlabeled_video_cues.csv` for nearest-color rankings per vial and `stream_phases.csv` for the raw phase candidates.

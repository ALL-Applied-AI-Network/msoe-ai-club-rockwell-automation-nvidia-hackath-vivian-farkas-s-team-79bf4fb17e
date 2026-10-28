# Video 5 label-blind cue test

## Protocol

- Vial departures and stable-color sample frames were detected from the video collar signal; no recipe labels or recipe time windows were used to extract vial features.
- Stream-color phase sequences were re-extracted from each detected collar-return-to-departure interval, independently of recipe labels.
- Manual meniscus ranges were joined by vial number after cue extraction. The ranges are image-pixel annotations, not calibrated volumes.
- The first vial in each fixed three-vial block was prespecified as transition/carryover-suspect and excluded from training; this schedule rule uses vial position, not recipe IDs. The held-out recipe label was used only after predictions were frozen, for scoring.
- The stream classifier learns observed phase-sequence examples from training vials only. The level cue can only rank recipe classes for which training menisci are visible.
- Combined ranking is an equal-weight mean of the available cue rank positions (color, stream, level); it is an exploratory fusion rule, not a trained or calibrated probability.

## Results

- Blind feature extraction produced 30 vial records. Primary scoring excludes the 10 carryover-suspect first-in-group vials, leaving 20 clean repeat vials (2 per recipe).
- Only 4 of these clean repeat vials have a manually visible meniscus; all other liquid-level ranges overlap the same holder-obscured interval.

| Cue/ranker | Clean top-1 | Clean top-2 | Clean coverage | All 30 top-1 |
|---|---:|---:|---:|---:|
| Color | 16/20 | 18/20 | 20/20 | 16/30 |
| Stream | 4/20 | 10/20 | 20/20 | 4/30 |
| Level | 2/4 | 4/4 | 4/20 | 3/6 |
| Combined | 13/20 | 18/20 | 20/20 | 14/30 |

## Interpretation and limitations

- This is a within-one-video, leave-one-vial-out experiment. It does not test another recording day, lighting setup, camera, or production run.
- Each clean recipe class has only two reference examples. A clean held-out vial has only one same-recipe clean training example.
- The stream extraction uses detected collar events rather than label-defined recipe intervals. Arrival detection can still include cart movement or imperfect window boundaries, and the stream classifier is noisy.
- The level evidence is largely uninformative because the holder obscures 16 of the 20 clean levels. The visible level measurements are manual image-pixel ranges, with no pixel-to-volume calibration.
- The combined ranker is a fixed exploratory comparison, not a validated classifier. Its score is not a probability or confidence estimate.
- Recipe IDs are supplied as the training catalog for candidate comparison; without labeled training examples or a recipe-to-visual-profile mapping, a fully unlabeled video can only be clustered, not assigned recipe IDs.

See `blind_feature_extraction.csv` for cues without recipe IDs and `blind_test_scored_predictions.csv` for held-out predictions joined to labels after scoring.

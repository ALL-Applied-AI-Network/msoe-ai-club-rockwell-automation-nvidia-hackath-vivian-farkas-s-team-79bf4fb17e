# Video 5 meniscus-height review

- Source: Video 5's 640 × 480 vial-fill recording.
- Samples: the 30 existing last-stable frames selected from the collar-motion analysis.
- Measurements: manually reviewed image-coordinate ranges in `meniscus_measurements.csv`.
- First vial after each recipe switch remains included but flagged as carryover-suspect.

## Method and limits

The sample for each vial is the frame immediately before the detected sustained
collar-motion onset. This gives a repeatable late-stationary view, but does not
by itself prove that the liquid had fully settled. The meniscus is recorded as
a pixel-coordinate interval, with smaller `y` values higher in the image.
Visible menisci are bounded by the observed edge; where the black holder hides
the edge, the interval spans the holder-obscured band rather than assigning a
point estimate.

The relative image height is `400 - meniscus_y` pixels, using an approximate
fixed vial-bottom reference at image row 400. These pixel ranges are comparative
image measurements only. No camera-to-vial geometry or volume calibration is
available, so they must not be interpreted as milliliters. `source_total_ml` is
copied from the recipe labels for comparison and was not used to select the
meniscus position.

## Initial observation

The meniscus is visible below the holder in the first six samples (recipes 5
and 6). Their measured image-height ranges are 70–96 px for the source-labeled
30 mL vials and 87–115 px for the 40 mL vials; these ranges overlap, so the
current samples do not reliably distinguish 30 mL from 40 mL. In the remaining
24 samples, the meniscus reaches into the holder-obscured band; only a broad
137–195 px height interval can be recorded. This suggests a coarse
lower-versus-higher grouping in the images, but the current view does not
provide a reliable fine-grained measurement among high fills. In particular,
the source-labeled 60–80 mL cases are all obscured in these selected frames, so
their identical pixel intervals cannot distinguish those volumes.

The first six point-range estimates are approximate and the images are
low-resolution, reflective, and partly shadowed. Use them as a first-pass
manual review, not calibrated or settled-volume ground truth. A physical
height-to-volume calibration (or a camera view that sees the meniscus above
the holder) is needed before reporting mL or identifying recipes from level
alone.

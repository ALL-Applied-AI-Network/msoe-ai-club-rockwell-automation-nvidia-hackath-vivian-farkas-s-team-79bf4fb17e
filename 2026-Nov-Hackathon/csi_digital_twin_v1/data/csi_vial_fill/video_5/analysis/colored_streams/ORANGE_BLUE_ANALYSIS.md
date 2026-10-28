# Video 5 orange/blue stream analysis

- Source: `C:\Development\2026-Nov-Hackathon\csi_digital_twin_v1\data\csi_vial_fill\video_5\video\vial_fill_video_5.mp4` (50942 frames at 30 fps).
- Labeled vial windows analyzed: 30.
- Frame-level measurements: 30777.
- Candidate visible orange/blue phases: 57.
- Vials whose complete observed colored sequence matches the expected recipe order: 8/30.

## Scope

This pass deliberately measures only visible orange and blue stream color. It does not classify clear flow, and it does not interpret a missing orange/blue signal as proof that liquid flow stopped. For recipes containing T200 and T400, the expected colored order is orange then blue; T100 is omitted from the colored target sequence. Recipes using only one colored tank are checked against that one expected color. A sequence counts as a match only when the complete candidate sequence exactly matches the expected colors; missing or extra phases do not count as a match.

Recipe labels are used to define the vial frame windows and to compare the observed colored sequence after image measurement. They do not force a missing phase to appear. Intermediate colored hues are assigned to the nearer orange/blue hue reference. Per-frame color evidence and smoothed class are preserved in `frame_measurements.csv`; candidate phases are in `color_phases.csv`; expected-versus-observed order and orange-to-blue unclassified intervals are in `vial_color_order_summary.csv`.

The stream detector examines a narrow region immediately below the nozzle and compares saturated pixels against nearby background. Image hue is affected by lighting, reflections, flow thickness, and mixing in the shared path. For this pass, the hue references were anchored to the same-camera stream appearances in the labeled single-colored recipes: T200-only recipe 6 (clean vial 5, median observed hue 30) and T400-only recipe 7 (clean vials 8-9, median observed hue 87). Those references are approximate and the anchors are not physical color calibration. These color labels and phase boundaries remain exploratory candidates, not confirmed valve timings.

An orange-to-blue interval with no detected orange/blue signal is reported as an unclassified interval. It may contain clear flow, a pause, or both; this analysis cannot distinguish those cases. A phase with fewer than 12 active colored frames is marked for review. The first vial after each recipe switch remains measured and is flagged as carryover-suspect.

Compare candidates with the full source footage before using exact colors or timings as simulation targets.

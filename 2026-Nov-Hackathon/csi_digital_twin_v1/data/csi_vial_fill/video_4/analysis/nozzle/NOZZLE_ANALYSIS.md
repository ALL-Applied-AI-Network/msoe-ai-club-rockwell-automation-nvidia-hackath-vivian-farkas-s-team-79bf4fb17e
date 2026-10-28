# Video 4 nozzle-stream analysis

- Source: `C:\Development\2026-Nov-Hackathon\csi_digital_twin_v1\data\csi_vial_fill\video_4\video\vial_fill_video_4.mp4` (9482 frames at 30 fps).
- Vial intervals analyzed: 6.
- Frames measured within the analysis windows: 9428; raw frame-level flow detections: 3036.
- Measured color phases: 12; inter-color visible pauses: 0.

## Method and interpretation

The stream detector compares the nozzle-center strip x=298:312, y=95:175 with adjacent background strips. It flags a candidate stream when at least 15 rows have a Lab contrast above 10 and a continuous vertical run is at least 15 rows. A five-frame majority smooths flow detections; short color flicker is folded into the nearest adjacent measured phase.

For active frames, median HSV and 8-bit Lab values are measured on the strongest background-contrasting line pixels in the nozzle strip. OpenCV hue nearer 15 is labeled orange and nearer 95 is labeled blue; saturation at or below 18 is labeled `clear_candidate`. These are heuristic image-space classes, not calibrated fluid colors. Raw and smoothed flow/color states are preserved in `frame_measurements.csv`.

A pause is reported only when a visible stream-off interval lies between two different measured color phases. Pauses within a single phase, including same-color interruptions, are intentionally not included.

The detector is an exploratory automated measurement, not a validated optical classifier. The clear-liquid stream and faint/transparent flow may be missed; reflections, nozzle motion, and weak contrast may create uncertain boundaries. Check low-confidence frames and each reported phase against the source video before using exact timings or colors as simulation targets.

Video 4 has no recipe labels. Vial numbering is inferred only from the six collar-departure events; no phase is assigned to a recipe or tank.
No between-color stream-off pause met the current detector threshold in this pass; this does not prove that pauses never occur, and brief or transparent flow may be missed.

# Video 5 nozzle-stream analysis

- Source: `C:\Development\2026-Nov-Hackathon\csi_digital_twin_v1\data\csi_vial_fill\video_5\video\vial_fill_video_5.mp4` (50942 frames at 30 fps).
- Vial intervals analyzed: 30.
- Frames measured within the analysis windows: 30777; raw frame-level flow detections: 13402.
- Measured color phases: 93; inter-color visible pauses: 7.

## Method and interpretation

The stream detector compares the nozzle-center strip x=298:312, y=95:175 with adjacent background strips. It flags a candidate stream when at least 15 rows have a Lab contrast above 10 and a continuous vertical run is at least 15 rows. A five-frame majority smooths flow detections; short color flicker is folded into the nearest adjacent measured phase.

For active frames, median HSV and 8-bit Lab values are measured on the strongest background-contrasting line pixels in the nozzle strip. OpenCV hue nearer 15 is labeled orange and nearer 95 is labeled blue; saturation at or below 18 is labeled `clear_candidate`. These are heuristic image-space classes, not calibrated fluid colors. Raw and smoothed flow/color states are preserved in `frame_measurements.csv`.

A pause is reported only when a visible stream-off interval lies between two different measured color phases. Pauses within a single phase, including same-color interruptions, are intentionally not included.

The detector is an exploratory automated measurement, not a validated optical classifier. The clear-liquid stream and faint/transparent flow may be missed; reflections, nozzle motion, and weak contrast may create uncertain boundaries. Check low-confidence frames and each reported phase against the source video before using exact timings or colors as simulation targets.

- Color-order disagreements against the Video 5 recipe sequence: 45.

Video 5's source recipe window separates vial records. Its dispense order is checked only after measuring the visible stream. A low-saturation phase is a candidate T100 only when T100 is next in the labeled order; disagreements are retained, not relabeled.

Video 5 first-after-switch vials are: 1, 4, 7, 10, 13, 16, 19, 22, 25, and 28. They remain in the measurements but should not be used as clean recipe references.

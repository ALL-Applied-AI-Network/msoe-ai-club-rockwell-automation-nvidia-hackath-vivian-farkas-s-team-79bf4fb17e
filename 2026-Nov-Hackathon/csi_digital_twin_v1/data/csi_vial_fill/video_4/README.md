# Video 4 vial-fill data

This folder contains the original vial-fill Video 4 extracted from the supplied
`csi-vial-fill-dataset` ZIP. The video is 640 × 480 at 30 fps and contains six
vials. The source dataset does not label their recipes, so the analysis here
does not assign confirmed recipe IDs or tank identities.

## Contents

- `video/vial_fill_video_4.mp4`: original vial-fill footage.
- `analysis/nozzle/`: full-frame nozzle flow measurements, observed color
  phases, between-color pause timings, and the analysis report.
- `../unlabeled_video_analysis/`: exploratory cross-video comparison of final
  color, stream phases, and visible liquid level against Video 5 recipe
  references. It suggests candidate recipes but is not ground truth.

Regenerate the nozzle analysis from the project root with:

```powershell
python tools\analyze_nozzle_streams.py
```

Video 4 vial numbering is inferred from six black-collar departure events. The
reported color names describe approximate image-space appearance only. Use
Video 4 as an unlabeled example for reviewing visible stream pauses and color
changes, not as recipe ground truth. The cross-video candidate analysis finds
two visual families: the first tentatively resembles Recipe 7, while the
second could be Recipe 9 or 11; neither assignment is confirmed.

The current automated pass found 12 candidate color-phase segments and no
between-color stream-off pause that met its detector threshold. That is not
proof that a pause never occurs: transparent flow and weak boundaries may be
missed, so review the source video around any pause you observed.

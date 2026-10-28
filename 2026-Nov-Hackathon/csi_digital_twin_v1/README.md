# CSI vial line: digital twin

This is a digital twin of the CSI vial line, prepared for generating synthetic data in NVIDIA Isaac Sim / Omniverse. It contains two stations, each with a camera matched to a real camera on the line:

- **Tray inspection station:** robot, inspection trays and capped vials.
- **Fill (nozzle) station:** vial carts under the dispensing nozzle, with a filling animation.

Units are **meters** and **Z is up**. There is **no physics** anywhere: everything is static geometry, except the fill station's pre-recorded filling animation.

## Contents
```
csi_line.usda                        the full line (open this for everything)
stations/
  tray_inspection/tray_inspection.usdc   tray inspection station + cap-seal camera + its lights
  fill_station/fill_station.usda         fill station + fill camera + its lights (animated, frames 1-686)
  magnemover/magnemover.usdc             MagneMover track and carts
  facility/facility.usdc                 the rest of the plant, floor and dome light
cameras/                             camera settings (JSON), one file per camera
tools/
  render_example.py                  render one image from any camera (Isaac Sim)
  apply_lens.py                      adds the real cap-seal camera lens distortion to a render
```
Keep the folder structure as it is: the files reference each other by relative paths.

## The full line or a single station?
`csi_line.usda` **is** the digital twin. It does not hold any geometry itself: it references the four station files and places them together.

| You want to... | Open |
|---|---|
| See or render the whole line | `csi_line.usda` |
| Work only on the tray inspection data | `stations/tray_inspection/tray_inspection.usdc` |
| Work only on the fill station data | `stations/fill_station/fill_station.usda` |

- **Open a station file on its own** when you only need that station. It loads in seconds, while the full line loads the whole plant (about 0.7 GB). Each station file has its own camera(s) and lights, so you can render from it directly.
- **To change something inside a station** (a material, a vial, a light), **edit the station file.** The full line picks up the change automatically.
- **Edit `csi_line.usda` only for line-level changes:** where the stations sit relative to each other, or switching parts of the line on or off.

  If you edit a station's contents while `csi_line.usda` is open, Isaac Sim saves the change into `csi_line.usda` as an override. It applies only to the full line, not to the station file.
- The tray inspection, MagneMover and facility files use the same coordinates as the full line. The fill station file uses its own local coordinates, and `csi_line.usda` moves it into place on the track.

## Cameras
| Camera | Station | Final image | Prim path (in the station file) |
|---|---|---|---|
| `CapSealCam` | tray inspection | 640 × 480 | `/TrayInspection/CapSealCam/CapSealCam` |
| `FillCam` | fill station | 640 × 480 | `/FillStation/FillStation_LocalRoot/FillCam/FillCam` |

- **Paths in the full line:** add the prefix `/CSI_Line`. For example, `/CSI_Line/TrayInspection/CapSealCam/CapSealCam`.
- **Camera JSON files:** `cameras/<name>.json` has each camera's position, orientation, focal length, resolution and lens values, plus its prim path in both the station file and the full line.
- **Cap-seal camera:** `CapSealCam` matches the real 640 × 480 cap-seal camera, solved from the cap_seal video clip.
- **Lens distortion (CapSealCam):** the real camera has a slight lens distortion, so:
  1. Render at `render_px` (768 × 576, a 1.2× wider pinhole view).
  2. Run `tools/apply_lens.py`, which adds the distortion and crops to 640 × 480.
- **Fill camera:** a plain pinhole. Render 640 × 480 directly.

## Fill station animation
- The fill station plays a filling sequence over time codes **1–686** at **30 fps** (22.9 s). Blue liquid fills, then clear liquid is added, while the next cart moves in.
- Pick the moment by time code. For example, 301 is mid-fill and 686 is the finished vial.
- Everything else in the line is static.

## Recipe reference data
- Unlabeled vial-fill Videos 1–4 are organized under `data/csi_vial_fill/video_1/` through `video_4/`; the exploratory three-cue comparison against Video 5 is under `data/csi_vial_fill/unlabeled_video_analysis/`.
- Video 5's vial-fill video, timestamp-aligned recipe labels, and nozzle analysis are organized under [`data/csi_vial_fill/video_5/`](data/csi_vial_fill/video_5/).
- Unlabeled Video 4 is organized under [`data/csi_vial_fill/video_4/`](data/csi_vial_fill/video_4/) as a separate pause/color-transition example.
- Run `python tools\analyze_nozzle_streams.py` to regenerate the full-frame nozzle measurements for both videos. See each data folder's README for provenance, analysis limits, and carryover handling.
- Run `python tools\analyze_colored_streams.py` for the separate Video 5 orange/blue-only pass. Its hue references come from labeled single-color recipe windows; results remain exploratory and are not yet reliable enough to identify recipes.
- Video 5's first-pass meniscus height intervals are recorded under `data/csi_vial_fill/video_5/analysis/meniscus/`; they are image pixels, not calibrated volumes.
- Run `python tools\combine_video5_recipe_cues.py` to join stream, final-vial color, and meniscus evidence by vial; the combined result remains exploratory and includes manually reviewed stream observations.
- Run `python tools\run_video5_blind_test.py` to extract Video 5 color and stream cues without recipe labels, then score held-out vials against the labels. The exploratory leave-one-vial-out results and limitations are under `data/csi_vial_fill/video_5/analysis/blind_test/`; this is not a cross-run validation.
- Run `python tools\analyze_unlabeled_video_recipes.py` to compare Videos 1–4 against the Video 5 clean recipe references. These clips have no authoritative recipe labels; outputs are candidate matches only.
- The browser-ready hackathon pitch, recipe reference table, ten-recipe photo gallery, 34-vial color-candidate gallery, and annotated Video 4 stream clip are in `data/csi_vial_fill/hackathon_pitch/`. The presentation separates color, level, and stream-sequence evidence, then lists color-led candidates for all 34 unlabeled vials with the other cues and limitations. Open `pitch.html` to present; regenerate the package with `python tools\build_hackathon_pitch.py` (install the clip encoder first with `python -m pip install -r requirements-hackathon-pitch.txt`). Videos 1–4 have no ground-truth labels; their candidates are not measured accuracy.

## Quick start
Run with Isaac Sim's Python (`python.sh` in the Isaac Sim install folder):
```bash
# full line, fill camera, finished vial
<isaac-sim>/python.sh tools/render_example.py --camera FillCam --frame 686 --out fill.png
# full line, cap-seal camera (lens distortion applied automatically)
<isaac-sim>/python.sh tools/render_example.py --camera CapSealCam --out cap_seal.png
# a single station file
<isaac-sim>/python.sh tools/render_example.py --camera FillCam --frame 301 \
    --stage stations/fill_station/fill_station.usda --out fill_station.png
```
`apply_lens.py` can also be run on its own, with any Python that has `numpy` and `opencv-python`:
```bash
python tools/apply_lens.py cap_seal_render_768x576.png cameras/CapSealCam.json cap_seal_final.png
```

## Notes
- **Materials** are standard USD materials (UsdPreviewSurface). Glass and liquid are approximations, so you may want to adjust them for Isaac Sim's RTX renderer.
- **Labels on fill station parts:** they carry `userProperties:synthetic_class`, `synthetic_class_id` and `synthetic_instance_id` attributes, which can be used as labels.
- **Tested with:** Isaac Sim 6.0.

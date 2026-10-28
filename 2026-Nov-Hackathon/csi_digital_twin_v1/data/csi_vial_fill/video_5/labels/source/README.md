# CSI Vial-Fill Multi-Camera Dataset

Synchronized multi-camera video + image captures of an automated **liquid-dosing / vial-fill line**.
Three fixed cameras observe three stations of the process. The dataset is organized around **5 videos**
(IDs **1–5**); every sampled frame carries the `video_id` it came from. One video (**video 5**) is fully
labeled with the dosing **recipe** of every vial.

- **Owner / contact:** tcellio@nvidia.com
- **Resolution / rate:** 640 × 480; videos 30 fps, still images sampled ~every 2 s.

---

## 1. What's in the dataset

Three camera views (the three "data types"):

| Folder | Station | What it shows |
| --- | --- | --- |
| `cap_seal/` | Cap / seal station | The vial cap being placed / sealed. |
| `tank_level/` | Reagent tanks | The dosing tanks (T100 / T200 / T300 / T400) and their levels. |
| `vial_fill/` | Vial fill station | A vial being filled by the dosing nozzle (the labeled station). |

Each camera folder contains:
- `videos/` — `{camera}_video_{id}.mp4`, one per video ID 1–5.
- `images/` — the ~2 s-sampled still frames (filenames encode the capture time; see §5).
- `image_index.csv` — per-image index: `filename, timestamp, video_id`.
- `vial_fill/labels/` — the **video-5 vial labels** (see §4). *Only `vial_fill` is labeled.*

Top level: `videos.csv` (video manifest) and this `README.md`.

```
csi-vial-fill-dataset/
├── README.md
├── videos.csv
├── cap_seal/    { videos/, images/, image_index.csv }
├── tank_level/  { videos/, images/, image_index.csv }
└── vial_fill/   { videos/, images/, image_index.csv, labels/ }
```

---

## 2. How it was collected

Three USB cameras recorded the stations **simultaneously** during each run. For every run the system
saved a continuous **video** per camera plus periodic **still frames** (~every 2 s). Several runs were
recorded; faulty / aborted ones were discarded and the keepers were end-trimmed to drop idle tails,
leaving **5 clean videos (IDs 1–5)**. Because the three cameras in a given video ID were recorded
together, their footage and frames are **time-synchronized** and can be cross-referenced by the
timestamp embedded in each image filename.

During collection a **T300 tank was intermittent / out of service**, so dosing used the three working
tanks **{T100, T200, T400}**.

---

## 3. Videos

| video_id | Duration | Vials | Labeled |
| --- | --- | --- | --- |
| 1 | 18:42 | 19 | no |
| 2 | 2:40 | 3 | no |
| 3 | 3:13 | 6 | no |
| 4 | 5:16 | 6 | no |
| **5** | 28:18 | **30** | **yes — vial_fill** |

All three cameras are present and synchronized for every video ID (see `videos.csv`).
**Video 5 is the only labeled video.** Videos 1–4 are provided **unlabeled** for you to label as you
see fit. Cap and tank data are unlabeled for all videos.

---

## 4. Vial labeling schema (video 5 only)

Every vial is dosed from a **recipe**. Video 5 ran **10 recipes × 3 vials = 30 vials**, in order:
**vial `N` → recipe `5 + ⌊(N−1)/3⌋`** (vials 1–3 = recipe 5, … vials 28–30 = recipe 14).

**Tanks & colors** (dye seen through translucent tanks): `T100` = **clear** (diluent) · `T200` =
**orange** · `T400` = **blue**. (`T300` exists but was out of service — not used.) Config notation
`100:10` means 10 mL drawn from tank T100. **Dispense order per vial: T200 → T400 → T100** (any
absent tank skipped).

### The 10 recipes

| Recipe | Vials | T100 | T200 | T400 | Total (mL) | Dispense order | Color / purpose |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5  | 1–3   | 10 | 10 | 10 | 30 | T200→T400→T100 | mixed – low even |
| 6  | 4–6   | 30 | 10 | –  | 40 | T200→T100 | pale orange |
| 7  | 7–9   | 20 | –  | 50 | 70 | T400→T100 | pale blue |
| 8  | 10–12 | 20 | 20 | 20 | 60 | T200→T400→T100 | even |
| 9  | 13–15 | 10 | 35 | 35 | 80 | T200→T400→T100 | dark saturated |
| 10 | 16–18 | 45 | 15 | 15 | 75 | T200→T400→T100 | pale wash |
| 11 | 19–21 | 10 | 10 | 50 | 70 | T200→T400→T100 | — |
| 12 | 22–24 | 10 | 50 | 10 | 70 | T200→T400→T100 | — |
| 13 | 25–27 | –  | 50 | 20 | 70 | T200→T400 | — |
| 14 | 28–30 | 60 | –  | 10 | 70 | T400→T100 | — |

(Recipes 11–14 were added live at the machine; no purpose note was recorded.)

### Label files (`vial_fill/labels/`)

**`video5_vial_recipes.csv`** / `.json` — the authoritative per-vial table (one row per vial):

| Column | Meaning |
| --- | --- |
| `vial` | 1–30, in order |
| `recipe_id`, `type` | recipe number (5–14) and type (Triple / Pair) |
| `t100_ml`, `t200_ml`, `t400_ml` | mL dispensed from each tank (blank = tank not used) |
| `total_ml` | total volume |
| `dispense_order` | e.g. `T200>T400>T100` |
| `color_purpose` | note (blank for recipes 11–14) |
| `start_time`, `end_time` | fill start/end as `m:ss.s` |
| `start_s`, `end_s`, `duration_s` | fill start/end/length in seconds |
| `start_frame`, `end_frame` | frame index at 30 fps |

All times are **relative to the `vial_fill` video 5** (t = 0 at its first frame).

**`video5_frame_labels.csv`** — the same labels mapped onto the **sampled `vial_fill` images** of
video 5 (one row per frame): `filename, timestamp, video_s, in_fill, vial, recipe_id, type,
t100_ml, t200_ml, t400_ml, total_ml, dispense_order, color_purpose`. `in_fill=1` when the frame falls
inside a vial's dispense window (tagged with that vial/recipe); `in_fill=0` = `between_fills` (idle
gap between vials, no vial being dosed).

---

## 5. Image index & timestamps

Image filenames are `{camera}_{YYYYMMDD}_{HHMMSS}_{microseconds}.jpg` — the capture time is in the
name. Each camera's `image_index.csv` parses this into `filename, timestamp, video_id`, where
`video_id` is `1`–`5` (or `unassigned`). Use the timestamp to align the three cameras within a video ID.

*Note:* the raw capture's `capture_metadata.csv` / `verdicts.csv` were stale (an earlier batch whose
filenames did not match these images) and were **dropped**; `image_index.csv` replaces them with an
accurate, regenerated index.

---

## 6. Summary

| Camera | Images | Videos (1–5) |
| --- | --- | --- |
| cap_seal | 1,181 | 5 |
| tank_level | 1,733 | 5 |
| vial_fill | 1,733 | 5 |
| **Total** | **4,647** | **15** |

- **Frames per video** (tank_level & vial_fill): V1 558 · V2 78 · V3 95 · V4 157 · V5 845.
  cap_seal matches for V2/V3/V4/V5 but has sparse V1 coverage (5 frames).
- **Labels:** video 5, vial_fill only — **30 vials** across 10 recipes; **845** sampled frames
  (**509** inside a fill, 336 between fills).
- **Unlabeled** (for you to label): all of cap_seal and tank_level; and vial_fill videos 1, 2, 3, 4.

Everything is 640×480. Videos are H.264 MP4 (30 fps); images are JPEG.

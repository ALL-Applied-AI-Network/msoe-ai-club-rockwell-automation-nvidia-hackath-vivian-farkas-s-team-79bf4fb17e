import argparse
import csv
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = ROOT / "data" / "csi_vial_fill" / "video_5"
VIDEO_PATH = VIDEO_DIR / "video" / "vial_fill_video_5.mp4"
RECIPE_PATH = VIDEO_DIR / "labels" / "source" / "video5_vial_recipes.csv"
OUTPUT_DIR = VIDEO_DIR / "analysis"

COLLAR_ROI = (255, 190, 390, 255)
COLOR_ROI = (278, 275, 350, 425)
LOW_BLACK_FRACTION = 0.04
RETURN_BLACK_FRACTION = 0.10


def read_recipes(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as source:
        recipes = list(csv.DictReader(source))
    if len(recipes) != 30 or [int(row["vial"]) for row in recipes] != list(range(1, 31)):
        raise ValueError(f"Expected 30 recipe rows for vials 1-30 in {path}")
    return recipes


def scan_collar(video_path: Path) -> tuple[np.ndarray, float, int]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise OSError(f"Could not open source video: {video_path}")

    fps = capture.get(cv2.CAP_PROP_FPS)
    declared_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    x0, y0, x1, y1 = COLLAR_ROI
    occupancy: list[float] = []
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            gray = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
            occupancy.append(float(np.mean(gray < 60)))
    finally:
        capture.release()

    if not occupancy or fps <= 0:
        raise ValueError(f"Video has no readable frames or valid FPS: {video_path}")
    if declared_frames and abs(declared_frames - len(occupancy)) > 1:
        raise ValueError(
            f"Decoded {len(occupancy)} frames, but video metadata reports {declared_frames}"
        )
    return np.asarray(occupancy), fps, len(occupancy)


def low_occupancy_runs(occupancy: np.ndarray) -> list[tuple[int, int]]:
    low = occupancy < LOW_BLACK_FRACTION
    starts = np.flatnonzero(low & np.r_[True, ~low[:-1]])
    ends = np.flatnonzero(low & np.r_[~low[1:], True])
    return list(zip(starts.tolist(), ends.tolist()))


def sustained_return(
    occupancy: np.ndarray, start: int, stop: int, fps: float
) -> int | None:
    high = occupancy > RETURN_BLACK_FRACTION
    for frame in range(start, min(stop, len(occupancy) - 2)):
        if high[frame] and high[frame + 1] and high[frame + 2]:
            return frame
    return None


def movement_onset(occupancy: np.ndarray, departure: int, fps: float) -> tuple[int, float]:
    baseline_start = max(0, departure - round(2.5 * fps))
    baseline_end = max(baseline_start + 1, departure - round(1.5 * fps))
    baseline = float(np.median(occupancy[baseline_start:baseline_end]))
    if baseline <= 0:
        raise ValueError(f"Invalid collar baseline before frame {departure}")

    search_start = max(0, departure - round(3 * fps))
    threshold = baseline * 0.90
    for frame in range(search_start, max(search_start, departure - 2)):
        if np.all(occupancy[frame : frame + 3] < threshold):
            return frame, baseline
    raise ValueError(f"Could not find sustained movement onset before frame {departure}")


def get_frame(capture: cv2.VideoCapture, frame_number: int) -> np.ndarray:
    capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ok, frame = capture.read()
    if not ok:
        raise OSError(f"Could not read video frame {frame_number}")
    return frame


def color_statistics(frame: np.ndarray) -> dict[str, float]:
    x0, y0, x1, y1 = COLOR_ROI
    roi = frame[y0:y1, x0:x1]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
    mask = (
        (hsv[:, :, 1] > 30)
        & (hsv[:, :, 2] > 25)
        & (hsv[:, :, 2] < 245)
    )
    if not np.any(mask):
        raise ValueError("Color ROI has no pixels passing the saturation/value mask")

    hsv_median = np.median(hsv[mask], axis=0)
    lab_median = np.median(lab[mask], axis=0)
    return {
        "color_mask_fraction": float(np.mean(mask)),
        "hue_median_opencv": float(hsv_median[0]),
        "saturation_median": float(hsv_median[1]),
        "value_median": float(hsv_median[2]),
        "lab_l_median_8bit": float(lab_median[0]),
        "lab_a_median_8bit": float(lab_median[1]),
        "lab_b_median_8bit": float(lab_median[2]),
    }


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detect video-5 vial transitions and compare clean-vial colors."
    )
    parser.add_argument("--video", type=Path, default=VIDEO_PATH)
    parser.add_argument("--recipes", type=Path, default=RECIPE_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    recipes = read_recipes(args.recipes)
    occupancy, fps, frame_count = scan_collar(args.video)
    runs = low_occupancy_runs(occupancy)
    if len(runs) != len(recipes):
        raise ValueError(
            f"Detected {len(runs)} collar-disappearance runs for "
            f"{len(recipes)} labeled vials; refusing positional label mapping."
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    frame_dir = args.output_dir / "stable_frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        raise OSError(f"Could not reopen source video: {args.video}")

    events: list[dict] = []
    colors: list[dict] = []
    try:
        for index, ((departure, low_end), recipe) in enumerate(zip(runs, recipes)):
            vial = int(recipe["vial"])
            position = (vial - 1) % 3 + 1
            onset, baseline = movement_onset(occupancy, departure, fps)
            sample_frame = max(0, onset - 1)
            frame = get_frame(capture, sample_frame)
            sample_path = frame_dir / f"vial_{vial:02d}_frame_{sample_frame:06d}.jpg"
            if not cv2.imwrite(
                str(sample_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95]
            ):
                raise OSError(f"Could not save sample frame: {sample_path}")

            next_arrival = (
                sustained_return(occupancy, low_end + 1, runs[index + 1][0], fps)
                if index + 1 < len(runs)
                else None
            )
            sample_time = sample_frame / fps
            event = {
                "vial": vial,
                "recipe_id": int(recipe["recipe_id"]),
                "position_in_recipe": position,
                "carryover_suspect": position == 1,
                "color_reference_eligible": position != 1,
                "observed_arrival_frame": (
                    0 if index == 0 else sustained_return(
                        occupancy, runs[index - 1][1] + 1, departure, fps
                    )
                ),
                "departure_signal_start_frame": departure,
                "departure_signal_end_frame": low_end,
                "movement_onset_frame": onset,
                "last_stable_sample_frame": sample_frame,
                "last_stable_sample_time_s": f"{sample_time:.3f}",
                "next_collar_return_frame": next_arrival,
                "recipe_label_start_s": recipe["start_s"],
                "recipe_label_end_s": recipe["end_s"],
                "collar_baseline_black_fraction": f"{baseline:.5f}",
                "sample_image": str(sample_path.relative_to(args.output_dir)),
            }
            events.append(event)

            color = {
                "vial": vial,
                "recipe_id": int(recipe["recipe_id"]),
                "position_in_recipe": position,
                "color_reference_eligible": position != 1,
                "sample_frame": sample_frame,
                "sample_time_s": f"{sample_time:.3f}",
                **color_statistics(frame),
            }
            colors.append(color)
    finally:
        capture.release()

    eligible = [row for row in colors if row["color_reference_eligible"]]
    recipe_ids = sorted({row["recipe_id"] for row in eligible})
    for row in eligible:
        test = np.array(
            [row["lab_l_median_8bit"], row["lab_a_median_8bit"], row["lab_b_median_8bit"]]
        )
        distances = []
        for recipe_id in recipe_ids:
            peers = [item for item in eligible if item["recipe_id"] == recipe_id and item["vial"] != row["vial"]]
            if not peers:
                raise ValueError(f"Cannot cross-validate recipe {recipe_id}: no peer vial")
            centroid = np.mean(
                [
                    [
                        peer["lab_l_median_8bit"],
                        peer["lab_a_median_8bit"],
                        peer["lab_b_median_8bit"],
                    ]
                    for peer in peers
                ],
                axis=0,
            )
            distances.append((float(np.linalg.norm(test - centroid)), recipe_id))
        distances.sort()
        row["loo_nearest_recipe_id"] = distances[0][1]
        row["loo_color_only_correct"] = row["loo_nearest_recipe_id"] == row["recipe_id"]
        row["loo_nearest_distance"] = f"{distances[0][0]:.2f}"
        row["loo_second_recipe_id"] = distances[1][1]
        row["loo_second_distance"] = f"{distances[1][0]:.2f}"

    summaries: list[dict] = []
    for recipe_id in recipe_ids:
        group = [row for row in eligible if row["recipe_id"] == recipe_id]
        lab = np.array(
            [
                [row["lab_l_median_8bit"], row["lab_a_median_8bit"], row["lab_b_median_8bit"]]
                for row in group
            ]
        )
        hsv = np.array(
            [
                [row["hue_median_opencv"], row["saturation_median"], row["value_median"]]
                for row in group
            ]
        )
        correct = sum(row["loo_color_only_correct"] for row in group)
        summaries.append(
            {
                "recipe_id": recipe_id,
                "clean_candidate_vials": ";".join(str(row["vial"]) for row in group),
                "lab_l_median_8bit": f"{np.median(lab[:, 0]):.1f}",
                "lab_a_median_8bit": f"{np.median(lab[:, 1]):.1f}",
                "lab_b_median_8bit": f"{np.median(lab[:, 2]):.1f}",
                "hue_median_opencv": f"{np.median(hsv[:, 0]):.1f}",
                "saturation_median": f"{np.median(hsv[:, 1]):.1f}",
                "value_median": f"{np.median(hsv[:, 2]):.1f}",
                "within_recipe_lab_distance": f"{np.linalg.norm(lab[0] - lab[1]):.2f}",
                "loo_color_only_correct": f"{correct}/{len(group)}",
            }
        )

    write_csv(
        args.output_dir / "collar_detected_vials.csv",
        events,
        list(events[0]),
    )
    write_csv(
        args.output_dir / "vial_color_measurements.csv",
        colors,
        list(colors[0])
        + [
            "loo_nearest_recipe_id",
            "loo_color_only_correct",
            "loo_nearest_distance",
            "loo_second_recipe_id",
            "loo_second_distance",
        ],
    )
    write_csv(
        args.output_dir / "recipe_color_summary.csv",
        summaries,
        list(summaries[0]),
    )

    correct_count = sum(row["loo_color_only_correct"] for row in eligible)
    errors = [
        f"vial {row['vial']} (recipe {row['recipe_id']} -> {row['loo_nearest_recipe_id']})"
        for row in eligible
        if not row["loo_color_only_correct"]
    ]
    report = [
        "# Video 5 color-only assessment",
        "",
        f"- Source video: `{args.video}` ({frame_count} frames at {fps:g} fps).",
        f"- Black-collar signal detector: {len(runs)} disappearance runs, mapped in sequence to the 30 source recipe rows.",
        "- Detection settings: grayscale `<60` fraction in ROI x=255:390, y=190:255; disappearance below 0.04.",
        "- Each color sample is the frame immediately before a sustained 10% collar-signal drop, using a preceding stable baseline.",
        "- Color measurement: median masked HSV and OpenCV 8-bit Lab values in ROI x=278:350, y=275:425; this is image-derived, not calibrated physical color.",
        "- The first vial in each 3-vial recipe group is retained for timing but excluded from clean color references.",
        f"- Exploratory leave-one-vial-out nearest-centroid check: {correct_count}/{len(eligible)} clean candidate frames assigned to the correct recipe.",
        f"- Misclassifications: {', '.join(errors) if errors else 'none'}.",
        "",
        "## Interpretation",
        "",
        "Color is useful for coarse recipe grouping, but these measurements do not support reliable unique identification of all 10 recipes. "
        "The leave-one-out check has only two candidate vials per recipe, uses one remaining vial as the comparison reference, "
        "and is sensitive to lighting, reflections, glass, liquid level, and the fixed ROI. It is exploratory, not a validated classifier.",
        "",
        "Recipes 5 and 8 have the same T100:T200:T400 proportions (10:10:10 mL versus 20:20:20 mL) and the same dispense order. "
        "Their mixed-liquid color is therefore expected to be indistinguishable by color alone; their total volume/fill height is a useful additional cue. "
        "The observed candidate samples also show overlap among recipes 5, 8, and 9, and between recipes 6 and 12.",
        "",
        "For robust recipe identification, combine settled liquid color with fill height and the ordered nozzle-stream colors. "
        "The source recipe labels remain authoritative for recipe IDs; this image analysis does not rewrite them.",
    ]
    (args.output_dir / "COLOR_ASSESSMENT.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    print(
        f"Analyzed {len(runs)} vial events; color-only leave-one-out matched "
        f"{correct_count}/{len(eligible)} clean candidate frames."
    )
    print(f"Outputs: {args.output_dir}")


if __name__ == "__main__":
    main()

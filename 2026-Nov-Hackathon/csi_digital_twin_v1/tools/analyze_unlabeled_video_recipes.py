import argparse
import csv
from pathlib import Path

import cv2
import numpy as np

import analyze_nozzle_streams as nozzle
import analyze_video5_colors as video5


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "csi_vial_fill"
REFERENCE_PATH = (
    DATA_DIR
    / "video_5"
    / "analysis"
    / "vial_color_measurements.csv"
)
OUTPUT_DIR = DATA_DIR / "unlabeled_video_analysis"
EXPECTED_VIALS = {1: 19, 2: 3, 3: 6, 4: 6}

VISIBLE_LEVEL_NOTES = {
    1: {},
    2: {},
    3: {
        4: "Clear/very low liquid appears visible near the vial bottom.",
        5: "Clear/very low liquid appears visible near the vial bottom.",
        6: "Colored liquid appears limited to the lower vial; level estimate is rough.",
    },
    4: {},
}

VIAL_FIELDS = [
    "video_id",
    "vial",
    "video_path",
    "departure_frame",
    "last_stable_sample_frame",
    "last_stable_sample_time_s",
    "final_color_hue_median_opencv",
    "final_color_saturation_median",
    "final_color_value_median",
    "final_color_lab_l_median_8bit",
    "final_color_lab_a_median_8bit",
    "final_color_lab_b_median_8bit",
    "nearest_color_recipe_id",
    "nearest_color_distance",
    "second_color_recipe_id",
    "second_color_distance",
    "third_color_recipe_id",
    "third_color_distance",
    "stream_color_sequence_candidate",
    "stream_phase_count",
    "liquid_level_visibility",
    "liquid_level_note",
    "recipe_id_status",
]

PHASE_FIELDS = [
    "video_id",
    "vial",
    "phase_index",
    "observed_color_nearest",
    "start_frame",
    "end_frame",
    "start_time_s",
    "end_time_s",
    "active_flow_duration_s",
    "median_hue_opencv",
    "median_saturation",
    "color_class_confidence",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


def color_reference_centroids(path: Path) -> dict[int, np.ndarray]:
    references = read_csv(path)
    eligible = [
        row
        for row in references
        if row["color_reference_eligible"].lower() == "true"
    ]
    centroids = {}
    for recipe_id in range(5, 15):
        samples = [
            [
                float(row["lab_l_median_8bit"]),
                float(row["lab_a_median_8bit"]),
                float(row["lab_b_median_8bit"]),
            ]
            for row in eligible
            if int(row["recipe_id"]) == recipe_id
        ]
        if len(samples) != 2:
            raise ValueError(
                f"Expected two clean Video 5 color samples for recipe {recipe_id}"
            )
        centroids[recipe_id] = np.mean(samples, axis=0)
    return centroids


def prepare_departures(
    video_path: Path, video_id: int
) -> tuple[np.ndarray, float, list[tuple[int, int]], str]:
    occupancy, fps, frame_count = video5.scan_collar(video_path)
    departures = video5.low_occupancy_runs(occupancy)
    expected = EXPECTED_VIALS[video_id]
    correction = "none"
    if (
        len(departures) == expected + 1
        and departures[0][0] == 0
    ):
        departures = departures[1:]
        correction = "ignored leading low-collar run beginning at frame 0"
    if len(departures) != expected:
        raise ValueError(
            f"Video {video_id}: found {len(departures)} collar events after "
            f"allowed startup correction; expected {expected}. Refusing to "
            "assign vial numbers by sequence."
        )
    if any(end >= frame_count for _, end in departures):
        raise ValueError(f"Video {video_id}: collar event exceeds decoded frames")
    return occupancy, fps, departures, correction


def build_windows(
    departures: list[tuple[int, int]],
    video_id: int,
) -> list[dict]:
    windows = []
    first_frame = 0
    for vial, (departure_start, departure_end) in enumerate(departures, start=1):
        last_frame = departure_start - 1
        if last_frame < first_frame:
            raise ValueError(
                f"Video {video_id}: empty vial window for inferred vial {vial}"
            )
        windows.append(
            {
                "first_frame": first_frame,
                "last_frame": last_frame,
                "vial": vial,
                "recipe_id": "",
                "carryover_suspect": "",
                "dispense_order": "",
                "label_start_s": "",
                "label_end_s": "",
                "departure_frame": departure_start,
            }
        )
        first_frame = departure_end + 1
    return windows


def classify_color(
    measured: dict[str, float],
    centroids: dict[int, np.ndarray],
) -> list[tuple[float, int]]:
    sample = np.array(
        [
            measured["lab_l_median_8bit"],
            measured["lab_a_median_8bit"],
            measured["lab_b_median_8bit"],
        ],
        dtype=np.float64,
    )
    distances = [
        (float(np.linalg.norm(sample - centroid)), recipe_id)
        for recipe_id, centroid in centroids.items()
    ]
    return sorted(distances)


def analyze_video(
    video_path: Path,
    video_id: int,
    centroids: dict[int, np.ndarray],
) -> tuple[list[dict[str, str]], list[dict[str, str]], str, int, float]:
    occupancy, fps, departures, correction = prepare_departures(video_path, video_id)
    windows = build_windows(departures, video_id)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise OSError(f"Could not open video: {video_path}")

    vial_rows = []
    phase_rows = []
    try:
        for window in windows:
            onset, _baseline = video5.movement_onset(
                occupancy, window["departure_frame"], fps
            )
            sample_frame = max(window["first_frame"], onset - 1)
            sample = video5.get_frame(capture, sample_frame)
            measured = video5.color_statistics(sample)
            distances = classify_color(measured, centroids)
            _frame_rows, phases, _pauses = nozzle.analyze_window(
                capture, window, fps, video_id
            )

            colors = [phase["observed_color_nearest"] for phase in phases]
            grouped_colors = []
            for color in colors:
                if not grouped_colors or grouped_colors[-1] != color:
                    grouped_colors.append(color)

            note = VISIBLE_LEVEL_NOTES[video_id].get(window["vial"], "")
            level_visibility = (
                "visible_low_candidate"
                if note
                else "holder_obscured_or_uncertain"
            )
            ordered_distances = distances[:3]
            vial_rows.append(
                {
                    "video_id": str(video_id),
                    "vial": str(window["vial"]),
                    "video_path": str(video_path),
                    "departure_frame": str(window["departure_frame"]),
                    "last_stable_sample_frame": str(sample_frame),
                    "last_stable_sample_time_s": f"{sample_frame / fps:.3f}",
                    "final_color_hue_median_opencv": f'{measured["hue_median_opencv"]:.1f}',
                    "final_color_saturation_median": f'{measured["saturation_median"]:.1f}',
                    "final_color_value_median": f'{measured["value_median"]:.1f}',
                    "final_color_lab_l_median_8bit": f'{measured["lab_l_median_8bit"]:.1f}',
                    "final_color_lab_a_median_8bit": f'{measured["lab_a_median_8bit"]:.1f}',
                    "final_color_lab_b_median_8bit": f'{measured["lab_b_median_8bit"]:.1f}',
                    "nearest_color_recipe_id": str(ordered_distances[0][1]),
                    "nearest_color_distance": f"{ordered_distances[0][0]:.2f}",
                    "second_color_recipe_id": str(ordered_distances[1][1]),
                    "second_color_distance": f"{ordered_distances[1][0]:.2f}",
                    "third_color_recipe_id": str(ordered_distances[2][1]),
                    "third_color_distance": f"{ordered_distances[2][0]:.2f}",
                    "stream_color_sequence_candidate": ">".join(grouped_colors)
                    if grouped_colors
                    else "none_detected",
                    "stream_phase_count": str(len(phases)),
                    "liquid_level_visibility": level_visibility,
                    "liquid_level_note": note
                    or "Meniscus is not confidently measurable from this review frame.",
                    "recipe_id_status": "unlabeled exploratory color-nearest candidates",
                }
            )

            for phase_index, phase in enumerate(phases, start=1):
                phase_rows.append(
                    {
                        "video_id": str(video_id),
                        "vial": str(window["vial"]),
                        "phase_index": str(phase_index),
                        "observed_color_nearest": phase["observed_color_nearest"],
                        "start_frame": phase["start_frame"],
                        "end_frame": phase["end_frame"],
                        "start_time_s": phase["start_time_s"],
                        "end_time_s": phase["end_time_s"],
                        "active_flow_duration_s": phase["active_flow_duration_s"],
                        "median_hue_opencv": phase["median_hue_opencv"],
                        "median_saturation": phase["median_saturation"],
                        "color_class_confidence": (
                            "heuristic; review required"
                        ),
                    }
                )
    finally:
        capture.release()
    frame_count = int(occupancy.size)
    return vial_rows, phase_rows, correction, frame_count, fps


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def write_report(
    path: Path,
    all_rows: list[dict[str, str]],
    corrections: dict[int, str],
    metadata: dict[int, tuple[int, float]],
) -> None:
    lines = [
        "# Candidate recipe patterns in unlabeled Videos 1-4",
        "",
        "Videos 1-4 do not have recipe labels. Candidate IDs below are exploratory "
        "similarities to Video 5's clean final-vial color references, not verified "
        "recipe assignments. The color-only cross-validation on Video 5 matched "
        "16/20 clean samples, and the stream detector also produces false or "
        "missing phases.",
        "",
        "## Processing and evidence limits",
        "",
        "- Vial order is inferred from black-collar disappearance events and checked "
        "against the source-documented vial counts: 19, 3, 6, and 6.",
        "- Video 2 had four low-collar runs; the first began at frame 0 and was "
        "treated as a likely empty-startup signal, leaving three vial departures.",
        "- Final-vial color is compared in image Lab space with two clean Video 5 "
        "samples per recipe. The nearest recipes are ranked only; lighting, mixing, "
        "glass, sample timing, and level affect the color.",
        "- Nozzle phases are heuristic appearance labels and are not confirmed tank "
        "dispense phases. They are reported per vial in `stream_phases.csv`.",
        "- Meniscus positions are hidden or uncertain in most review frames. Video "
        "3 vials 4-6 visibly appear to have liquid only near the lower vial, but "
        "those rough observations are not calibrated volumes.",
        "- First vial/recipe transitions cannot be located reliably in these "
        "unlabeled clips, so no vials were excluded as carryover-suspect.",
        "",
        "## Per-video patterns",
        "",
    ]
    visual_groups = {
        1: (
            "Vials 1-5 are consistently vivid blue; their nearest-color result is "
            "Recipe 7 for all five. Vials 7-10 and 16-19 are orange-dominant; "
            "their nearest-color results alternate between Recipes 6 and 12, "
            "which are plausible orange-rich candidates. The remaining dark "
            "green/teal vials have nearest-color results among Recipes 5, 8, 9, "
            "10, and 11. These suggest Recipe 7, one or more orange-rich recipes "
            "(6/12), and one or more dark mixture recipes, but do not establish "
            "exact IDs or group boundaries."
        ),
        2: (
            "Three vial departures are supported after ignoring the frame-0 "
            "run as a likely startup artifact. All three are closest in final color to Recipe 11; "
            "vials 2 and 3 have a notably dark blue-green appearance and "
            "orange/blue stream candidates. Recipe 11 is the leading hypothesis, "
            "but an unlabeled first vial could include carryover, and the stream "
            "classifier is not reliable enough to confirm the assignment."
        ),
        3: (
            "The six vials do not form a reliable match to the known recipes. "
            "The color-only nearest result is Recipe 10 for vial 1 and Recipe 14 "
            "for vials 2-6, but the latter frames look pale/clear and vials 4-6 "
            "appear to contain only a small amount near the bottom. Those "
            "nearest-color results are likely confounded by low color signal, "
            "partial fills, or a process state unlike the Video 5 reference. "
            "Recipe 14 is only a weak possibility, not an assignment."
        ),
        4: (
            "Two repeated visual families are apparent: vials 1-3 are vivid blue; "
            "their nearest-color results are Recipe 11 for vial 1 (Recipe 7 is "
            "second) and Recipe 7 for vials 2-3. Vials 4-6 are consistently dark "
            "green/teal; vials 4-5 are nearest Recipe 11 and vial 6 is nearest "
            "Recipe 9, with Recipe 11 a close second. The first group is most "
            "consistent with Recipe 7; the second is a Recipe 9/11 candidate. "
            "These two recipes have similar mixed-color references, and the "
            "hidden level prevents separating their 80 mL versus 70 mL totals. "
            "This is the clearest two-family candidate in the four clips, but it "
            "is not confirmed."
        ),
    }
    for video_id in range(1, 5):
        vial_count, fps = metadata[video_id]
        correction = corrections[video_id]
        note = (
            f" Startup adjustment: {correction}."
            if correction != "none"
            else ""
        )
        lines.extend(
            [
                f"### Video {video_id}",
                "",
                f"- Source vial count: {vial_count}; detected and analyzed: "
                f"{sum(int(row['video_id']) == video_id for row in all_rows)}; "
                f"{fps:g} fps.{note}",
                f"- Candidate interpretation: {visual_groups[video_id]}",
                "",
            ]
        )

    lines.extend(
        [
            "## Overall conclusion",
            "",
            "Video 4 provides the clearest candidate pair: a blue-dominant group "
            "consistent with Recipe 7, followed by a dark blue-green/orange-mix "
            "group most consistent with Recipe 9 or 11. Video 2 also points toward "
            "Recipe 11, though this needs confirmation. Video 1 appears to include "
            "a Recipe 7-like blue family, orange-rich candidates (Recipes 6/12), "
            "and dark mixed-color candidates (Recipes 5/8/9/10/11); exact IDs are "
            "unresolved. Video 3 cannot be matched reliably; Recipe 14 is a weak "
            "color-only possibility, but the apparent low/clear fills conflict "
            "with that interpretation.",
            "",
            "No absolute recipe IDs can be confirmed for Videos 1-4 without "
            "labels or additional independent evidence (for example tank levels, "
            "batch scheduler records, or manually verified stream/meniscus "
            "observations). Use `unlabeled_video_cues.csv` for nearest-color "
            "rankings per vial and `stream_phases.csv` for the raw phase candidates.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare unlabeled Videos 1-4 against Video 5 recipe cues."
    )
    for video_id in range(1, 5):
        parser.add_argument(
            f"--video{video_id}",
            type=Path,
            default=(
                DATA_DIR
                / f"video_{video_id}"
                / "video"
                / f"vial_fill_video_{video_id}.mp4"
            ),
        )
    parser.add_argument("--references", type=Path, default=REFERENCE_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    centroids = color_reference_centroids(args.references)
    all_vials = []
    all_phases = []
    corrections = {}
    metadata = {}
    for video_id in range(1, 5):
        video_path = getattr(args, f"video{video_id}")
        vials, phases, correction, frame_count, fps = analyze_video(
            video_path, video_id, centroids
        )
        all_vials.extend(vials)
        all_phases.extend(phases)
        corrections[video_id] = correction
        metadata[video_id] = (len(vials), fps)
        print(
            f"Video {video_id}: analyzed {len(vials)} vials, "
            f"{frame_count} frames at {fps:g} fps; startup adjustment={correction}."
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "unlabeled_video_cues.csv", all_vials, VIAL_FIELDS)
    write_csv(args.output_dir / "stream_phases.csv", all_phases, PHASE_FIELDS)
    write_report(
        args.output_dir / "RECIPE_CANDIDATE_ASSESSMENT.md",
        all_vials,
        corrections,
        metadata,
    )
    print(f"Outputs: {args.output_dir}")


if __name__ == "__main__":
    main()

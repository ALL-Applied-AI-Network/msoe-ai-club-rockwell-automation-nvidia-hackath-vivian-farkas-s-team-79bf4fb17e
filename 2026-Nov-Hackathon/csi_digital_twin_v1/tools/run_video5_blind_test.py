import csv
import statistics
from pathlib import Path

import cv2

import analyze_colored_streams as stream
import analyze_video5_colors as color


ROOT = Path(__file__).resolve().parents[1]
VIDEO_PATH = ROOT / "data" / "csi_vial_fill" / "video_5" / "video" / "vial_fill_video_5.mp4"
LABEL_PATH = ROOT / "data" / "csi_vial_fill" / "video_5" / "labels" / "source" / "video5_vial_recipes.csv"
LEVEL_PATH = ROOT / "data" / "csi_vial_fill" / "video_5" / "analysis" / "meniscus" / "meniscus_measurements.csv"
OUTPUT_DIR = ROOT / "data" / "csi_vial_fill" / "video_5" / "analysis" / "blind_test"

FEATURE_FIELDS = [
    "vial",
    "sample_frame",
    "sample_time_s",
    "lab_l",
    "lab_a",
    "lab_b",
    "stream_sequence",
    "stream_phase_count",
    "level_status",
    "level_height_min_px",
    "level_height_max_px",
    "level_confidence",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def detected_vial_bounds(video_path: Path) -> tuple[list[dict[str, int]], float]:
    occupancy, fps, frame_count = color.scan_collar(video_path)
    departures = color.low_occupancy_runs(occupancy)
    if len(departures) != 30:
        raise ValueError(
            f"Label-blind collar detection found {len(departures)} departures; expected 30."
        )
    bounds = []
    for index, (departure, low_end) in enumerate(departures):
        if index == 0:
            arrival = 0
        else:
            previous_end = departures[index - 1][1]
            arrival = color.sustained_return(
                occupancy, previous_end + 1, departure, fps
            )
            if arrival is None:
                raise ValueError(
                    f"Could not detect vial {index + 1} arrival from collar signal."
                )
        onset, _baseline = color.movement_onset(occupancy, departure, fps)
        if arrival >= departure or onset <= arrival:
            raise ValueError(f"Invalid blind window for detected vial {index + 1}.")
        bounds.append(
            {
                "arrival": arrival,
                "departure": departure,
                "departure_end": low_end,
                "sample": max(arrival, onset - 1),
            }
        )
    if bounds[-1]["departure_end"] >= frame_count:
        raise ValueError("Last collar event exceeds decoded video frames.")
    return bounds, fps


def extract_blind_features() -> list[dict[str, str]]:
    bounds, fps = detected_vial_bounds(VIDEO_PATH)
    capture = cv2.VideoCapture(str(VIDEO_PATH))
    if not capture.isOpened():
        raise OSError(f"Could not open Video 5: {VIDEO_PATH}")
    rows = []
    try:
        for vial, bound in enumerate(bounds, start=1):
            sample = color.get_frame(capture, bound["sample"])
            measurements = color.color_statistics(sample)
            phases = []
            states = []
            capture.set(cv2.CAP_PROP_POS_FRAMES, bound["arrival"])
            for frame_number in range(bound["arrival"], bound["departure"]):
                ok, frame = capture.read()
                if not ok:
                    raise OSError(
                        f"Could not decode blind stream frame {frame_number}."
                    )
                states.append(stream.measure_colored_stream(frame)["observed_color_nearest"])
            smoothed = stream.smooth_short_uncolored_gaps(
                stream.majority_smooth(states)
            )
            phases = [
                (end - start + 1, phase_color)
                for start, end, phase_color in stream.collapse_runs(smoothed)
                if phase_color in ("orange", "blue")
                and end - start + 1 >= stream.MIN_PHASE_FRAMES
            ]
            sequence = []
            for _duration, phase_color in phases:
                if not sequence or sequence[-1] != phase_color:
                    sequence.append(phase_color)
            rows.append(
                {
                    "vial": str(vial),
                    "sample_frame": str(bound["sample"]),
                    "sample_time_s": f'{bound["sample"] / fps:.3f}',
                    "lab_l": f'{measurements["lab_l_median_8bit"]:.3f}',
                    "lab_a": f'{measurements["lab_a_median_8bit"]:.3f}',
                    "lab_b": f'{measurements["lab_b_median_8bit"]:.3f}',
                    "stream_sequence": ">".join(sequence),
                    "stream_phase_count": str(len(sequence)),
                }
            )
    finally:
        capture.release()

    levels = {int(row["vial"]): row for row in read_csv(LEVEL_PATH)}
    for row in rows:
        vial = int(row["vial"])
        level = levels[vial]
        if int(level["sample_frame"]) != int(row["sample_frame"]):
            raise ValueError(
                f"Manual level review sample frame mismatch for vial {vial}: "
                f'{level["sample_frame"]} vs {row["sample_frame"]}.'
            )
        row.update(
            {
                "level_status": level["measurement_status"],
                "level_height_min_px": level["liquid_height_min_px"],
                "level_height_max_px": level["liquid_height_max_px"],
                "level_confidence": level["confidence"],
            }
        )
    return rows


def sequence_edit_distance(first: tuple[str, ...], second: tuple[str, ...]) -> int:
    previous = list(range(len(second) + 1))
    for row_index, first_item in enumerate(first, start=1):
        current = [row_index]
        for column_index, second_item in enumerate(second, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column_index] + 1,
                    previous[column_index - 1] + (first_item != second_item),
                )
            )
        previous = current
    return previous[-1]


def interval_gap(first: tuple[float, float], second: tuple[float, float]) -> float:
    return max(0.0, second[0] - first[1], first[0] - second[1])


def ranked_ids(scores: dict[int, float]) -> list[int]:
    return [
        recipe_id
        for recipe_id, _score in sorted(scores.items(), key=lambda item: (item[1], item[0]))
    ]


def average_ranks(ids: list[int]) -> dict[int, float]:
    return {recipe_id: float(index) for index, recipe_id in enumerate(ids)}


def cross_validate(
    features: list[dict[str, str]],
    labels: list[dict[str, str]],
) -> tuple[list[dict[str, str]], dict[str, dict[str, int]]]:
    label_by_vial = {int(row["vial"]): row for row in labels}
    if set(label_by_vial) != set(range(1, 31)):
        raise ValueError("Scoring labels must contain Video 5 vials 1–30.")
    feature_by_vial = {int(row["vial"]): row for row in features}

    predictions = []
    metrics: dict[str, dict[str, int]] = {}
    cue_names = ("color", "stream", "level", "combined")
    for cue_name in cue_names:
        metrics[cue_name] = {
            "clean_correct": 0,
            "clean_top2": 0,
            "clean_covered": 0,
            "all_correct": 0,
            "all_covered": 0,
        }

    for test_vial in range(1, 31):
        test = feature_by_vial[test_vial]
        train_vials = [
            vial
            for vial in range(1, 31)
            if vial != test_vial
            and (vial - 1) % 3 != 0
        ]
        train_by_recipe: dict[int, list[dict[str, str]]] = {}
        for vial in train_vials:
            recipe_id = int(label_by_vial[vial]["recipe_id"])
            train_by_recipe.setdefault(recipe_id, []).append(feature_by_vial[vial])
        candidate_ids = sorted(train_by_recipe)
        if len(candidate_ids) != 10:
            raise ValueError(
                f"Fold for vial {test_vial} has {len(candidate_ids)} recipe classes."
            )

        test_lab = tuple(float(test[key]) for key in ("lab_l", "lab_a", "lab_b"))
        color_scores = {}
        for recipe_id, reference_rows in train_by_recipe.items():
            centroid = tuple(
                statistics.median(float(row[key]) for row in reference_rows)
                for key in ("lab_l", "lab_a", "lab_b")
            )
            color_scores[recipe_id] = sum(
                (observed - expected) ** 2
                for observed, expected in zip(test_lab, centroid)
            ) ** 0.5

        observed_sequence = tuple(
            item for item in test["stream_sequence"].split(">") if item
        )
        stream_scores: dict[int, float] = {}
        if observed_sequence:
            for recipe_id, reference_rows in train_by_recipe.items():
                references = [
                    tuple(item for item in row["stream_sequence"].split(">") if item)
                    for row in reference_rows
                ]
                references = [reference for reference in references if reference]
                if references:
                    stream_scores[recipe_id] = min(
                        sequence_edit_distance(observed_sequence, reference)
                        / max(len(observed_sequence), len(reference), 1)
                        for reference in references
                    )

        test_has_level = test["level_status"] == "visible"
        level_scores: dict[int, float] = {}
        if test_has_level:
            test_interval = (
                float(test["level_height_min_px"]),
                float(test["level_height_max_px"]),
            )
            for recipe_id, reference_rows in train_by_recipe.items():
                reference_intervals = [
                    (
                        float(row["level_height_min_px"]),
                        float(row["level_height_max_px"]),
                    )
                    for row in reference_rows
                    if row["level_status"] == "visible"
                ]
                if reference_intervals:
                    level_scores[recipe_id] = min(
                        interval_gap(test_interval, reference)
                        for reference in reference_intervals
                    )

        rankings = {
            "color": ranked_ids(color_scores),
            "stream": ranked_ids(stream_scores),
            "level": ranked_ids(level_scores),
        }
        active_cues = [
            average_ranks(rankings[name])
            for name in ("color", "stream", "level")
            if rankings[name]
        ]
        combined_scores = {}
        for recipe_id in candidate_ids:
            combined_scores[recipe_id] = statistics.mean(
                ranks.get(recipe_id, float(len(ranks)))
                for ranks in active_cues
            )
        rankings["combined"] = ranked_ids(combined_scores)

        actual = label_by_vial[test_vial]
        true_recipe = int(actual["recipe_id"])
        # Exclude first vial of each scheduled three-vial block as a
        # prespecified transition/carryover precaution, without reading labels.
        is_clean = (test_vial - 1) % 3 != 0
        result = {
            "vial": str(test_vial),
            "carryover_suspect": str(not is_clean).lower(),
            "true_recipe_id": str(true_recipe),
            "color_prediction": "",
            "color_top2": "",
            "stream_prediction": "",
            "stream_top2": "",
            "level_prediction": "",
            "level_top2": "",
            "combined_prediction": "",
            "combined_top2": "",
            "color_ranked_candidates": ">".join(map(str, rankings["color"])),
            "stream_ranked_candidates": ">".join(map(str, rankings["stream"])),
            "level_ranked_candidates": ">".join(map(str, rankings["level"])),
            "combined_ranked_candidates": ">".join(map(str, rankings["combined"])),
            "stream_sequence_detected": test["stream_sequence"],
            "level_status": test["level_status"],
            "scored_in_clean_subset": str(is_clean).lower(),
        }
        for name in cue_names:
            ranking = rankings[name]
            if ranking:
                result[f"{name}_prediction"] = str(ranking[0])
                result[f"{name}_top2"] = ">".join(map(str, ranking[:2]))
                metrics[name]["all_covered"] += 1
                if ranking[0] == true_recipe:
                    metrics[name]["all_correct"] += 1
                if is_clean:
                    metrics[name]["clean_covered"] += 1
                    if ranking[0] == true_recipe:
                        metrics[name]["clean_correct"] += 1
                    if true_recipe in ranking[:2]:
                        metrics[name]["clean_top2"] += 1
        predictions.append(result)
    return predictions, metrics


def write_report(
    path: Path,
    features: list[dict[str, str]],
    predictions: list[dict[str, str]],
    metrics: dict[str, dict[str, int]],
) -> None:
    clean_count = sum(row["scored_in_clean_subset"] == "true" for row in predictions)
    visible_clean = sum(
        row["scored_in_clean_subset"] == "true" and row["level_status"] == "visible"
        for row in predictions
    )
    lines = [
        "# Video 5 label-blind cue test",
        "",
        "## Protocol",
        "",
        "- Vial departures and stable-color sample frames were detected from the video collar signal; no recipe labels or recipe time windows were used to extract vial features.",
        "- Stream-color phase sequences were re-extracted from each detected collar-return-to-departure interval, independently of recipe labels.",
        "- Manual meniscus ranges were joined by vial number after cue extraction. The ranges are image-pixel annotations, not calibrated volumes.",
        "- The first vial in each fixed three-vial block was prespecified as transition/carryover-suspect and excluded from training; this schedule rule uses vial position, not recipe IDs. The held-out recipe label was used only after predictions were frozen, for scoring.",
        "- The stream classifier learns observed phase-sequence examples from training vials only. The level cue can only rank recipe classes for which training menisci are visible.",
        "- Combined ranking is an equal-weight mean of the available cue rank positions (color, stream, level); it is an exploratory fusion rule, not a trained or calibrated probability.",
        "",
        "## Results",
        "",
        f"- Blind feature extraction produced {len(features)} vial records. Primary scoring excludes the 10 carryover-suspect first-in-group vials, leaving {clean_count} clean repeat vials ({clean_count // 10} per recipe).",
        f"- Only {visible_clean} of these clean repeat vials have a manually visible meniscus; all other liquid-level ranges overlap the same holder-obscured interval.",
        "",
        "| Cue/ranker | Clean top-1 | Clean top-2 | Clean coverage | All 30 top-1 |",
        "|---|---:|---:|---:|---:|",
    ]
    for name in ("color", "stream", "level", "combined"):
        row = metrics[name]
        clean_top1 = (
            f'{row["clean_correct"]}/{row["clean_covered"]}'
            if row["clean_covered"]
            else "no predictions"
        )
        clean_top2 = (
            f'{row["clean_top2"]}/{row["clean_covered"]}'
            if row["clean_covered"]
            else "no predictions"
        )
        all_top1 = (
            f'{row["all_correct"]}/{row["all_covered"]}'
            if row["all_covered"]
            else "no predictions"
        )
        coverage = f'{row["clean_covered"]}/{clean_count}'
        lines.append(
            f"| {name.title()} | {clean_top1} | {clean_top2} | {coverage} | {all_top1} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation and limitations",
            "",
            "- This is a within-one-video, leave-one-vial-out experiment. It does not test another recording day, lighting setup, camera, or production run.",
            "- Each clean recipe class has only two reference examples. A clean held-out vial has only one same-recipe clean training example.",
            "- The stream extraction uses detected collar events rather than label-defined recipe intervals. Arrival detection can still include cart movement or imperfect window boundaries, and the stream classifier is noisy.",
            "- The level evidence is largely uninformative because the holder obscures 16 of the 20 clean levels. The visible level measurements are manual image-pixel ranges, with no pixel-to-volume calibration.",
            "- The combined ranker is a fixed exploratory comparison, not a validated classifier. Its score is not a probability or confidence estimate.",
            "- Recipe IDs are supplied as the training catalog for candidate comparison; without labeled training examples or a recipe-to-visual-profile mapping, a fully unlabeled video can only be clustered, not assigned recipe IDs.",
            "",
            "See `blind_feature_extraction.csv` for cues without recipe IDs and `blind_test_scored_predictions.csv` for held-out predictions joined to labels after scoring.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features = extract_blind_features()
    write_csv(OUTPUT_DIR / "blind_feature_extraction.csv", features, FEATURE_FIELDS)

    # Recipe labels enter only after blind feature extraction is complete.
    labels = read_csv(LABEL_PATH)
    predictions, metrics = cross_validate(features, labels)
    prediction_fields = list(predictions[0])
    write_csv(
        OUTPUT_DIR / "blind_test_scored_predictions.csv",
        predictions,
        prediction_fields,
    )
    write_report(
        OUTPUT_DIR / "BLIND_TEST_REPORT.md",
        features,
        predictions,
        metrics,
    )
    print(f"Blind test outputs: {OUTPUT_DIR}")
    print(f"Extracted cues for {len(features)} vials without recipe labels.")
    print(f"Scored {sum(row['scored_in_clean_subset'] == 'true' for row in predictions)} clean repeats.")
    for name in ("color", "stream", "level", "combined"):
        values = metrics[name]
        print(
            f"{name}: clean top-1 {values['clean_correct']}/{values['clean_covered']}, "
            f"top-2 {values['clean_top2']}/{values['clean_covered']}, "
            f"coverage {values['clean_covered']}/20; "
            f"all-vial top-1 {values['all_correct']}/{values['all_covered']}"
        )


if __name__ == "__main__":
    main()

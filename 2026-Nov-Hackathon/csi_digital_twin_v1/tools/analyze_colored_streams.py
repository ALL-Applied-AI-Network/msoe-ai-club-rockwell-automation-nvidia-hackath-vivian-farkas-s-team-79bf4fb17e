import argparse
import csv
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = ROOT / "data" / "csi_vial_fill" / "video_5"
VIDEO_PATH = VIDEO_DIR / "video" / "vial_fill_video_5.mp4"
RECIPE_PATH = VIDEO_DIR / "labels" / "source" / "video5_vial_recipes.csv"
OUTPUT_DIR = VIDEO_DIR / "analysis" / "colored_streams"

NOZZLE_X = (298, 312)
NOZZLE_Y = (95, 175)
BACKGROUND_LEFT_X = (285, 297)
BACKGROUND_RIGHT_X = (313, 325)
MIN_COLOR_ROWS = 8
MIN_CONTIGUOUS_COLOR_ROWS = 8
SMOOTH_RADIUS = 4
MIN_PHASE_FRAMES = 12
SHORT_UNCLASSIFIED_GAP_FRAMES = 6
ORANGE_HUE_CENTER = 30.0
BLUE_HUE_CENTER = 87.0
MIXED_HUE_SPLIT = (ORANGE_HUE_CENTER + BLUE_HUE_CENTER) / 2
MIN_SATURATION = 20
MIN_VALUE = 35


def read_recipes(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as source:
        recipes = list(csv.DictReader(source))
    if len(recipes) != 30 or [int(row["vial"]) for row in recipes] != list(range(1, 31)):
        raise ValueError(f"Expected Video 5 recipe rows for vials 1-30 in {path}")
    return recipes


def color_row_runs(mask: np.ndarray) -> tuple[int, int]:
    count = int(mask.sum())
    padded = np.r_[False, mask, False].astype(np.int8)
    edges = np.diff(padded)
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1)
    longest = max((int(end - start) for start, end in zip(starts, ends)), default=0)
    return count, longest


def nearest_color(hue: float) -> str:
    orange_distance = min(
        abs(hue - ORANGE_HUE_CENTER),
        180 - abs(hue - ORANGE_HUE_CENTER),
    )
    blue_distance = min(
        abs(hue - BLUE_HUE_CENTER),
        180 - abs(hue - BLUE_HUE_CENTER),
    )
    return "orange" if orange_distance <= blue_distance else "blue"


def measure_colored_stream(frame: np.ndarray) -> dict:
    x0, x1 = NOZZLE_X
    y0, y1 = NOZZLE_Y
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB).astype(np.float32)

    center_hsv = hsv[y0:y1, x0:x1]
    center_lab = lab[y0:y1, x0:x1]
    left = np.median(lab[y0:y1, BACKGROUND_LEFT_X[0] : BACKGROUND_LEFT_X[1]], axis=1)
    right = np.median(lab[y0:y1, BACKGROUND_RIGHT_X[0] : BACKGROUND_RIGHT_X[1]], axis=1)
    background = (left + right) / 2
    delta = np.linalg.norm(center_lab - background[:, np.newaxis, :], axis=2)

    selected_hues = []
    selected_saturations = []
    selected_values = []
    orange_rows = np.zeros(y1 - y0, dtype=bool)
    blue_rows = np.zeros(y1 - y0, dtype=bool)

    for row in range(y1 - y0):
        row_hsv = center_hsv[row]
        hue = row_hsv[:, 0].astype(np.float32)
        saturation = row_hsv[:, 1].astype(np.float32)
        value = row_hsv[:, 2].astype(np.float32)
        eligible = (
            (saturation >= MIN_SATURATION)
            & (value >= MIN_VALUE)
            & (hue >= 4)
            & (hue <= 120)
            & (delta[row] > 4)
        )
        if not np.any(eligible):
            continue

        scores = saturation * np.maximum(delta[row], 0)
        scores[~eligible] = -1
        column = int(np.argmax(scores))
        observed_hue = float(hue[column])
        selected_hues.append(observed_hue)
        selected_saturations.append(float(saturation[column]))
        selected_values.append(float(value[column]))
        if observed_hue <= MIXED_HUE_SPLIT:
            orange_rows[row] = True
        else:
            blue_rows[row] = True

    orange_count, orange_contiguous = color_row_runs(orange_rows)
    blue_count, blue_contiguous = color_row_runs(blue_rows)
    orange_supported = (
        orange_count >= MIN_COLOR_ROWS
        and orange_contiguous >= MIN_CONTIGUOUS_COLOR_ROWS
    )
    blue_supported = (
        blue_count >= MIN_COLOR_ROWS
        and blue_contiguous >= MIN_CONTIGUOUS_COLOR_ROWS
    )

    if orange_supported and blue_supported:
        color = "orange" if orange_count >= blue_count else "blue"
    elif orange_supported:
        color = "orange"
    elif blue_supported:
        color = "blue"
    else:
        color = "no_orange_blue_detected"

    evidence_rows = orange_count if color == "orange" else blue_count if color == "blue" else 0
    evidence_contiguous = (
        orange_contiguous
        if color == "orange"
        else blue_contiguous
        if color == "blue"
        else 0
    )
    if color == "orange":
        chosen = [h for h in selected_hues if h <= MIXED_HUE_SPLIT]
        selected_saturations = [
            s for h, s in zip(selected_hues, selected_saturations) if h <= MIXED_HUE_SPLIT
        ]
        selected_values = [
            v for h, v in zip(selected_hues, selected_values) if h <= MIXED_HUE_SPLIT
        ]
    elif color == "blue":
        chosen = [h for h in selected_hues if h > MIXED_HUE_SPLIT]
        selected_saturations = [
            s for h, s in zip(selected_hues, selected_saturations) if h > MIXED_HUE_SPLIT
        ]
        selected_values = [
            v for h, v in zip(selected_hues, selected_values) if h > MIXED_HUE_SPLIT
        ]
    else:
        chosen = []
        selected_saturations = []
        selected_values = []

    return {
        "orange_evidence_rows": orange_count,
        "orange_longest_rows": orange_contiguous,
        "blue_evidence_rows": blue_count,
        "blue_longest_rows": blue_contiguous,
        "colored_stream_detected": color != "no_orange_blue_detected",
        "observed_color_nearest": color,
        "evidence_rows": evidence_rows,
        "evidence_longest_rows": evidence_contiguous,
        "median_hue_opencv": f"{np.median(chosen):.1f}" if chosen else "",
        "median_saturation": f"{np.median(selected_saturations):.1f}"
        if selected_saturations
        else "",
        "median_value": f"{np.median(selected_values):.1f}" if selected_values else "",
        "mixed_hue_split": f"{MIXED_HUE_SPLIT:.1f}",
    }


def majority_smooth(states: list[str]) -> list[str]:
    smoothed = []
    for index in range(len(states)):
        start = max(0, index - SMOOTH_RADIUS)
        end = min(len(states), index + SMOOTH_RADIUS + 1)
        counts: dict[str, int] = {}
        for state in states[start:end]:
            counts[state] = counts.get(state, 0) + 1
        smoothed.append(max(counts, key=counts.get))
    return smoothed


def collapse_runs(states: list[str]) -> list[tuple[int, int, str]]:
    if not states:
        return []
    result = []
    start = 0
    for index in range(1, len(states) + 1):
        if index == len(states) or states[index] != states[start]:
            result.append((start, index - 1, states[start]))
            start = index
    return result


def smooth_short_uncolored_gaps(
    states: list[str],
) -> list[str]:
    smoothed = list(states)
    for start, end, state in collapse_runs(list(states)):
        if (
            state != "no_orange_blue_detected"
            or end - start + 1 > SHORT_UNCLASSIFIED_GAP_FRAMES
            or start == 0
            or end == len(states) - 1
        ):
            continue
        left = smoothed[start - 1]
        right = smoothed[end + 1]
        if left == right and left in ("orange", "blue"):
            smoothed[start : end + 1] = [left] * (end - start + 1)
    return smoothed


def expected_colors(recipe: dict[str, str]) -> list[tuple[str, str]]:
    colors = []
    for tank in recipe["dispense_order"].split(">"):
        if tank in ("T200", "T400"):
            colors.append((tank, "orange" if tank == "T200" else "blue"))
    return colors


def analyze_vial(
    capture: cv2.VideoCapture,
    recipe: dict[str, str],
    fps: float,
) -> tuple[list[dict], list[dict], dict]:
    first = int(recipe["start_frame"])
    last = int(recipe["end_frame"])
    vial = int(recipe["vial"])
    recipe_id = int(recipe["recipe_id"])
    if last < first:
        raise ValueError(f"Empty labeled frame interval for vial {vial}")

    capture.set(cv2.CAP_PROP_POS_FRAMES, first)
    rows = []
    for frame_number in range(first, last + 1):
        ok, frame = capture.read()
        if not ok:
            raise OSError(f"Could not decode frame {frame_number} for vial {vial}")
        rows.append(
            {
                "video_id": 5,
                "vial": vial,
                "recipe_id": recipe_id,
                "carryover_suspect": str((vial - 1) % 3 == 0).lower(),
                "frame": frame_number,
                "time_s": f"{frame_number / fps:.3f}",
                **measure_colored_stream(frame),
            }
        )

    smoothed = smooth_short_uncolored_gaps(
        majority_smooth([row["observed_color_nearest"] for row in rows])
    )
    for row, state in zip(rows, smoothed):
        row["color_state_smoothed"] = state

    runs = collapse_runs(smoothed)
    detected_runs = [
        (start, end, color)
        for start, end, color in runs
        if color in ("orange", "blue")
    ]
    groups: list[dict] = []
    for start, end, color in detected_runs:
        if groups and groups[-1]["color"] == color:
            groups[-1]["end"] = end
            groups[-1]["segments"].append((start, end))
        else:
            groups.append(
                {"color": color, "start": start, "end": end, "segments": [(start, end)]}
            )

    expected = expected_colors(recipe)
    expected_names = [color for _, color in expected]
    phase_rows = []
    for phase_index, group in enumerate(groups, start=1):
        active = []
        for start, end in group["segments"]:
            active.extend(
                row
                for row in rows[start : end + 1]
                if row["color_state_smoothed"] == group["color"]
            )
        if not active:
            continue

        if phase_index <= len(expected):
            expected_tank, expected_color = expected[phase_index - 1]
            alignment = (
                "in_expected_order"
                if group["color"] == expected_color
                else "color_order_mismatch"
            )
        else:
            expected_tank, expected_color = "", ""
            alignment = "extra_color_phase"
        if len(active) < MIN_PHASE_FRAMES:
            status = "short_candidate_review"
        else:
            status = "candidate_detected"
        hues = [float(row["median_hue_opencv"]) for row in active if row["median_hue_opencv"]]
        saturations = [
            float(row["median_saturation"]) for row in active if row["median_saturation"]
        ]
        values = [float(row["median_value"]) for row in active if row["median_value"]]
        phase_rows.append(
            {
                "video_id": 5,
                "vial": vial,
                "recipe_id": recipe_id,
                "carryover_suspect": str((vial - 1) % 3 == 0).lower(),
                "phase_index": phase_index,
                "observed_color_nearest": group["color"],
                "expected_tank_by_recipe_order": expected_tank,
                "expected_color_by_recipe_order": expected_color,
                "order_status": alignment,
                "phase_status": status,
                "start_frame": active[0]["frame"],
                "end_frame": active[-1]["frame"],
                "start_time_s": active[0]["time_s"],
                "end_time_s": active[-1]["time_s"],
                "visible_color_span_s": f"{(int(active[-1]['frame']) - int(active[0]['frame']) + 1) / fps:.3f}",
                "detected_colored_frame_duration_s": f"{len(active) / fps:.3f}",
                "detected_colored_frame_count": len(active),
                "median_hue_opencv": f"{np.median(hues):.1f}" if hues else "",
                "median_saturation": f"{np.median(saturations):.1f}"
                if saturations
                else "",
                "median_value": f"{np.median(values):.1f}" if values else "",
                "recipe_dispense_order": recipe["dispense_order"],
                "labeled_window_start_s": recipe["start_s"],
                "labeled_window_end_s": recipe["end_s"],
            }
        )

    ordered_observed = [group["color"] for group in groups]
    if expected_names == ["orange", "blue"]:
        # Keep the detected subsequence separate from the strict sequence check:
        # missing phases must not count as a complete recipe-order match.
        cursor = 0
        matched = []
        for color in ordered_observed:
            if cursor < len(expected_names) and color == expected_names[cursor]:
                matched.append(color)
                cursor += 1
        missing = expected_names[cursor:]
    else:
        missing = [color for color in expected_names if color not in ordered_observed]
        matched = list(dict.fromkeys(
            color for color in ordered_observed if color in expected_names
        ))
    order_match = ordered_observed == expected_names

    expected_sequence = ">".join(expected_names) if expected_names else "none"
    observed_sequence = ">".join(ordered_observed) if ordered_observed else "none_detected"
    summary = {
        "video_id": 5,
        "vial": vial,
        "recipe_id": recipe_id,
        "carryover_suspect": str((vial - 1) % 3 == 0).lower(),
        "recipe_dispense_order": recipe["dispense_order"],
        "expected_visible_colored_order": expected_sequence,
        "observed_visible_color_sequence": observed_sequence,
        "sequence_respects_recipe_order": str(order_match).lower(),
        "expected_colored_phases_detected": ">".join(matched) if matched else "none",
        "expected_colors_not_detected": ">".join(missing) if missing else "none",
        "detected_phase_count": len(phase_rows),
        "labeled_window_start_s": recipe["start_s"],
        "labeled_window_end_s": recipe["end_s"],
    }

    if expected_names == ["orange", "blue"]:
        first_orange = next(
            (phase for phase in phase_rows if phase["observed_color_nearest"] == "orange"),
            None,
        )
        first_blue_after_orange = None
        if first_orange is not None:
            first_blue_after_orange = next(
                (
                    phase
                    for phase in phase_rows
                    if phase["observed_color_nearest"] == "blue"
                    and int(phase["start_frame"]) > int(first_orange["end_frame"])
                ),
                None,
            )
        if first_orange is not None and first_blue_after_orange is not None:
            gap_start = int(first_orange["end_frame"]) + 1
            gap_end = int(first_blue_after_orange["start_frame"]) - 1
            if gap_end >= gap_start:
                summary["orange_to_blue_unclassified_interval_s"] = (
                    f"{(gap_end - gap_start + 1) / fps:.3f}"
                )
                summary["orange_to_blue_interval_note"] = (
                    "No orange/blue signal detected in interval; may include clear flow or pause."
                )
            else:
                summary["orange_to_blue_unclassified_interval_s"] = "0.000"
                summary["orange_to_blue_interval_note"] = "Colored detections overlap or are adjacent."
        else:
            summary["orange_to_blue_unclassified_interval_s"] = ""
            summary["orange_to_blue_interval_note"] = (
                "Not calculated because both ordered color phases were not detected."
            )
    else:
        summary["orange_to_blue_unclassified_interval_s"] = ""
        summary["orange_to_blue_interval_note"] = "Not applicable for this recipe's colored order."

    return rows, phase_rows, summary


FRAME_FIELDS = [
    "video_id",
    "vial",
    "recipe_id",
    "carryover_suspect",
    "frame",
    "time_s",
    "orange_evidence_rows",
    "orange_longest_rows",
    "blue_evidence_rows",
    "blue_longest_rows",
    "colored_stream_detected",
    "observed_color_nearest",
    "evidence_rows",
    "evidence_longest_rows",
    "median_hue_opencv",
    "median_saturation",
    "median_value",
    "mixed_hue_split",
    "color_state_smoothed",
]

PHASE_FIELDS = [
    "video_id",
    "vial",
    "recipe_id",
    "carryover_suspect",
    "phase_index",
    "observed_color_nearest",
    "expected_tank_by_recipe_order",
    "expected_color_by_recipe_order",
    "order_status",
    "phase_status",
    "start_frame",
    "end_frame",
    "start_time_s",
    "end_time_s",
    "visible_color_span_s",
    "detected_colored_frame_duration_s",
    "detected_colored_frame_count",
    "median_hue_opencv",
    "median_saturation",
    "median_value",
    "recipe_dispense_order",
    "labeled_window_start_s",
    "labeled_window_end_s",
]

SUMMARY_FIELDS = [
    "video_id",
    "vial",
    "recipe_id",
    "carryover_suspect",
    "recipe_dispense_order",
    "expected_visible_colored_order",
    "observed_visible_color_sequence",
    "sequence_respects_recipe_order",
    "expected_colored_phases_detected",
    "expected_colors_not_detected",
    "detected_phase_count",
    "labeled_window_start_s",
    "labeled_window_end_s",
    "orange_to_blue_unclassified_interval_s",
    "orange_to_blue_interval_note",
]


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure orange and blue stream phases in Video 5 without classifying clear flow."
    )
    parser.add_argument("--video", type=Path, default=VIDEO_PATH)
    parser.add_argument("--recipes", type=Path, default=RECIPE_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    recipes = read_recipes(args.recipes)
    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        raise OSError(f"Could not open video: {args.video}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if fps <= 0 or frame_count <= 0:
        capture.release()
        raise ValueError(f"Video has invalid FPS or frame count: {args.video}")

    all_frames, all_phases, all_summaries = [], [], []
    try:
        for recipe in recipes:
            if int(recipe["end_frame"]) >= frame_count:
                raise ValueError(
                    f"Vial {recipe['vial']} label extends past the source video"
                )
            frames, phases, summary = analyze_vial(capture, recipe, fps)
            all_frames.extend(frames)
            all_phases.extend(phases)
            all_summaries.append(summary)
    finally:
        capture.release()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "frame_measurements.csv", all_frames, FRAME_FIELDS)
    write_csv(args.output_dir / "color_phases.csv", all_phases, PHASE_FIELDS)
    write_csv(args.output_dir / "vial_color_order_summary.csv", all_summaries, SUMMARY_FIELDS)

    matching = sum(row["sequence_respects_recipe_order"] == "true" for row in all_summaries)
    report = [
        "# Video 5 orange/blue stream analysis",
        "",
        f"- Source: `{args.video}` ({frame_count} frames at {fps:g} fps).",
        f"- Labeled vial windows analyzed: {len(recipes)}.",
        f"- Frame-level measurements: {len(all_frames)}.",
        f"- Candidate visible orange/blue phases: {len(all_phases)}.",
        f"- Vials whose complete observed colored sequence matches the expected recipe order: {matching}/{len(recipes)}.",
        "",
        "## Scope",
        "",
        "This pass deliberately measures only visible orange and blue stream color. It does not "
        "classify clear flow, and it does not interpret a missing orange/blue signal as proof that "
        "liquid flow stopped. For recipes containing T200 and T400, the expected colored order is "
        "orange then blue; T100 is omitted from the colored target sequence. Recipes using only one "
        "colored tank are checked against that one expected color. A sequence counts as a match "
        "only when the complete candidate sequence exactly matches the expected colors; missing "
        "or extra phases do not count as a match.",
        "",
        "Recipe labels are used to define the vial frame windows and to compare the observed colored "
        "sequence after image measurement. They do not force a missing phase to appear. Intermediate "
        "colored hues are assigned to the nearer orange/blue hue reference. Per-frame color evidence "
        "and smoothed class are preserved in `frame_measurements.csv`; candidate phases are in "
        "`color_phases.csv`; expected-versus-observed order and orange-to-blue unclassified intervals "
        "are in `vial_color_order_summary.csv`.",
        "",
        "The stream detector examines a narrow region immediately below the nozzle and compares "
        "saturated pixels against nearby background. Image hue is affected by lighting, reflections, "
        "flow thickness, and mixing in the shared path. For this pass, the hue references were anchored "
        "to the same-camera stream appearances in the labeled single-colored recipes: T200-only recipe 6 "
        "(clean vial 5, median observed hue 30) and T400-only recipe 7 (clean vials 8-9, median observed "
        "hue 87). Those references are approximate and the anchors are not physical color calibration. "
        "These color labels and phase boundaries remain exploratory candidates, not confirmed valve timings.",
        "",
        "An orange-to-blue interval with no detected orange/blue signal is reported as an "
        "unclassified interval. It may contain clear flow, a pause, or both; this analysis cannot "
        "distinguish those cases. A phase with fewer than 12 active colored frames is marked for "
        "review. The first vial after each recipe switch remains measured and is flagged as "
        "carryover-suspect.",
        "",
        "Compare candidates with the full source footage before using exact colors or timings as "
        "simulation targets.",
    ]
    (args.output_dir / "ORANGE_BLUE_ANALYSIS.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )

    print(
        f"Analyzed {len(all_frames)} frames across {len(recipes)} labeled vials; "
        f"found {len(all_phases)} candidate colored phases."
    )
    print(f"Observed color order agrees in {matching}/{len(recipes)} vial records.")
    print(f"Outputs: {args.output_dir}")


if __name__ == "__main__":
    main()

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "csi_vial_fill"
VIDEO5_DIR = DATA_DIR / "video_5"
VIDEO4_DIR = DATA_DIR / "video_4"

NOZZLE_X = (298, 312)
NOZZLE_Y = (95, 175)
BACKGROUND_LEFT_X = (285, 297)
BACKGROUND_RIGHT_X = (313, 325)
COLLAR_ROI = (255, 190, 390, 255)
MIN_CONTRAST_ROWS = 15
MIN_CONTIGUOUS_ROWS = 15
MIN_PHASE_RUN_FRAMES = 12

TANK_COLOR = {"T100": "clear_candidate", "T200": "orange", "T400": "blue"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


def longest_true_run(values: np.ndarray) -> int:
    padded = np.r_[False, values, False].astype(np.int8)
    edges = np.diff(padded)
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1)
    return max((int(end - start) for start, end in zip(starts, ends)), default=0)


def collar_departures(video_path: Path) -> tuple[list[tuple[int, int]], float, int]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise OSError(f"Could not open video: {video_path}")

    fps = float(capture.get(cv2.CAP_PROP_FPS))
    declared_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    x0, y0, x1, y1 = COLLAR_ROI
    signal: list[float] = []
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            gray = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
            signal.append(float(np.mean(gray < 60)))
    finally:
        capture.release()

    if fps <= 0 or not signal:
        raise ValueError(f"Video has no readable frames or valid FPS: {video_path}")
    if declared_frames and abs(declared_frames - len(signal)) > 1:
        raise ValueError(
            f"Decoded {len(signal)} frames, but video metadata reports {declared_frames}"
        )

    low = np.asarray(signal) < 0.04
    starts = np.flatnonzero(low & np.r_[True, ~low[:-1]])
    ends = np.flatnonzero(low & np.r_[~low[1:], True])
    return list(zip(starts.tolist(), ends.tolist())), fps, len(signal)


def video4_windows(
    departures: list[tuple[int, int]], frame_count: int
) -> list[dict]:
    if len(departures) != 6:
        raise ValueError(
            f"Video 4 collar detector found {len(departures)} departures; "
            "expected six from the source dataset documentation."
        )
    if any(end >= frame_count for _, end in departures):
        raise ValueError("Video 4 collar departure extends beyond the decoded video")
    windows = []
    start = 0
    for vial, (departure_start, departure_end) in enumerate(departures, start=1):
        if departure_start < start:
            raise ValueError("Video 4 collar events are not in chronological order")
        windows.append(
            {
                "first_frame": start,
                "last_frame": departure_start - 1,
                "vial": vial,
                "recipe_id": "",
                "carryover_suspect": "",
                "dispense_order": "",
                "label_start_s": "",
                "label_end_s": "",
            }
        )
        start = departure_end + 1
    if len(windows) != 6:
        raise ValueError(f"Expected six Video 4 vial intervals, got {len(windows)}")
    return windows


def video5_windows(recipes_path: Path, fps: float, frame_count: int) -> list[dict]:
    recipes = read_csv(recipes_path)
    if len(recipes) != 30:
        raise ValueError(f"Expected 30 Video 5 recipe rows in {recipes_path}")
    windows = []
    for row in recipes:
        first = int(row["start_frame"])
        last = int(row["end_frame"])
        vial = int(row["vial"])
        if first < 0 or last < first or last >= frame_count:
            raise ValueError(f"Invalid frame window for vial {vial}: {first}-{last}")
        order = [tank for tank in row["dispense_order"].split(">") if tank]
        if not order or any(tank not in TANK_COLOR for tank in order):
            raise ValueError(f"Unexpected dispense order for vial {vial}")
        windows.append(
            {
                "first_frame": first,
                "last_frame": last,
                "vial": vial,
                "recipe_id": row["recipe_id"],
                "carryover_suspect": str((vial - 1) % 3 == 0).lower(),
                "dispense_order": row["dispense_order"],
                "label_start_s": f"{first / fps:.3f}",
                "label_end_s": f"{last / fps:.3f}",
            }
        )
    return windows


def measure_frame(frame: np.ndarray) -> dict:
    x0, x1 = NOZZLE_X
    y0, y1 = NOZZLE_Y
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB).astype(np.float32)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    center_lab = lab[y0:y1, x0:x1]
    left_rows = np.median(
        lab[y0:y1, BACKGROUND_LEFT_X[0] : BACKGROUND_LEFT_X[1]], axis=1
    )
    right_rows = np.median(
        lab[y0:y1, BACKGROUND_RIGHT_X[0] : BACKGROUND_RIGHT_X[1]], axis=1
    )
    background_rows = (left_rows + right_rows) / 2
    pixel_deltas = np.linalg.norm(
        center_lab - background_rows[:, np.newaxis, :], axis=2
    )
    best_column = np.argmax(pixel_deltas, axis=1)
    row_delta = np.max(pixel_deltas, axis=1)
    row_hits = row_delta > 10
    hit_count = int(np.count_nonzero(row_hits))
    continuous_hits = longest_true_run(row_hits)
    is_flowing = hit_count >= MIN_CONTRAST_ROWS and continuous_hits >= MIN_CONTIGUOUS_ROWS

    result = {
        "flow_contrast_rows": hit_count,
        "flow_longest_contiguous_rows": continuous_hits,
        "is_flowing": is_flowing,
        "color_sample_pixels": 0,
        "hue_median_opencv": "",
        "saturation_median": "",
        "value_median": "",
        "lab_l_median_8bit": "",
        "lab_a_median_8bit": "",
        "lab_b_median_8bit": "",
        "observed_color_nearest": "",
        "color_class_confidence": "",
    }
    if not is_flowing:
        return result

    line_pixels = []
    line_hsv = []
    for row_index, column in enumerate(best_column):
        if not row_hits[row_index]:
            continue
        left = max(0, int(column) - 1)
        right = min(x1 - x0, int(column) + 2)
        for pixel_column in range(left, right):
            if pixel_deltas[row_index, pixel_column] > 3:
                line_pixels.append(center_lab[row_index, pixel_column])
                line_hsv.append(hsv[y0 + row_index, x0 + pixel_column])
    if not line_pixels:
        return result

    hsv_values = np.asarray(line_hsv, dtype=np.float32)
    lab_values = np.asarray(line_pixels, dtype=np.float32)
    hue, saturation, value = np.median(hsv_values, axis=0)
    lab_l, lab_a, lab_b = np.median(lab_values, axis=0)
    if saturation <= 18:
        color = "clear_candidate"
        confidence = "low"
    else:
        orange_distance = min(abs(hue - 15), 180 - abs(hue - 15))
        blue_distance = min(abs(hue - 95), 180 - abs(hue - 95))
        color = "orange" if orange_distance <= blue_distance else "blue"
        confidence = "high" if abs(orange_distance - blue_distance) >= 12 else "low"

    result.update(
        {
            "color_sample_pixels": len(line_pixels),
            "hue_median_opencv": f"{hue:.1f}",
            "saturation_median": f"{saturation:.1f}",
            "value_median": f"{value:.1f}",
            "lab_l_median_8bit": f"{lab_l:.1f}",
            "lab_a_median_8bit": f"{lab_a:.1f}",
            "lab_b_median_8bit": f"{lab_b:.1f}",
            "observed_color_nearest": color,
            "color_class_confidence": (
                "low"
                if len(line_pixels) < 20
                else confidence
            ),
        }
    )
    return result


def majority_smooth(values: list[str], radius: int) -> list[str]:
    smoothed = []
    for index in range(len(values)):
        start = max(0, index - radius)
        end = min(len(values), index + radius + 1)
        counts: dict[str, int] = {}
        for value in values[start:end]:
            counts[value] = counts.get(value, 0) + 1
        smoothed.append(max(counts, key=counts.get))
    return smoothed


def runs(states: list[str]) -> list[tuple[int, int, str]]:
    if not states:
        return []
    result = []
    start = 0
    for index in range(1, len(states) + 1):
        if index == len(states) or states[index] != states[start]:
            result.append((start, index - 1, states[start]))
            start = index
    return result


def nearest_color_distance(left: dict, right: dict) -> float:
    hue_left = float(left["hue_median_opencv"])
    hue_right = float(right["hue_median_opencv"])
    hue_delta = min(abs(hue_left - hue_right), 180 - abs(hue_left - hue_right))
    sat_delta = float(left["saturation_median"]) - float(right["saturation_median"])
    value_delta = float(left["value_median"]) - float(right["value_median"])
    return float(np.sqrt(hue_delta**2 + sat_delta**2 + value_delta**2))


def merge_short_color_runs(
    state_runs: list[tuple[int, int, str]], frame_rows: list[dict]
) -> list[tuple[int, int, str]]:
    result = list(state_runs)
    for index, (start, end, state) in enumerate(list(result)):
        if state == "no_stream" or end - start + 1 >= MIN_PHASE_RUN_FRAMES:
            continue
        left = next(
            (result[i] for i in range(index - 1, -1, -1) if result[i][2] != "no_stream"),
            None,
        )
        right = next(
            (result[i] for i in range(index + 1, len(result)) if result[i][2] != "no_stream"),
            None,
        )
        if left is None and right is None:
            continue
        if left is None:
            replacement = right[2]
        elif right is None:
            replacement = left[2]
        elif left[2] == right[2]:
            replacement = left[2]
        else:
            current_samples = [
                row
                for row in frame_rows[start : end + 1]
                if row["observed_color_nearest"]
            ]
            left_samples = [
                row
                for row in frame_rows[left[0] : left[1] + 1]
                if row["observed_color_nearest"]
            ]
            right_samples = [
                row
                for row in frame_rows[right[0] : right[1] + 1]
                if row["observed_color_nearest"]
            ]
            if not current_samples or not left_samples or not right_samples:
                replacement = left[2] if left[1] - left[0] >= right[1] - right[0] else right[2]
            else:
                current = current_samples[len(current_samples) // 2]
                left_ref = left_samples[len(left_samples) // 2]
                right_ref = right_samples[len(right_samples) // 2]
                replacement = (
                    left[2]
                    if nearest_color_distance(current, left_ref)
                    <= nearest_color_distance(current, right_ref)
                    else right[2]
                )
        result[index] = (start, end, replacement)
    return result


def analyze_window(
    capture: cv2.VideoCapture, window: dict, fps: float, video_id: int
) -> tuple[list[dict], list[dict], list[dict]]:
    first = window["first_frame"]
    last = window["last_frame"]
    if last < first:
        raise ValueError(f"Empty frame interval for vial {window['vial']}")

    capture.set(cv2.CAP_PROP_POS_FRAMES, first)
    frame_rows = []
    for frame_number in range(first, last + 1):
        ok, frame = capture.read()
        if not ok:
            raise OSError(f"Could not decode frame {frame_number} in Video {video_id}")
        measured = measure_frame(frame)
        frame_rows.append(
            {
                "video_id": video_id,
                "vial": window["vial"],
                "recipe_id": window["recipe_id"],
                "carryover_suspect": window["carryover_suspect"],
                "frame": frame_number,
                "time_s": f"{frame_number / fps:.3f}",
                **measured,
            }
        )

    flow_values = [row["is_flowing"] for row in frame_rows]
    smoothed_flow = majority_smooth(
        ["flow" if value else "no_stream" for value in flow_values], radius=2
    )
    raw_states = [
        row["observed_color_nearest"] if smoothed_flow[i] == "flow" else "no_stream"
        for i, row in enumerate(frame_rows)
    ]
    smoothed_states = majority_smooth(raw_states, radius=3)
    for index, row in enumerate(frame_rows):
        row["flow_active_smoothed"] = smoothed_flow[index] == "flow"
        row["phase_color_smoothed"] = smoothed_states[index]
    state_runs = merge_short_color_runs(runs(smoothed_states), frame_rows)

    color_runs = [
        item
        for item in state_runs
        if item[2] not in ("no_stream", "")
    ]
    if not color_runs:
        return frame_rows, [], []

    phase_groups: list[dict] = []
    for start, end, color in color_runs:
        if phase_groups and phase_groups[-1]["color"] == color:
            phase_groups[-1]["end"] = end
            phase_groups[-1]["segments"].append((start, end))
        else:
            phase_groups.append(
                {"color": color, "start": start, "end": end, "segments": [(start, end)]}
            )

    expected_order = [
        item for item in window["dispense_order"].split(">") if item
    ]
    phase_rows = []
    phase_lookup = []
    for phase_index, group in enumerate(phase_groups, start=1):
        color = group["color"]
        active = []
        for start, end in group["segments"]:
            active.extend(
                row
                for row in frame_rows[start : end + 1]
                if row["flow_active_smoothed"]
            )
        if not active:
            continue
        hsv = np.asarray(
            [
                [
                    float(row["hue_median_opencv"]),
                    float(row["saturation_median"]),
                    float(row["value_median"]),
                ]
                for row in active
                if row["hue_median_opencv"] != ""
            ]
        )
        lab = np.asarray(
            [
                [
                    float(row["lab_l_median_8bit"]),
                    float(row["lab_a_median_8bit"]),
                    float(row["lab_b_median_8bit"]),
                ]
                for row in active
                if row["lab_l_median_8bit"] != ""
            ]
        )
        if len(hsv) == 0 or len(lab) == 0:
            continue

        expected_tank = (
            expected_order[phase_index - 1]
            if phase_index <= len(expected_order)
            else ""
        )
        expected_color = TANK_COLOR.get(expected_tank, "")
        alignment = (
            "consistent"
            if expected_color and expected_color == color
            else "visual_order_mismatch"
            if expected_tank
            else "no_order_phase"
        )
        phase = {
            "video_id": video_id,
            "vial": window["vial"],
            "recipe_id": window["recipe_id"],
            "carryover_suspect": window["carryover_suspect"],
            "phase_index": phase_index,
            "observed_color_nearest": color,
            "expected_tank_by_order": expected_tank,
            "expected_color_by_order": expected_color,
            "order_alignment": alignment,
            "candidate_T100": str(
                expected_tank == "T100" and color == "clear_candidate"
            ).lower(),
            "start_frame": active[0]["frame"],
            "end_frame": active[-1]["frame"],
            "start_time_s": active[0]["time_s"],
            "end_time_s": active[-1]["time_s"],
            "elapsed_duration_s": f"{(int(active[-1]['frame']) - int(active[0]['frame']) + 1) / fps:.3f}",
            "active_flow_duration_s": f"{len(active) / fps:.3f}",
            "active_frame_count": len(active),
            "median_hue_opencv": f"{np.median(hsv[:, 0]):.1f}",
            "median_saturation": f"{np.median(hsv[:, 1]):.1f}",
            "median_value": f"{np.median(hsv[:, 2]):.1f}",
            "median_lab_l_8bit": f"{np.median(lab[:, 0]):.1f}",
            "median_lab_a_8bit": f"{np.median(lab[:, 1]):.1f}",
            "median_lab_b_8bit": f"{np.median(lab[:, 2]):.1f}",
            "median_color_sample_pixels": int(
                np.median([int(row["color_sample_pixels"]) for row in active])
            ),
            "label_window_start_s": window["label_start_s"],
            "label_window_end_s": window["label_end_s"],
        }
        phase_rows.append(phase)
        phase_lookup.append((group["start"], group["end"], phase))

    pause_rows = []
    for (prev_start, prev_end, prev_phase), (next_start, next_end, next_phase) in zip(
        phase_lookup, phase_lookup[1:]
    ):
        if prev_phase["observed_color_nearest"] == next_phase["observed_color_nearest"]:
            continue
        gap_start = int(prev_phase["end_frame"]) + 1
        gap_end = int(next_phase["start_frame"]) - 1
        if gap_end < gap_start:
            continue
        pause_rows.append(
            {
                "video_id": video_id,
                "vial": window["vial"],
                "recipe_id": window["recipe_id"],
                "carryover_suspect": window["carryover_suspect"],
                "previous_color": prev_phase["observed_color_nearest"],
                "next_color": next_phase["observed_color_nearest"],
                "previous_expected_tank": prev_phase["expected_tank_by_order"],
                "next_expected_tank": next_phase["expected_tank_by_order"],
                "start_frame": gap_start,
                "end_frame": gap_end,
                "start_time_s": f"{gap_start / fps:.3f}",
                "end_time_s": f"{gap_end / fps:.3f}",
                "pause_duration_s": f"{(gap_end - gap_start + 1) / fps:.3f}",
                "interpretation": "visible stream-off interval between different measured color phases",
            }
        )
    return frame_rows, phase_rows, pause_rows


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


FRAME_FIELDS = [
    "video_id",
    "vial",
    "recipe_id",
    "carryover_suspect",
    "frame",
    "time_s",
    "flow_contrast_rows",
    "flow_longest_contiguous_rows",
    "is_flowing",
    "flow_active_smoothed",
    "color_sample_pixels",
    "hue_median_opencv",
    "saturation_median",
    "value_median",
    "lab_l_median_8bit",
    "lab_a_median_8bit",
    "lab_b_median_8bit",
    "observed_color_nearest",
    "color_class_confidence",
    "phase_color_smoothed",
]

PHASE_FIELDS = [
    "video_id",
    "vial",
    "recipe_id",
    "carryover_suspect",
    "phase_index",
    "observed_color_nearest",
    "expected_tank_by_order",
    "expected_color_by_order",
    "order_alignment",
    "candidate_T100",
    "start_frame",
    "end_frame",
    "start_time_s",
    "end_time_s",
    "elapsed_duration_s",
    "active_flow_duration_s",
    "active_frame_count",
    "median_hue_opencv",
    "median_saturation",
    "median_value",
    "median_lab_l_8bit",
    "median_lab_a_8bit",
    "median_lab_b_8bit",
    "median_color_sample_pixels",
    "label_window_start_s",
    "label_window_end_s",
]

PAUSE_FIELDS = [
    "video_id",
    "vial",
    "recipe_id",
    "carryover_suspect",
    "previous_color",
    "next_color",
    "previous_expected_tank",
    "next_expected_tank",
    "start_frame",
    "end_frame",
    "start_time_s",
    "end_time_s",
    "pause_duration_s",
    "interpretation",
]


def analyze_video(
    video_path: Path,
    video_id: int,
    windows: list[dict],
    fps: float,
    output_dir: Path,
) -> tuple[list[dict], list[dict], list[dict]]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise OSError(f"Could not open video: {video_path}")
    all_frames, all_phases, all_pauses = [], [], []
    try:
        for window in windows:
            frames, phases, pauses = analyze_window(capture, window, fps, video_id)
            all_frames.extend(frames)
            all_phases.extend(phases)
            all_pauses.extend(pauses)
    finally:
        capture.release()

    write_csv(output_dir / "frame_measurements.csv", all_frames, FRAME_FIELDS)
    write_csv(output_dir / "color_phases.csv", all_phases, PHASE_FIELDS)
    write_csv(output_dir / "inter_color_pauses.csv", all_pauses, PAUSE_FIELDS)
    return all_frames, all_phases, all_pauses


def write_report(
    path: Path,
    video_id: int,
    video_path: Path,
    fps: float,
    frame_count: int,
    windows: list[dict],
    frames: list[dict],
    phases: list[dict],
    pauses: list[dict],
) -> None:
    active_count = sum(row["is_flowing"] for row in frames)
    mismatches = sum(
        phase["order_alignment"] == "visual_order_mismatch" for phase in phases
    )
    lines = [
        f"# Video {video_id} nozzle-stream analysis",
        "",
        f"- Source: `{video_path}` ({frame_count} frames at {fps:g} fps).",
        f"- Vial intervals analyzed: {len(windows)}.",
        f"- Frames measured within the analysis windows: {len(frames)}; raw frame-level flow detections: {active_count}.",
        f"- Measured color phases: {len(phases)}; inter-color visible pauses: {len(pauses)}.",
        "",
        "## Method and interpretation",
        "",
        f"The stream detector compares the nozzle-center strip x={NOZZLE_X[0]}:{NOZZLE_X[1]}, "
        f"y={NOZZLE_Y[0]}:{NOZZLE_Y[1]} with adjacent background strips. It flags a candidate "
        f"stream when at least {MIN_CONTRAST_ROWS} rows have a Lab contrast above 10 and a "
        f"continuous vertical run is at least {MIN_CONTIGUOUS_ROWS} rows. A five-frame majority "
        "smooths flow detections; short color flicker is folded into the nearest adjacent measured phase.",
        "",
        "For active frames, median HSV and 8-bit Lab values are measured on the strongest "
        "background-contrasting line pixels in the nozzle strip. OpenCV hue nearer 15 is labeled "
        "orange and nearer 95 is labeled blue; saturation at or below 18 is labeled "
        "`clear_candidate`. These are heuristic image-space classes, not calibrated fluid colors. "
        "Raw and smoothed flow/color states are preserved in `frame_measurements.csv`.",
        "",
        "A pause is reported only when a visible stream-off interval lies between two different "
        "measured color phases. Pauses within a single phase, including same-color interruptions, "
        "are intentionally not included.",
        "",
        "The detector is an exploratory automated measurement, not a validated optical classifier. "
        "The clear-liquid stream and faint/transparent flow may be missed; reflections, nozzle "
        "motion, and weak contrast may create uncertain boundaries. Check low-confidence frames "
        "and each reported phase against the source video before using exact timings or colors as "
        "simulation targets.",
    ]
    if video_id == 4:
        lines.extend(
            [
                "",
                "Video 4 has no recipe labels. Vial numbering is inferred only from the six "
                "collar-departure events; no phase is assigned to a recipe or tank.",
                (
                    "No between-color stream-off pause met the current detector threshold in this "
                    "pass; this does not prove that pauses never occur, and brief or transparent "
                    "flow may be missed."
                    if not pauses
                    else "The reported between-color pause is a candidate for visual review, not a "
                    "recipe-timing label."
                ),
            ]
        )
    else:
        lines.extend(
            [
                "",
                f"- Color-order disagreements against the Video 5 recipe sequence: {mismatches}.",
                "",
                "Video 5's source recipe window separates vial records. Its dispense order is checked "
                "only after measuring the visible stream. A low-saturation phase is a candidate T100 "
                "only when T100 is next in the labeled order; disagreements are retained, not relabeled.",
                "",
                "Video 5 first-after-switch vials are: 1, 4, 7, 10, 13, 16, 19, 22, 25, and 28. "
                "They remain in the measurements but should not be used as clean recipe references.",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure nozzle-stream activity, color phases, and pauses in Videos 4 and 5."
    )
    parser.add_argument("--video4", type=Path, default=VIDEO4_DIR / "video" / "vial_fill_video_4.mp4")
    parser.add_argument("--video5", type=Path, default=VIDEO5_DIR / "video" / "vial_fill_video_5.mp4")
    parser.add_argument(
        "--recipes",
        type=Path,
        default=VIDEO5_DIR / "labels" / "source" / "video5_vial_recipes.csv",
    )
    args = parser.parse_args()

    departures4, fps4, count4 = collar_departures(args.video4)
    windows4 = video4_windows(departures4, count4)
    frames4, phases4, pauses4 = analyze_video(
        args.video4, 4, windows4, fps4, VIDEO4_DIR / "analysis" / "nozzle"
    )
    write_report(
        VIDEO4_DIR / "analysis" / "nozzle" / "NOZZLE_ANALYSIS.md",
        4,
        args.video4,
        fps4,
        count4,
        windows4,
        frames4,
        phases4,
        pauses4,
    )

    departures5, fps5, count5 = collar_departures(args.video5)
    if len(departures5) != 30:
        raise ValueError(f"Video 5 collar detector found {len(departures5)} vials, expected 30")
    windows5 = video5_windows(args.recipes, fps5, count5)
    frames5, phases5, pauses5 = analyze_video(
        args.video5, 5, windows5, fps5, VIDEO5_DIR / "analysis" / "nozzle"
    )
    write_report(
        VIDEO5_DIR / "analysis" / "nozzle" / "NOZZLE_ANALYSIS.md",
        5,
        args.video5,
        fps5,
        count5,
        windows5,
        frames5,
        phases5,
        pauses5,
    )

    print(
        f"Video 4: {len(windows4)} unlabeled vial windows, {len(phases4)} color phases, "
        f"{len(pauses4)} between-color pauses."
    )
    print(
        f"Video 5: {len(windows5)} labeled vial windows, {len(phases5)} color phases, "
        f"{len(pauses5)} between-color pauses."
    )
    print(f"Outputs: {VIDEO4_DIR / 'analysis' / 'nozzle'}")
    print(f"Outputs: {VIDEO5_DIR / 'analysis' / 'nozzle'}")


if __name__ == "__main__":
    main()

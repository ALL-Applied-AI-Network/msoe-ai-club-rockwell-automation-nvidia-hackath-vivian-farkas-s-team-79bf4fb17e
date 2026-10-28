import csv
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = ROOT / "data" / "csi_vial_fill" / "video_5"
ANALYSIS_DIR = VIDEO_DIR / "analysis"
OUTPUT_DIR = ANALYSIS_DIR / "combined_cues"
RECIPE_PATH = VIDEO_DIR / "labels" / "source" / "video5_vial_recipes.csv"
COLOR_PATH = ANALYSIS_DIR / "vial_color_measurements.csv"
STREAM_PATH = ANALYSIS_DIR / "colored_streams" / "vial_color_order_summary.csv"
LEVEL_PATH = ANALYSIS_DIR / "meniscus" / "meniscus_measurements.csv"

MANUAL_STREAM_NOTES = {
    2: (
        "User review: blue first, then a mixed blue-orange color; "
        "not confirmed as a distinct orange phase."
    ),
    3: (
        "User review: green until 1:36, then green-brown until 1:59; "
        "tank colors not confidently identified."
    ),
    10: (
        "User review: clear blue through 7:23; no visible stream until 7:35; "
        "light blue fading to clear through 7:41."
    ),
    11: "User review: orange to green to blue, with no visible stop.",
    12: "User review: orange to green to blue, with no visible stop.",
}

FIELDS = [
    "video_id",
    "vial",
    "recipe_id",
    "position_in_recipe",
    "carryover_suspect",
    "t100_ml",
    "t200_ml",
    "t400_ml",
    "source_total_ml",
    "recipe_dispense_order",
    "expected_visible_colored_order",
    "automated_stream_sequence",
    "automated_stream_exact_order_match",
    "manually_reviewed_stream_observation",
    "sample_frame",
    "sample_time_s",
    "final_color_hue_median_opencv",
    "final_color_saturation_median",
    "final_color_lab_l_median_8bit",
    "final_color_lab_a_median_8bit",
    "final_color_lab_b_median_8bit",
    "color_only_loo_nearest_recipe_id",
    "color_only_loo_correct",
    "meniscus_measurement_status",
    "meniscus_y_range_px",
    "liquid_height_range_px",
    "meniscus_confidence",
    "combined_cue_note",
]


def read_by_vial(path: Path) -> dict[int, dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as source:
        rows = list(csv.DictReader(source))
    result = {int(row["vial"]): row for row in rows}
    if len(result) != len(rows):
        raise ValueError(f"Duplicate vial records in {path}")
    return result


def optional_number(value: str) -> float | None:
    return float(value) if value else None


def join_cues() -> list[dict[str, str]]:
    recipes = read_by_vial(RECIPE_PATH)
    colors = read_by_vial(COLOR_PATH)
    streams = read_by_vial(STREAM_PATH)
    levels = read_by_vial(LEVEL_PATH)
    expected_vials = set(range(1, 31))
    for path, records in (
        (RECIPE_PATH, recipes),
        (COLOR_PATH, colors),
        (STREAM_PATH, streams),
        (LEVEL_PATH, levels),
    ):
        if set(records) != expected_vials:
            raise ValueError(f"Expected records for vials 1-30 in {path}")

    combined = []
    for vial in range(1, 31):
        recipe = recipes[vial]
        color = colors[vial]
        stream = streams[vial]
        level = levels[vial]
        if not (
            recipe["recipe_id"] == color["recipe_id"]
            == stream["recipe_id"]
            == level["recipe_id"]
        ):
            raise ValueError(f"Recipe ID mismatch while joining vial {vial}")
        if (
            color["sample_frame"] != level["sample_frame"]
            or color["sample_time_s"] != level["sample_time_s"]
        ):
            raise ValueError(f"Color and level samples differ for vial {vial}")

        total_ml = sum(
            optional_number(recipe[key]) or 0
            for key in ("t100_ml", "t200_ml", "t400_ml")
        )
        if total_ml != float(recipe["total_ml"]):
            raise ValueError(f"Recipe component total mismatch for vial {vial}")

        manual_note = MANUAL_STREAM_NOTES.get(vial, "")
        combined_note = (
            "Manual stream observation is available; prefer it to the exploratory "
            "automated stream label for this vial."
            if manual_note
            else "No manual stream review recorded for this vial."
        )
        if level["measurement_status"] == "holder_obscured":
            combined_note += " Meniscus is hidden; height interval is broad."
        if color["color_reference_eligible"] != "True":
            combined_note += " First vial after recipe switch; carryover-suspect."

        combined.append(
            {
                "video_id": "5",
                "vial": str(vial),
                "recipe_id": recipe["recipe_id"],
                "position_in_recipe": str((vial - 1) % 3 + 1),
                "carryover_suspect": str((vial - 1) % 3 == 0).lower(),
                "t100_ml": recipe["t100_ml"],
                "t200_ml": recipe["t200_ml"],
                "t400_ml": recipe["t400_ml"],
                "source_total_ml": recipe["total_ml"],
                "recipe_dispense_order": recipe["dispense_order"],
                "expected_visible_colored_order": stream[
                    "expected_visible_colored_order"
                ],
                "automated_stream_sequence": stream[
                    "observed_visible_color_sequence"
                ],
                "automated_stream_exact_order_match": stream[
                    "sequence_respects_recipe_order"
                ],
                "manually_reviewed_stream_observation": manual_note,
                "sample_frame": color["sample_frame"],
                "sample_time_s": color["sample_time_s"],
                "final_color_hue_median_opencv": color["hue_median_opencv"],
                "final_color_saturation_median": color["saturation_median"],
                "final_color_lab_l_median_8bit": color["lab_l_median_8bit"],
                "final_color_lab_a_median_8bit": color["lab_a_median_8bit"],
                "final_color_lab_b_median_8bit": color["lab_b_median_8bit"],
                "color_only_loo_nearest_recipe_id": color[
                    "loo_nearest_recipe_id"
                ],
                "color_only_loo_correct": color["loo_color_only_correct"],
                "meniscus_measurement_status": level["measurement_status"],
                "meniscus_y_range_px": (
                    f'{level["meniscus_y_min_px"]}-{level["meniscus_y_max_px"]}'
                ),
                "liquid_height_range_px": (
                    f'{level["liquid_height_min_px"]}-{level["liquid_height_max_px"]}'
                ),
                "meniscus_confidence": level["confidence"],
                "combined_cue_note": combined_note,
            }
        )
    return combined


def recipe_group_statistics(
    combined: list[dict[str, str]],
) -> dict[int, dict[str, object]]:
    group_stats = {}
    for recipe_id in range(5, 15):
        group = [
            row
            for row in combined
            if int(row["recipe_id"]) == recipe_id
            and row["carryover_suspect"] == "false"
        ]
        hues = [
            float(row["final_color_hue_median_opencv"])
            for row in group
            if row["final_color_hue_median_opencv"]
        ]
        correct = [
            row["color_only_loo_correct"] == "True"
            for row in group
            if row["color_only_loo_correct"]
        ]
        heights = {
            row["liquid_height_range_px"] for row in group
        }
        group_stats[recipe_id] = {
            "rows": group,
            "hue_median": statistics.median(hues) if hues else None,
            "color_correct": sum(correct),
            "color_count": len(correct),
            "height_ranges": heights,
        }
    return group_stats


def write_report(
    path: Path,
    combined: list[dict[str, str]],
) -> None:
    statistics = recipe_group_statistics(combined)
    stream_matches = sum(
        row["automated_stream_exact_order_match"] == "true" for row in combined
    )
    visible_levels = sum(
        row["meniscus_measurement_status"] == "visible" for row in combined
    )
    obscured_levels = len(combined) - visible_levels
    color_correct = sum(
        row["color_only_loo_correct"] == "True"
        for row in combined
        if row["color_only_loo_correct"]
    )
    color_tested = sum(bool(row["color_only_loo_correct"]) for row in combined)

    lines = [
        "# Video 5 combined recipe cues",
        "",
        "This report joins the nozzle-stream analysis, final-vial color "
        "measurements, and meniscus-height review by vial. Source recipe labels "
        "are retained as reference labels, not inferred results.",
        "",
        "## Overall result",
        "",
        f"- Joined records: {len(combined)} vials.",
        f"- Final-color exploratory leave-one-out assignments: "
        f"{color_correct}/{color_tested} clean candidate vials; this is a small, "
        "exploratory check, not validated accuracy.",
        f"- Automated stream sequences exactly matched the expected sequence for "
        f"{stream_matches}/{len(combined)} vials; the detector is not reliable "
        "enough to use this as a process or recipe score.",
        f"- Meniscus visible below the holder in {visible_levels}/{len(combined)} "
        f"selected frames; hidden in {obscured_levels}/{len(combined)}.",
        "- No combined classifier or confidence score is reported: the stream "
        "detector and many height intervals are not sufficiently reliable.",
        "",
        "## Manually reviewed stream evidence",
        "",
        "- Vial 2 (recipe 5): blue, then a mixed blue-orange appearance; not "
        "confirmed as a separate orange phase.",
        "- Vial 3 (recipe 5): green until 1:36, then green-brown until 1:59; "
        "tank colors remain ambiguous.",
        "- Vial 10 (recipe 8): blue through 7:23, no visible stream until 7:35, "
        "then light blue fading toward clear until 7:41.",
        "- Vials 11 and 12 (recipe 8): orange to green to blue, with no visible "
        "stop. This agrees qualitatively with the expected orange-to-blue order; "
        "green is treated as a transition color, not a third tank.",
        "- These five user-reviewed vials are the only manual stream observations "
        "included here. For other vials, the automated color sequence remains "
        "unverified.",
        "",
        "## What the three cues suggest",
        "",
        "### Recipes 5 and 8: same proportions, different total volume",
        "",
        "Their clean candidate final-color hues are close (recipe 5: "
        f"{statistics[5]['hue_median']:g}; recipe 8: "
        f"{statistics[8]['hue_median']:g} in OpenCV hue units), consistent with "
        "their equal component ratios. Recipe 5 samples have visible 70–96 px "
        "height ranges; recipe 8 menisci are hidden in a broad 137–195 px range. "
        "That suggests a coarse low-versus-higher fill distinction, but it does "
        "not provide calibrated volume or a trustworthy exact level measurement.",
        "",
        "### Recipes 7 and 14: both total 70 mL, blue-heavy versus clear-heavy",
        "",
        "The clean recipe 7 samples are strongly blue in the image (hues 98 and "
        "99); recipe 14 samples are more variable (hues 66 and 80). Both have "
        "the same broad holder-obscured height interval, and both are expected "
        "to show blue then clear, so level and stream order do not separate "
        "them. Final-vial color may help, but the two recipe 14 samples are not "
        "consistent enough for a dependable automatic decision.",
        "",
        "### Recipes 11 and 12: same total, contrasting colored proportions",
        "",
        "Both are labeled 70 mL and share the same obscured height interval. "
        "Their clean final-vial colors differ strongly in the image: recipe 11 "
        f"has median hue {statistics[11]['hue_median']:g}, versus "
        f"{statistics[12]['hue_median']:g} for recipe 12; the exploratory "
        f"color-only check assigned {statistics[11]['color_correct']}/"
        f"{statistics[11]['color_count']} and {statistics[12]['color_correct']}/"
        f"{statistics[12]['color_count']} clean candidates correctly. This is a "
        "promising visual distinction in this clip, but it is based on only two "
        "clean vials per recipe and is not validated. Automated stream output "
        "often misses one of the expected colors.",
        "",
        "### Remaining comparisons",
        "",
        "All source-labeled 60–80 mL cases have the same broad obscured level "
        "interval in this first pass. Their separation therefore depends mostly "
        "on final-vial color and, potentially, stream phase durations. The "
        "current stream detector does not measure those reliably. Recipe 6 and "
        "recipe 12 both look orange-heavy but have different totals; color alone "
        "can confuse them, while height only gives a coarse lower-versus-higher "
        "cue. Recipe 12 and recipe 13 also look similar in the current final "
        "color measurements despite different component mixtures.",
        "",
        "## Conclusion",
        "",
        "Combining the cues improves the qualitative picture but does not yet "
        "identify every recipe reliably. The strongest current use is coarse "
        "grouping: low versus higher fill for some comparisons, and visibly "
        "different final colors for recipes such as 11 versus 12. The manual "
        "stream checks help interpret transitions, but the automated stream "
        "labels should not be treated as ground truth. For dependable recipe "
        "identification, the meniscus needs a clearer view and height-to-volume "
        "calibration; stream phases need additional manual checks or a better "
        "detector.",
        "",
        "See `combined_recipe_cues.csv` for every joined vial record and its "
        "source measurements.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    combined = join_cues()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT_DIR / "combined_recipe_cues.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=FIELDS, extrasaction="raise")
        writer.writeheader()
        writer.writerows(combined)
    write_report(OUTPUT_DIR / "COMBINED_CUE_ANALYSIS.md", combined)
    print(f"Joined {len(combined)} vial records.")
    print(f"Outputs: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

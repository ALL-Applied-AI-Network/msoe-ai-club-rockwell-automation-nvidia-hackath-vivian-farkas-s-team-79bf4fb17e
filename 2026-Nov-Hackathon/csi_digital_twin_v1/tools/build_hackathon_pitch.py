import base64
import csv
import html
import subprocess
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "csi_vial_fill"
OUTPUT = DATA / "hackathon_pitch"
RECIPES_PATH = DATA / "video_5" / "labels" / "source" / "video5_vial_recipes.csv"
CUES_PATH = DATA / "unlabeled_video_analysis" / "unlabeled_video_cues.csv"
PHASES_PATH = DATA / "unlabeled_video_analysis" / "stream_phases.csv"
VIDEO_PATH = DATA / "video_4" / "video" / "vial_fill_video_4.mp4"
BLIND_FEATURES_PATH = (
    DATA / "video_5" / "analysis" / "blind_test" / "blind_feature_extraction.csv"
)
BLIND_PREDICTIONS_PATH = (
    DATA / "video_5" / "analysis" / "blind_test" / "blind_test_scored_predictions.csv"
)
STABLE_FRAMES_DIR = DATA / "video_5" / "analysis" / "stable_frames"
VIDEO5_COLOR_PATH = DATA / "video_5" / "analysis" / "vial_color_measurements.csv"
VIDEO5_LEVEL_PATH = DATA / "video_5" / "analysis" / "meniscus" / "meniscus_measurements.csv"
REFERENCE_GALLERY_PATH = OUTPUT / "video5_ten_recipe_reference_gallery.jpg"
UNLABELED_COLOR_GALLERY_PATH = OUTPUT / "videos1_4_all34_color_candidates.jpg"
GALLERY_PATH = OUTPUT / "video5_blind_candidate_groups.jpg"

WIDTH = 1280
HEIGHT = 720
FPS = 30
INK = (35, 38, 42)
BLUE = (255, 170, 72)
WHITE = (255, 255, 255)
PHASE_BGR = {
    "blue": (255, 170, 72),
    "orange": (78, 152, 242),
    "clear_candidate": (185, 185, 185),
}
PHASE_HEX = {
    "blue": "#48aaff",
    "orange": "#f0924f",
    "clear_candidate": "#b9bfc7",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


def load_recipes() -> list[dict[str, str]]:
    rows = read_csv(RECIPES_PATH)
    recipes: dict[int, dict[str, str]] = {}
    fields = (
        "type",
        "t100_ml",
        "t200_ml",
        "t400_ml",
        "total_ml",
        "dispense_order",
        "color_purpose",
    )
    for row in rows:
        recipe_id = int(row["recipe_id"])
        profile = {field: row[field] for field in fields}
        existing = recipes.setdefault(recipe_id, profile)
        if existing != profile:
            raise ValueError(f"Recipe {recipe_id} has inconsistent reference rows")
    expected_ids = list(range(5, 15))
    if sorted(recipes) != expected_ids:
        raise ValueError(f"Expected Video 5 recipe IDs {expected_ids}; found {sorted(recipes)}")
    result = []
    for recipe_id, profile in sorted(recipes.items()):
        recipe = {"recipe_id": str(recipe_id), **profile}
        for field in ("t100_ml", "t200_ml", "t400_ml", "total_ml"):
            recipe[field] = recipe[field] or "0"
        component_total = sum(int(recipe[key]) for key in ("t100_ml", "t200_ml", "t400_ml"))
        if component_total != int(recipe["total_ml"]):
            raise ValueError(f"Recipe {recipe_id} component volumes do not sum to total")
        result.append(recipe)
    return result


def write_recipe_csv(recipes: list[dict[str, str]]) -> None:
    output_path = OUTPUT / "recipe_reference_data.csv"
    fields = [
        "recipe_id",
        "type",
        "t100_ml",
        "t200_ml",
        "t400_ml",
        "total_ml",
        "dispense_order",
        "color_purpose",
        "source",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        for recipe in recipes:
            writer.writerow(
                {
                    **{field: recipe[field] for field in fields if field != "source"},
                    "source": "Video 5 labeled reference; source recipe table",
                }
            )


def recipe_chart(recipes: list[dict[str, str]]) -> str:
    width, height = 1000, 400
    left, top, row_h, bar_h, scale = 86, 34, 32, 24, 7.3
    tank_styles = (
        ("t100_ml", "T100 · clear", "#e7edf2", "#344452"),
        ("t200_ml", "T200 · orange", "#ed8a32", "#ffffff"),
        ("t400_ml", "T400 · blue", "#318bd2", "#ffffff"),
    )
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Recipe component volumes">',
        '<text x="0" y="18" class="axis">Component volume by tank (mL); colors follow the Video 5 tank legend</text>',
    ]
    for index, recipe in enumerate(recipes):
        y = top + index * row_h
        parts.append(f'<text x="0" y="{y + 13}" class="label">R{recipe["recipe_id"]}</text>')
        x = left
        for key, tank_name, color, text_color in tank_styles:
            volume = int(recipe[key])
            if volume:
                w = volume * scale
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{w}" height="{bar_h}" rx="3" fill="{color}" stroke="#c3cdd5" stroke-width="0.7"/>'
                )
                if w >= 27:
                    parts.append(
                        f'<text x="{x + w / 2}" y="{y + 12}" text-anchor="middle" fill="{text_color}" class="inside">{volume}</text>'
                    )
                x += w
        parts.append(
            f'<text x="{x + 8}" y="{y + 13}" class="label">{recipe["total_ml"]} mL</text>'
        )
    legend_y = top + len(recipes) * row_h + 18
    for index, (_key, tank_name, color, _text_color) in enumerate(tank_styles):
        x = left + index * 190
        parts.append(f'<rect x="{x}" y="{legend_y}" width="15" height="13" rx="2" fill="{color}" stroke="#aab6c0"/>')
        parts.append(f'<text x="{x + 21}" y="{legend_y + 12}" class="axis">{tank_name}</text>')
    parts.append("</svg>")
    return "".join(parts)


def candidate_chart(cues: list[dict[str, str]]) -> tuple[str, dict[str, int]]:
    counts = {str(recipe_id): 0 for recipe_id in range(5, 15)}
    for row in cues:
        recipe_id = row["nearest_color_recipe_id"]
        if recipe_id in counts:
            counts[recipe_id] += 1
    width, height = 780, 330
    left, bottom, chart_h, bar_w, gap = 45, 267, 214, 43, 26
    max_count = max(counts.values(), default=1) or 1
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Nearest color recipe counts by vial">',
        '<text x="0" y="18" class="axis">Number of unlabeled vial samples whose nearest Video 5 color is this recipe</text>',
    ]
    for step in range(0, max_count + 1):
        y = bottom - (step / max_count) * chart_h
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - 10}" y2="{y:.1f}" stroke="#e5e9ee"/>')
        parts.append(f'<text x="{left - 15}" y="{y + 4:.1f}" text-anchor="end" class="axis">{step}</text>')
    for index, (recipe_id, count) in enumerate(counts.items()):
        x = left + 10 + index * (bar_w + gap)
        bar_h = count / max_count * chart_h
        y = bottom - bar_h
        parts.append(f'<rect x="{x}" y="{y:.1f}" width="{bar_w}" height="{bar_h:.1f}" rx="5" fill="#287c9e"/>')
        parts.append(f'<text x="{x + bar_w / 2}" y="{y - 7:.1f}" text-anchor="middle" class="label">{count}</text>')
        parts.append(f'<text x="{x + bar_w / 2}" y="{bottom + 22}" text-anchor="middle" class="axis">{recipe_id}</text>')
    parts.extend(
        [
            f'<text x="{width / 2}" y="{height - 5}" text-anchor="middle" class="axis">Recipe ID (color-only nearest match)</text>',
            "</svg>",
        ]
    )
    return "".join(parts), counts


def make_recipe_reference_gallery(recipes: list[dict[str, str]]) -> str:
    references = {
        int(row["recipe_id"]): row
        for row in read_csv(VIDEO5_COLOR_PATH)
        if row["color_reference_eligible"].lower() == "true"
    }
    image_width, columns = 2000, 2
    margin, gap_x, gap_y = 30, 14, 12
    card_width = (image_width - margin * 2 - gap_x * (columns - 1)) // columns
    card_height = 320
    rows = (len(recipes) + columns - 1) // columns
    image_height = 82 + rows * card_height + (rows - 1) * gap_y + 54
    gallery = np.full((image_height, image_width, 3), (248, 250, 252), dtype=np.uint8)
    cv2.putText(
        gallery,
        "VIDEO 5 LABELED COLOR REFERENCES | ONE CLEAN REPEAT PER RECIPE",
        (margin, 42),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (37, 47, 58),
        2,
        cv2.LINE_AA,
    )
    for index, recipe in enumerate(recipes):
        recipe_id = int(recipe["recipe_id"])
        reference = references.get(recipe_id)
        if reference is None:
            raise ValueError(f"Missing clean color reference for recipe {recipe_id}.")
        frame_path = STABLE_FRAMES_DIR / (
            f"vial_{int(reference['vial']):02d}_frame_{int(reference['sample_frame']):06d}.jpg"
        )
        frame = cv2.imread(str(frame_path))
        if frame is None:
            raise OSError(f"Could not read recipe reference frame: {frame_path}")
        column, row = index % columns, index // columns
        x = margin + column * (card_width + gap_x)
        y = 82 + row * (card_height + gap_y)
        cv2.rectangle(gallery, (x, y), (x + card_width, y + card_height), (255, 255, 255), -1)
        cv2.rectangle(gallery, (x, y), (x + card_width, y + card_height), (218, 226, 232), 1)
        cv2.putText(
            gallery,
            f"RECIPE {recipe_id} | {recipe['total_ml']} mL",
            (x + 14, y + 31),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.92,
            (37, 47, 58),
            2,
            cv2.LINE_AA,
        )
        crop = frame[165:415, 245:390]
        thumb_w, thumb_h = 180, 250
        thumbnail = cv2.resize(crop, (thumb_w, thumb_h), interpolation=cv2.INTER_AREA)
        thumb_x, thumb_y = x + 16, y + 52
        gallery[thumb_y : thumb_y + thumb_h, thumb_x : thumb_x + thumb_w] = thumbnail
        cv2.rectangle(
            gallery,
            (thumb_x, thumb_y),
            (thumb_x + thumb_w - 1, thumb_y + thumb_h - 1),
            (202, 212, 220),
            1,
        )
        details_x = thumb_x + thumb_w + 20
        details = [
            f"T100 clear: {recipe['t100_ml']} mL",
            f"T200 orange: {recipe['t200_ml']} mL",
            f"T400 blue: {recipe['t400_ml']} mL",
            f"Vial {reference['vial']} reference",
        ]
        for detail_index, detail in enumerate(details):
            cv2.putText(
                gallery,
                detail,
                (details_x, y + 105 + detail_index * 43),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.72,
                (52, 62, 73),
                1,
                cv2.LINE_AA,
            )
    cv2.putText(
        gallery,
        "These are labeled Video 5 reference examples; color appearance can shift with lighting, level, mixing, and camera conditions.",
        (margin, image_height - 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (70, 83, 96),
        1,
        cv2.LINE_AA,
    )
    if not cv2.imwrite(str(REFERENCE_GALLERY_PATH), gallery, [cv2.IMWRITE_JPEG_QUALITY, 94]):
        raise OSError(f"Could not save recipe reference gallery: {REFERENCE_GALLERY_PATH}")
    return base64.b64encode(REFERENCE_GALLERY_PATH.read_bytes()).decode("ascii")


def make_unlabeled_color_gallery(cues: list[dict[str, str]]) -> str:
    image_width, columns = 2000, 6
    margin, gap_x, gap_y = 24, 12, 8
    card_width = (image_width - margin * 2 - gap_x * (columns - 1)) // columns
    card_height = 116
    rows = (len(cues) + columns - 1) // columns
    image_height = 76 + rows * card_height + (rows - 1) * gap_y + 64
    gallery = np.full((image_height, image_width, 3), (248, 250, 252), dtype=np.uint8)
    cv2.putText(
        gallery,
        "VIDEOS 1-4 | 34 UNLABELED VIALS | NEAREST COLOR-REFERENCE CANDIDATES",
        (margin, 37),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.73,
        (37, 47, 58),
        2,
        cv2.LINE_AA,
    )
    captures: dict[str, cv2.VideoCapture] = {}
    try:
        for index, cue in enumerate(cues):
            video_path = cue["video_path"]
            capture = captures.get(video_path)
            if capture is None:
                capture = cv2.VideoCapture(video_path)
                if not capture.isOpened():
                    raise OSError(f"Could not open source video: {video_path}")
                captures[video_path] = capture
            capture.set(cv2.CAP_PROP_POS_FRAMES, int(cue["last_stable_sample_frame"]))
            ok, frame = capture.read()
            if not ok:
                raise OSError(
                    f"Could not decode Video {cue['video_id']} vial {cue['vial']} "
                    f"at frame {cue['last_stable_sample_frame']}"
                )
            column, row = index % columns, index // columns
            x = margin + column * (card_width + gap_x)
            y = 76 + row * (card_height + gap_y)
            cv2.rectangle(gallery, (x, y), (x + card_width, y + card_height), (255, 255, 255), -1)
            cv2.rectangle(gallery, (x, y), (x + card_width, y + card_height), (218, 226, 232), 1)
            crop = frame[165:415, 245:390]
            thumb_w, thumb_h = 72, 92
            thumbnail = cv2.resize(crop, (thumb_w, thumb_h), interpolation=cv2.INTER_AREA)
            thumb_x, thumb_y = x + 10, y + 12
            gallery[thumb_y : thumb_y + thumb_h, thumb_x : thumb_x + thumb_w] = thumbnail
            cv2.rectangle(
                gallery,
                (thumb_x, thumb_y),
                (thumb_x + thumb_w - 1, thumb_y + thumb_h - 1),
                (202, 212, 220),
                1,
            )
            text_x = thumb_x + thumb_w + 13
            first = f"V{cue['video_id']}-{int(cue['vial']):02d} | nearest R{cue['nearest_color_recipe_id']}"
            second = f"Lab distance: {float(cue['nearest_color_distance']):.1f}"
            third = f"Next: R{cue['second_color_recipe_id']} ({float(cue['second_color_distance']):.1f})"
            for text_index, text in enumerate((first, second, third)):
                cv2.putText(
                    gallery,
                    text,
                    (text_x, y + 40 + text_index * 29),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.39,
                    (37, 47, 58),
                    1,
                    cv2.LINE_AA,
                )
    finally:
        for capture in captures.values():
            capture.release()
    cv2.putText(
        gallery,
        "Lower Lab distance means closer to the Video 5 color reference; it is a ranking distance, NOT a probability or confirmed recipe.",
        (margin, image_height - 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.47,
        (70, 83, 96),
        1,
        cv2.LINE_AA,
    )
    if not cv2.imwrite(
        str(UNLABELED_COLOR_GALLERY_PATH),
        gallery,
        [cv2.IMWRITE_JPEG_QUALITY, 94],
    ):
        raise OSError(f"Could not save unlabeled color gallery: {UNLABELED_COLOR_GALLERY_PATH}")
    return base64.b64encode(UNLABELED_COLOR_GALLERY_PATH.read_bytes()).decode("ascii")


def candidate_summary_table(cues: list[dict[str, str]]) -> str:
    rows = []
    for cue in cues:
        if cue["liquid_level_visibility"] == "visible_low_candidate":
            level = "Low-fill candidate"
            integrated = "Level conflict"
        else:
            level = "Hidden / uncertain"
            integrated = "Color-led"
        stream = cue["stream_color_sequence_candidate"].replace(">", " > ").replace("_", " ")
        if stream == "none detected":
            stream = "No phase detected"
        rows.append(
            "<tr>"
            f"<td>V{cue['video_id']}-{int(cue['vial']):02d}</td>"
            f"<td>R{cue['nearest_color_recipe_id']} <small>(next R{cue['second_color_recipe_id']})</small></td>"
            f"<td>{html.escape(stream)}</td>"
            f"<td>{html.escape(level)}</td>"
            f"<td>{html.escape(integrated)}</td>"
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table class="candidate-table">'
        "<thead><tr><th>Vial</th><th>Color candidate</th><th>Detected stream appearance</th>"
        "<th>Level</th><th>Overall read</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def make_candidate_gallery() -> str:
    groups = [
        ("Likely Recipe 5", [2], False),
        ("Likely Recipe 6", [6], False),
        ("Likely Recipe 7", [8, 9], False),
        ("Likely Recipe 8", [12], False),
        ("Likely Recipe 9", [14, 15], False),
        ("Likely Recipe 10", [17, 18], False),
        ("Likely Recipe 11", [20, 21], False),
        ("Unclear: R5 / R9", [3], True),
        ("Unclear: R8 / R9", [11], True),
        ("Unclear: R5 / R6 / R12", [5, 23, 24], True),
        ("Unclear: R5 / R13", [26, 27], True),
        ("Unclear: R7 / R14", [30], True),
        ("Unresolved: R5 vs R10", [29], True),
    ]
    features = {
        int(row["vial"]): row for row in read_csv(BLIND_FEATURES_PATH)
    }
    predictions = {
        int(row["vial"]): row for row in read_csv(BLIND_PREDICTIONS_PATH)
    }
    clean_vials = {
        int(row["vial"])
        for row in predictions.values()
        if row["scored_in_clean_subset"] == "true"
    }
    grouped_vials = [vial for _title, vial_group, _ambiguous in groups for vial in vial_group]
    if len(grouped_vials) != 20 or set(grouped_vials) != clean_vials:
        raise ValueError("Candidate gallery must contain each of the 20 clean vials once.")
    if len(grouped_vials) != len(set(grouped_vials)):
        raise ValueError("A clean vial appears in more than one candidate group.")

    image_width = 1800
    columns = 3
    rows = (len(groups) + columns - 1) // columns
    margin, gap_x, gap_y = 30, 14, 10
    card_width = (image_width - margin * 2 - gap_x * (columns - 1)) // columns
    card_height = 178
    image_height = 47 + rows * card_height + (rows - 1) * gap_y + 60
    image = np.full((image_height, image_width, 3), (248, 250, 252), dtype=np.uint8)
    cv2.putText(
        image,
        "20 CLEAN REPEAT VIALS  |  GROUPED BY BLIND-TEST CANDIDATES",
        (margin, 31),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (37, 47, 58),
        2,
        cv2.LINE_AA,
    )
    likely_color = (56, 125, 80)
    uncertain_color = (41, 126, 158)

    for group_index, (title, vials, ambiguous) in enumerate(groups):
        column = group_index % columns
        row = group_index // columns
        x = margin + column * (card_width + gap_x)
        y = 47 + row * (card_height + gap_y)
        accent = uncertain_color if ambiguous else likely_color
        cv2.rectangle(
            image,
            (x, y),
            (x + card_width, y + card_height),
            (255, 255, 255),
            -1,
        )
        cv2.rectangle(
            image,
            (x, y),
            (x + card_width, y + card_height),
            (218, 226, 232),
            1,
        )
        cv2.rectangle(image, (x, y), (x + card_width, y + 5), accent, -1)
        cv2.putText(
            image,
            title.upper(),
            (x + 12, y + 29),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            accent,
            1,
            cv2.LINE_AA,
        )

        thumb_w, thumb_h = 70, 112
        item_w, item_gap = 104, 8
        total_items_w = len(vials) * item_w + max(0, len(vials) - 1) * item_gap
        item_x0 = x + (card_width - total_items_w) // 2
        for item_index, vial in enumerate(vials):
            feature = features.get(vial)
            prediction = predictions.get(vial)
            if feature is None or prediction is None:
                raise ValueError(f"Missing blind-test data for vial {vial}.")
            source = STABLE_FRAMES_DIR / (
                f"vial_{vial:02d}_frame_{int(feature['sample_frame']):06d}.jpg"
            )
            frame = cv2.imread(str(source))
            if frame is None:
                raise OSError(f"Could not read stable reference frame: {source}")
            crop = frame[190:415, 250:385]
            thumbnail = cv2.resize(
                crop,
                (thumb_w, thumb_h),
                interpolation=cv2.INTER_AREA,
            )
            item_x = item_x0 + item_index * (item_w + item_gap)
            thumb_x = item_x + (item_w - thumb_w) // 2
            thumb_y = y + 39
            image[thumb_y : thumb_y + thumb_h, thumb_x : thumb_x + thumb_w] = thumbnail
            cv2.rectangle(
                image,
                (thumb_x, thumb_y),
                (thumb_x + thumb_w - 1, thumb_y + thumb_h - 1),
                (202, 212, 220),
                1,
            )
            color_id = prediction["color_prediction"] or "—"
            combined_id = prediction["combined_prediction"] or "—"
            label = f"V{vial:02d}  C{color_id}/F{combined_id}"
            text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.31, 1)[0]
            label_x = item_x + max(0, (item_w - text_size[0]) // 2)
            cv2.putText(
                image,
                label,
                (label_x, y + 170),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.31,
                (52, 62, 73),
                1,
                cv2.LINE_AA,
            )

    footer_y = image_height - 45
    cv2.putText(
        image,
        "C = color-only top match   F = fused color/stream/visible-level rank   |   Candidates only; not confirmed recipe IDs.",
        (margin, footer_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.49,
        (70, 83, 96),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        image,
        "First vial from each fixed 3-vial block excluded as transition/carryover-suspect. Source frames use the final stable image.",
        (margin, image_height - 16),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.43,
        (95, 106, 117),
        1,
        cv2.LINE_AA,
    )
    if not cv2.imwrite(str(GALLERY_PATH), image, [cv2.IMWRITE_JPEG_QUALITY, 94]):
        raise OSError(f"Could not save candidate gallery: {GALLERY_PATH}")
    return base64.b64encode(GALLERY_PATH.read_bytes()).decode("ascii")


def make_reference_level_comparison(
    recipes: list[dict[str, str]],
) -> str:
    examples = [
        (5, 2),
        (8, 11),
        (9, 14),
    ]
    color_rows = {int(row["vial"]): row for row in read_csv(VIDEO5_COLOR_PATH)}
    level_rows = {int(row["vial"]): row for row in read_csv(VIDEO5_LEVEL_PATH)}
    recipe_by_id = {int(row["recipe_id"]): row for row in recipes}
    cards = []
    for recipe_id, vial in examples:
        recipe = recipe_by_id[recipe_id]
        color_row = color_rows[vial]
        level_row = level_rows[vial]
        if int(color_row["recipe_id"]) != recipe_id or int(level_row["recipe_id"]) != recipe_id:
            raise ValueError(f"Reference image labels disagree for vial {vial}.")
        frame_path = STABLE_FRAMES_DIR / (
            f"vial_{vial:02d}_frame_{int(color_row['sample_frame']):06d}.jpg"
        )
        frame = cv2.imread(str(frame_path))
        if frame is None:
            raise OSError(f"Could not read recipe comparison frame: {frame_path}")
        crop_y0, crop_y1 = 165, 415
        crop = frame[crop_y0:crop_y1, 245:390].copy()
        if level_row["measurement_status"] == "visible":
            y0 = int(level_row["meniscus_y_min_px"]) - crop_y0
            y1 = int(level_row["meniscus_y_max_px"]) - crop_y0
            cv2.line(crop, (20, y0), (120, y0), (66, 180, 90), 2, cv2.LINE_AA)
            cv2.line(crop, (20, y1), (120, y1), (66, 180, 90), 2, cv2.LINE_AA)
        else:
            y0 = int(level_row["meniscus_y_min_px"]) - crop_y0
            y1 = int(level_row["meniscus_y_max_px"]) - crop_y0
            cv2.line(crop, (10, y0), (10, y1), (38, 156, 228), 2, cv2.LINE_AA)
            cv2.line(crop, (5, y0), (17, y0), (38, 156, 228), 2, cv2.LINE_AA)
            cv2.line(crop, (5, y1), (17, y1), (38, 156, 228), 2, cv2.LINE_AA)
        ok, encoded = cv2.imencode(
            ".jpg",
            crop,
            [cv2.IMWRITE_JPEG_QUALITY, 90],
        )
        if not ok:
            raise OSError(f"Could not encode recipe comparison image for vial {vial}.")
        image_uri = "data:image/jpeg;base64," + base64.b64encode(encoded).decode("ascii")
        components = " + ".join(
            f'{tank}: {recipe[field]} mL'
            for tank, field in (
                ("T100", "t100_ml"),
                ("T200", "t200_ml"),
                ("T400", "t400_ml"),
            )
            if int(recipe[field])
        )
        if level_row["measurement_status"] == "visible":
            level_note = (
                f'Visible meniscus; estimated image height '
                f'{level_row["liquid_height_min_px"]}–{level_row["liquid_height_max_px"]} px.'
            )
        else:
            level_note = "Meniscus range is behind the holder; not directly visible."
        cards.append(
            f'<article class="level-card"><img src="{image_uri}" alt="Video 5 vial {vial}, Recipe {recipe_id} reference frame">'
            f'<div><h3>Recipe {recipe_id} · {recipe["total_ml"]} mL</h3>'
            f'<p>{html.escape(components)}</p><p class="level-note">{html.escape(level_note)}</p></div></article>'
        )
    return "".join(cards)


def format_time(seconds: float) -> str:
    minutes = int(seconds // 60)
    remaining = seconds - minutes * 60
    return f"{minutes}:{remaining:05.2f}"


def load_video4_phases() -> dict[int, list[dict[str, str]]]:
    phases = read_csv(PHASES_PATH)
    result: dict[int, list[dict[str, str]]] = {}
    for row in phases:
        if row["video_id"] == "4" and int(row["vial"]) in (4, 5, 6):
            result.setdefault(int(row["vial"]), []).append(row)
    for rows in result.values():
        rows.sort(key=lambda row: float(row["start_time_s"]))
    if sorted(result) != [4, 5, 6]:
        raise ValueError("Expected heuristic stream phase data for Video 4 vials 4–6")
    return result


def put_text(
    image: np.ndarray,
    text: str,
    point: tuple[int, int],
    scale: float = 0.62,
    color: tuple[int, int, int] = WHITE,
    thickness: int = 1,
) -> None:
    cv2.putText(image, text, point, cv2.FONT_HERSHEY_SIMPLEX, scale, (18, 22, 27), 4, cv2.LINE_AA)
    cv2.putText(image, text, point, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)


def make_title_card(
    writer: cv2.VideoWriter,
    title: str,
    subtitle: str,
    note: str,
    frames: int,
) -> None:
    image = np.full((HEIGHT, WIDTH, 3), INK, dtype=np.uint8)
    cv2.rectangle(image, (0, 0), (16, HEIGHT), BLUE, -1)
    put_text(image, title, (76, 195), 1.15, WHITE, 2)
    put_text(image, subtitle, (78, 260), 0.72, (210, 220, 228), 1)
    put_text(image, note, (78, 600), 0.56, (184, 197, 207), 1)
    for _ in range(frames):
        writer.write(image)


def make_stream_clip(phases_by_vial: dict[int, list[dict[str, str]]]) -> None:
    capture = cv2.VideoCapture(str(VIDEO_PATH))
    if not capture.isOpened():
        raise OSError(f"Could not open source video: {VIDEO_PATH}")
    source_fps = capture.get(cv2.CAP_PROP_FPS)
    if source_fps <= 0:
        capture.release()
        raise ValueError("Source video reports an invalid frame rate")
    raw_path = OUTPUT / "_video4_stream_analysis_raw.mp4"
    output_path = OUTPUT / "video4_stream_analysis_demo.mp4"
    writer = cv2.VideoWriter(
        str(raw_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        FPS,
        (WIDTH, HEIGHT),
    )
    if not writer.isOpened():
        capture.release()
        raise OSError(f"Could not create demo clip: {output_path}")
    try:
        make_title_card(
            writer,
            "STREAM PHASE REVIEW",
            "Unlabeled Video 4 • observed appearance candidates, not confirmed tank identities",
            "Source footage: Video 4 | Phase labels: automated hue/saturation heuristic",
            2 * FPS,
        )
        sample_ranges = {4: (167.0, 180.0), 5: (234.0, 245.0), 6: (299.0, 310.0)}
        for vial, (start_s, end_s) in sample_ranges.items():
            phases = phases_by_vial[vial]
            phase_names = [row["observed_color_nearest"] for row in phases]
            sequence = " > ".join(name.upper() for name in phase_names)
            capture.set(cv2.CAP_PROP_POS_FRAMES, round(start_s * source_fps))
            for frame_index in range(round(start_s * source_fps), round(end_s * source_fps)):
                ok, frame = capture.read()
                if not ok:
                    raise OSError(f"Could not decode Video 4 frame {frame_index}")
                canvas = np.full((HEIGHT, WIDTH, 3), INK, dtype=np.uint8)
                resized = cv2.resize(frame, (800, 600), interpolation=cv2.INTER_AREA)
                canvas[60:660, 30:830] = resized
                panel_x = 865
                put_text(canvas, f"VIDEO 4  /  VIAL {vial}", (panel_x, 93), 0.72, WHITE, 2)
                put_text(canvas, "HEURISTIC STREAM SEQUENCE", (panel_x, 150), 0.47, (180, 195, 207), 1)
                put_text(canvas, sequence, (panel_x, 187), 0.58, WHITE, 1)

                t = frame_index / source_fps
                time_text = format_time(t)
                put_text(canvas, f"SOURCE TIME  {time_text}", (panel_x, 239), 0.56, (215, 225, 233), 1)
                put_text(canvas, "DETECTED PHASE WINDOWS", (panel_x, 306), 0.47, (180, 195, 207), 1)
                phase_x, phase_y, phase_w = panel_x, 328, 350
                first = min(float(row["start_time_s"]) for row in phases)
                last = max(float(row["end_time_s"]) for row in phases)
                span = last - first
                current_marker = phase_x + max(0, min(1, (t - first) / span)) * phase_w
                for phase in phases:
                    x1 = phase_x + (float(phase["start_time_s"]) - first) / span * phase_w
                    x2 = phase_x + (float(phase["end_time_s"]) - first) / span * phase_w
                    color = PHASE_BGR.get(phase["observed_color_nearest"], (130, 130, 130))
                    cv2.rectangle(canvas, (round(x1), phase_y), (max(round(x2), round(x1) + 2), phase_y + 19), color, -1)
                cv2.line(canvas, (round(current_marker), phase_y - 6), (round(current_marker), phase_y + 27), WHITE, 2)
                put_text(canvas, format_time(first), (phase_x, phase_y + 44), 0.42, (195, 206, 215), 1)
                put_text(canvas, format_time(last), (phase_x + 254, phase_y + 44), 0.42, (195, 206, 215), 1)

                y = 425
                for phase in phases:
                    name = phase["observed_color_nearest"].replace("_", " ").upper()
                    start = format_time(float(phase["start_time_s"]))
                    end = format_time(float(phase["end_time_s"]))
                    active = float(phase["start_time_s"]) <= t <= float(phase["end_time_s"])
                    color = PHASE_BGR.get(phase["observed_color_nearest"], (130, 130, 130))
                    cv2.circle(canvas, (panel_x + 8, y - 6), 7, color, -1)
                    put_text(
                        canvas,
                        f"{name}  {start}-{end}",
                        (panel_x + 25, y),
                        0.45,
                        WHITE if active else (183, 195, 204),
                        1,
                    )
                    y += 34
                cv2.line(canvas, (panel_x, 555), (1228, 555), (75, 85, 96), 1)
                put_text(canvas, "Appearance class only; not a validated recipe or tank ID.", (panel_x, 594), 0.42, (198, 208, 216), 1)
                put_text(canvas, "Detector can miss clear flow or short transitions.", (panel_x, 624), 0.42, (198, 208, 216), 1)
                writer.write(canvas)
        make_title_card(
            writer,
            "WHAT THE CLIP SHOWS",
            "Repeated blue → orange → blue candidates in vials 4–6",
            "Next step: manually verify phases and align with an independent recipe record.",
            3 * FPS,
        )
    finally:
        writer.release()
        capture.release()
    import imageio_ffmpeg

    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-y",
            "-i",
            str(raw_path),
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    raw_path.unlink()
    (OUTPUT / "video4_stream_analysis_demo.webm").unlink(missing_ok=True)


def slide_html(title: str, eyebrow: str, content: str, note: str) -> str:
    return (
        f'<section class="slide"><div class="eyebrow">{html.escape(eyebrow)}</div>'
        f'<h1>{title}</h1><div class="content">{content}</div>'
        f'<div class="presenter-note"><b>Say:</b> {html.escape(note)}</div></section>'
    )


def make_pitch_html(
    recipes: list[dict[str, str]],
    cues: list[dict[str, str]],
    reference_gallery_base64: str,
    unlabeled_gallery_base64: str,
    level_comparisons: str,
) -> None:
    held_out = read_csv(BLIND_PREDICTIONS_PATH)
    clean = [row for row in held_out if row["scored_in_clean_subset"] == "true"]

    def top_k_accuracy(cue: str, k: int, rows: list[dict[str, str]]) -> tuple[int, int]:
        correct = 0
        for row in rows:
            ranked = row[f"{cue}_prediction"] if k == 1 else row[f"{cue}_top2"]
            candidates = ranked.split(">") if ranked else []
            if row["true_recipe_id"] in candidates[:k]:
                correct += 1
        return correct, len(rows)

    color_top1 = top_k_accuracy("color", 1, clean)
    color_top2 = top_k_accuracy("color", 2, clean)
    stream_top1 = top_k_accuracy("stream", 1, clean)
    stream_top2 = top_k_accuracy("stream", 2, clean)
    combined_top1 = top_k_accuracy("combined", 1, clean)
    combined_top2 = top_k_accuracy("combined", 2, clean)
    visible_level = [
        row for row in clean if row["level_prediction"] and row["level_prediction"] != "—"
    ]
    level_top1 = top_k_accuracy("level", 1, visible_level)
    level_top2 = top_k_accuracy("level", 2, visible_level)
    visible_unlabeled = sum(
        row["liquid_level_visibility"] == "visible_low_candidate" for row in cues
    )
    hidden_unlabeled = len(cues) - visible_unlabeled
    no_stream = sum(row["stream_color_sequence_candidate"] == "none_detected" for row in cues)
    phase_count = len(read_csv(PHASES_PATH))
    recipe_svg = recipe_chart(recipes)
    clip_base64 = base64.b64encode(
        (OUTPUT / "video4_stream_analysis_demo.mp4").read_bytes()
    ).decode("ascii")
    embedded_video = (
        f'<video controls preload="metadata" '
        f'src="data:video/mp4;base64,{clip_base64}"></video>'
    )
    slides = [
        slide_html(
            "Three visual clues. One recipe search.",
            "CSI DIGITAL TWIN • EXPLAINABLE HACKATHON PROTOTYPE",
            '<div class="hero"><div><p class="lead">Can footage narrow down which recipe filled each vial?</p>'
            '<p class="muted">1. Finished-liquid color<br>2. Liquid level<br>3. Orange/blue stream sequence</p>'
            '<p class="callout">We compare 34 unlabeled vials from Videos 1–4 with 10 labeled recipe references from Video 5.</p></div>'
            '<div class="hero-stat"><strong>3</strong><span>separate methods, then an evidence review</span></div></div>',
            "We will show what each of the three methods can tell us, where it fails, and then the candidate recipe for every one of the 34 unlabeled vials.",
        ),
        slide_html(
            "Our reference: 10 labeled recipes",
            "VIDEO 5 • ONE CLEAN VIAL IMAGE PER RECIPE",
            f'<div class="reference-gallery-wrap"><a href="video5_ten_recipe_reference_gallery.jpg" target="_blank" rel="noopener" aria-label="Open full-size ten recipe reference image"><img class="reference-gallery" src="data:image/jpeg;base64,{reference_gallery_base64}" alt="Ten clean labeled Video 5 vial images, one for each recipe from 5 through 14, with component volumes"></a></div>'
            '<div class="small">Each photo is paired with the labeled tank volumes. Open the full-size image to inspect all ten recipes.</div>',
            "These ten labeled Video 5 recipes are the reference library. Videos 1–4 have no authoritative recipe labels, so every ID we assign to them remains a candidate.",
        ),
        slide_html(
            "Method 1 | Match the finished-liquid color",
            "COLOR FINGERPRINT • NEAREST LAB-SPACE RECIPE REFERENCES",
            f'<div class="method-metrics"><b>Video 5 holdout:</b> color top-1 {color_top1[0]}/{color_top1[1]}, top-2 {color_top2[0]}/{color_top2[1]}'
            '<span>Within this one recording; not cross-run accuracy.</span></div>'
            f'<div class="gallery-wrap"><a href="videos1_4_all34_color_candidates.jpg" target="_blank" rel="noopener" aria-label="Open full-size color matches for all 34 unlabeled vials"><img class="candidate-gallery" src="data:image/jpeg;base64,{unlabeled_gallery_base64}" alt="Photographs and nearest and second-nearest recipe color candidates for all 34 vials in Videos 1 through 4"></a></div>'
            '<div class="small">Each vial photo shows its closest and next-closest color reference. Lower Lab distance means closer; it is not a probability. Examples of close alternatives: R14 can rank R7 second; an R12 test vial ranked R13 second.</div>',
            "Color is the most useful single cue so far: it ranked 16 of 20 clean Video 5 repeats first and 18 in the top two. But look at the runner-up too: similar colors and lighting make a single exact ID risky.",
        ),
        slide_html(
            "Method 2 | Use liquid level as a volume clue",
            "HEIGHT CUE • RECIPE VOLUME GRAPH AND VIAL EVIDENCE",
            f'<div class="recipe-reference-layout"><div class="chart recipe-chart">{recipe_svg}</div>'
            f'<div class="level-comparison-panel"><div class="comparison-heading">What the level images show</div>{level_comparisons}</div></div>'
            f'<div class="method-metrics"><b>Across the 34 unlabeled vials:</b> {visible_unlabeled} appear low; {hidden_unlabeled} have hidden/uncertain menisci. '
            f'<b>Separate Video 5 holdout:</b> level top-1 {level_top1[0]}/{level_top1[1]}, top-2 {level_top2[0]}/{level_top2[1]} when visible ({len(visible_level)}/{len(clean)} clean vials).</div>'
            '<div class="small">This flags a possible low-fill conflict for Video 3 vials 4–6, but does not produce recipe IDs. Holder obstruction and no pixel-to-mL calibration are the main limits.</div>',
            "Level only helped on a handful of visible examples. In the 34-vial set, just three are flagged as possibly low and the other 31 cannot be measured confidently; in the separate labeled holdout only four of twenty levels were visible.",
        ),
        slide_html(
            "Method 3 | Follow orange/blue stream sequences",
            "NOZZLE APPEARANCE • AUTOMATIC PHASES ARE HEURISTIC",
            f'<div class="video-wrap">{embedded_video}'
            f'<div><div class="metric-badge"><strong>{phase_count}</strong><span>heuristic phase detections across 34 vials</span></div>'
            f'<div class="metric-badge"><strong>{no_stream}/34</strong><span>with no orange/blue phase detected</span></div>'
            f'<p><b>Separate Video 5 holdout:</b> stream top-1 {stream_top1[0]}/{stream_top1[1]}, top-2 {stream_top2[0]}/{stream_top2[1]}.</p>'
            '<p>Sequences can reveal a repeated visual pattern, but a detected hue is not proof of which tank flowed.</p>'
            '<p class="warning">Short phases, reflections, mixed hues, clear flow, and missed intervals all affect the result. Video 5 exact expected colored order was observed in only 8 of 30 labeled windows.</p>'
            '<a href="video4_stream_analysis_demo.mp4" download>Open/download the annotated clip</a></div></div>',
            "The stream view adds process context, but it is the noisiest cue: the automatic labels are only appearance candidates. The held-out score and incomplete sequences show why we should not let it override the vial color by itself.",
        ),
        slide_html(
            "All 34 vials | current combined reading",
            "COLOR-LED CANDIDATES WITH STREAM AND LEVEL CAVEATS",
            f'<div class="method-metrics"><b>Separate Video 5 fusion check:</b> equal-weight cue-rank top-1 {combined_top1[0]}/{combined_top1[1]}, top-2 {combined_top2[0]}/{combined_top2[1]}. '
            'This is exploratory, not a probability and not a score for Videos 1–4.</div>'
            f'{candidate_summary_table(cues)}'
            '<div class="small">Videos 1–4 have no labels, so their accuracy cannot be measured. “Combined reading” keeps the color top match as a candidate, flags level conflicts, and reports stream evidence without forcing an unvalidated fusion score.</div>',
            "Here is the per-vial answer: color supplies a ranked candidate and runner-up; stream sequence and visible level add context. Video 2 consistently points to R11, Video 4 separates a blue-looking group from a dark teal group, and Video 3's R14-like color conflicts with low-level observations on its last three vials. These are hypotheses until checked against batch records.",
        ),
    ]
    chart_style = """
      .chart svg{width:100%;height:auto}.axis{font:23px Arial,sans-serif;fill:#637082}
      .label{font:bold 24px Arial,sans-serif;fill:#263443}.inside{font:bold 21px Arial,sans-serif}
    """
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Recipe Fingerprint Explorer — Hackathon Pitch</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;background:#111923;color:#263443;font:18px/1.45 Arial,sans-serif}}
.deck{{width:min(100vw,1280px);height:min(100vh,720px);margin:auto;position:relative;background:#f7f9fb;overflow:hidden}}
.slide{{display:none;height:100%;padding:48px 66px 72px;position:relative}} .slide.active{{display:flex;flex-direction:column}}
.eyebrow{{font-size:13px;font-weight:bold;letter-spacing:2px;color:#287c9e;margin-bottom:12px}}
h1{{font-size:38px;line-height:1.15;margin:0 0 26px;color:#172734}} .content{{flex:1;min-height:0}}
.lead{{font-size:32px;line-height:1.25;font-weight:bold;max-width:680px;margin:12px 0}}
.muted,.small{{color:#637082}}.small{{font-size:13px;margin-top:8px}}
.hero{{display:flex;align-items:center;justify-content:space-between;height:100%}} .hero-stat{{background:#e5f1f5;padding:30px;border-radius:20px;text-align:center;width:260px}}
.hero-stat strong{{display:block;font-size:72px;color:#287c9e}}.hero-stat span{{font-size:16px}}
.flow{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:56px 0 44px}}
.flow div{{background:white;border:1px solid #e1e7eb;padding:22px;border-radius:14px;min-height:170px;box-shadow:0 4px 14px #1727340a}}
.flow b{{display:block;font-size:30px;color:#287c9e;margin-bottom:20px}}.flow strong,.flow span{{display:block}}.flow span{{font-size:14px;color:#637082;margin-top:8px}}
.callout{{background:#e5f1f5;border-left:5px solid #287c9e;padding:15px 18px;border-radius:8px;margin-top:16px;font-size:16px}}
.chart{{background:white;border:1px solid #e1e7eb;border-radius:14px;padding:18px 22px}}
.recipe-reference-layout{{display:grid;grid-template-columns:1.03fr .97fr;gap:14px;align-items:stretch}}
.recipe-chart{{padding:8px 10px;display:flex;align-items:center}}
.comparison-heading{{font-size:15px;font-weight:bold;color:#287c9e;margin:0 0 6px}}
.level-comparison-panel{{display:flex;flex-direction:column;gap:6px;min-width:0}}
.level-card{{display:flex;align-items:center;gap:10px;flex:1;min-height:0;background:white;border:1px solid #e1e7eb;border-radius:10px;padding:6px 9px}}
.level-card img{{width:66px;height:110px;object-fit:contain;background:#f1f3f5;border-radius:5px}}
.level-card h3{{font-size:13px;margin:0 0 4px;color:#263443}}.level-card p{{font-size:11px;margin:3px 0;color:#526170}}
.level-card .level-note{{font-size:10px;color:#a35b22}}
.small{{color:#637082;font-size:12px;margin-top:8px}}
.candidate-chart{{max-width:900px;margin:0 auto}} .gallery-wrap{{display:flex;justify-content:center;max-height:490px;overflow:hidden}}.candidate-gallery{{display:block;width:100%;height:auto;max-height:490px;object-fit:contain;cursor:zoom-in}} .video-wrap{{display:grid;grid-template-columns:1.5fr 1fr;gap:26px;align-items:center}}
.reference-gallery-wrap{{display:flex;justify-content:center;max-height:500px;overflow:hidden}}.reference-gallery{{display:block;width:100%;height:auto;max-height:500px;object-fit:contain;cursor:zoom-in}}
.method-metrics{{background:#e5f1f5;border-left:4px solid #287c9e;border-radius:7px;padding:8px 12px;margin:8px 0;font-size:13px}}.method-metrics span{{display:block;color:#637082;font-size:11px}}
.metric-badge{{display:inline-flex;align-items:center;gap:10px;background:#e5f1f5;border-radius:8px;padding:8px 12px;margin:4px 8px 4px 0}}.metric-badge strong{{font-size:22px;color:#287c9e}}.metric-badge span{{font-size:12px}}
.table-wrap{{max-height:440px;overflow:auto;background:white;border:1px solid #e1e7eb;border-radius:9px}}.candidate-table{{width:100%;border-collapse:collapse;font-size:12px}}.candidate-table th{{position:sticky;top:0;background:#eaf1f5;text-align:left}}.candidate-table th,.candidate-table td{{padding:5px 7px;border-bottom:1px solid #e5e9ee;vertical-align:top}}.candidate-table th:first-child,.candidate-table td:first-child{{white-space:nowrap}}.candidate-table small{{color:#637082}}
video{{width:100%;border-radius:12px;background:#1f2933}} .video-wrap p{{font-size:16px}}.warning{{color:#a65122;background:#fff2e8;padding:12px;border-radius:8px}}
.video-wrap a{{color:#287c9e;font-weight:bold}}.columns{{display:grid;grid-template-columns:1fr 1fr;gap:40px}}
.columns h2{{font-size:21px;color:#287c9e}}.columns li{{margin:9px 0}}
.presenter-note{{position:absolute;bottom:15px;left:66px;right:340px;font-size:12px;color:#6b7683;border-top:1px solid #e2e7ec;padding-top:8px}}
.controls{{position:absolute;right:24px;bottom:16px;display:flex;gap:8px;align-items:center}}
button{{border:0;border-radius:8px;background:#287c9e;color:white;padding:10px 15px;font-size:15px;cursor:pointer}}
.count{{font-size:13px;color:#637082;min-width:55px;text-align:center}}
{chart_style}
@media(max-width:850px){{.deck{{width:100vw;height:100vh;overflow:auto}}.slide{{padding:30px 24px 96px}}h1{{font-size:30px}}.flow{{grid-template-columns:1fr 1fr;margin:20px 0}}.recipe-reference-layout{{grid-template-columns:1fr;gap:8px}}.recipe-chart{{padding:6px}}.recipe-chart svg{{max-height:300px}}.level-comparison-panel{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:4px}}.comparison-heading{{grid-column:1/-1}}.level-card{{flex-direction:column;justify-content:flex-start;gap:3px;padding:4px;text-align:center}}.level-card img{{width:54px;height:95px}}.level-card h3{{font-size:11px}}.level-card p{{font-size:9px}}.level-card .level-note{{font-size:9px}}.video-wrap,.columns{{grid-template-columns:1fr}}.video-wrap video{{max-height:210px;object-fit:contain}}.video-wrap p{{font-size:13px;margin:6px 0}}.video-wrap .warning{{font-size:12px;padding:8px}}.presenter-note{{left:24px;right:24px;bottom:62px}}.table-wrap{{max-height:440px}}.candidate-table{{font-size:10px}}.candidate-table th,.candidate-table td{{padding:4px 5px}}.candidate-table th:nth-child(5),.candidate-table td:nth-child(5){{display:none}}}}
@media(max-width:560px){{.recipe-reference-layout{{grid-template-columns:1fr;gap:6px}}.recipe-chart svg{{max-height:180px}}.level-comparison-panel{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:4px}}.comparison-heading{{grid-column:1/-1}}.level-card{{flex-direction:column;justify-content:flex-start;gap:2px;padding:3px;text-align:center}}.level-card img{{width:50px;height:80px}}.level-card h3{{font-size:10px}}.level-card p,.level-card .level-note{{font-size:8px;margin:2px 0}}.candidate-table{{font-size:9px}}.candidate-table th,.candidate-table td{{padding:4px 3px}}.candidate-table td:nth-child(3){{max-width:96px}}.method-metrics{{font-size:11px}}.gallery-wrap{{max-height:440px}}}}
</style></head><body><main class="deck">{''.join(slides)}
<nav class="controls"><button id="prev" aria-label="Previous slide">←</button><span class="count" id="count"></span><button id="next" aria-label="Next slide">→</button><button id="full">Full screen</button></nav>
</main><script>
const slides=[...document.querySelectorAll('.slide')];let current=0;
function show(n){{current=(n+slides.length)%slides.length;slides.forEach((s,i)=>s.classList.toggle('active',i===current));document.querySelector('#count').textContent=`${{current+1}} / ${{slides.length}}`;}}
document.querySelector('#prev').onclick=()=>show(current-1);document.querySelector('#next').onclick=()=>show(current+1);
document.querySelector('#full').onclick=()=>document.querySelector('.deck').requestFullscreen();
document.addEventListener('keydown',e=>{{if(e.key==='ArrowRight'||e.key===' ')show(current+1);if(e.key==='ArrowLeft')show(current-1);}});
show(0);
</script></body></html>"""
    (OUTPUT / "pitch.html").write_text(document, encoding="utf-8")


def write_pitch_script(recipes: list[dict[str, str]], cues: list[dict[str, str]]) -> None:
    recipe_ids = ", ".join(recipe["recipe_id"] for recipe in recipes)
    videos = sorted({row["video_id"] for row in cues}, key=int)
    script = f"""# Hackathon pitch: Recipe Fingerprint Explorer

## 2–3 minute talk track

“Can fill-line video help us narrow down which recipe went into each vial? We tested three visual methods against ten labeled reference recipes from Video 5: finished-liquid color, liquid level, and the orange/blue stream sequence.

First, color: each vial is compared in Lab color space with clean reference examples. In a small leave-one-vial-out test on Video 5, color ranked the right recipe first for 16 of 20 clean repeats, and in the top two for 18. This is the strongest single cue, but not a probability or cross-run accuracy. Recipe profiles can look similar—for example, an R14 sample had R7 as its next color match, and R12/R13 can appear as alternatives. Lighting, glass reflections, fill amount, and mixing all shift the image.

Second, level: the volume chart and vial photos show how fill height could separate mixtures with similar colors. But only 4 of 20 clean Video 5 holdout vials had visible menisci; among those, top-1 was 2 of 4 and top-2 was 4 of 4. In our 34 unlabeled Videos 1–4 samples, only three looked possibly low; the other 31 were obscured or uncertain. These are not calibrated milliliters.

Third, stream sequence: the detector finds orange/blue-looking phases, but reflections, short phases, clear flow, and missed intervals make the labels noisy. In the separate Video 5 holdout, stream ranked only 4 of 20 first and 10 of 20 in the top two. Treat it as process context—not tank identity.

Putting the evidence together, an exploratory equal-weight rank fusion reached 13 of 20 top-1 and 18 of 20 top-2 on the same small Video 5 test. For Videos 1–4, we show the nearest color candidate and runner-up alongside stream and level observations for every one of the {len(cues)} vials. Because those videos have no recipe labels, we cannot calculate their accuracy. The result is a transparent shortlist, not confirmed recipe IDs.”

## Demo sequence

1. Show the ten labeled Video 5 vial photos as the comparison library.
2. Color: show all 34 vial photos, the nearest color candidate and the runner-up; explain that Lab distance is not probability.
3. Level: use the recipe volume bars and example vial images; point out that three of 34 unlabeled vials are only qualitative low-level candidates and 31 are obscured/uncertain.
4. Stream: play the annotated Video 4 clip and explain that phase colors are heuristic appearances, not verified tank identities.
5. Finish on the all-34 table. The listed recipe is a color-led candidate, qualified by stream and level evidence; it is not a scored fusion or confirmed label.

## Evidence boundary

- Videos 1–4 have no authoritative recipe IDs in the provided dataset.
- Video 5 contains the labeled reference recipes ({recipe_ids}).
- The color, level, stream, and equal-weight fusion scores are a small within-Video-5 leave-one-vial-out exercise, not cross-day or production validation.
- Stream-phase classes are heuristic; a detected color name does not identify a tank or confirm dispensing order.
- Most meniscus observations are obscured and none have pixel-to-volume calibration.
- Color distances are relative rankings, not probabilities. Do not describe any Videos 1–4 candidate ID as ground truth.
"""
    (OUTPUT / "PITCH_SCRIPT.md").write_text(script, encoding="utf-8")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    recipes = load_recipes()
    cues = read_csv(CUES_PATH)
    if len(cues) != 34:
        raise ValueError(f"Expected 34 analyzed vial records; found {len(cues)}")
    write_recipe_csv(recipes)
    make_stream_clip(load_video4_phases())
    reference_gallery_base64 = make_recipe_reference_gallery(recipes)
    unlabeled_gallery_base64 = make_unlabeled_color_gallery(cues)
    level_comparisons = make_reference_level_comparison(recipes)
    make_pitch_html(
        recipes,
        cues,
        reference_gallery_base64,
        unlabeled_gallery_base64,
        level_comparisons,
    )
    write_pitch_script(recipes, cues)
    print(f"Pitch assets written to {OUTPUT}")
    print(f"Reference recipes: {len(recipes)}; unlabeled vial records: {len(cues)}")
    print(
        "Created pitch.html, recipe_reference_data.csv, "
        "video4_stream_analysis_demo.mp4, recipe and vial galleries, PITCH_SCRIPT.md"
    )


if __name__ == "__main__":
    main()

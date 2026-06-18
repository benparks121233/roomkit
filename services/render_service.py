# services/render_service.py
# Owns: generating a photorealistic AI room render from a completed design.
#
# Pipeline:
#   1. Collect selected products' image URLs from the design response.
#   2. Download hero product images and convert to PNG for the API.
#   3. Call OpenAI images.edit (gpt-image-1) with product images as references
#      plus a prompt describing the room layout, style, and aesthetic.
#   4. Save the render to data/renders/<run_id>.jpg (stable, cacheable URL).
#
# The render is presentation-only — never a source of product or price truth.
# Render failures must not block the design board from being shown.

from __future__ import annotations

import base64
import io
import logging
import os
from pathlib import Path

import requests
from PIL import Image as PILImage, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

_RENDERS_DIR = Path(__file__).parent.parent / "data" / "renders"
_RENDERS_DIR.mkdir(parents=True, exist_ok=True)

# Render quality/size — tunable via env vars for cost control.
# Defaults: 1536x1024 medium ($0.10) instead of high ($0.30).
_RENDER_SIZE = os.environ.get("RENDER_SIZE", "1536x1024")
_RENDER_QUALITY = os.environ.get("RENDER_QUALITY", "medium")

# Per-slot placement instructions — the render prompt is assembled dynamically
# from only the slots that have selected products.  No fixed slot list.
_SLOT_PLACEMENTS: dict[str, dict[str, str]] = {
    "bedroom": {
        "bed_frame":     "BED (bed_frame + mattress + sheets + bedding + pillows): center of image, against the back wall, taking up ~40% of the frame width",
        "nightstand":    "NIGHTSTAND: small table to the LEFT of the bed",
        "table_lamp":    "TABLE LAMP: sitting ON TOP of the nightstand",
        "dresser":       "DRESSER: against the RIGHT wall or right side of the room",
        "floor_lamp":    "FLOOR LAMP: tall standing lamp in the RIGHT area, between bed and dresser",
        "rug":           "RUG: on the floor UNDER and in front of the bed, visible at the bottom of the frame",
        "curtains":      "CURTAINS: framing the window(s) on the back wall, LEFT and RIGHT side panels",
        "wall_art":      "WALL ART: framed prints/art on the wall ABOVE the bed — clearly visible, this is ESSENTIAL",
        "plants":        "PLANTS: potted plant(s) in the FAR RIGHT corner on the floor",
        "mirror":        "MIRROR: on the wall to the RIGHT, above or near the dresser",
        "ceiling_light": "CEILING LIGHT: pendant/fixture hanging from the CEILING at the TOP CENTER of the image",
        "throw_blanket": "THROW BLANKET: draped over the foot of the bed",
        "comforter":     "COMFORTER: covering the bed surface, neatly spread",
        "duvet_cover":   "DUVET COVER: covering the bed surface with the duvet insert inside, neatly spread",
        "pillows":       "PILLOWS: arranged at the head of the bed against the headboard",
        "sheets":        "SHEETS: visible at the bed edges where the comforter/duvet doesn't cover",
        "mattress":      "MATTRESS: standard thickness (8-12 inches), sitting naturally on the bed frame",
        "desk":          "DESK: against the LEFT wall, between the nightstand and the corner — a workspace area",
        "desk_chair":    "DESK CHAIR: tucked under or in front of the desk",
        "sconce":        "WALL SCONCE: CLEARLY VISIBLE wall-mounted light fixture(s) flanking the bed headboard — these MUST be prominent and recognizable, not hidden or tiny",
        "duvet_insert":  "DUVET INSERT: inside the duvet cover (not separately visible — skip if duvet_cover is present)",
    },
    "living_room": {
        "sofa":          "SOFA: center-left, facing toward the viewer, the focal point",
        "coffee_table":  "COFFEE TABLE: in front of the sofa, center of the seating area",
        "side_table":    "SIDE TABLE: to the right of the sofa",
        "table_lamp":    "TABLE LAMP: on the side table",
        "tv":            "TV: mounted on or sitting above the TV stand/wall, screen facing the seating area",
        "tv_stand":      "TV STAND: against the far wall, right side, with the TV on top",
        "tv_mount":      "TV MOUNT: TV wall-mounted on the far wall, right side — no TV stand, clean floating look",
        "floor_lamp":    "FLOOR LAMP: tall lamp in a corner, right side",
        "rug":           "RUG: on the floor anchoring the seating area",
        "curtains":      "CURTAINS: framing the window(s)",
        "wall_art":      "WALL ART: on the wall above the sofa — clearly visible, ESSENTIAL",
        "plants":        "PLANTS: potted plants in a corner",
        "throw_pillows": "THROW PILLOWS: arranged on the sofa",
        "throw_blanket": "THROW BLANKET: draped over the sofa arm",
        "ceiling_light": "CEILING LIGHT: pendant/fixture from the ceiling",
        "armchair":      "ARMCHAIR: angled beside the sofa, part of the seating group",
        "bookshelf":     "BOOKSHELF: against a wall, styled with books and objects",
    },
}


_MIRROR_SHAPES = ["round", "arched", "oval", "rectangular", "square", "full length", "full-length", "floor"]

# Dimensional patterns like "24x36" → rectangular, "24x24" → square
import re
_DIM_PATTERN = re.compile(r"(\d+)\s*x\s*(\d+)")


def _detect_mirror_shape(product_name: str) -> str | None:
    """Extract mirror shape from the product name, if recognizable."""
    name_lower = product_name.lower()
    for shape in _MIRROR_SHAPES:
        if shape in name_lower:
            return shape.replace("-", " ").title()
    # Infer from dimensions: WxH where W≈H → square, W≠H → rectangular
    m = _DIM_PATTERN.search(name_lower)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        if abs(w - h) <= 2:
            return "Square"
        elif w >= h * 1.3 or h >= w * 1.3:
            return "Rectangular"
    return None


def _build_layout_for_products(
    room_type: str,
    product_slot_ids: set[str],
    products: dict[str, list[dict]] | None = None,
) -> str:
    """Build a dynamic layout instruction using only the slots that have products."""
    placements = _SLOT_PLACEMENTS.get(room_type, _SLOT_PLACEMENTS["bedroom"])
    lines = ["PRODUCT PLACEMENT — place each item in its EXACT described position:"]
    for slot_id, instruction in placements.items():
        if slot_id in product_slot_ids:
            # Skip duvet_insert when duvet_cover is present (it's inside)
            if slot_id == "duvet_insert" and "duvet_cover" in product_slot_ids:
                continue
            # Mirror: inject the actual shape from the selected product name
            if slot_id == "mirror" and products and "mirror" in products:
                mirror_name = products["mirror"][0].get("name", "")
                shape = _detect_mirror_shape(mirror_name)
                if shape:
                    instruction = instruction.rstrip() + f" — the mirror is {shape.upper()} shaped, render it as a {shape.upper()} mirror"
            lines.append(f"- {instruction}")
    return "\n".join(lines)

# Predetermined hotspot positions (normalized 0-1) for each slot by room type.
# These match the render prompt layout directions above, so hotspots land
# where the render places items — no post-hoc vision detection needed.
HOTSPOT_POSITIONS: dict[str, dict[str, dict]] = {
    "bedroom": {
        "bed_frame":     {"x": 0.42, "y": 0.55, "w": 0.40, "h": 0.35},
        "mattress":      {"x": 0.42, "y": 0.50, "w": 0.35, "h": 0.18},
        "sheets":        {"x": 0.42, "y": 0.52, "w": 0.30, "h": 0.12},
        "comforter":     {"x": 0.42, "y": 0.55, "w": 0.35, "h": 0.20},
        "duvet_cover":   {"x": 0.42, "y": 0.55, "w": 0.35, "h": 0.20},
        "duvet_insert":  {"x": 0.42, "y": 0.55, "w": 0.35, "h": 0.20},
        "pillows":       {"x": 0.42, "y": 0.38, "w": 0.25, "h": 0.10},
        "nightstand":    {"x": 0.14, "y": 0.55, "w": 0.12, "h": 0.18},
        "table_lamp":    {"x": 0.14, "y": 0.40, "w": 0.08, "h": 0.14},
        "dresser":       {"x": 0.82, "y": 0.52, "w": 0.18, "h": 0.25},
        "floor_lamp":    {"x": 0.68, "y": 0.38, "w": 0.08, "h": 0.30},
        "rug":           {"x": 0.42, "y": 0.78, "w": 0.45, "h": 0.18},
        "curtains":      {"x": 0.42, "y": 0.25, "w": 0.55, "h": 0.15},
        "wall_art":      {"x": 0.42, "y": 0.18, "w": 0.25, "h": 0.16},
        "plants":        {"x": 0.90, "y": 0.62, "w": 0.12, "h": 0.22},
        "mirror":        {"x": 0.82, "y": 0.28, "w": 0.12, "h": 0.18},
        "ceiling_light": {"x": 0.45, "y": 0.06, "w": 0.12, "h": 0.10},
        "throw_blanket": {"x": 0.42, "y": 0.65, "w": 0.25, "h": 0.10},
        "desk":          {"x": 0.12, "y": 0.52, "w": 0.16, "h": 0.22},
        "desk_chair":    {"x": 0.12, "y": 0.65, "w": 0.10, "h": 0.18},
        "sconce":        {"x": 0.28, "y": 0.32, "w": 0.06, "h": 0.12},
    },
    "living_room": {
        "sofa":          {"x": 0.38, "y": 0.55, "w": 0.40, "h": 0.25},
        "coffee_table":  {"x": 0.40, "y": 0.72, "w": 0.22, "h": 0.12},
        "side_table":    {"x": 0.65, "y": 0.55, "w": 0.10, "h": 0.15},
        "table_lamp":    {"x": 0.65, "y": 0.40, "w": 0.08, "h": 0.14},
        "tv":            {"x": 0.82, "y": 0.38, "w": 0.16, "h": 0.14},
        "tv_stand":      {"x": 0.82, "y": 0.50, "w": 0.18, "h": 0.20},
        "tv_mount":      {"x": 0.82, "y": 0.35, "w": 0.16, "h": 0.14},
        "sound_bar":     {"x": 0.82, "y": 0.48, "w": 0.14, "h": 0.05},
        "floor_lamp":    {"x": 0.88, "y": 0.35, "w": 0.08, "h": 0.30},
        "rug":           {"x": 0.40, "y": 0.78, "w": 0.40, "h": 0.15},
        "curtains":      {"x": 0.40, "y": 0.22, "w": 0.50, "h": 0.15},
        "wall_art":      {"x": 0.38, "y": 0.18, "w": 0.25, "h": 0.16},
        "plants":        {"x": 0.90, "y": 0.60, "w": 0.12, "h": 0.22},
        "bookshelf":     {"x": 0.12, "y": 0.45, "w": 0.14, "h": 0.30},
        "throw_pillows": {"x": 0.35, "y": 0.48, "w": 0.15, "h": 0.10},
        "throw_blanket": {"x": 0.42, "y": 0.58, "w": 0.18, "h": 0.10},
        "ceiling_light": {"x": 0.45, "y": 0.06, "w": 0.12, "h": 0.10},
        "armchair":      {"x": 0.14, "y": 0.58, "w": 0.16, "h": 0.20},
    },
}

# Style-to-room-description mapping for the prompt.
_STYLE_ROOMS: dict[str, str] = {
    "cottagecore": "vintage pastoral cottage — soft florals, distressed white wood, warm golden light",
    "dark_academia": "scholarly sanctuary — dark walnut paneling, rich leather, warm moody lamplight",
    "japandi": "zen minimalist — light ash wood, clean lines, generous negative space, serene natural light",
    "coastal": "breezy beach house — whitewashed wood, rattan, seafoam accents, bright natural sunlight",
    "industrial": "converted loft — exposed brick, black metal, concrete, warm Edison bulb glow",
    "quiet_luxury": "understated elegance — cream upholstery, marble accents, brushed gold, serene diffused light",
    "sports_den": "refined lounge — dark charcoal walls, cognac leather, warm amber accents",
    "city_modern": "sleek high-rise — polished surfaces, monochrome palette, one bold accent color",
    "ski_lodge": "alpine retreat — exposed timber beams, stone, plaid wool, warm firelight",
    "warm_minimalist": "calm simplicity — cream walls, light oak floors, natural textures, bright morning light",
    "jungle_oasis": "tropical retreat — lush greens, rattan, natural wood, warm earthy light",
    "gamer_den": "immersive tech space — dark matte surfaces, LED accents, moody atmospheric lighting",
    "poster_maximalist": "expressive gallery — dense wall art, mixed patterns, colorful layered textiles, warm string lights",
}


def get_render_path(run_id: str) -> Path:
    """Return the filesystem path for a design's render image."""
    return _RENDERS_DIR / f"{run_id}.jpg"


def render_exists(run_id: str) -> bool:
    """Check if a render has already been generated and cached."""
    return get_render_path(run_id).exists()


def render_room(
    run_id: str,
    room_type: str,
    style_name: str,
    mood: str,
    keywords: list[str],
    products: dict[str, list[dict]],
) -> str | None:
    """Generate a photorealistic room render from selected products.

    Args:
        run_id: Design run ID (used for caching).
        room_type: "bedroom" or "living_room".
        style_name: Style profile ID (e.g. "japandi", "warm_minimalist").
        mood: Style mood string (e.g. "calm, grounded, uncluttered").
        keywords: Style keywords list.
        products: Dict of slot_id → list of {"name": str, "image_url": str}.
                  Multi-select slots (wall_art, plants) may have multiple items.

    Returns:
        Path to the saved render image, or None on failure.
    """
    # Check cache first.
    render_path = get_render_path(run_id)
    if render_path.exists():
        logger.info("Render cache hit for %s", run_id)
        return str(render_path)

    # Download product images as references — iterate the caller's products dict
    # directly so the render is dynamic per user's actual selections.
    # Excluded/unselected slots simply aren't in the dict → not in the render.
    image_files = []
    product_labels = []
    text_fallbacks = []
    for slot_id in products:
        items = products[slot_id]
        for idx, product in enumerate(items):
            image_url = product.get("image_url", "")
            # Label: wall_art_1.png, wall_art_2.png, etc. for multi-select
            suffix = f"_{idx + 1}" if len(items) > 1 else ""
            file_label = f"{slot_id}{suffix}"
            if not image_url:
                text_fallbacks.append(f"- {file_label}: {product['name'][:80]}")
                continue

            try:
                img_data = _download_image(image_url)
                if img_data:
                    buf = io.BytesIO()
                    img_data.save(buf, format="PNG")
                    buf.seek(0)
                    buf.name = f"{file_label}.png"
                    image_files.append(buf)
                    product_labels.append(
                        f"- {file_label}.png: {product['name'][:80]}"
                    )
            except Exception:
                logger.warning("Failed to download image for %s", file_label, exc_info=True)
                text_fallbacks.append(f"- {file_label}: {product['name'][:80]}")

    if len(image_files) < 3:
        logger.error("Too few product images (%d) for render", len(image_files))
        return None

    # Build the prompt — dynamic layout based on which slots have products.
    prompt = _build_render_prompt(
        room_type, style_name, mood, keywords,
        product_labels, text_fallbacks,
        product_slot_ids=set(products.keys()),
        products=products,
    )

    # Call OpenAI with timeout protection.
    try:
        from dotenv import load_dotenv
        load_dotenv()
        from openai import OpenAI
        client = OpenAI(timeout=90.0)  # 90s max for the API call

        logger.info(
            "Generating room render for %s (%d reference images)",
            run_id, len(image_files),
        )

        response = client.images.edit(
            model="gpt-image-1",
            image=image_files,
            prompt=prompt,
            size=_RENDER_SIZE,
            quality=_RENDER_QUALITY,
            n=1,
        )

        b64_data = response.data[0].b64_json
        if not b64_data:
            logger.error("Render returned empty b64_json for %s", run_id)
            return None

        raw_bytes = base64.b64decode(b64_data)

        # Compress and save as JPEG (with watermark for free tier).
        img = PILImage.open(io.BytesIO(raw_bytes)).convert("RGB")
        img = _apply_watermark(img)
        img.save(render_path, "JPEG", quality=85, optimize=True)

        size_kb = render_path.stat().st_size // 1024
        logger.info("Render saved: %s (%d KB)", render_path, size_kb)
        return str(render_path)

    except Exception:
        logger.exception("Room render failed for %s", run_id)
        # Clean up partial file if it exists.
        if render_path.exists():
            render_path.unlink()
        return None


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

_FONT_PATH = Path(__file__).parent.parent / "assets" / "fonts" / "DMSans-Variable.ttf"


def _apply_watermark(img: PILImage.Image) -> PILImage.Image:
    """Bake a subtle 'Made with RoomKit' watermark into the bottom-right corner.

    Spec: DM Sans Bold, ~2.5% image height, white at 45% opacity,
    dark drop shadow for readability on light rooms, 20px margin.
    """
    width, height = img.size
    font_size = max(16, int(height * 0.05))
    margin = 30
    text = "Made with RoomKit"

    # Load font — fall back to default if DM Sans is missing.
    try:
        font = ImageFont.truetype(str(_FONT_PATH), size=font_size)
        # Set bold weight on variable font axis.
        try:
            font.set_variation_by_axes([font_size, 700])  # opsz, wght
        except Exception:
            pass  # Non-variable build or unsupported — regular weight is fine.
    except (OSError, IOError):
        logger.warning("DM Sans font not found at %s, using default", _FONT_PATH)
        font = ImageFont.load_default()

    # Measure text bounding box.
    dummy_draw = ImageDraw.Draw(img)
    bbox = dummy_draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # Position: bottom-right with margin.
    x = width - text_w - margin
    y = height - text_h - margin

    # Compositing via RGBA overlay for true alpha blending.
    overlay = PILImage.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Drop shadow: 2px offset, 30% opacity black.
    shadow_alpha = int(255 * 0.30)
    draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, shadow_alpha))

    # Main text: white at 45% opacity.
    text_alpha = int(255 * 0.45)
    draw.text((x, y), text, font=font, fill=(255, 255, 255, text_alpha))

    # Composite and convert back to RGB for JPEG save.
    composited = PILImage.alpha_composite(img.convert("RGBA"), overlay)
    return composited.convert("RGB")


def _download_image(url: str, timeout: int = 10) -> PILImage.Image | None:
    """Download an image URL and return a PIL Image."""
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return PILImage.open(io.BytesIO(resp.content)).convert("RGB")


def _build_render_prompt(
    room_type: str,
    style_name: str,
    mood: str,
    keywords: list[str],
    product_labels: list[str],
    text_products: list[str],
    product_slot_ids: set[str] | None = None,
    products: dict[str, list[dict]] | None = None,
) -> str:
    """Build the image generation prompt.

    Args:
        product_slot_ids: The set of slot IDs that have products. Used to build
            a dynamic layout instruction with only the relevant placements.
        products: The full products dict (slot_id → items) for shape/detail extraction.
    """
    style_desc = _STYLE_ROOMS.get(style_name, _STYLE_ROOMS["warm_minimalist"])
    layout = _build_layout_for_products(room_type, product_slot_ids or set(), products=products)
    kw_str = ", ".join(keywords[:8])

    product_section = "\n".join(product_labels)
    text_section = ""
    if text_products:
        text_section = (
            "\n\nAlso include these items (described, not shown as references):\n"
            + "\n".join(text_products)
        )

    return f"""Compose ALL of these exact furniture and decor products into one cohesive photorealistic {room_type} photograph.

STYLE: {style_desc}
MOOD: {mood}
KEY MATERIALS/TEXTURES: {kw_str}

{layout}
Reference image products:
{product_section}{text_section}

CRITICAL RULES:
1. EVERY item listed above MUST appear in the render — do NOT omit any product. Wall art on the walls, ceiling light overhead, rug on the floor, etc. All must be visible.
2. For multi-select items (e.g. wall_art_1, wall_art_2, wall_art_3): show ALL of them. Multiple wall art pieces form a gallery wall. Multiple plants are grouped together. Each must be recognizably distinct.
3. The furniture must be RECOGNIZABLY the same items from the reference images — same shapes, materials, colors, and proportions. This is a product showcase.
4. The room must feel like a REAL, LIVED-IN space — natural and believable, not a sterile product display.
5. Lighting should be bright, natural, and magazine-quality — the room should feel inviting.
6. The overall composition should match the {style_name} aesthetic perfectly.
7. Show the FULL room wall-to-wall in a wide-angle editorial interior photograph, straight-on at eye level.
8. Leave a thin strip of empty floor/wall at the very bottom of the image.
9. The MATTRESS should be a standard thickness (8-12 inches) — not exaggerated or paper-thin. It sits naturally on top of the bed frame.

Professional interior design magazine photograph. Photorealistic. No text, no watermarks, no logos."""

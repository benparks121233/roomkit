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
from PIL import Image as PILImage

logger = logging.getLogger(__name__)

_RENDERS_DIR = Path(__file__).parent.parent / "data" / "renders"
_RENDERS_DIR.mkdir(parents=True, exist_ok=True)

# Render quality/size — tunable via env vars for cost control.
# Defaults: 1536x1024 medium ($0.10) instead of high ($0.30).
_RENDER_SIZE = os.environ.get("RENDER_SIZE", "1536x1024")
_RENDER_QUALITY = os.environ.get("RENDER_QUALITY", "medium")

# ALL slots sent as image references — maximizes determinism by giving the AI
# the actual product image for every item. Ordered by visual priority.
_ALL_SLOTS = [
    "bed_frame", "dresser", "nightstand", "floor_lamp", "rug",
    "curtains", "wall_art", "table_lamp", "plants", "mirror",
    "ceiling_light", "throw_blanket", "comforter", "pillows",
    "sheets", "mattress",
]

# Room layout templates by room type.
_ROOM_LAYOUTS: dict[str, str] = {
    "bedroom": (
        "PRODUCT PLACEMENT — place each item in its EXACT described position:\n"
        "- BED (bed_frame + mattress + sheets + comforter + pillows): center of image, against the back wall, taking up ~40% of the frame width\n"
        "- NIGHTSTAND: small table to the LEFT of the bed\n"
        "- TABLE LAMP: sitting ON TOP of the nightstand\n"
        "- DRESSER: against the RIGHT wall or right side of the room\n"
        "- FLOOR LAMP: tall standing lamp in the RIGHT area, between bed and dresser\n"
        "- RUG: on the floor UNDER and in front of the bed, visible at the bottom of the frame\n"
        "- CURTAINS: framing the window(s) on the back wall, LEFT and RIGHT side panels\n"
        "- WALL ART: framed prints/art on the wall ABOVE the bed — clearly visible, this is ESSENTIAL\n"
        "- PLANTS: potted plant(s) in the FAR RIGHT corner on the floor\n"
        "- MIRROR: on the wall to the RIGHT, above or near the dresser\n"
        "- CEILING LIGHT: pendant/fixture hanging from the CEILING at the TOP CENTER of the image\n"
        "- THROW BLANKET: draped over the foot of the bed\n"
    ),
    "living_room": (
        "PRODUCT PLACEMENT — place each item in its EXACT described position:\n"
        "- SOFA: center-left, facing toward the viewer, the focal point\n"
        "- COFFEE TABLE: in front of the sofa, center of the seating area\n"
        "- SIDE TABLE: to the right of the sofa\n"
        "- TABLE LAMP: on the side table\n"
        "- TV STAND: against the far wall, right side\n"
        "- FLOOR LAMP: tall lamp in a corner, right side\n"
        "- RUG: on the floor anchoring the seating area\n"
        "- CURTAINS: framing the window(s)\n"
        "- WALL ART: on the wall above the sofa — clearly visible, ESSENTIAL\n"
        "- PLANTS: potted plants in a corner\n"
    ),
}

# Predetermined hotspot positions (normalized 0-1) for each slot by room type.
# These match the render prompt layout directions above, so hotspots land
# where the render places items — no post-hoc vision detection needed.
HOTSPOT_POSITIONS: dict[str, dict[str, dict]] = {
    "bedroom": {
        "bed_frame":     {"x": 0.42, "y": 0.55, "w": 0.40, "h": 0.35},
        "mattress":      {"x": 0.42, "y": 0.50, "w": 0.35, "h": 0.18},
        "sheets":        {"x": 0.42, "y": 0.52, "w": 0.30, "h": 0.12},
        "comforter":     {"x": 0.42, "y": 0.55, "w": 0.35, "h": 0.20},
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
    },
    "living_room": {
        "sofa":          {"x": 0.38, "y": 0.55, "w": 0.40, "h": 0.25},
        "coffee_table":  {"x": 0.40, "y": 0.72, "w": 0.22, "h": 0.12},
        "side_table":    {"x": 0.65, "y": 0.55, "w": 0.10, "h": 0.15},
        "table_lamp":    {"x": 0.65, "y": 0.40, "w": 0.08, "h": 0.14},
        "tv_stand":      {"x": 0.82, "y": 0.50, "w": 0.18, "h": 0.20},
        "floor_lamp":    {"x": 0.88, "y": 0.35, "w": 0.08, "h": 0.30},
        "rug":           {"x": 0.40, "y": 0.78, "w": 0.40, "h": 0.15},
        "curtains":      {"x": 0.40, "y": 0.22, "w": 0.50, "h": 0.15},
        "wall_art":      {"x": 0.38, "y": 0.18, "w": 0.25, "h": 0.16},
        "plants":        {"x": 0.90, "y": 0.60, "w": 0.12, "h": 0.22},
        "mirror":        {"x": 0.82, "y": 0.25, "w": 0.12, "h": 0.18},
        "throw_pillows": {"x": 0.35, "y": 0.48, "w": 0.15, "h": 0.10},
        "throw_blanket": {"x": 0.42, "y": 0.58, "w": 0.18, "h": 0.10},
        "ceiling_light": {"x": 0.45, "y": 0.06, "w": 0.12, "h": 0.10},
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

    # Download ALL product images as references for maximum accuracy.
    # Multi-select slots send every selected item as a separate reference image.
    image_files = []
    product_labels = []
    text_fallbacks = []
    for slot_id in _ALL_SLOTS:
        if slot_id not in products:
            continue
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

    # Build the prompt.
    prompt = _build_render_prompt(
        room_type, style_name, mood, keywords,
        product_labels, text_fallbacks,
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

        # Compress and save as JPEG.
        img = PILImage.open(io.BytesIO(raw_bytes)).convert("RGB")
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
) -> str:
    """Build the image generation prompt."""
    style_desc = _STYLE_ROOMS.get(style_name, _STYLE_ROOMS["warm_minimalist"])
    layout = _ROOM_LAYOUTS.get(room_type, _ROOM_LAYOUTS["bedroom"])
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

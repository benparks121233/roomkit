#!/usr/bin/env python3
"""
Generate quiz option images via OpenAI image API + compress all quiz images.

Usage:
    python scripts/generate_quiz_images.py          # generate missing, compress all
    python scripts/generate_quiz_images.py --force   # regenerate ALL (overwrite)
    python scripts/generate_quiz_images.py --compress-only  # just compress existing

Images land in web/public/quiz/ (shared) and web/public/quiz/bedroom/.
Compression: resize to 768x768, JPEG quality 80%.
"""

from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from openai import OpenAI  # noqa: E402

try:
    from PIL import Image as PILImage
except ImportError:
    print("ERROR: Pillow is required for compression. Run: pip install Pillow")
    sys.exit(1)

OUTPUT_DIR = Path(__file__).parent.parent / "web" / "public" / "quiz"
BEDROOM_DIR = OUTPUT_DIR / "bedroom"

# ---------------------------------------------------------------------------
# Shared prompt suffixes — consistent framing within each zoom level
# ---------------------------------------------------------------------------

_ROOM_WIDE_SUFFIX = (
    "Interior design editorial photograph of a full bedroom. Shot straight-on at "
    "eye level, wide framing showing the entire room from wall to wall. Soft natural "
    "daylight from the left. No people, no text, no logos, no watermarks."
)

_VIGNETTE_SUFFIX = (
    "Interior design editorial photograph of a bedroom corner vignette. Medium shot "
    "focusing on a specific corner or nook — the LIGHTING QUALITY and ATMOSPHERE are "
    "the subject. Soft, directional light emphasizing mood. Shallow depth of field on "
    "the background. No people, no text, no logos, no watermarks."
)

_COLOR_DETAIL_SUFFIX = (
    "Interior design editorial photograph, tight shot of a styled nightstand or "
    "shelf vignette in a bedroom. The COLOR PALETTE is the hero — every object is "
    "chosen to showcase the palette. Soft even lighting, slightly overhead angle. "
    "No people, no text, no logos, no watermarks."
)

_MATERIAL_SUFFIX = (
    "Close-up interior design detail photograph, 45-degree angle, shallow "
    "depth of field, soft natural light. The materials fill most of the frame. "
    "No people, no text, no logos, no watermarks."
)

_TEXTURE_SUFFIX = (
    "Extreme close-up macro photograph of the texture surface. The unique "
    "tactile quality must be instantly recognizable — exaggerate the defining "
    "characteristic. Sharp focus, even studio lighting, fills the entire frame. "
    "No people, no text, no logos, no watermarks."
)

# ---------------------------------------------------------------------------
# Image definitions: (relative_path, prompt)
# ---------------------------------------------------------------------------

IMAGES: list[tuple[str, str]] = [
    # ── CORE (6) — full-room wide, decor-rich world-building, bedroom ─────
    (
        "bedroom/core_cottagecore.jpg",
        "A richly styled cottagecore bedroom that transports you into a pastoral "
        "fantasy. Vintage painted-white iron bed with a hand-stitched quilt and "
        "floral pillowcases. The nightstand holds a ceramic pitcher of dried "
        "lavender and a stack of weathered hardcover books. Framed botanical "
        "prints hang in mismatched vintage frames on the wall. Trailing ivy "
        "cascades from a wall-mounted shelf. A small woven basket sits on the "
        "floor with a folded linen throw. A ceramic vase of wildflowers on a "
        "vintage lace doily on the dresser. Warm golden afternoon light streams "
        "through soft linen curtains. Cream, blush, and sage tones throughout. "
        + _ROOM_WIDE_SUFFIX,
    ),
    (
        "bedroom/core_dark_academia.jpg",
        "A richly styled dark academia bedroom that transports you into a "
        "scholarly sanctuary. Floor-to-ceiling dark wood bookshelves packed with "
        "leather-bound volumes line one wall. A brass banker's lamp glows warm "
        "on a heavy wooden desk beside a leather journal and fountain pen. A "
        "small framed oil painting in a gilt frame hangs above the bed. An "
        "antique globe sits on the dresser. A tufted oxblood leather armchair "
        "in the corner with a cashmere throw. Lit taper candles in brass "
        "candlesticks on the nightstand. Deep forest green, mahogany, and "
        "amber tones. Moody late-afternoon light through heavy drapes. "
        + _ROOM_WIDE_SUFFIX,
    ),
    (
        "bedroom/core_japandi.jpg",
        "A richly styled japandi bedroom that transports you into serene "
        "intentionality — rich through RESTRAINT, not clutter. A low ash wood "
        "platform bed with crisp linen bedding. A single ikebana branch in a "
        "handmade ceramic vessel on the nightstand. A paper lantern pendant "
        "casts warm diffused light. One piece of minimal abstract line art in "
        "a thin light-wood frame on the wall. A hand-thrown ceramic bowl and "
        "a small bonsai on a low floating shelf. A woven tatami-style rug on "
        "pale wood floors. Generous calm negative space between each element. "
        "Warm whites, sand, and pale wood tones. Soft even natural light. "
        + _ROOM_WIDE_SUFFIX,
    ),
    (
        "bedroom/core_coastal.jpg",
        "A richly styled coastal bedroom that transports you into a breezy "
        "beach house. Whitewashed wood walls with a natural rattan headboard "
        "and layered white and seafoam linen bedding. A large piece of ocean "
        "photography in a driftwood-colored frame above the bed. The nightstand "
        "holds a coral sculpture, a glass jar of sea glass, and a small potted "
        "succulent. Woven jute pendant light overhead. A stack of travel books "
        "and a rattan tray on the dresser. Sheer white curtains billow with "
        "breeze from an open window. A striped blue-and-cream throw draped over "
        "a wicker chair. White, sandy beige, and soft blue-green tones. Bright "
        "natural sunlight fills the room. " + _ROOM_WIDE_SUFFIX,
    ),
    (
        "bedroom/core_grandmillennial.jpg",
        "A richly styled grandmillennial bedroom that transports you into "
        "modern-classic charm. Bold chintz floral wallpaper in blue and pink "
        "covers the walls. An upholstered headboard in a coordinating stripe "
        "pattern. Needlepoint and toile throw pillows layered on the bed. A "
        "skirted table lamp with a pleated shade on the antique dark wood "
        "nightstand. A gallery wall of small gilt-framed watercolors and "
        "silhouette portraits. A bone china teacup on a stack of art books on "
        "the dresser. A monogrammed hand towel draped over a chair. Scalloped-"
        "edge curtains with tassel tiebacks. Blue, pink, cream, and dark wood "
        "tones. Warm, diffused window light. " + _ROOM_WIDE_SUFFIX,
    ),
    (
        "bedroom/core_industrial.jpg",
        "A richly styled industrial bedroom that transports you into a "
        "converted loft space. Exposed red brick wall behind the bed. Black "
        "metal pipe shelving unit displaying curated objects — vintage cameras, "
        "stacked hardcovers, a small sculptural piece. Edison bulb pendant "
        "cluster hanging from exposed ceiling pipes. A worn leather club chair "
        "in the corner with a dark wool throw. Large black-and-white graphic "
        "art print leaning against the wall. Concrete floor with a dark "
        "flatweave rug. Metal-framed bed with rumpled grey linen. A factory-"
        "style task lamp on a reclaimed wood nightstand. Charcoal, warm "
        "leather brown, black metal, and amber tones. Directional warm light "
        "from the Edison bulbs. " + _ROOM_WIDE_SUFFIX,
    ),

    # ── MOOD (6) — decor-rich vignette corners, bedroom ───────────────────
    (
        "bedroom/mood_soft_still.jpg",
        "A richly styled, quiet bedroom corner that transports you into "
        "contemplative stillness. A low wooden stool holds a handmade ceramic "
        "cup and a small open book. A single stem of dried pampas grass in a "
        "slender clay vase on the windowsill. Sheer linen curtains filter soft "
        "morning light into gentle rays. A folded wool meditation blanket on "
        "the floor. A tiny incense holder with a wisp of smoke. A framed piece "
        "of minimal calligraphy on the wall. Muted cream, stone, and warm grey "
        "tones. Every element chosen, nothing extra — serene and unhurried. "
        + _VIGNETTE_SUFFIX,
    ),
    (
        "bedroom/mood_bright_airy.jpg",
        "A richly styled, sun-drenched bedroom corner that transports you into "
        "cheerful lightness. A light wood side table holds a large bunch of "
        "fresh white tulips in a clear glass vase, a small bowl of lemons, and "
        "a coffee cup. A fiddle leaf fig plant in a woven basket catches the "
        "sun. Sheer curtains billow with breeze. A woven wall hanging and a "
        "framed watercolor print of an abstract landscape. A linen throw in "
        "soft yellow draped over a rattan chair. White, warm cream, and touches "
        "of soft yellow and green. Abundant natural sunlight flooding in. "
        + _VIGNETTE_SUFFIX,
    ),
    (
        "bedroom/mood_warm_cozy.jpg",
        "A richly styled, intimate bedroom reading nook that transports you "
        "into enveloping warmth. A deep upholstered armchair in warm camel "
        "fabric with a chunky cable-knit throw. A tall stack of well-loved "
        "books on the floor beside it. A brass reading lamp casting a warm "
        "amber pool of light. A small side table with a steaming mug, a "
        "half-eaten cookie on a ceramic plate, and a lit beeswax candle. A "
        "small framed vintage illustration on the wall. Thick wool rug "
        "underfoot. Warm honey, camel, rust, and cream tones. Warm lamp glow "
        "against the evening outside the window. " + _VIGNETTE_SUFFIX,
    ),
    (
        "bedroom/mood_bold_confident.jpg",
        "A richly styled, dramatic bedroom corner that transports you into "
        "confident boldness. A deep saturated teal wall behind a styled "
        "nightstand with a sculptural brass table lamp, a stack of oversized "
        "art books, and a bold ceramic vase in burnt orange. A large abstract "
        "expressionist painting in saturated colors hangs on the wall. Velvet "
        "throw pillow in deep magenta on the edge of the bed. A faceted glass "
        "decanter on a brass tray. Strong directional light creates dramatic "
        "shadows. Teal, brass, burnt orange, and deep magenta tones. The "
        "energy is decisive and gallery-like. " + _VIGNETTE_SUFFIX,
    ),
    (
        "bedroom/mood_moody_deep.jpg",
        "A richly styled, atmospheric bedroom corner that transports you into "
        "dark, layered depth. Deep charcoal walls. A dark wood nightstand with "
        "three lit pillar candles at different heights, a small stack of "
        "antiquarian books, and an aged brass dish. Heavy velvet curtains in "
        "deep burgundy partially drawn. A dark framed moody landscape painting "
        "barely visible in the shadows. A leather-bound journal open on the "
        "bed corner. Rich wool throw in dark plum. Warm candlelight is the "
        "primary illumination — everything else recedes into shadow. Charcoal, "
        "burgundy, aged brass, and deep plum tones. " + _VIGNETTE_SUFFIX,
    ),
    (
        "bedroom/mood_playful_eclectic.jpg",
        "A richly styled, vibrant bedroom corner that transports you into "
        "playful creative energy. A dense gallery wall of mismatched frames "
        "containing colorful prints, a vintage movie poster, a hand-drawn "
        "sketch, and a small mirror. String lights weave through the frames. "
        "Below: a daybed piled with patterned throw pillows — stripes, florals, "
        "geometric — in terracotta, teal, and saffron. A turquoise ceramic "
        "planter with a trailing pothos. A stack of vinyl records beside a "
        "small record player. A patterned kilim rug. Warm, festive, multi-"
        "colored tones. Overhead string lights plus warm natural light. "
        + _VIGNETTE_SUFFIX,
    ),

    # ── PALETTE (6) — color-forward tight shots, bedroom ──────────────────
    (
        "bedroom/palette_warm_neutrals.jpg",
        "A styled bedroom nightstand vignette showcasing a warm neutral palette: "
        "cream ceramic vase, light oak tray, terracotta candle, warm white linen, "
        "every object chosen for its cream-oak-terracotta color harmony. "
        + _COLOR_DETAIL_SUFFIX,
    ),
    (
        "bedroom/palette_earthy_rich.jpg",
        "A styled bedroom shelf vignette showcasing an earthy rich palette: "
        "walnut wood bookends, mustard yellow ceramic bowl, olive green foliage, "
        "every object chosen for its walnut-mustard-olive color harmony. "
        + _COLOR_DETAIL_SUFFIX,
    ),
    (
        "bedroom/palette_jewel_tones.jpg",
        "A styled bedroom nightstand vignette showcasing a jewel-tone palette: "
        "deep teal ceramic vase, burgundy velvet tray, gold picture frame, "
        "every object chosen for its teal-burgundy-gold color harmony. "
        + _COLOR_DETAIL_SUFFIX,
    ),
    (
        "bedroom/palette_coastal_soft.jpg",
        "A styled bedroom shelf vignette showcasing a coastal soft palette: "
        "white coral sculpture, seafoam blue glass jar, sandy beige woven basket, "
        "every object chosen for its white-seafoam-sand color harmony. "
        + _COLOR_DETAIL_SUFFIX,
    ),
    (
        "bedroom/palette_dark_moody.jpg",
        "A styled bedroom nightstand vignette showcasing a dark moody palette: "
        "charcoal ceramic mug, dark walnut clock, warm amber glass bottle, "
        "every object chosen for its charcoal-walnut-amber color harmony. "
        + _COLOR_DETAIL_SUFFIX,
    ),
    (
        "bedroom/palette_blush_sage.jpg",
        "A styled bedroom shelf vignette showcasing a blush and sage palette: "
        "dusty pink ceramic vase, sage green eucalyptus stems, cream linen runner, "
        "every object chosen for its pink-sage-cream color harmony. "
        + _COLOR_DETAIL_SUFFIX,
    ),

    # ── MATERIALS (5) — shared, already generated ─────────────────────────
    (
        "material_wood_linen.jpg",
        "A detail vignette of natural light oak wood grain surface next to "
        "rumpled cream linen fabric, showing the contrast between smooth wood "
        "and soft textile. " + _MATERIAL_SUFFIX,
    ),
    (
        "material_walnut_leather.jpg",
        "A detail vignette of rich dark walnut wood surface next to cognac "
        "brown leather with visible grain, showing warmth and patina. "
        + _MATERIAL_SUFFIX,
    ),
    (
        "material_velvet_brass.jpg",
        "A detail vignette of deep burgundy crushed velvet fabric next to "
        "polished brass hardware and fixtures, showing luxurious contrast. "
        + _MATERIAL_SUFFIX,
    ),
    (
        "material_rattan_cotton.jpg",
        "A detail vignette of woven natural rattan cane pattern next to soft "
        "white cotton fabric, showing organic tropical texture. "
        + _MATERIAL_SUFFIX,
    ),
    (
        "material_metal_concrete.jpg",
        "A detail vignette of brushed steel metal surface next to raw grey "
        "concrete, showing industrial material contrast. " + _MATERIAL_SUFFIX,
    ),

    # ── TEXTURES (9) — shared, already generated ──────────────────────────
    (
        "texture_sheer_light.jpg",
        "Macro close-up of sheer white linen curtain fabric with visible loose "
        "weave and light passing through, backlit, ethereal and translucent. "
        "The sheerness and airiness must be unmistakable. " + _TEXTURE_SUFFIX,
    ),
    (
        "texture_soft_nubby.jpg",
        "Macro close-up of cream boucle fabric showing prominent round loops "
        "and nubby curled yarn texture. The chunky looped pile must be clearly "
        "visible and tactile-looking. " + _TEXTURE_SUFFIX,
    ),
    (
        "texture_smooth_clean.jpg",
        "Macro close-up of a perfectly smooth matte ceramic or plaster surface "
        "in warm grey, showing flawless flat finish with subtle light gradient. "
        "The smoothness and absence of texture is the point. " + _TEXTURE_SUFFIX,
    ),
    (
        "texture_rich_tactile.jpg",
        "Macro close-up of deep emerald velvet upholstery showing dramatic "
        "light-and-shadow pile direction, with visible crushed areas creating "
        "sheen contrast. The velvet pile and luster must be unmistakable. "
        + _TEXTURE_SUFFIX,
    ),
    (
        "texture_woven_layered.jpg",
        "Macro close-up of a colorful hand-woven kilim rug showing tight "
        "flat-weave pattern with visible warp and weft threads in terracotta, "
        "navy, and cream. The handmade woven quality must be obvious. "
        + _TEXTURE_SUFFIX,
    ),
    (
        "texture_polished_refined.jpg",
        "Macro close-up of high-gloss dark brown leather surface showing "
        "mirror-like polished sheen, fine grain, and a sharp light reflection. "
        "The polished refinement must be unmistakable. " + _TEXTURE_SUFFIX,
    ),
    (
        "texture_raw_industrial.jpg",
        "Macro close-up of raw poured concrete surface showing aggregate "
        "stones, air bubble holes, and rough sandy texture. The brutalist "
        "raw concrete quality must be unmistakable. " + _TEXTURE_SUFFIX,
    ),
    (
        "texture_sleek_minimal.jpg",
        "Macro close-up of matte black powder-coated metal surface, perfectly "
        "flat and uniform with a subtle soft-touch feel. The sleek minimal "
        "darkness and precision must be unmistakable. " + _TEXTURE_SUFFIX,
    ),
    (
        "texture_mixed_grit.jpg",
        "Macro close-up showing a split composition: rough distressed wood on "
        "the left meeting polished brass metal on the right, a clear contrast "
        "of raw and refined in one frame. " + _TEXTURE_SUFFIX,
    ),
]


def compress_image(path: Path, size: int = 768, quality: int = 80) -> tuple[int, int]:
    """Resize to {size}x{size} and save as JPEG quality {quality}. Returns (before, after) bytes."""
    before = path.stat().st_size
    img = PILImage.open(path)
    img = img.convert("RGB")
    img = img.resize((size, size), PILImage.LANCZOS)
    img.save(path, "JPEG", quality=quality, optimize=True)
    after = path.stat().st_size
    return before, after


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate + compress quiz images.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    parser.add_argument("--compress-only", action="store_true", help="Skip generation, just compress")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    BEDROOM_DIR.mkdir(parents=True, exist_ok=True)

    # ── Generation ────────────────────────────────────────────────────────
    if not args.compress_only:
        client = OpenAI()
        total = len(IMAGES)
        skipped = 0
        generated = 0
        errors = 0

        print(f"Generating quiz images into {OUTPUT_DIR}/\n")

        for i, (rel_path, prompt) in enumerate(IMAGES, 1):
            out_path = OUTPUT_DIR / rel_path

            if out_path.exists() and not args.force:
                print(f"  [{i}/{total}] {rel_path} — exists, skipping")
                skipped += 1
                continue

            print(f"  [{i}/{total}] {rel_path}...", end=" ", flush=True)

            try:
                response = client.images.generate(
                    model="gpt-image-1",
                    prompt=prompt,
                    size="1024x1024",
                    n=1,
                )

                b64_data = response.data[0].b64_json
                if not b64_data:
                    print("ERROR: no image data returned")
                    errors += 1
                    continue

                out_path.write_bytes(base64.b64decode(b64_data))
                generated += 1
                print("done")

            except Exception as exc:
                print(f"ERROR: {exc}")
                errors += 1

        print(f"\n{'─' * 60}")
        print(f"  Generation: {generated} new, {skipped} skipped, {errors} errors.")
        print(f"{'─' * 60}\n")

    # ── Compression ───────────────────────────────────────────────────────
    print("Compressing all quiz images to 768×768 @ JPEG 80%...\n")
    jpg_files = sorted(OUTPUT_DIR.rglob("*.jpg"))
    # Exclude _originals
    jpg_files = [f for f in jpg_files if "_originals" not in str(f)]

    total_before = 0
    total_after = 0
    for f in jpg_files:
        rel = f.relative_to(OUTPUT_DIR)
        before, after = compress_image(f)
        total_before += before
        total_after += after
        saved_pct = (1 - after / before) * 100 if before > 0 else 0
        print(f"  {str(rel):45s}  {before/1024:7.0f} KB → {after/1024:7.0f} KB  ({saved_pct:.0f}% smaller)")

    print(f"\n{'─' * 60}")
    print(f"  Total: {total_before/1024/1024:.1f} MB → {total_after/1024/1024:.1f} MB")
    print(f"  Output: {OUTPUT_DIR}/")
    print(f"{'─' * 60}")


if __name__ == "__main__":
    main()

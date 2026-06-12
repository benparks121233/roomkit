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
    # ── CORE (9) — full-room wide, decor-rich world-building, bedroom ─────
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
    (
        "bedroom/core_quiet_luxury.jpg",
        "A richly styled quiet luxury bedroom that transports you into "
        "understated old-money elegance. A cream upholstered bed with perfectly "
        "pressed ivory linen sheets and a cashmere throw folded at the foot. "
        "Marble-topped nightstand with a small arrangement of fresh white "
        "orchids in a fluted glass vase, a pair of coffee-table books, and a "
        "gold-rimmed water glass. A large gilt-framed mirror leans against "
        "the wall reflecting soft light. Tailored linen armchair in warm cream. "
        "Brushed brass floor lamp with a linen shade. A marble tray with a "
        "single candle and a small ceramic dish. Cream, ivory, warm gold, and "
        "soft stone tones — nothing loud, everything exquisite. Serene, diffused "
        "natural light through floor-length sheer curtains. " + _ROOM_WIDE_SUFFIX,
    ),
    (
        "bedroom/core_sports_den.jpg",
        "A richly styled sports den bedroom — clearly a BEDROOM with a large bed "
        "and upholstered headboard as the focal point. Dark charcoal walls. The "
        "bed has dark grey linen bedding with a cognac leather bolster pillow. "
        "Above the headboard, two framed abstract athletic action art prints in "
        "painterly brushstrokes showing dynamic human figures in motion (NO real "
        "team logos, NO readable text, NO jersey numbers). To one side, a "
        "leather accent bench at the foot of the bed. A small brass and glass "
        "cart with crystal tumblers and a brass tray. An abstract geometric "
        "neon light sculpture on the wall glowing warm amber (NO letters, NO "
        "words — just an angular abstract shape). Dark walnut nightstand with a "
        "brass trophy, stacked books, and a vintage clock. Warm low ambient "
        "lighting from recessed spots and the neon glow. Dark charcoal, cognac "
        "leather, warm amber, and brass tones throughout. " + _ROOM_WIDE_SUFFIX,
    ),
    (
        "bedroom/core_city_modern.jpg",
        "A richly styled city modern bedroom that transports you into a sleek "
        "high-rise apartment. Floor-to-ceiling glass windows reveal a glittering "
        "city skyline at dusk. The room is polished monochrome — charcoal and "
        "white — with ONE bold accent: a large abstract painting in deep cobalt "
        "blue above the bed. Clean-lined low platform bed with crisp white "
        "bedding and a single charcoal throw. A polished chrome and glass side "
        "table holds an architectural sculpture and a coffee-table book. Sleek "
        "modern floor lamp in brushed steel. A statement designer chair in "
        "charcoal wool. Polished dark wood floors with a subtle grey area rug. "
        "Everything has sheen — glass, chrome, polished surfaces. Distinct from "
        "industrial: no exposed brick, no concrete, no raw textures. Refined "
        "urban sophistication. Warm dusk light from the skyline blends with "
        "soft interior lighting. " + _ROOM_WIDE_SUFFIX,
    ),
    (
        "bedroom/core_ski_lodge.jpg",
        "A richly styled ski lodge bedroom that transports you into a cozy "
        "alpine retreat. Exposed timber ceiling beams with warm honey-toned "
        "knotty wood. A stone fireplace with a low crackling fire in the corner. "
        "The bed has layered plaid wool blankets, a chunky cable-knit throw, and "
        "a faux fur accent draped across the foot. Heavy curtains frame a large "
        "window revealing a snowy mountain landscape. A pair of rustic antler "
        "wall sconces cast warm amber light. Reclaimed wood nightstand with a "
        "ceramic mug, a worn paperback, and a small lantern. A thick sheepskin "
        "rug on wide-plank dark wood floors. Warm honey wood, cream wool, "
        "charcoal plaid, and stone tones. Rugged mountain warmth — distinct from "
        "cottagecore (no florals, no dainty, no garden). Warm firelight and "
        "amber lamp glow. " + _ROOM_WIDE_SUFFIX,
    ),

    # ── MOOD (6) — decor-rich vignette corners, bedroom ───────────────────
    (
        "bedroom/mood_soft_still.jpg",
        "A richly styled, quiet bedroom corner that transports you into "
        "contemplative stillness. A low light-wood stool holds a handmade ceramic "
        "cup and a small open book. A single stem of dried pampas grass in a "
        "slender clay vase on the windowsill. Sheer white linen curtains let "
        "generous soft MORNING SUNLIGHT pour in, illuminating the space in gentle "
        "bright warmth. A folded cream wool meditation blanket on the pale floor. "
        "A tiny incense holder with a wisp of smoke. A framed piece of minimal "
        "calligraphy on a light wall. Muted cream, warm white, and soft stone "
        "tones. The room is BRIGHT and calm — luminous serenity, not dim. "
        "Every element chosen, nothing extra — serene and unhurried. "
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
        "into enveloping warmth. GOLDEN AFTERNOON SUNLIGHT streams through a "
        "window, bathing the space in rich warm light. A deep upholstered "
        "armchair in warm camel fabric with a chunky cable-knit throw catches "
        "the sun. A tall stack of well-loved books on the floor beside it. A "
        "small side table with a steaming mug, a half-eaten cookie on a ceramic "
        "plate, and a lit beeswax candle. A small framed vintage illustration on "
        "a warm-toned wall. Thick wool rug underfoot. Warm honey, camel, rust, "
        "and cream tones. The room is WELL-LIT with golden natural light — warm "
        "and inviting, not dim or shadowy. " + _VIGNETTE_SUFFIX,
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

    # ── PALETTE — additional colors ──────────────────────────────────────
    (
        "bedroom/palette_verdant.jpg",
        "A styled bedroom nightstand vignette showcasing a deep botanical green palette: "
        "emerald green ceramic vase with fresh monstera leaf, olive green linen napkin, "
        "aged brass candle holder, dark green leather-bound journal, every object chosen "
        "for its emerald-olive-brass color harmony. " + _COLOR_DETAIL_SUFFIX,
    ),
    (
        "bedroom/palette_electric.jpg",
        "A styled bedroom shelf vignette showcasing a saturated modern brights palette: "
        "bold cobalt blue ceramic sculpture, vivid coral pink book spine, sunshine yellow "
        "ceramic bowl, clean white background — intentional color-blocking, premium and "
        "curated, NOT cheap or garish. Every object chosen for its cobalt-coral-yellow "
        "color harmony. " + _COLOR_DETAIL_SUFFIX,
    ),

    # ── MOOD — additional feels ──────────────────────────────────────────
    (
        "bedroom/mood_heritage.jpg",
        "A richly styled, refined bedroom corner that transports you into sunlit "
        "old-money elegance. BRIGHT NATURAL SUNLIGHT floods through tall windows into "
        "a grand, airy study corner. A warm mahogany antique writing desk with turned "
        "legs holds a small stack of leather-bound books, a brass desk lamp with green "
        "glass shade, and a silver-framed family photograph. Above, an oil portrait in "
        "an ornate gilt frame on a LIGHT cream wall. A wingback chair in olive velvet "
        "beside the desk. Rich Persian rug on the floor. A crystal decanter catches "
        "sunlight on a brass butler tray. Everything feels inherited, refined, and "
        "luminous — old money that is AIRY and GRAND, not dark or cavernous. Warm "
        "cream walls, rich wood accents, abundant natural daylight. "
        + _VIGNETTE_SUFFIX,
    ),
    (
        "bedroom/mood_alpine.jpg",
        "A richly styled, cozy-grand bedroom corner that transports you into a DAYLIT "
        "mountain lodge retreat. BRIGHT SNOW-GLOW LIGHT pours through a large window "
        "revealing a stunning snowy mountain landscape in bright daylight. Exposed honey-"
        "toned timber beam overhead. A chunky reclaimed wood side table holds a ceramic "
        "mug of hot chocolate, a lit lantern-style candle, and a worn paperback. A thick "
        "sheepskin draped over a leather and wood chair. A plaid wool blanket folded on "
        "the armrest. The room is BRIGHT and well-lit from the snow-reflected daylight — "
        "cozy and grand, not dim or nighttime. Warm timber, cream wool, and natural "
        "mountain light fill the space. "
        + _VIGNETTE_SUFFIX,
    ),

    # ── MATERIALS (4) — shared, already generated ─────────────────────────
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
    # ── SHAPE (3) — decor-rich room shots, shared/room-agnostic ──────────
    (
        "shape_straight.jpg",
        "A richly styled modern bedroom emphasizing STRAIGHT LINES and "
        "GEOMETRIC SHAPES. Rectangular platform bed with a crisp upholstered "
        "headboard, angular nightstands, a square-framed mirror, grid-pattern "
        "shelving, and structured rectangular throw pillows. Everything is "
        "intentionally rectilinear — no curves anywhere. Warm neutral palette, "
        "layered with books, candles, and small objects on the shelves. "
        + _ROOM_WIDE_SUFFIX,
    ),
    (
        "shape_curved.jpg",
        "A richly styled bedroom emphasizing SOFT CURVES and ARCHES. An "
        "arched upholstered headboard, round nightstand, oval mirror, curved "
        "table lamp with a mushroom shade, an arched doorway or niche in the "
        "wall, and rounded throw pillows. Every piece is deliberately organic "
        "and rounded — no sharp right angles. Warm neutral palette, styled "
        "with trailing plants, ceramic vases, and stacked books. "
        + _ROOM_WIDE_SUFFIX,
    ),
    (
        "shape_mixed.jpg",
        "A richly styled bedroom showing a DELIBERATE MIX of straight lines "
        "and soft curves. Rectangular bed frame with an arched headboard, "
        "angular bookshelf next to a round side table, square window with "
        "billowing curtains, geometric art above an oval mirror. The tension "
        "between sharp and soft is the point. Warm neutral palette, layered "
        "with plants, books, candles, and ceramics. "
        + _ROOM_WIDE_SUFFIX,
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

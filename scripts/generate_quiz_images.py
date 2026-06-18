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
LIVING_ROOM_DIR = OUTPUT_DIR / "living_room"

# ---------------------------------------------------------------------------
# Shared prompt suffixes — consistent framing within each zoom level
# ---------------------------------------------------------------------------

_ROOM_WIDE_SUFFIX = (
    "Interior design editorial photograph of a full bedroom. Wide-angle shot "
    "straight-on at eye level showing the room wall-to-wall. The BED is the clear "
    "focal point at center frame. A window is visible to one side for depth but the "
    "furniture and decor are the main subject. The room feels spacious, lived-in, and "
    "real — like walking into someone's actual home. Soft natural daylight. "
    "No people, no text, no logos, no watermarks."
)

_LR_ROOM_WIDE_SUFFIX = (
    "Interior design editorial photograph of a full living room. Wide-angle shot "
    "straight-on at eye level showing the room wall-to-wall. A window is visible "
    "to one side but the FURNITURE AND DECOR are the main subject — the sofa and "
    "coffee table should be the focal point, not the window. The room feels spacious, "
    "lived-in, and real. Soft natural daylight. No people, no text, no logos, no watermarks."
)

_DARK_BEDROOM_SUFFIX = (
    "Interior design editorial photograph of a full bedroom. Wide-angle shot "
    "straight-on at eye level showing the room wall-to-wall. The BED is the clear "
    "focal point at center frame. The room is MOODY but WELL-LIT ENOUGH to clearly "
    "see every piece of furniture and decor — use warm ambient lighting (lamps, sconces, "
    "backlighting) so nothing disappears into shadow. The room feels spacious, lived-in, "
    "and real. No people, no text, no logos, no watermarks."
)

_DARK_LR_SUFFIX = (
    "Interior design editorial photograph of a full living room. Wide-angle shot "
    "straight-on at eye level showing the room wall-to-wall. The room is MOODY but "
    "WELL-LIT ENOUGH to clearly see every piece of furniture and decor — use warm "
    "ambient lighting (lamps, sconces, backlighting) so nothing disappears into shadow. "
    "The room feels spacious, lived-in, and real. No people, no text, no logos, no watermarks."
)

_VIGNETTE_SUFFIX = (
    "Interior design editorial photograph of a bedroom corner vignette. Medium shot "
    "focusing on a specific corner or nook — the LIGHTING QUALITY and ATMOSPHERE are "
    "the subject. Soft, directional light emphasizing mood. Shallow depth of field on "
    "the background. No people, no text, no logos, no watermarks."
)

_LR_VIGNETTE_SUFFIX = (
    "Interior design editorial photograph of a living room corner vignette. Medium shot "
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

_LR_COLOR_DETAIL_SUFFIX = (
    "Interior design editorial photograph, tight shot of a styled coffee table or "
    "side table vignette in a living room. The COLOR PALETTE is the hero — every object is "
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
    # ── CORE (12) — full-room wide, decor-rich world-building, bedroom ────
    (
        "bedroom/core_cottagecore.jpg",
        "A cottagecore bedroom that transports you to a PASTORAL COTTAGE. "
        "CENTER: a vintage painted-white iron bed with a hand-stitched patchwork "
        "quilt, floral pillowcases, and layered linen bedding. ABOVE THE BED: "
        "framed botanical prints in mismatched vintage frames. A nightstand with "
        "a ceramic pitcher of dried lavender, a stack of weathered hardcovers, "
        "and a small beeswax candle. Trailing ivy cascades from a wall-mounted "
        "shelf. A distressed white dresser with a ceramic vase of wildflowers on "
        "a vintage lace doily. A wicker chair in the corner with a folded linen "
        "throw. A small woven basket on the floor. Worn wide-plank wood floors "
        "with a braided rug. Window to one side with soft linen curtains — golden "
        "afternoon light and garden greenery visible. Cream, blush, sage green, "
        "warm white. " + _ROOM_WIDE_SUFFIX,
    ),
    (
        "bedroom/core_dark_academia.jpg",
        "A dark academia bedroom that transports you to a SCHOLARLY SANCTUARY. "
        "CENTER: a rich dark walnut bed frame with a tufted headboard, deep "
        "forest green velvet bedding, and burgundy accent pillows. ABOVE THE "
        "BED: a small oil painting in an ornate gilt frame. One wall has "
        "FLOOR-TO-CEILING dark wood bookshelves packed with leather-bound "
        "volumes. A heavy wooden desk with a brass banker's lamp with green "
        "shade, a leather journal, and a fountain pen. An antique globe on the "
        "dresser. A tufted oxblood leather armchair in the corner with a "
        "cashmere throw. Lit taper candles in brass candlesticks on the "
        "nightstand beside stacked books. Aged Persian rug on dark hardwood. A "
        "tall window with heavy drapes letting in ENOUGH moody natural light to "
        "see everything clearly. Deep mahogany, forest green, burgundy, antique "
        "gold, warm amber lamp glow. " + _DARK_BEDROOM_SUFFIX,
    ),
    (
        "bedroom/core_japandi.jpg",
        "A japandi bedroom that transports you to SERENE INTENTIONALITY — rich "
        "through restraint. CENTER: a low ash wood platform bed with crisp warm "
        "linen bedding, a soft throw draped casually, and simple linen pillows. "
        "ABOVE THE BED: one piece of minimal abstract line art in a thin "
        "light-wood frame. A nightstand with a single ikebana branch in a "
        "handmade ceramic vessel, a small book, and a ceramic cup. A paper "
        "lantern pendant casting warm diffused light. A low floating shelf with "
        "a hand-thrown ceramic bowl and a small bonsai. A low oak media console "
        "or dresser along one wall with a few ceramic objects and a small plant. "
        "Woven tatami-style rug on pale wood floors. Window to one side with "
        "sheer linen curtains — soft daylight and trees visible. Generous calm "
        "space between elements but the room feels WARM and lived-in, not cold. "
        "Warm whites, sand, honey oak, soft sage. " + _ROOM_WIDE_SUFFIX,
    ),
    (
        "bedroom/core_coastal.jpg",
        "A coastal bedroom that transports you to a BREEZY BEACH HOUSE. CENTER: "
        "a natural rattan headboard bed with layered white and seafoam linen "
        "bedding and a striped blue-cream throw. ABOVE THE BED: a large piece "
        "of ocean photography in a driftwood-colored frame. A whitewashed "
        "nightstand with a coral sculpture, a glass jar of sea glass, a small "
        "potted succulent, and a stack of travel books. A woven jute pendant "
        "light overhead. A rattan dresser with a rattan tray and shells. A "
        "wicker chair with a linen cushion in the corner. Sisal rug on "
        "whitewashed wide-plank floors. Window to one side with sheer white "
        "curtains billowing — BRIGHT blue sky and ocean or palm trees visible. "
        "White, sandy beige, seafoam, driftwood, soft blue. " + _ROOM_WIDE_SUFFIX,
    ),
    (
        "bedroom/core_industrial.jpg",
        "An industrial bedroom that transports you to a CONVERTED LOFT. CENTER: "
        "a black metal-framed bed with rumpled grey linen bedding and a dark "
        "wool throw. BEHIND: an exposed RED BRICK wall — raw and textured. Black "
        "metal pipe shelving on the wall displaying vintage cameras, stacked "
        "hardcovers, and a small sculpture. An Edison bulb pendant cluster "
        "hanging from exposed ceiling pipes. A worn cognac leather club chair in "
        "the corner with a dark throw. A large black-and-white urban photography "
        "print leaning against the brick. A reclaimed wood nightstand with a "
        "factory-style task lamp. Dark flatweave rug on concrete floor. A metal "
        "side table. Tall industrial window with metal frames to one side. "
        "Charcoal, warm leather brown, black iron, red brick, amber Edison glow. "
        + _ROOM_WIDE_SUFFIX,
    ),
    (
        "bedroom/core_quiet_luxury.jpg",
        "A quiet luxury bedroom that transports you to UNDERSTATED OLD-MONEY "
        "ELEGANCE. CENTER: a cream upholstered bed with a tall tufted headboard, "
        "perfectly pressed ivory linen sheets, a cashmere throw folded at the "
        "foot, and plush pillows. ABOVE: a large gilt-framed abstract in soft "
        "golds. A marble-topped nightstand with fresh white orchids in a fluted "
        "glass vase, coffee-table books, and a gold-rimmed water glass. A large "
        "gilt-framed mirror leaning against one wall reflecting soft light. A "
        "tailored cream linen armchair. A brushed brass floor lamp with a linen "
        "shade. A marble tray with a candle and ceramic dish on the dresser. A "
        "fluted console table. Herringbone wood floors with a plush cream rug. "
        "Floor-length sheer curtains. Every surface whispers expensive. Ivory, "
        "taupe, champagne gold, warm marble, stone. " + _ROOM_WIDE_SUFFIX,
    ),
    (
        "bedroom/core_sports_den.jpg",
        "A sports den bedroom that transports you to a LUXE LOUNGE — like "
        "sleeping in a high-end members club. CENTER: a large bed with a dark "
        "upholstered headboard, charcoal linen bedding, and cognac leather "
        "bolster pillows. ABOVE THE BED: two framed abstract athletic action "
        "art prints in painterly brushstrokes showing dynamic human figures (NO "
        "real logos, NO text, NO numbers). Dark charcoal walls. A dark walnut "
        "nightstand with a brass trophy, vintage clock, stacked books, and a "
        "warm brass table lamp. A cognac leather bench at the foot of the bed. "
        "A brass and glass bar cart with crystal decanters and tumblers. A "
        "geometric amber neon wall accent (NO letters, abstract shape only). "
        "Dark walnut built-in shelves with memorabilia and books. WARM BRASS "
        "SCONCES provide enough light to clearly see everything. Thick dark "
        "rug. Charcoal, cognac leather, warm amber, walnut, brass. "
        + _DARK_BEDROOM_SUFFIX,
    ),
    (
        "bedroom/core_city_modern.jpg",
        "A city modern bedroom that transports you to a SLEEK HIGH-RISE "
        "PENTHOUSE at dusk. CENTER: a clean-lined low platform bed with crisp "
        "white bedding and a single charcoal throw. ABOVE THE BED: one bold "
        "oversized abstract painting in deep cobalt blue — a gallery statement. "
        "A polished chrome and glass nightstand with an architectural sculpture "
        "and a coffee-table book. A sleek modern brushed steel floor lamp. A "
        "statement designer chair in charcoal wool. A polished lacquer dresser "
        "with a small art object. Polished dark wood floors with a subtle grey "
        "rug. Floor-to-ceiling windows to one side revealing CITY SKYLINE at "
        "golden hour — cinematic but furniture is the subject. Everything has "
        "SHEEN — glass, chrome, polished surfaces. Black, white, cool grey, "
        "chrome, cobalt accent. " + _ROOM_WIDE_SUFFIX,
    ),
    (
        "bedroom/core_ski_lodge.jpg",
        "A ski lodge bedroom that transports you to a GRAND ALPINE CHALET. "
        "CENTER: a large bed with layered PLAID WOOL blankets, a chunky "
        "cable-knit throw, and faux fur pillows against a rustic wood headboard. "
        "Exposed timber ceiling beams in warm honey-toned knotty wood. A STONE "
        "FIREPLACE with a crackling fire to one side. A reclaimed wood "
        "nightstand with a ceramic mug, a worn paperback, and a small lantern. "
        "ANTLER wall sconces casting warm amber light. A thick sheepskin rug on "
        "wide-plank dark wood floors. A woven basket with firewood beside the "
        "hearth. Vintage crossed skis mounted on the wall. A window showing "
        "SNOWY PEAKS. Warm honey wood, cream wool, charcoal plaid, stone, amber "
        "firelight. " + _ROOM_WIDE_SUFFIX,
    ),
    (
        "bedroom/core_jungle_oasis.jpg",
        "A jungle oasis bedroom that transports you to a LUSH TROPICAL "
        "RETREAT — like sleeping in a botanical garden. CENTER: a rattan-framed "
        "bed with olive and terracotta linen bedding and a woven throw. PLANTS "
        "EVERYWHERE — a massive monstera beside the bed, hanging pothos trailing "
        "from a shelf, a tall bird of paradise in a terracotta pot, ferns on "
        "the nightstand. A bamboo nightstand with a ceramic cup and a botanical "
        "book. MACRAMÉ wall hanging above the bed. A cane bookshelf with "
        "trailing vines winding through books and pots. Woven jute rug. "
        "Terracotta pots of all sizes on the floor. Natural light filtering "
        "through plants creates dappled green shadows. You can almost smell the "
        "soil. Deep green, terracotta, warm cream, rattan tan, olive. "
        + _ROOM_WIDE_SUFFIX,
    ),
    (
        "bedroom/core_gamer_den.jpg",
        "A gamer den bedroom that transports you to an IMMERSIVE COMMAND "
        "CENTER — high-end and sleek, NOT a messy teenager room. CENTER: a "
        "modern dark bed frame with dark grey bedding and a sleek dark throw. "
        "ON ONE WALL: a GAMING SETUP — an ultrawide monitor on a sleek dark "
        "desk with a gaming keyboard, mouse, and headphones on a stand. Purple "
        "and blue LED AMBIENT BACKLIGHTING behind the monitor creates a soft "
        "color wash. Dark acoustic panels on the walls for texture. A matte "
        "black floating shelf with a small plant, a controller, and a figurine. "
        "One NEON ART PIECE on the wall — abstract geometric shape glowing soft "
        "purple (NO text). A modern dark rug. The room is DARK AND MOODY but "
        "every piece is CLEARLY VISIBLE — lit by LED backlighting, neon art, "
        "and soft recessed ceiling lights. Charcoal, matte black, deep purple "
        "glow, electric blue accents. " + _DARK_BEDROOM_SUFFIX,
    ),
    (
        "bedroom/core_poster_maximalist.jpg",
        "A poster maximalist bedroom that transports you to an ECLECTIC ARTIST "
        "APARTMENT — curated chaos. CENTER: a bed with colorful mismatched "
        "patterned pillows and a vibrant kilim throw — terracotta, saffron, "
        "teal, dusty pink. BEHIND THE BED: a MASSIVE floor-to-ceiling GALLERY "
        "WALL covered in mismatched frames of all sizes — vintage movie posters, "
        "abstract art prints, hand-drawn sketches, postcards, small round "
        "mirrors. STRING LIGHTS weave through the frames. A colorful KILIM RUG "
        "with bold geometric patterns on the floor. A mid-century nightstand "
        "stacked with art books. A TURQUOISE painted bookshelf crammed with "
        "books, vinyl records, quirky ceramics, and trailing plants. A vintage "
        "record player on a side table. Fairy lights draped along the ceiling. "
        "The room is MAXIMALIST but loved — every object tells a story. "
        "Terracotta, teal, saffron, pink, warm amber. String lights plus "
        "natural daylight. " + _ROOM_WIDE_SUFFIX,
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
        "on the wall. A leather-bound journal open on the bed corner. Rich wool "
        "throw in dark plum. BRIGHT daytime photo with soft natural light flooding "
        "in — every piece of furniture and decor is clearly visible despite the "
        "dark color palette. Charcoal, burgundy, aged brass, and deep plum tones. " + _VIGNETTE_SUFFIX,
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
    # ══════════════════════════════════════════════════════════════════════
    # LIVING ROOM images (28)
    # ══════════════════════════════════════════════════════════════════════

    # ── LR CORE (12) — full-room wide, living room ──────────────────────
    (
        "living_room/core_cottagecore.jpg",
        "A warm cottagecore living room — a country parlor that feels genuinely "
        "lived-in. CENTER OF FRAME: a soft linen-slipcovered sofa with mismatched "
        "floral throw pillows, facing the viewer. In front of it, a round "
        "distressed white coffee table with a ceramic pitcher of dried wildflowers, "
        "vintage hardcovers, and a teacup. To one side, a wicker armchair with a "
        "patchwork quilt draped over it. Above the sofa, framed botanical prints "
        "in mismatched vintage frames. Trailing ivy from a wall shelf. A small "
        "bookcase with ceramic vases and old books against the side wall. A window "
        "to one side with soft linen curtains — greenery visible outside but the "
        "window is NOT the focal point. Jute rug on worn wood floors. Cream, blush, "
        "sage, warm white tones. " + _LR_ROOM_WIDE_SUFFIX,
    ),
    (
        "living_room/core_dark_academia.jpg",
        "A richly styled dark academia living room — a library lounge. CENTER OF "
        "FRAME: a deep tufted leather Chesterfield sofa in oxblood, facing the "
        "viewer. In front, a heavy wood coffee table with an antique globe, stacked "
        "art books, and a brass lamp. Floor-to-ceiling dark wood bookshelves packed "
        "with volumes on the wall behind or beside the sofa. An oil painting in a "
        "gilt frame above the sofa. A tufted leather wingback chair to one side "
        "beside a brass floor lamp. Aged Persian rug on dark hardwood. A tall "
        "window with heavy velvet curtains in forest green to one side — some moody "
        "light comes in but the window is secondary to the furniture. The room has "
        "depth and warmth. Mahogany, forest green, burgundy, amber tones. Warm "
        "lamplight mixed with natural light. " + _LR_ROOM_WIDE_SUFFIX,
    ),
    (
        "living_room/core_japandi.jpg",
        "A japandi living room that feels like a real warm home. CENTER OF FRAME: "
        "a low-profile ash wood sofa with cream linen cushions and a casually "
        "draped soft throw blanket, facing the viewer. In front, a round wood "
        "coffee table with a ceramic bowl, a couple of books, and an ikebana "
        "branch in a handmade vase. A paper lantern pendant overhead. Against the "
        "side wall, a low floating media console in light oak with a few curated "
        "ceramic objects and a small potted plant. One piece of minimal art in a "
        "thin wood frame on the wall behind the sofa. A woven rug on pale wood "
        "floors. A window to one side with sheer linen curtains — natural daylight "
        "comes in but the sofa and decor are the clear subject. The space has "
        "warmth despite restraint — cozy minimalism, not cold or empty. Warm "
        "whites, sand, honey oak, and soft sage tones. " + _LR_ROOM_WIDE_SUFFIX,
    ),
    (
        "living_room/core_coastal.jpg",
        "A coastal living room — a breezy shore house. CENTER OF FRAME: a white "
        "slipcovered sofa with blue-and-white striped throw pillows, facing the "
        "viewer. In front, a driftwood coffee table with a coral sculpture, a "
        "stack of travel books, and a glass jar of sea glass. Large ocean "
        "photography in a whitewash frame above the sofa. Natural rattan armchair "
        "with a linen cushion to one side. Woven jute pendant light overhead. "
        "Sheer white curtains billowing with light. A sisal rug on whitewashed "
        "wood floors. A window to one side — bright blue sky visible but the "
        "furniture is the focal point. White, sandy beige, seafoam, and soft blue "
        "tones. Bright natural sunlight flooding the room. " + _LR_ROOM_WIDE_SUFFIX,
    ),
    (
        "living_room/core_industrial.jpg",
        "An industrial living room — a converted warehouse loft. CENTER OF FRAME: "
        "a dark grey canvas sofa facing the viewer. Behind it, an exposed red "
        "brick wall — raw and textured. Black metal pipe shelving displaying "
        "vintage cameras, stacked hardcovers, and small sculptures. Edison bulb "
        "pendant cluster hanging from exposed ceiling beams. A reclaimed wood "
        "coffee table on a dark flatweave rug. A worn leather club chair in the "
        "corner. Large black-and-white photography leaning against the brick wall. "
        "Metal factory task lamp. Concrete floor visible at edges. A tall "
        "industrial window with metal frames to one side. Charcoal, warm leather "
        "brown, black metal, and amber tones. Warm Edison bulb light. "
        + _LR_ROOM_WIDE_SUFFIX,
    ),
    (
        "living_room/core_quiet_luxury.jpg",
        "A quiet luxury living room — an understated salon. CENTER OF FRAME: a "
        "cream bouclé sofa with perfectly arranged ivory cashmere throw pillows, "
        "facing the viewer. In front, a marble-topped coffee table with a fluted "
        "glass vase of white orchids, two coffee-table books, and a small brass "
        "dish. A large gilt-framed abstract painting in soft golds and creams "
        "above the sofa. Brushed brass floor lamp with a linen shade. A tailored "
        "cream linen armchair. Sheer floor-length curtains in warm white. "
        "Herringbone wood floors with a subtle cream area rug. Every surface "
        "whispers expensive. Ivory, taupe, warm gold, and soft stone tones. "
        "Serene diffused natural light. " + _LR_ROOM_WIDE_SUFFIX,
    ),
    (
        "living_room/core_sports_den.jpg",
        "A sports den living room — a LUXE LOUNGE like a high-end members club. "
        "CENTER OF FRAME: a large deep charcoal leather sectional sofa facing the "
        "viewer. Dark walls with two framed abstract athletic art prints in "
        "painterly brushstrokes (NO real logos, NO text, NO jersey numbers). A "
        "dark walnut coffee table with crystal tumblers on a brass tray. A cognac "
        "leather ottoman. A large flat-screen TV on a sleek dark media console. A "
        "brass and glass bar cart with crystal decanters. Warm low ambient "
        "lighting from brass sconces and a geometric neon accent (NO letters — "
        "just abstract shapes). A thick dark area rug. WARM BRASS SCONCES "
        "provide enough light to clearly see everything. Charcoal, cognac, warm "
        "amber, and brass tones. " + _DARK_LR_SUFFIX,
    ),
    (
        "living_room/core_city_modern.jpg",
        "A city modern living room — a SLEEK HIGH-RISE PENTHOUSE at dusk. CENTER "
        "OF FRAME: a low-profile charcoal sofa with geometric cushions, facing "
        "the viewer. In front, a glass-and-chrome coffee table with an "
        "architectural sculpture and a coffee-table book. One bold abstract "
        "painting in deep cobalt blue on the wall — a gallery statement. A sleek "
        "modern floor lamp in brushed steel. A statement designer chair in "
        "charcoal wool. Polished dark wood floors with a subtle grey rug. "
        "Floor-to-ceiling windows to one side revealing CITY SKYLINE at golden "
        "hour — cinematic but furniture is the subject. Everything has SHEEN — "
        "glass, chrome, polished surfaces. Black, white, cool grey, chrome, and "
        "cobalt accent. " + _LR_ROOM_WIDE_SUFFIX,
    ),
    (
        "living_room/core_ski_lodge.jpg",
        "A ski lodge living room — a GRAND ALPINE CHALET fireside retreat. CENTER "
        "OF FRAME: a deep sofa with layered PLAID WOOL blankets, chunky cable-knit "
        "throws, and faux fur pillows, facing the viewer. A STONE FIREPLACE with "
        "a crackling fire to one side. Exposed timber ceiling beams with warm "
        "honey-toned knotty wood. Reclaimed wood coffee table with ceramic mugs "
        "and a worn paperback. ANTLER wall sconces cast warm amber light. A thick "
        "sheepskin rug on wide-plank dark wood floors. A woven basket with "
        "firewood beside the hearth. A window showing SNOWY PEAKS. Warm honey "
        "wood, cream wool, charcoal plaid, and stone tones. Warm firelight and "
        "amber glow. " + _LR_ROOM_WIDE_SUFFIX,
    ),
    (
        "living_room/core_jungle_oasis.jpg",
        "A jungle oasis living room — a LUSH GREENHOUSE living space. CENTER OF "
        "FRAME: a rattan-framed sofa with olive and terracotta linen cushions, "
        "facing the viewer. PLANTS EVERYWHERE — monstera, fiddle leaf fig, hanging "
        "pothos, bird of paradise. A round wood coffee table with a ceramic "
        "planter centerpiece. Woven jute rug. Macramé wall hanging. Bamboo side "
        "tables. A cane bookshelf with trailing vines winding through books and "
        "pots. Terracotta pots in various sizes. Natural light flooding through "
        "large windows with visible greenery outside. Deep green, terracotta, warm "
        "cream, and natural tan tones. Bright lush natural light. "
        + _LR_ROOM_WIDE_SUFFIX,
    ),
    (
        "living_room/core_gamer_den.jpg",
        "A gamer den living room — an IMMERSIVE COMMAND CENTER, high-end and "
        "sleek. CENTER OF FRAME: a deep black sectional sofa facing a wall-mounted "
        "widescreen display. LED ambient backlighting in purple and blue behind "
        "the screen creates a soft color wash. A sleek matte black media console "
        "with clean cable management. Dark acoustic panels on the walls for "
        "texture. A modern black coffee table with a glass of water and wireless "
        "controller. One abstract NEON ART PIECE on the wall — geometric shape "
        "glowing soft purple (NO text). Everything matte black, carbon fiber "
        "texture, and clean. The room is DARK AND MOODY but every piece is "
        "CLEARLY VISIBLE — lit by LED backlighting, neon art, and soft recessed "
        "ceiling lights. Charcoal, deep purple, electric blue, and neon accents. "
        + _DARK_LR_SUFFIX,
    ),
    (
        "living_room/core_poster_maximalist.jpg",
        "A poster maximalist living room — an ECLECTIC ARTIST GALLERY. CENTER OF "
        "FRAME: a colorful velvet sofa in deep teal piled with mismatched "
        "patterned throw pillows in terracotta, saffron, and pink, facing the "
        "viewer. BEHIND THE SOFA: a MASSIVE gallery wall covered in mismatched "
        "frames — vintage movie posters, abstract prints, hand-drawn sketches, "
        "small mirrors, postcards. STRING LIGHTS weave through the frames. A "
        "colorful KILIM RUG with bold geometric patterns. A mid-century coffee "
        "table with stacked art books and a bold ceramic vase. A TURQUOISE "
        "bookshelf crammed with books and quirky objects. Vinyl records leaning "
        "against the wall. A vintage record player. The room is MAXIMALIST but "
        "loved — every object tells a story. Terracotta, teal, saffron, pink. "
        "Warm overhead string lights plus natural light. " + _LR_ROOM_WIDE_SUFFIX,
    ),

    # ── LR MOOD (8) — decor-rich vignette corners, living room ──────────
    (
        "living_room/mood_soft_still.jpg",
        "A richly styled, quiet living room corner that transports you into "
        "contemplative stillness. A low linen armchair beside a window with sheer "
        "white curtains letting BRIGHT MORNING SUNLIGHT pour in. A small wood side "
        "table holds a handmade ceramic cup and a single stem of dried pampas grass "
        "in a clay vase. A folded cream wool throw on the chair. A framed piece of "
        "minimal calligraphy on a light wall. Muted cream, warm white, and soft "
        "stone tones. Bright and calm — luminous serenity. " + _LR_VIGNETTE_SUFFIX,
    ),
    (
        "living_room/mood_bright_airy.jpg",
        "A richly styled, sun-drenched living room corner. A light rattan side "
        "table holds a large bunch of fresh white tulips in a clear glass vase, a "
        "small bowl of lemons, and a coffee cup. A fiddle leaf fig in a woven basket "
        "catches the sun. Sheer curtains billow. A woven wall hanging and a framed "
        "watercolor. A linen throw in soft yellow draped over a rattan chair. White, "
        "warm cream, soft yellow and green touches. Abundant flooding sunlight. "
        + _LR_VIGNETTE_SUFFIX,
    ),
    (
        "living_room/mood_warm_cozy.jpg",
        "A richly styled, intimate living room reading corner. GOLDEN AFTERNOON "
        "SUNLIGHT streams through a window, bathing the space in rich warm light. "
        "A deep upholstered armchair in warm camel with a chunky cable-knit throw "
        "catches the sun. A tall stack of books on the floor beside it. A small side "
        "table with a steaming mug, a lit beeswax candle, and a half-eaten cookie. "
        "Thick wool rug underfoot. Warm honey, camel, rust, and cream tones. Well-lit "
        "with golden natural light. " + _LR_VIGNETTE_SUFFIX,
    ),
    (
        "living_room/mood_bold_confident.jpg",
        "A richly styled, dramatic living room corner. A deep teal wall behind a "
        "styled side table with a sculptural brass lamp, oversized art books, and a "
        "bold ceramic vase in burnt orange. A large abstract expressionist painting "
        "in saturated colors on the wall. Velvet throw pillow in deep magenta on "
        "the sofa edge visible at the side. Faceted glass decanter on a brass tray. "
        "Strong directional light creates dramatic shadows. Teal, brass, burnt "
        "orange, and magenta tones. Decisive gallery energy. " + _LR_VIGNETTE_SUFFIX,
    ),
    (
        "living_room/mood_moody_deep.jpg",
        "A richly styled, atmospheric living room corner. Deep charcoal walls. A "
        "dark wood side table with three lit pillar candles at different heights, "
        "antiquarian books, and an aged brass dish. Heavy velvet curtains in deep "
        "burgundy partially drawn. A dark framed moody landscape painting on the "
        "wall. Rich wool throw in dark plum on the sofa edge. BRIGHT daytime photo "
        "with soft natural light flooding in — every piece of furniture and decor "
        "is clearly visible despite the dark color palette. Charcoal, burgundy, "
        "aged brass, and plum tones. " + _LR_VIGNETTE_SUFFIX,
    ),
    (
        "living_room/mood_playful_eclectic.jpg",
        "A richly styled, vibrant living room corner. A dense gallery wall of "
        "mismatched frames — colorful prints, a vintage poster, hand-drawn sketches, "
        "a small mirror. String lights weave through the frames. Below: a daybed or "
        "sofa section piled with patterned throw pillows — stripes, florals, "
        "geometric — in terracotta, teal, and saffron. A turquoise ceramic planter "
        "with trailing pothos. A stack of vinyl records and a small record player. "
        "Colorful kilim rug. Warm festive multi-colored tones. String lights plus "
        "warm natural light. " + _LR_VIGNETTE_SUFFIX,
    ),
    (
        "living_room/mood_heritage.jpg",
        "A richly styled, refined living room corner that feels like sunlit old-money "
        "elegance. BRIGHT NATURAL SUNLIGHT floods through tall windows into a grand "
        "reading corner. A warm mahogany side table with leather-bound books, a brass "
        "lamp with green glass shade, and a silver-framed photograph. An oil portrait "
        "in an ornate gilt frame on a LIGHT cream wall. A wingback chair in olive "
        "velvet. Rich Persian rug on the floor. Crystal decanter catching sunlight "
        "on a brass tray. Inherited, refined, luminous — airy and grand, not dark. "
        "Warm cream walls, rich wood accents, abundant daylight. " + _LR_VIGNETTE_SUFFIX,
    ),
    (
        "living_room/mood_alpine.jpg",
        "A richly styled, cozy-grand living room corner. BRIGHT SNOW-GLOW LIGHT "
        "pours through a large window revealing snowy mountains in bright daylight. "
        "Exposed honey-toned timber beam overhead. A chunky reclaimed wood side table "
        "holds a ceramic mug of hot chocolate, a lit lantern candle, and a worn "
        "paperback. A thick sheepskin draped over a leather and wood chair. Plaid "
        "wool blanket on the armrest. BRIGHT and well-lit from snow-reflected light — "
        "cozy and grand. Warm timber, cream wool, and mountain light. "
        + _LR_VIGNETTE_SUFFIX,
    ),

    # ── LR PALETTE (8) — color-forward tight shots, living room ─────────
    (
        "living_room/palette_warm_neutrals.jpg",
        "A styled living room coffee table vignette showcasing a warm neutral palette: "
        "cream ceramic vase, light oak tray, terracotta candle, warm white linen coaster, "
        "every object chosen for its cream-oak-terracotta color harmony. "
        + _LR_COLOR_DETAIL_SUFFIX,
    ),
    (
        "living_room/palette_earthy_rich.jpg",
        "A styled living room side table vignette showcasing an earthy rich palette: "
        "walnut wood bookends, mustard yellow ceramic bowl, olive green trailing plant, "
        "every object chosen for its walnut-mustard-olive color harmony. "
        + _LR_COLOR_DETAIL_SUFFIX,
    ),
    (
        "living_room/palette_jewel_tones.jpg",
        "A styled living room coffee table vignette showcasing a jewel-tone palette: "
        "deep teal ceramic vase, burgundy velvet coaster, gold picture frame, "
        "every object chosen for its teal-burgundy-gold color harmony. "
        + _LR_COLOR_DETAIL_SUFFIX,
    ),
    (
        "living_room/palette_coastal_soft.jpg",
        "A styled living room shelf vignette showcasing a coastal soft palette: "
        "white coral sculpture, seafoam blue glass jar, sandy beige woven basket, "
        "every object chosen for its white-seafoam-sand color harmony. "
        + _LR_COLOR_DETAIL_SUFFIX,
    ),
    (
        "living_room/palette_dark_moody.jpg",
        "A styled living room side table vignette showcasing a dark moody palette: "
        "charcoal ceramic mug, dark walnut tray, warm amber glass bottle, "
        "every object chosen for its charcoal-walnut-amber color harmony. "
        + _LR_COLOR_DETAIL_SUFFIX,
    ),
    (
        "living_room/palette_blush_sage.jpg",
        "A styled living room coffee table vignette showcasing a blush and sage palette: "
        "dusty pink ceramic vase, sage green eucalyptus stems, cream linen runner, "
        "every object chosen for its pink-sage-cream color harmony. "
        + _LR_COLOR_DETAIL_SUFFIX,
    ),
    (
        "living_room/palette_verdant.jpg",
        "A styled living room side table vignette showcasing a deep botanical green palette: "
        "emerald green ceramic vase with fresh monstera leaf, olive green linen napkin, "
        "aged brass candle holder, dark green leather-bound journal, every object chosen "
        "for its emerald-olive-brass color harmony. " + _LR_COLOR_DETAIL_SUFFIX,
    ),
    (
        "living_room/palette_electric.jpg",
        "A styled living room shelf vignette showcasing a saturated modern brights palette: "
        "bold cobalt blue ceramic sculpture, vivid coral pink book spine, sunshine yellow "
        "ceramic bowl, clean white background — intentional color-blocking, premium and "
        "curated, NOT cheap or garish. Every object chosen for its cobalt-coral-yellow "
        "color harmony. " + _LR_COLOR_DETAIL_SUFFIX,
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
    LIVING_ROOM_DIR.mkdir(parents=True, exist_ok=True)

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

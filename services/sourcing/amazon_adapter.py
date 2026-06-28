# services/sourcing/amazon_adapter.py
# Owns: Amazon sourcing via Canopy API-backed local cache (primary) or
# hand-curated fixture files (fallback for dev/tests).
#
# Data flow:
#   1. Read data/catalog/<slot_id>.json (Canopy-backed cache, written by
#      scripts/refresh_catalog.py — the ONLY thing that makes live API calls).
#   2. If cache miss, fall back to data/fixtures/<slot_id>.json (hand fixtures).
#   3. Filter by price_band and required_specs.
#   4. Inject affiliate tag into every buy_url.
#
# Critical rule: a buy_url without the affiliate tag is a bug.

from __future__ import annotations

import json
import logging
import os
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from schemas.product import Product
from services.sourcing.base import SourcingAdapter
from services.sourcing.catalog_cache import read_cache

_FIXTURES_DIR = Path(__file__).parent.parent.parent / "data" / "fixtures"
_CATALOG_DIR = Path(__file__).parent.parent.parent / "data" / "catalog"

# Default affiliate tag; overridden via AMAZON_AFFILIATE_TAG env var.
_DEFAULT_AFFILIATE_TAG = "roomkitai-20"

# Maximum candidates sent to the selection LLM.  Keeps input tokens bounded
# while leaving room for style-matches, interest items, and price spread.
_MAX_CANDIDATES = 80

# Name phrases indicating bathroom/vanity mirrors — excluded from the mirror
# slot because we want bedroom wall/floor mirrors, not bathroom vanity mirrors.
_DECORATIVE_PILLOW_PHRASES = [
    "decorative",
    "throw pillow",
    "accent pillow",
    "cushion cover",
    "pillow cover",
    "lumbar pillow",
    "bolster",
    "outdoor pillow",
    "floor cushion",
    "couch pillow",
    "sofa pillow",
    "patio pillow",
    "pillow sham",
    "euro sham",
    "pillow insert",
    "pillow form",
    "toss pillow",
    "velvet pillow",
    "embroidered pillow",
    "sequin pillow",
    "faux fur pillow",
    "pillow set of",
    "18x18",
    "20x20",
    "16x16",
    "12x20",
]

_PLANT_STAND_PHRASES = [
    "plant stand",
    "plant shelf",
    "plant rack",
    "plant hanger",
    "plant hook",
    "plant holder",
    "tiered stand",
    "corner stand",
    "ladder shelf",
    "watering can",
    "soil",
    "fertilizer",
    "gardening tool",
    "garden hose",
    "plant saucer",
    # Vases, display items, and non-plant junk
    "vase",
    "floating shelf",
    "wall shelf",
    "display shelf",
    "corner shelf",
    "bookshelf",
    "lego",
    "building block",
    "building set",
    "candle",
    "terrarium kit",
    "moss ball",
    "seed starter",
    "grow light",
    "grow kit",
    "propagation",
    # Accessories / filler that aren't plants
    "glass beads", "glass pebbles", "river rocks", "decorative stones",
    "decorative pebbles", "vase filler", "gravel filler", "aquarium gravel",
    "potting soil", "plant food",
]

# Bulk-pack pot detection: quantity indicators + pot words = empty pots, not plants.
# "24 Pack Colorful Flower Pots Succulent Planter" contains plant indicator words
# but is obviously a pot multi-pack, not a plant.  Catch these before the
# pot+plant-indicator exemption can save them.
_BULK_POT_RE = re.compile(
    r"\b(?:\d+\s*(?:pack|pcs|piece|set of|count))\b.*"
    r"\b(?:pot|pots|planter|planters|flower\s*pot|plant\s*pot)\b",
    re.IGNORECASE,
)

# Empty pot/planter detection for the plants slot.
# Products with these words are pots/planters/vessels.  We keep them ONLY
# if the name also contains a plant indicator (artificial, faux, tree, etc.).
_POT_PLANTER_WORDS = re.compile(
    r"\b(?:planters?|plant\s*pots?|flower\s*pots?|ceramic\s*pots?|garden\s*pots?"
    r"|cachepot|jardiniere|nursery\s*pot|planting\s*pot"
    r"|(?:plastic|metal|resin|terracotta|clay|concrete|stone)\s+pots?)\b",
    re.IGNORECASE,
)
_PLANT_INDICATOR_WORDS = re.compile(
    r"\b(?:artificial|faux|fake|silk|real|live|tree|fern|palm|succulent"
    r"|cactus|ivy|monstera|snake\s*plant|fiddle|pothos|eucalyptus|olive"
    r"|ficus|grass|topiary|bonsai|dracaena|philodendron|orchid|aloe"
    r"|agave|vine|leaf|leaves|bouquet|arrangement|greenery|bamboo"
    r"|herb|lavender|rosemary|bush|shrub|stem|branch|floral|potted)\b",
    re.IGNORECASE,
)

_BATHROOM_MIRROR_PHRASES = [
    "bathroom mirror",
    "vanity mirror",
    "medicine cabinet",
    "over sink",
    "makeup mirror",
    "lighted makeup",
    "bath mirror",
    "bathroom vanity",
]

# Slots where user interests influence product selection.
_INTEREST_SLOTS = {"wall_art", "plants", "throw_blanket", "throw_pillows", "rug", "bookshelf"}

# Cheugy / low-taste product name patterns filtered at the catalog level.
# These never reach the LLM.  Patterns are checked case-insensitively.
_CHEUGY_PATTERNS = [
    r"live\s*,?\s*laugh\s*,?\s*love",
    # motivational/inspirational only when paired with generic quote/text signals
    r"motivational\s+(quote|wall\s*art|poster|sign|canvas)\b",
    r"inspirational\s+(quote|wall\s*art|sign|canvas)\b",
    r"\b(quote|sign|canvas)\b.*\bmotivational\b",
    r"\b(quote|sign|canvas)\b.*\binspirational\b",
    r"\bbless(ed)?\s+(this|our)\b",
    r"\bhome\s+sweet\s+home\b",
    r"\bman\s+cave\b",
    r"\bfan\s+cave\b",
    r"\bshe\s+shed\b",
    r"\bbathroom\s+rules\b",
    r"\bkitchen\s+rules\b",
    r"\blaundry\s+room\b",
    r"\bfamily\s+rules\b",
    r"\bnever\s+give\s+up\b",
    r"\bdream\s+big\b",
    r"\bhustle\b",
    r"\bbible\s+verse\b",
    r"\bscripture\b",
    r"\bprayer\b",
    r"\bfarmhouse\s+sign\b",
    r"\brustic\s+(sign|quote|word)\b",
    r"\bword\s+art\b",
    r"\bletter\s+board\b",
    r"\bcollage\s+frame\b",
    r"\bphoto\s+collage\b",
    r"\bbelieve\b.*\bsign\b",
    r"\bgathered?\b.*\bsign\b",
    r"\bfaith\b.*\b(sign|wall)\b",
    r"\bgrateful\b.*\bsign\b",
    r"\bblessed\b.*\bsign\b",
    r"\bbarn\s+door\b.*\bdecor\b",
    r"\bcheesy\b",
    r"\bnovelty\b",
    r"\bgag\s+gift\b",
    r"\bfunny\b.*\bsign\b",
    # Corny gamer decor — filter the worst offenders
    r"\bgamer\b.*\b(canvas|poster|sign|wall\s*art)\b",
    r"\b(canvas|poster|sign|wall\s*art)\b.*\bgamer\b",
    r"\bgame\s+room\s+(sign|rules|decor)\b",
    r"\bgaming\s+(zone|rules|area)\s+(sign|poster)\b",
    r"\beat\s+sleep\s+game\b",
    r"\bdo\s+not\s+disturb.*gam(e|ing)\b",
    r"\bkill\s+streak\b.*\b(sign|poster)\b",
    r"\bRGB\s+(rug|carpet)\b",
    # Sports: only kill the worst offenders, NOT all sports art.
    # Sports art is legitimate when users have sports interests.
    r"\bboys\s+room\b.*\b(sports|ball|football|basketball|baseball)\b",
    r"\b(sports|ball|football|basketball|baseball)\b.*\bboys\s+room\b",
    r"\bgraffiti\s+sport",
    r"\bsports\s+ball",
    r"\bball\s+(theme|themed)\b",
    r"\blocker\s+room\b",
    r"\bsports\s+christian\b",
    r"\bsport\s+superstar\b",
    r"\bsports\s+car\s+poster\b",
    # Generic movie/anime merch — cheap licensed posters
    r"\bmovie\s+poster\b",
    r"\bfilm\s+poster\b",
]
_CHEUGY_RE = re.compile("|".join(_CHEUGY_PATTERNS), re.IGNORECASE)

# Floral-pattern keywords excluded from the sheets slot.
# Live Amazon results frequently surface floral bedding; we want clean/solid
# or geometric patterns only.  Checked case-insensitively as substrings.
_FLORAL_SHEET_PHRASES = [
    "floral",
    "flower",
    "blossom",
    "bloom",
    "botanical",
    "rose pattern",
    "daisy",
    "tulip",
    "poppy",
    "lily pattern",
    "wildflower",
    "garden print",
]

# Plaid excluded from sheets slot only. Plaid throws/comforters are fine —
# only plaid SHEETS produce wildcards in auto-generate (alpine plaid sheets).
_PLAID_SHEET_PHRASES = [
    "plaid",
    "tartan",
    "buffalo check",
    "checker",
    "gingham",
]

# Per-slot exclusion phrases — consolidated contamination filters.
# Checked case-insensitively against product names during fetch_candidates().
_SLOT_EXCLUDE_PHRASES: dict[str, list[str]] = {
    "wall_art": [
        # Multi-panel / multi-pack exclusions
        "5 piece canvas", "5 panel", "5-panel", "5-piece canvas",
        "3 piece canvas", "3 panel", "3-panel", "3-piece canvas",
        "4 piece canvas", "4 panel", "4-panel", "4-piece canvas",
        "canvas art set of", "panel wall art set", "multi panel",
        "split canvas", "canvas set of", "panels canvas",
        "set of 3", "set of 4", "set of 5", "set of 6",
        "set of 7", "set of 8", "set of 9", "set of 10", "set of 12",
        "3pcs", "4pcs", "5pcs", "6pcs", "8pcs", "10pcs", "12pcs",
        "3 pcs", "4 pcs", "5 pcs", "6 pcs",
        "3 pieces", "4 pieces", "5 pieces", "6 pieces",
        "3 piece ", "4 piece ", "5 piece ", "6 piece ",
        # Generic gaming canvas / video game merch
        "gaming canvas", "video game wall", "video game canvas",
        "gamer canvas", "gaming poster set", "game room canvas",
        "retro video game", "retro gaming canvas",
    ],
    "ceiling_light": [
        "kitchen", "utility", "garage", "workshop", "closet", "pantry",
        "laundry", "basement", "stairwell", "outdoor", "porch", "barn light",
        "shop light", "work light", "under cabinet",
    ],
    "rug": [
        "outdoor rug", "bath mat", "bathroom rug", "bath rug", "kitchen mat",
        "door mat", "doormat", "welcome mat", "kitchen rug", "patio rug",
    ],
    "nightstand": ["bathroom vanity", "bathroom cabinet"],
    "dresser": [
        "jewelry box", "makeup vanity", "bathroom cabinet", "vanity desk",
        "kids", "toddler", "nursery", "children", "baby", "kid's", "child's",
        "toy chest", "toy box", "toy organizer", "diaper",
    ],
    "pillows": [
        "neck pillow", "dog pillow", "pet pillow", "body pillow",
        "travel pillow", "cervical pillow", "knee pillow",
    ],
    "curtains": ["shower curtain", "shower liner"],
    "sheets": [
        "toddler sheet", "crib sheet", "paper towel", "sheet music",
        "sticker sheet", "coloring sheet",
    ],
    "throw_pillows": [
        "pillow cover", "pillowcase", "pillow case", "cover only",
        "covers only", "no insert", "without insert", "cushion cover",
        "pillow sham", "sham", "cover set", "covers set",
        "replacement cover", "pillow shell",
    ],
    "bed_frame": ["bunk bed", "daybed", "day bed", "toddler bed", "loft bed", "crib"],
    "throw_blanket": [
        "outdoor blanket", "beach blanket", "picnic blanket",
        "stadium blanket", "camping blanket",
    ],
    "mattress": [
        "mattress topper", "mattress pad", "mattress protector",
        "air mattress", "inflatable mattress", "mattress cover",
    ],
    "comforter": ["duvet cover", "duvet set", "cover set"],
    "duvet_insert": ["duvet cover", "cover set", "comforter set"],
    "duvet_cover": [
        "comforter", "down alternative comforter", "quilted comforter",
        "duvet insert", "down comforter",
    ],
    "desk": [
        "standing desk converter", "desk organizer", "desk pad", "desk mat",
        "desk lamp", "desk light", "task light", "reading light", "clip light",
        "clip on light", "book light",
        "desk shelf", "monitor stand", "laptop stand",
        "keyboard tray", "cable management",
        # Contamination: non-desk furniture
        "console table", "entryway table", "sofa table",
        "nightstand", "night stand", "bedside table", "end table",
        "sideboard", "buffet cabinet", "coffee bar",
        "vanity desk", "vanity table", "makeup vanity", "dressing table",
        # Contamination: table lamps that aren't desks
        "table lamp", "bedside lamp", "rattan lamp", "wicker lamp",
    ],
    "desk_chair": [
        "chair cushion", "chair pad", "chair cover", "chair mat",
        "stool", "bar stool", "dining chair", "folding chair",
    ],
    "sofa": [
        # Standalone covers/slipcovers (not slipcovered sofas)
        "sofa slipcover", "couch slipcover", "stretch sofa cover",
        "stretch couch cover", "sofa cover furniture protector",
        "couch cover for dogs", "waterproof sofa cover",
        "waterproof couch cover", "furniture protector couch",
        "recliner slipcover", "recliner cover",
        "seat protector", "cushion slipcover",
        # Standalone recliners (not reclining sofas)
        "recliner chair", "power lift recliner",
        "rocker recliner", "swivel recliner", "glider recliner",
        # Non-sofa seating
        "floor chair", "meditation chair", "meditation cushion",
        "legless floor", "tatami chair",
        # Bundled sets (sofa + armchair/loveseat combos, not sectionals)
        "sofa set", "couch set", "living room set", "furniture set",
        "with armchair", "with accent chair",
        "sofa and loveseat", "couch and loveseat",
        "sofa and chair", "couch and chair",
        # Outdoor / patio furniture
        "outdoor", "patio",
    ],
    "armchair": [
        # Multi-piece sets (set of 2, set of 3, etc.)
        "set of 2", "set of 3", "set of 4",
        "2 pack", "2-pack", "pair of",
    ],
    "sconce": [
        "outdoor", "porch", "garage", "bathroom vanity light",
        "kitchen", "under cabinet",
    ],
}

# Keywords that indicate a product matches a user interest category.
# Emphasize elevated/vintage/framed versions over generic merch.
_INTEREST_KEYWORDS: dict[str, list[str]] = {
    "music": ["music", "vinyl", "record", "concert", "guitar", "piano",
              "jazz", "notes", "band", "album", "vintage concert",
              "retro music", "tour poster"],
    "sports": ["sports", "basketball", "football", "baseball", "athletic",
               "soccer", "hockey", "tennis", "golf", "vintage sports",
               "retro sports", "stadium", "pennant", "sport",
               "nba", "nfl", "mlb", "kobe", "jordan", "lebron"],
    "travel": ["travel", "map", "world", "destination", "city", "globe",
               "adventure", "wanderlust", "passport", "vintage travel",
               "retro travel"],
    "gaming": ["gaming", "video game", "retro game", "neon", "controller",
               "arcade", "pixel"],
    "books": ["literary", "book", "library", "reading", "novel",
              "bookshelf"],
    "art_film": ["movie", "film", "cinema", "classic film", "poster",
                 "vintage movie", "retro film", "gallery", "fine art",
                 "abstract", "painting", "modern art", "mid century",
                 "bauhaus", "matisse"],
    "nature": ["nature", "landscape", "botanical", "mountain", "forest",
               "ocean", "sunset", "wildlife"],
}


class AmazonAdapter(SourcingAdapter):
    """Sourcing adapter that reads from Canopy cache or fixture files.

    Priority:
      1. data/catalog/<slot_id>.json — real Amazon data from Canopy API.
      2. data/fixtures/<slot_id>.json — hand-curated fixture fallback.

    The adapter:
      1. Loads products from cache (or fixtures on miss).
      2. Filters by price_band (inclusive on both ends).
      3. Filters by required_specs (every required key must be present in the
         product's specs dict, and the value must match if specified).
      4. Injects the affiliate tag into every buy_url.
    """

    def __init__(
        self,
        fixtures_dir: Path | None = None,
        catalog_dir: Path | None = None,
    ) -> None:
        self._fixtures_dir = fixtures_dir or _FIXTURES_DIR
        self._catalog_dir = catalog_dir or _CATALOG_DIR
        self._affiliate_tag = os.environ.get(
            "AMAZON_AFFILIATE_TAG", _DEFAULT_AFFILIATE_TAG
        )

    def fetch_candidates(
        self,
        slot_id: str,
        style_keywords: list[str],
        price_band: tuple[float, float],
        required_specs: dict,
        interests: list[str] | None = None,
        priority_terms: list[str] | None = None,
    ) -> list[Product]:
        raw_products = self._load_products(slot_id)
        min_price, max_price = price_band

        candidates: list[Product] = []
        now = datetime.now(tz=timezone.utc)

        for raw in raw_products:
            price = float(raw["normalized_price"])

            # Filter: price within band (inclusive).
            if price < min_price or price > max_price:
                continue

            # Filter: required specs must be present and match.
            specs = raw.get("specs", {})
            if not self._specs_match(specs, required_specs):
                continue

            # Filter: exclude bathroom/vanity mirrors from the mirror slot.
            if slot_id == "mirror":
                name_lower = raw.get("name", "").lower()
                if any(ph in name_lower for ph in _BATHROOM_MIRROR_PHRASES):
                    continue

            # Filter: pillows slot = bed/sleeping pillows only (not decorative).
            if slot_id == "pillows":
                name_lower = raw.get("name", "").lower()
                if any(ph in name_lower for ph in _DECORATIVE_PILLOW_PHRASES):
                    continue

            # Filter: plants slot = actual plants only (not stands or empty pots).
            if slot_id == "plants":
                name_lower = raw.get("name", "").lower()
                if any(ph in name_lower for ph in _PLANT_STAND_PHRASES):
                    continue
                # Bulk pot packs (e.g. "24 Pack Flower Pots Succulent Planter")
                # are always empty pots — exclude even if plant indicator words
                # are present (they're marketing keywords, not actual plants).
                raw_name = raw.get("name", "")
                if _BULK_POT_RE.search(raw_name):
                    continue
                # Exclude empty pots/planters that don't include an actual plant.
                if _POT_PLANTER_WORDS.search(raw_name) and not _PLANT_INDICATOR_WORDS.search(raw_name):
                    continue

            # Filter: consolidated per-slot contamination exclusions.
            _exclude = _SLOT_EXCLUDE_PHRASES.get(slot_id)
            if _exclude:
                name_lower = raw.get("name", "").lower()
                if any(ph in name_lower for ph in _exclude):
                    continue

            # Filter: exclude cheugy / low-taste products across all slots.
            if _CHEUGY_RE.search(raw.get("name", "")):
                continue

            # Inject affiliate tag into buy_url.
            tagged_url = self._inject_affiliate_tag(raw["buy_url"])

            candidates.append(Product(
                product_id=raw["product_id"],
                name=raw["name"],
                normalized_price=price,
                buy_url=tagged_url,
                specs=specs,
                source=raw.get("source", "amazon"),
                image_url=raw.get("image_url", ""),
                slot_id=slot_id,
                fetched_at=now,
            ))

        # Post-filter: remove floral-patterned sheets from the sheets slot.
        # Live Amazon results frequently surface floral bedding that doesn't
        # fit a clean/modern room design.
        if slot_id == "sheets":
            before = len(candidates)
            candidates = [
                p for p in candidates
                if not any(ph in p.name.lower() for ph in _FLORAL_SHEET_PHRASES)
            ]
            removed = before - len(candidates)
            if removed:
                logging.getLogger(__name__).info(
                    "sheets: removed %d floral candidate(s)", removed
                )
            # Plaid sheets exclusion — plaid throws/comforters are fine,
            # only plaid sheets produce wildcards in auto-generate.
            before = len(candidates)
            candidates = [
                p for p in candidates
                if not any(ph in p.name.lower() for ph in _PLAID_SHEET_PHRASES)
            ]
            removed = before - len(candidates)
            if removed:
                logging.getLogger(__name__).info(
                    "sheets: removed %d plaid candidate(s)", removed
                )

        # Diversity pass: remove near-duplicate products whose names
        # differ only in size, color, or minor descriptors.  Keeps the first
        # (cheapest) variant and drops repetitive clones.
        candidates = self._deduplicate(candidates)

        if len(candidates) <= _MAX_CANDIDATES:
            return candidates

        # Build a blended shortlist: style + interests + price spread.
        slot_interests = (
            interests if interests and slot_id in _INTEREST_SLOTS else None
        )
        return self._build_shortlist(
            candidates, style_keywords, max_price, slot_interests, slot_id,
            priority_terms=priority_terms,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_products(self, slot_id: str) -> list[dict]:
        """Load products: cache first, then fixtures fallback."""
        # Try Canopy-backed cache.
        cached = read_cache(slot_id, catalog_dir=self._catalog_dir)
        if cached is not None:
            return cached

        # Fall back to hand fixtures.
        return self._load_fixture(slot_id)

    def _load_fixture(self, slot_id: str) -> list[dict]:
        """Load data/fixtures/<slot_id>.json.  Returns [] if file missing."""
        path = self._fixtures_dir / f"{slot_id}.json"
        if not path.exists():
            return []
        with path.open() as fh:
            data = json.load(fh)
        if not isinstance(data, list):
            return []
        return data

    @staticmethod
    def _specs_match(product_specs: dict, required_specs: dict) -> bool:
        """Return True if the product satisfies every required spec.

        A required spec key must be present in the product's specs.  If the
        required_specs dict maps the key to a non-empty value, the product's
        value must match exactly (case-insensitive).
        """
        for key, required_value in required_specs.items():
            if key not in product_specs:
                return False
            if required_value:
                if product_specs[key].lower() != str(required_value).lower():
                    return False
        return True

    # Functional/commodity slots where aesthetic scoring is irrelevant.
    # These skip style Pool 1 entirely and rely on price-spread only.
    _AESTHETIC_AGNOSTIC_SLOTS = {"mattress", "duvet_insert"}

    @staticmethod
    def _build_shortlist(
        candidates: list[Product],
        style_keywords: list[str],
        max_price: float,
        interests: list[str] | None,
        slot_id: str = "",
        priority_terms: list[str] | None = None,
    ) -> list[Product]:
        """Build a capped shortlist blending style, interests, and price spread.

        Strategy (order of priority, deduped):
          1. Style-relevant: top items by keyword-match score (skipped for
             functional/commodity slots like mattress and duvet_insert).
          2. Interest-guaranteed: for decor slots, products matching the user's
             interest categories (music, sports, etc.) regardless of style score.
          3. Price-spread: sample across price terciles so the LLM sees cheap,
             mid, and expensive options — prevents under-budget picks.

        All three pools are merged, deduped, and capped at _MAX_CANDIDATES.
        """
        seen: set[str] = set()
        brand_count: dict[str, int] = {}
        result: list[Product] = []

        def _extract_brand(name: str) -> str:
            """First word of product name, lowered."""
            cleaned = re.sub(r'^[\d"\']+\s*', "", name.strip())
            return cleaned.split()[0].lower() if cleaned.split() else ""

        def _add(product: Product) -> bool:
            if product.product_id in seen:
                return False
            brand = _extract_brand(product.name)
            # Cap any single brand at 4 in the candidate pool
            if brand_count.get(brand, 0) >= 4:
                return False
            seen.add(product.product_id)
            brand_count[brand] = brand_count.get(brand, 0) + 1
            result.append(product)
            return True

        # --- Pool 1: style-relevant ---
        kw_lower = [k.lower() for k in style_keywords]
        # Aesthetic-differentiating terms ("farmhouse", "rattan") score 3x vs
        # generic terms ("wood", "brown").  Without this, all aesthetics converge
        # to the same bland shortlist.  3x was the minimum that reliably separated them.
        _PRIORITY_WEIGHT = 3
        priority_set = {t.lower() for t in (priority_terms or [])}

        def style_score(p: Product) -> int:
            name = p.name.lower()
            score = 0
            for kw in kw_lower:
                if kw in name:
                    score += _PRIORITY_WEIGHT if kw in priority_set else 1
            if score > 0 and max_price > 0 and p.normalized_price >= max_price * 0.5:
                score += 2
            return score

        # --- Pool 2: interest-matched ---
        interest_kw_lower: list[str] = []
        if interests:
            for cat in interests:
                interest_kw_lower.extend(
                    k.lower() for k in _INTEREST_KEYWORDS.get(cat, [cat])
                )

        def interest_score(p: Product) -> int:
            name = p.name.lower()
            return sum(1 for kw in interest_kw_lower if kw in name)

        # For wall_art with interests: flip priority — interests first (60),
        # then style fills the rest. This ensures the LLM sees mostly
        # interest-relevant candidates.
        is_interest_dominant = slot_id == "wall_art" and bool(interests)

        def _shuffle_within_tiers(products: list[Product], score_fn, cap: int = 0) -> list[Product]:
            """Sort by score descending, shuffle within tiers, sample all tiers.

            When cap > 0 and the pool is larger than the cap, each tier gets
            a share of the cap proportional to its size, with a guaranteed
            minimum of 1.  This ensures high-scoring items are well-represented
            but every tier contributes variety — preventing the same top-37
            items from locking out the pool every run.
            """
            from itertools import groupby
            scored = sorted(products, key=score_fn, reverse=True)

            if cap <= 0 or len(scored) <= cap:
                # No sampling needed — just shuffle within tiers
                shuffled: list[Product] = []
                for _score, group in groupby(scored, key=score_fn):
                    tier = list(group)
                    random.shuffle(tier)
                    shuffled.extend(tier)
                return shuffled

            # Proportional sampling: each tier gets cap * (tier_size / total)
            # slots, rounded up, with a minimum of 1.
            tiers: list[list[Product]] = []
            for _score, group in groupby(scored, key=score_fn):
                tiers.append(list(group))

            total = len(scored)
            result_list: list[Product] = []
            for tier in tiers:
                random.shuffle(tier)
                share = max(1, round(cap * len(tier) / total))
                result_list.extend(tier[:share])

            # Trim to cap (rounding may overshoot slightly)
            random.shuffle(result_list)
            # Re-sort by score so top items still lead the list
            result_list.sort(key=score_fn, reverse=True)
            return result_list[:cap]

        # Only take style-scored products (score > 0) in Pool 1.
        # Zero-score products are left for Pool 3 price-spread backfill.
        # Aesthetic-agnostic slots (mattress, duvet_insert) skip Pool 1
        # entirely — they're functional items where style doesn't matter.
        is_agnostic = slot_id in AmazonAdapter._AESTHETIC_AGNOSTIC_SLOTS

        if not is_agnostic:
            style_matched = [p for p in candidates if style_score(p) > 0]

            if is_interest_dominant:
                interest_matches = [
                    p for p in candidates if interest_score(p) > 0
                ]
                interest_matches = _shuffle_within_tiers(interest_matches, interest_score, cap=48)
                for p in interest_matches[:48]:
                    _add(p)
                style_matched = _shuffle_within_tiers(style_matched, style_score, cap=32)
                for p in style_matched[:32]:
                    _add(p)
            else:
                # Default: style first (up to 40), then interests (24)
                style_matched = _shuffle_within_tiers(style_matched, style_score, cap=40)
                for p in style_matched[:40]:
                    _add(p)

                if interests:
                    interest_matches = [
                        p for p in candidates if interest_score(p) > 0
                    ]
                    interest_matches = _shuffle_within_tiers(interest_matches, interest_score, cap=24)
                    for p in interest_matches[:24]:
                        _add(p)

        # --- Pool 3: price-spread (fill remaining budget with price diversity) ---
        remaining = _MAX_CANDIDATES - len(result)
        if remaining > 0 and candidates:
            # Split into 3 price terciles, sample evenly.
            by_price = sorted(candidates, key=lambda p: p.normalized_price)
            n = len(by_price)
            tercile_size = max(1, n // 3)
            terciles = [
                by_price[:tercile_size],
                by_price[tercile_size:2 * tercile_size],
                by_price[2 * tercile_size:],
            ]
            per_tercile = max(1, remaining // 3)

            for tercile in terciles:
                # Within each tercile, shuffle style-relevant items for variety.
                tercile_shuffled = _shuffle_within_tiers(tercile, style_score)
                added = 0
                for p in tercile_shuffled:
                    if added >= per_tercile:
                        break
                    if _add(p):
                        added += 1

        return result[:_MAX_CANDIDATES]

    # Regex stripping color/finish descriptors so we can compare
    # the "core" product name for near-duplicate detection.
    # NOTE: bed sizes (twin/full/queen/king) are NOT stripped — a Queen
    # and King bed frame are fundamentally different products.
    _DEDUP_STRIP_RE = re.compile(
        r"""
        \b(?:                                   # word boundary
          \d+["']\s*x\s*\d+["']?               # dimensions like 56"x16"
          |\d+\s*(?:inch|in|cm|mm|ft|pack)\b   # 24 inch, 6 pack
          |(?:x+\s*)?(?:small|medium|large|xl|xxl)\b
          |black|white|gray|grey|brown|beige|cream|ivory|taupe|sand
          |walnut|oak|espresso|natural|mahogany|cherry|rustic|charcoal
          |gold|silver|brass|bronze|copper|nickel
        )\b
        |–\s*                                   # dash separators
        |[,()[\]]                               # punctuation
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    @staticmethod
    def _deduplicate(candidates: list[Product]) -> list[Product]:
        """Remove near-duplicate products (same core name, different size/color).

        Keeps the first occurrence (by original order).  Two products are
        considered duplicates if their names, after stripping dimensions,
        colors, and size descriptors, are identical.
        """
        seen_cores: set[str] = set()
        result: list[Product] = []
        for p in candidates:
            core = AmazonAdapter._DEDUP_STRIP_RE.sub("", p.name.lower())
            core = re.sub(r"\s+", " ", core).strip()
            if core in seen_cores:
                continue
            seen_cores.add(core)
            result.append(p)
        removed = len(candidates) - len(result)
        if removed:
            logging.getLogger(__name__).info(
                "Diversity: removed %d near-duplicate(s) from %d candidates",
                removed, len(candidates),
            )
        return result

    def _inject_affiliate_tag(self, url: str) -> str:
        """Ensure the buy_url contains the affiliate tag query parameter."""
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        params["tag"] = [self._affiliate_tag]
        new_query = urlencode(params, doseq=True)
        return urlunparse(parsed._replace(query=new_query))

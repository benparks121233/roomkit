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
]

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
_INTEREST_SLOTS = {"wall_art", "plants", "throw_blanket"}

# Cheugy / low-taste product name patterns filtered at the catalog level.
# These never reach the LLM.  Patterns are checked case-insensitively.
_CHEUGY_PATTERNS = [
    r"live\s*,?\s*laugh\s*,?\s*love",
    r"motivational\b",
    r"inspirational\b",
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
]
_CHEUGY_RE = re.compile("|".join(_CHEUGY_PATTERNS), re.IGNORECASE)

# Per-slot exclusion phrases — consolidated contamination filters.
# Checked case-insensitively against product names during fetch_candidates().
_SLOT_EXCLUDE_PHRASES: dict[str, list[str]] = {
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
        "clip on light", "book light", "led light",
        "desk shelf", "monitor stand", "laptop stand",
        "keyboard tray", "cable management",
    ],
    "desk_chair": [
        "chair cushion", "chair pad", "chair cover", "chair mat",
        "stool", "bar stool", "dining chair", "folding chair",
    ],
    "sconce": [
        "outdoor", "porch", "garage", "bathroom vanity light",
        "kitchen", "under cabinet",
    ],
    "wallpaper": [
        "wallpaper paste", "wallpaper tool", "wallpaper smoother",
        "wallpaper scorer", "contact paper", "shelf liner",
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
               "retro sports", "stadium", "pennant"],
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

            # Filter: plants slot = actual plants/planters only (not stands).
            if slot_id == "plants":
                name_lower = raw.get("name", "").lower()
                if any(ph in name_lower for ph in _PLANT_STAND_PHRASES):
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

        if len(candidates) <= _MAX_CANDIDATES:
            return candidates

        # Build a blended shortlist: style + interests + price spread.
        slot_interests = (
            interests if interests and slot_id in _INTEREST_SLOTS else None
        )
        return self._build_shortlist(
            candidates, style_keywords, max_price, slot_interests, slot_id,
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

    @staticmethod
    def _build_shortlist(
        candidates: list[Product],
        style_keywords: list[str],
        max_price: float,
        interests: list[str] | None,
        slot_id: str = "",
    ) -> list[Product]:
        """Build a capped shortlist blending style, interests, and price spread.

        Strategy (order of priority, deduped):
          1. Style-relevant: top items by keyword-match score.
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

        def style_score(p: Product) -> int:
            name = p.name.lower()
            return sum(1 for kw in kw_lower if kw in name)

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

        def _shuffle_within_tiers(products: list[Product], score_fn) -> list[Product]:
            """Sort by score descending, but shuffle within same-score tiers.

            This preserves style/interest relevance ranking while ensuring
            different products surface across runs — kills selection bias
            without sacrificing on-aesthetic quality.
            """
            from itertools import groupby
            scored = sorted(products, key=score_fn, reverse=True)
            shuffled: list[Product] = []
            for _score, group in groupby(scored, key=score_fn):
                tier = list(group)
                random.shuffle(tier)
                shuffled.extend(tier)
            return shuffled

        if is_interest_dominant:
            # Interest pool first (up to 48)
            interest_matches = [
                p for p in candidates if interest_score(p) > 0
            ]
            interest_matches = _shuffle_within_tiers(interest_matches, interest_score)
            for p in interest_matches[:48]:
                _add(p)
            # Then backfill with style-relevant (remaining capacity)
            by_style = _shuffle_within_tiers(candidates, style_score)
            for p in by_style[:32]:
                _add(p)
        else:
            # Default: style first (32), then interests (24)
            by_style = _shuffle_within_tiers(candidates, style_score)
            for p in by_style[:32]:
                _add(p)

            if interests:
                interest_matches = [
                    p for p in candidates if interest_score(p) > 0
                ]
                interest_matches = _shuffle_within_tiers(interest_matches, interest_score)
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

    def _inject_affiliate_tag(self, url: str) -> str:
        """Ensure the buy_url contains the affiliate tag query parameter."""
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        params["tag"] = [self._affiliate_tag]
        new_query = urlencode(params, doseq=True)
        return urlunparse(parsed._replace(query=new_query))

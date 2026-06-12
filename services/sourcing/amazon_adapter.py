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
_MAX_CANDIDATES = 100

# Name phrases indicating bathroom/vanity mirrors — excluded from the mirror
# slot because we want bedroom wall/floor mirrors, not bathroom vanity mirrors.
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
]
_CHEUGY_RE = re.compile("|".join(_CHEUGY_PATTERNS), re.IGNORECASE)

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
    "film": ["movie", "film", "cinema", "classic film", "poster",
             "vintage movie", "retro film"],
    "nature": ["nature", "landscape", "botanical", "mountain", "forest",
               "ocean", "sunset", "wildlife"],
    "art": ["gallery", "fine art", "abstract", "painting", "modern art",
            "mid century", "bauhaus", "matisse"],
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

        if is_interest_dominant:
            # Interest pool first (up to 60)
            interest_matches = [
                p for p in candidates if interest_score(p) > 0
            ]
            interest_matches.sort(key=interest_score, reverse=True)
            for p in interest_matches[:60]:
                _add(p)
            # Then backfill with style-relevant (remaining capacity)
            by_style = sorted(candidates, key=style_score, reverse=True)
            for p in by_style[:40]:
                _add(p)
        else:
            # Default: style first (40), then interests (30)
            by_style = sorted(candidates, key=style_score, reverse=True)
            for p in by_style[:40]:
                _add(p)

            if interests:
                interest_matches = [
                    p for p in candidates if interest_score(p) > 0
                ]
                interest_matches.sort(key=interest_score, reverse=True)
                for p in interest_matches[:30]:
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
                # Within each tercile, prefer style-relevant items.
                tercile_sorted = sorted(tercile, key=style_score, reverse=True)
                added = 0
                for p in tercile_sorted:
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

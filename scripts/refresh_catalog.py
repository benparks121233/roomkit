#!/usr/bin/env python3
"""
Refresh the local Canopy cache for one or more slots.

This is the ONLY script that makes live Canopy API calls.  Normal adapter
reads go through data/catalog/ (cache) or data/fixtures/ (fallback).

Usage:
    python scripts/refresh_catalog.py bed_frame "queen bed frame"
    python scripts/refresh_catalog.py bed_frame "queen bed frame" --limit 10
    python scripts/refresh_catalog.py --batch scripts/refresh_batch.json

Batch JSON format:
    [
      {"slot_id": "bed_frame", "search_term": "queen bed frame"},
      {"slot_id": "rug", "search_term": "8x10 area rug"}
    ]

Each slot uses one Canopy API request.  Free tier = 100 requests/month.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Ensure project root is on sys.path for imports.
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv  # noqa: E402

from services.sourcing.canopy_client import CanopyClient  # noqa: E402
from services.sourcing.catalog_cache import write_cache  # noqa: E402

load_dotenv()

# ---------------------------------------------------------------------------
# Spec extraction from title / feature bullets
# ---------------------------------------------------------------------------

_BED_SIZE_RE = re.compile(
    r"\b(twin\s*xl|twin|full|queen|king|cal(?:ifornia)?\s*king)\b",
    re.IGNORECASE,
)
_SCREEN_SIZE_RE = re.compile(r"\b(\d{2,3})\s*(?:inch|in\b|[\"″\u201D\u201C])", re.IGNORECASE)
_RUG_DIM_RE = re.compile(r"\b(\d+)\s*[x×X]\s*(\d+)\b")

# Normalize bed-size strings to canonical form.
_BED_SIZE_CANONICAL = {
    "twin": "twin",
    "twin xl": "twin xl",
    "full": "full",
    "queen": "queen",
    "king": "king",
    "cal king": "king",
    "california king": "king",
}


def extract_specs(slot_id: str, title: str, bullets: list[str]) -> dict[str, str]:
    """Best-effort spec extraction from unstructured Canopy data.

    Canopy does not return structured specs like bed_size or screen_size.
    We parse them from the product title and feature bullets using regex
    patterns.  This is imperfect — edge cases will miss — but it's the
    right tradeoff for v1:  we get SOME spec filtering rather than none.

    Returns a dict of extracted specs (may be empty).
    """
    text = " ".join([title] + bullets)
    specs: dict[str, str] = {}

    # Bed-size extraction (bed_frame, mattress, sheets, comforter, bedding).
    if slot_id in ("bed_frame", "mattress", "sheets", "comforter", "bedding"):
        match = _BED_SIZE_RE.search(text)
        if match:
            raw = match.group(1).lower().strip()
            specs["bed_size"] = _BED_SIZE_CANONICAL.get(raw, raw)

    # Screen-size extraction (tv).
    if slot_id == "tv":
        match = _SCREEN_SIZE_RE.search(text)
        if match:
            specs["screen_size"] = f"{match.group(1)} inch"

    # Rug dimensions (rug).
    if slot_id == "rug":
        match = _RUG_DIM_RE.search(text)
        if match:
            specs["dimensions"] = f"{match.group(1)}x{match.group(2)}"

    return specs


# ---------------------------------------------------------------------------
# Canopy → cache format mapper
# ---------------------------------------------------------------------------

def map_canopy_product(slot_id: str, raw: dict) -> dict:
    """Map a raw Canopy search result to our internal cache format.

    Canopy search result shape:
        {title, url, asin, price: {value, ...}, mainImageUrl, ...}
    Our cache format:
        {product_id, name, normalized_price, buy_url, specs, image_url, source}
    """
    price_obj = raw.get("price") or {}
    price_val = price_obj.get("value")
    if price_val is None:
        return {}  # skip products with no price

    title = raw.get("title", "")
    bullets = raw.get("featureBullets", []) or []

    asin = raw.get("asin", "")
    clean_url = f"https://www.amazon.com/dp/{asin}" if asin else raw.get("url", "")

    return {
        "product_id": asin,
        "name": title,
        "normalized_price": float(price_val),
        "buy_url": clean_url,
        "specs": extract_specs(slot_id, title, bullets),
        "image_url": raw.get("mainImageUrl", ""),
        "source": "canopy",
    }


# ---------------------------------------------------------------------------
# Main refresh logic
# ---------------------------------------------------------------------------

def refresh_slot(
    client: CanopyClient,
    slot_id: str,
    search_term: str,
    *,
    min_price: float | None = None,
    max_price: float | None = None,
    limit: int = 20,
) -> int:
    """Fetch products for a slot from Canopy and write to cache.

    Returns the number of products cached.  Uses ONE API request.
    """
    results = client.search_products(
        search_term,
        min_price=min_price,
        max_price=max_price,
        limit=limit,
    )

    products = []
    for raw in results:
        mapped = map_canopy_product(slot_id, raw)
        if mapped:  # skip empties (no price)
            products.append(mapped)

    write_cache(slot_id, products)
    return len(products)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh Canopy cache for one or more slots.",
    )
    parser.add_argument("slot_id", nargs="?", help="Slot ID (e.g. bed_frame)")
    parser.add_argument("search_term", nargs="?", help="Search term for Canopy")
    parser.add_argument("--limit", type=int, default=20, help="Max results per slot")
    parser.add_argument(
        "--batch",
        type=str,
        help="Path to batch JSON file (array of {slot_id, search_term})",
    )
    parser.add_argument(
        "--min-price", type=float, default=None, help="Min price filter",
    )
    parser.add_argument(
        "--max-price", type=float, default=None, help="Max price filter",
    )
    args = parser.parse_args()

    # Determine jobs.
    jobs: list[dict] = []
    if args.batch:
        batch_path = Path(args.batch)
        if not batch_path.exists():
            print(f"Error: batch file not found: {batch_path}", file=sys.stderr)
            sys.exit(1)
        with batch_path.open() as fh:
            jobs = json.load(fh)
    elif args.slot_id and args.search_term:
        jobs = [{"slot_id": args.slot_id, "search_term": args.search_term}]
    else:
        parser.error("Provide slot_id + search_term, or --batch <file>")

    client = CanopyClient()
    total_requests = 0
    total_products = 0

    print(f"Refreshing {len(jobs)} slot(s)...\n")

    for job in jobs:
        slot_id = job["slot_id"]
        search_term = job["search_term"]
        min_price = job.get("min_price", args.min_price)
        max_price = job.get("max_price", args.max_price)

        print(f"  {slot_id}: searching \"{search_term}\"...", end=" ", flush=True)
        try:
            count = refresh_slot(
                client,
                slot_id,
                search_term,
                min_price=min_price,
                max_price=max_price,
                limit=args.limit,
            )
            total_requests += 1
            total_products += count
            print(f"{count} products cached")
        except Exception as exc:
            total_requests += 1
            print(f"ERROR: {exc}")

    print(f"\nDone. {total_requests} API request(s), {total_products} products cached.")
    print(f"  Free tier budget: ~{100 - total_requests} requests remaining this month (estimate)")


if __name__ == "__main__":
    main()

# services/sourcing/catalog_cache.py
# Owns: local JSON cache for Canopy API responses.
#
# Cache lives in data/catalog/<slot_id>.json.  Each file is a JSON array of
# product dicts in a normalized format (not raw Canopy shape — already mapped
# to our internal product dict format for fast adapter reads).
#
# The adapter reads cache first; the refresh script is the ONLY thing that
# writes to the cache via live Canopy calls.  Tests and normal dev never hit
# the live API.
#
# Cache format (each entry):
# {
#   "product_id": "B01HY0JA3G",           # ASIN
#   "name": "Product title",
#   "normalized_price": 29.99,
#   "buy_url": "https://www.amazon.com/dp/B01HY0JA3G",
#   "specs": {"bed_size": "queen"},        # extracted from title/bullets
#   "image_url": "https://...",
#   "source": "canopy",
#   "fetched_at": "2026-06-09T..."
# }

from __future__ import annotations

import json
from pathlib import Path

_CATALOG_DIR = Path(__file__).parent.parent.parent / "data" / "catalog"


def read_cache(slot_id: str, catalog_dir: Path | None = None) -> list[dict] | None:
    """Read cached products for a slot.  Returns None on cache miss."""
    directory = catalog_dir or _CATALOG_DIR
    path = directory / f"{slot_id}.json"
    if not path.exists():
        return None
    with path.open() as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        return None
    return data


def write_cache(slot_id: str, products: list[dict], catalog_dir: Path | None = None) -> Path:
    """Write products to cache.  Creates the directory if needed.  Returns the path."""
    directory = catalog_dir or _CATALOG_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{slot_id}.json"
    with path.open("w") as fh:
        json.dump(products, fh, indent=2)
    return path


def merge_cache(
    slot_id: str,
    new_products: list[dict],
    catalog_dir: Path | None = None,
) -> tuple[int, int]:
    """Merge new products into existing cache, deduplicating by product_id (ASIN).

    New products with the same product_id as an existing entry replace it
    (fresher data wins).  Returns (total_after_merge, newly_added_count).
    """
    existing = read_cache(slot_id, catalog_dir=catalog_dir) or []
    existing_by_id = {p["product_id"]: p for p in existing}
    before_count = len(existing_by_id)

    for product in new_products:
        pid = product.get("product_id", "")
        if pid:
            existing_by_id[pid] = product

    merged = list(existing_by_id.values())
    write_cache(slot_id, merged, catalog_dir=catalog_dir)
    newly_added = len(existing_by_id) - before_count
    return len(merged), newly_added

#!/usr/bin/env python3
"""
Batch catalog builder — fetches products from Canopy across multiple style
variants per slot, MERGING into existing cache by ASIN (never duplicates).

This script is NOT wired into room generation.  Generation always reads from
data/catalog/ (cache).  This script is run deliberately to populate or expand
that cache.

Usage:
    python scripts/build_catalog.py                # dry-run: show plan, no calls
    python scripts/build_catalog.py --go           # execute after confirmation
    python scripts/build_catalog.py --go --max 30  # lower request ceiling
    python scripts/build_catalog.py --go --limit 20  # fewer results per query

Each query = 1 Canopy API request.  Free tier = 100 requests/month.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Ensure project root is on sys.path for imports.
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.refresh_catalog import map_canopy_product  # noqa: E402
from services.sourcing.canopy_client import CanopyClient  # noqa: E402
from services.sourcing.catalog_cache import merge_cache, read_cache  # noqa: E402

# ---------------------------------------------------------------------------
# Planned query set — bedroom slots × style variants
# ---------------------------------------------------------------------------
# Each tuple: (slot_id, search_term)
# Goal: 2-3 style variants per slot so the LLM has diverse candidates.

BEDROOM_QUERIES: list[tuple[str, str]] = [
    # bed_frame — 3 style variants
    ("bed_frame", "wood platform queen bed frame"),
    ("bed_frame", "upholstered queen bed frame"),
    ("bed_frame", "metal queen bed frame"),
    # mattress — 2 variants
    ("mattress", "queen memory foam mattress"),
    ("mattress", "queen hybrid mattress"),
    # sheets — 3 variants
    ("sheets", "queen cotton sheet set"),
    ("sheets", "queen linen sheet set"),
    ("sheets", "queen microfiber sheet set"),
    # comforter — 3 variants
    ("comforter", "queen comforter set neutral"),
    ("comforter", "queen duvet insert white"),
    ("comforter", "queen down alternative comforter"),
    # pillows — 2 variants
    ("pillows", "bed pillows queen size 2 pack"),
    ("pillows", "down alternative pillows queen"),
    # nightstand — 3 variants
    ("nightstand", "wood nightstand with drawer"),
    ("nightstand", "modern nightstand"),
    ("nightstand", "rustic bedside table"),
    # dresser — 2 variants
    ("dresser", "6 drawer dresser wood"),
    ("dresser", "modern bedroom dresser"),
    # ceiling_light — 2 variants
    ("ceiling_light", "flush mount ceiling light modern"),
    ("ceiling_light", "boho rattan ceiling light"),
    # table_lamp — 3 variants
    ("table_lamp", "bedside table lamp modern"),
    ("table_lamp", "ceramic table lamp neutral"),
    ("table_lamp", "wood table lamp with linen shade"),
    # floor_lamp — 2 variants
    ("floor_lamp", "modern floor lamp living room"),
    ("floor_lamp", "wood tripod floor lamp"),
    # wall_art — 3 variants
    ("wall_art", "minimalist wall art set"),
    ("wall_art", "botanical print framed wall art"),
    ("wall_art", "abstract neutral canvas wall art"),
    # plants — 2 variants
    ("plants", "artificial plant indoor"),
    ("plants", "faux plant home decor"),
    # mirror — 2 variants
    ("mirror", "full length mirror bedroom"),
    ("mirror", "round wall mirror"),
    # rug — 3 variants
    ("rug", "wool area rug 5x8"),
    ("rug", "jute area rug 5x8"),
    ("rug", "modern area rug 5x8"),
    # curtains — 2 variants
    ("curtains", "linen curtains bedroom"),
    ("curtains", "blackout curtains neutral"),
    # throw_blanket — 2 variants
    ("throw_blanket", "knit throw blanket"),
    ("throw_blanket", "cozy throw blanket neutral"),
]

DEFAULT_LIMIT = 40
DEFAULT_MAX_REQUESTS = 60


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def show_plan(queries: list[tuple[str, str]], max_requests: int, limit: int) -> None:
    """Print the query plan and request count."""
    # Group by slot for readability.
    slot_order: list[str] = []
    by_slot: dict[str, list[str]] = {}
    for slot_id, term in queries:
        if slot_id not in by_slot:
            slot_order.append(slot_id)
            by_slot[slot_id] = []
        by_slot[slot_id].append(term)

    total = len(queries)
    print(f"{'=' * 72}")
    print("  Catalog Build Plan")
    print(f"  {total} queries across {len(by_slot)} slots"
          f"  |  limit={limit}/query  |  ceiling={max_requests}")
    print(f"{'=' * 72}\n")

    for slot_id in slot_order:
        terms = by_slot[slot_id]
        existing = read_cache(slot_id)
        existing_count = len(existing) if existing else 0
        print(f"  {slot_id} ({existing_count} cached)")
        for term in terms:
            print(f"    -> \"{term}\"")
    print()

    if total > max_requests:
        print(f"  WARNING: {total} queries exceeds ceiling of {max_requests}!")
        print("  Reduce queries or raise --max to proceed.\n")
    else:
        print(f"  Total: {total} requests (ceiling: {max_requests},"
              f" {max_requests - total} headroom)\n")


def run_build(
    client: CanopyClient,
    queries: list[tuple[str, str]],
    *,
    limit: int,
    max_requests: int,
) -> None:
    """Execute the batch build with merge and request ceiling."""
    total = len(queries)
    if total > max_requests:
        print(f"ABORTED: {total} queries exceeds ceiling of {max_requests}.")
        print("Raise --max or trim the query list.")
        sys.exit(1)

    requests_made = 0
    total_added = 0

    print(f"Executing {total} queries (ceiling: {max_requests})...\n")

    for i, (slot_id, search_term) in enumerate(queries, 1):
        # Hard ceiling check before every call.
        if requests_made >= max_requests:
            print(f"\n  CEILING HIT ({max_requests}). Stopping.")
            print(f"  Remaining queries skipped: {total - i + 1}")
            break

        print(f"  [{i}/{total}] {slot_id}: "
              f"\"{search_term}\"...", end=" ", flush=True)

        try:
            results = client.search_products(
                search_term, limit=limit,
            )
            requests_made += 1

            products = []
            for raw in results:
                mapped = map_canopy_product(slot_id, raw)
                if mapped:
                    products.append(mapped)

            merged_total, newly_added = merge_cache(slot_id, products)
            total_added += newly_added
            print(f"{len(products)} fetched, {newly_added} new "
                  f"(total: {merged_total})")

        except Exception as exc:
            requests_made += 1
            print(f"ERROR: {exc}")

    print(f"\n{'─' * 72}")
    print(f"  Done. {requests_made} API request(s), "
          f"{total_added} new products added to cache.")
    print(f"  Estimated remaining this month: ~{100 - requests_made}")
    print(f"{'─' * 72}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch catalog builder with style-variant queries.",
    )
    parser.add_argument(
        "--go", action="store_true",
        help="Actually execute queries (default is dry-run plan only)",
    )
    parser.add_argument(
        "--limit", type=int, default=DEFAULT_LIMIT,
        help=f"Max results per Canopy query (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--max", type=int, default=DEFAULT_MAX_REQUESTS,
        help=f"Hard request ceiling (default: {DEFAULT_MAX_REQUESTS})",
    )
    args = parser.parse_args()

    queries = BEDROOM_QUERIES

    show_plan(queries, max_requests=args.max, limit=args.limit)

    if not args.go:
        print("  Dry run. Pass --go to execute.\n")
        return

    client = CanopyClient()
    run_build(client, queries, limit=args.limit, max_requests=args.max)


if __name__ == "__main__":
    main()

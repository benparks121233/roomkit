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
    python scripts/build_catalog.py --go --max 150 # lower request ceiling
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
# Comprehensive query set — all slots × per-aesthetic depth
# ---------------------------------------------------------------------------
# Each tuple: (slot_id, search_term)
# Organized: bedroom new → living room new → existing slot gap-filling.
# Every decorative slot has per-aesthetic-family targeting.
# Functional slots (duvet_insert, mattress, pillows) get spec/budget depth.

CATALOG_QUERIES: list[tuple[str, str]] = [
    # =================================================================
    # SECTION 1: BEDROOM NEW SLOTS (zero catalog, 49 queries)
    # =================================================================

    # -----------------------------------------------------------------
    # desk — 0 cached, target 265+ (10 queries)
    # -----------------------------------------------------------------
    ("desk", "writing desk home office small"),
    ("desk", "computer desk bedroom compact"),
    ("desk", "mid century modern writing desk walnut"),
    ("desk", "japandi desk natural wood minimal"),
    ("desk", "industrial metal desk black"),
    ("desk", "dark wood desk traditional library"),
    ("desk", "white desk modern minimalist"),
    ("desk", "rustic farmhouse desk wood"),
    ("desk", "gaming desk black LED"),
    ("desk", "coastal white desk rattan"),

    # -----------------------------------------------------------------
    # desk_chair — 0 cached, target 265+ (8 queries)
    # -----------------------------------------------------------------
    ("desk_chair", "desk chair bedroom comfortable"),
    ("desk_chair", "ergonomic desk chair home office"),
    ("desk_chair", "mid century modern desk chair"),
    ("desk_chair", "velvet desk chair gold legs"),
    ("desk_chair", "industrial desk chair metal leather"),
    ("desk_chair", "rattan desk chair natural"),
    ("desk_chair", "gaming chair ergonomic black"),
    ("desk_chair", "white desk chair modern minimalist"),

    # -----------------------------------------------------------------
    # sconce — 0 cached, target 265+ (8 queries)
    # -----------------------------------------------------------------
    ("sconce", "wall sconce bedroom"),
    ("sconce", "plug in wall sconce"),
    ("sconce", "brass wall sconce modern"),
    ("sconce", "industrial wall sconce black metal"),
    ("sconce", "rattan wall sconce natural"),
    ("sconce", "minimalist wall sconce LED"),
    ("sconce", "rustic wood wall sconce"),
    ("sconce", "vintage wall sconce antique brass"),

    # -----------------------------------------------------------------
    # duvet_cover — 0 cached, target 265+ (8 queries)
    # -----------------------------------------------------------------
    ("duvet_cover", "duvet cover set queen"),
    ("duvet_cover", "linen duvet cover queen"),
    ("duvet_cover", "velvet duvet cover luxury"),
    ("duvet_cover", "boho duvet cover colorful"),
    ("duvet_cover", "white duvet cover minimalist"),
    ("duvet_cover", "dark duvet cover charcoal black"),
    ("duvet_cover", "plaid duvet cover flannel"),
    ("duvet_cover", "tropical duvet cover palm"),

    # -----------------------------------------------------------------
    # duvet_insert — 0 cached, target 175+ (5 queries, functional)
    # -----------------------------------------------------------------
    ("duvet_insert", "duvet insert queen all season"),
    ("duvet_insert", "down alternative duvet insert queen"),
    ("duvet_insert", "lightweight duvet insert queen"),
    ("duvet_insert", "cooling duvet insert queen"),
    ("duvet_insert", "warm duvet insert queen winter"),

    # =================================================================
    # SECTION 2: LIVING ROOM SLOTS (zero catalog, 62 queries)
    # =================================================================

    # -----------------------------------------------------------------
    # sofa — 0 cached, target 350+ (12 queries)
    # -----------------------------------------------------------------
    ("sofa", "sofa living room modern"),
    ("sofa", "couch apartment size"),
    ("sofa", "sectional sofa small living room"),
    ("sofa", "mid century modern sofa"),
    ("sofa", "velvet sofa tufted"),
    ("sofa", "leather sofa brown"),
    ("sofa", "linen sofa neutral beige"),
    ("sofa", "industrial sofa dark leather"),
    ("sofa", "modern sofa sleek low profile"),
    ("sofa", "rattan sofa natural"),
    ("sofa", "cozy sofa deep seat"),
    ("sofa", "futon sofa modern black"),

    # -----------------------------------------------------------------
    # armchair — 0 cached, target 265+ (8 queries)
    # -----------------------------------------------------------------
    ("armchair", "accent chair living room"),
    ("armchair", "armchair modern comfortable"),
    ("armchair", "velvet accent chair"),
    ("armchair", "leather armchair brown"),
    ("armchair", "rattan accent chair"),
    ("armchair", "mid century modern armchair"),
    ("armchair", "cozy armchair sherpa"),
    ("armchair", "modern accent chair geometric"),

    # -----------------------------------------------------------------
    # ottoman — 0 cached, target 200+ (6 queries)
    # -----------------------------------------------------------------
    ("ottoman", "ottoman living room"),
    ("ottoman", "storage ottoman"),
    ("ottoman", "velvet ottoman round"),
    ("ottoman", "leather ottoman brown"),
    ("ottoman", "pouf ottoman knit"),
    ("ottoman", "modern ottoman minimalist"),

    # -----------------------------------------------------------------
    # coffee_table — 0 cached, target 265+ (8 queries)
    # -----------------------------------------------------------------
    ("coffee_table", "coffee table living room"),
    ("coffee_table", "coffee table with storage"),
    ("coffee_table", "mid century modern coffee table walnut"),
    ("coffee_table", "industrial coffee table metal wood"),
    ("coffee_table", "glass coffee table modern"),
    ("coffee_table", "rattan coffee table natural"),
    ("coffee_table", "marble coffee table"),
    ("coffee_table", "rustic coffee table wood"),

    # -----------------------------------------------------------------
    # side_table — 0 cached, target 200+ (6 queries)
    # -----------------------------------------------------------------
    ("side_table", "side table living room"),
    ("side_table", "end table modern"),
    ("side_table", "mid century modern side table"),
    ("side_table", "industrial side table metal"),
    ("side_table", "rattan side table"),
    ("side_table", "marble side table gold"),

    # -----------------------------------------------------------------
    # tv_stand — 0 cached, target 265+ (8 queries)
    # -----------------------------------------------------------------
    ("tv_stand", "tv stand living room"),
    ("tv_stand", "tv console media cabinet"),
    ("tv_stand", "mid century modern tv stand walnut"),
    ("tv_stand", "industrial tv stand metal wood"),
    ("tv_stand", "white tv stand modern"),
    ("tv_stand", "rustic tv stand farmhouse"),
    ("tv_stand", "floating tv stand wall mount"),
    ("tv_stand", "dark wood tv stand traditional"),

    # -----------------------------------------------------------------
    # bookshelf — 0 cached, target 200+ (6 queries)
    # -----------------------------------------------------------------
    ("bookshelf", "bookshelf living room"),
    ("bookshelf", "bookcase modern"),
    ("bookshelf", "industrial bookshelf metal wood"),
    ("bookshelf", "mid century modern bookshelf"),
    ("bookshelf", "ladder bookshelf minimalist"),
    ("bookshelf", "rustic bookshelf wood"),

    # -----------------------------------------------------------------
    # throw_pillows — 0 cached, target 265+ (8 queries)
    # -----------------------------------------------------------------
    ("throw_pillows", "throw pillow covers 18x18"),
    ("throw_pillows", "decorative pillows living room"),
    ("throw_pillows", "velvet throw pillows"),
    ("throw_pillows", "boho throw pillows colorful"),
    ("throw_pillows", "linen throw pillows neutral"),
    ("throw_pillows", "leather throw pillows"),
    ("throw_pillows", "plaid throw pillows"),
    ("throw_pillows", "tropical throw pillows"),

    # =================================================================
    # SECTION 3: EXISTING SLOT GAP-FILLING (26 queries)
    # =================================================================

    # -----------------------------------------------------------------
    # pillows — 320 cached, functional depth (4 queries)
    # -----------------------------------------------------------------
    ("pillows", "luxury hotel pillow queen down alternative"),
    ("pillows", "organic cotton pillow queen"),
    ("pillows", "adjustable loft pillow queen"),
    ("pillows", "cooling gel pillow side sleeper"),

    # -----------------------------------------------------------------
    # sheets — 431 cached, sports/gamer/industrial thin (3 queries)
    # -----------------------------------------------------------------
    ("sheets", "dark sheets queen charcoal black"),
    ("sheets", "flannel sheets queen plaid"),
    ("sheets", "jersey sheets queen soft"),

    # -----------------------------------------------------------------
    # comforter — 596 cached, sports/gamer/industrial thin (3 queries)
    # -----------------------------------------------------------------
    ("comforter", "dark comforter set queen black charcoal"),
    ("comforter", "plaid comforter set queen"),
    ("comforter", "solid color comforter queen navy"),

    # -----------------------------------------------------------------
    # throw_blanket — 562 cached, industrial/gamer thin (2 queries)
    # -----------------------------------------------------------------
    ("throw_blanket", "sherpa throw blanket dark"),
    ("throw_blanket", "weighted blanket throw"),

    # -----------------------------------------------------------------
    # mattress — 265 cached, functional (2 queries)
    # -----------------------------------------------------------------
    ("mattress", "mattress in a box queen"),
    ("mattress", "hybrid mattress queen medium firm"),

    # -----------------------------------------------------------------
    # curtains — 689 cached, ski_lodge/jungle thin (2 queries)
    # -----------------------------------------------------------------
    ("curtains", "bamboo curtains natural"),
    ("curtains", "plaid curtains flannel"),

    # -----------------------------------------------------------------
    # rug — 728 cached, ski_lodge/jungle thin (2 queries)
    # -----------------------------------------------------------------
    ("rug", "jute area rug natural 5x8"),
    ("rug", "cowhide area rug"),

    # -----------------------------------------------------------------
    # ceiling_light — 703 cached (2 queries)
    # -----------------------------------------------------------------
    ("ceiling_light", "rattan ceiling light flush mount"),
    ("ceiling_light", "rustic ceiling light wood"),

    # -----------------------------------------------------------------
    # floor_lamp — 441 cached (2 queries)
    # -----------------------------------------------------------------
    ("floor_lamp", "rattan floor lamp natural"),
    ("floor_lamp", "tripod floor lamp wood"),

    # -----------------------------------------------------------------
    # mirror — 571 cached (2 queries)
    # -----------------------------------------------------------------
    ("mirror", "rattan mirror round"),
    ("mirror", "rustic wood mirror"),

    # -----------------------------------------------------------------
    # plants — 982 cached (2 queries)
    # -----------------------------------------------------------------
    ("plants", "artificial cactus plant"),
    ("plants", "artificial palm plant indoor"),
]

DEFAULT_LIMIT = 40
DEFAULT_MAX_REQUESTS = 150


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
    print(f"{'─' * 72}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch catalog builder with per-aesthetic queries.",
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

    queries = CATALOG_QUERIES

    show_plan(queries, max_requests=args.max, limit=args.limit)

    if not args.go:
        print("  Dry run. Pass --go to execute.\n")
        return

    client = CanopyClient()
    run_build(client, queries, limit=args.limit, max_requests=args.max)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Targeted catalog fetch — 46 queries filling confirmed-empty aesthetic×slot cells.
Generated from catalog_gap_v2.py analysis.

Usage:
    python scripts/targeted_fetch.py          # dry-run
    python scripts/targeted_fetch.py --go     # execute
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.refresh_catalog import map_canopy_product
from services.sourcing.canopy_client import CanopyClient
from services.sourcing.catalog_cache import merge_cache

# ---------------------------------------------------------------------------
# The 46 approved queries — each fills a confirmed-empty aesthetic×slot cell
# ---------------------------------------------------------------------------

QUERIES: list[tuple[str, str]] = [
    # === quiet_luxury (6 queries) ===
    ("bed_frame", "upholstered bed frame queen linen"),
    ("bed_frame", "luxury bed frame queen velvet tufted"),
    ("plants", "luxury artificial orchid arrangement"),
    ("plants", "faux olive tree premium indoor"),
    ("curtains", "luxury linen curtains ivory 96 inch"),
    ("curtains", "silk curtains cream bedroom premium"),

    # === dark_academia (9 queries) ===
    ("ceiling_light", "antique brass ceiling light flush"),
    ("ceiling_light", "vintage dark flush mount light"),
    ("table_lamp", "antique brass desk lamp green shade"),
    ("plants", "artificial fern vintage planter"),
    ("plants", "faux ivy plant antique pot"),
    ("rug", "dark oriental area rug 5x8"),
    ("rug", "vintage persian rug dark red"),
    ("throw_blanket", "velvet throw blanket dark green"),
    ("throw_blanket", "tartan plaid throw blanket wool"),

    # === sports_den (16 queries) ===
    ("bed_frame", "dark upholstered bed frame queen leather"),
    ("bed_frame", "platform bed frame dark charcoal queen"),
    ("nightstand", "industrial nightstand dark metal wood"),
    ("nightstand", "dark leather nightstand bedroom"),
    ("dresser", "industrial dresser dark metal wood"),
    ("ceiling_light", "industrial flush mount ceiling light dark"),
    ("ceiling_light", "matte black ceiling light modern"),
    ("table_lamp", "industrial table lamp matte black metal"),
    ("table_lamp", "brass desk lamp dark masculine"),
    ("floor_lamp", "industrial floor lamp dark metal"),
    ("floor_lamp", "brass floor lamp dark shade"),
    ("wall_art", "dark moody wall art framed masculine"),
    ("plants", "artificial plant dark planter modern"),
    ("plants", "faux snake plant black pot"),
    ("curtains", "dark charcoal blackout curtains 84"),
    ("curtains", "navy velvet curtains bedroom"),

    # === industrial (8 queries) ===
    ("table_lamp", "industrial pipe table lamp"),
    ("wall_art", "industrial metal wall art"),
    ("wall_art", "urban loft wall decor metal"),
    ("plants", "artificial plant concrete planter"),
    ("curtains", "industrial curtains grey linen"),
    ("curtains", "dark grey curtains industrial"),
    ("throw_blanket", "grey knit throw blanket industrial"),
    ("throw_blanket", "charcoal woven throw blanket"),

    # === japandi (2 queries) ===
    ("plants", "artificial bonsai tree"),
    ("plants", "faux moss ball zen minimalist"),

    # === coastal (1 query) ===
    ("throw_blanket", "coastal throw blanket blue white"),

    # === cottagecore (1 query) ===
    ("plants", "artificial lavender plant"),

    # === premium curtains — price ceiling fix (3 queries) ===
    ("curtains", "luxury velvet curtains 96 inch"),
    ("curtains", "premium linen curtains long 108 inch"),
    ("curtains", "silk curtains bedroom luxury"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Targeted catalog fetch (46 queries)")
    parser.add_argument("--go", action="store_true", help="Execute (default is dry-run)")
    parser.add_argument("--limit", type=int, default=40, help="Results per query")
    parser.add_argument("--max", type=int, default=50, help="Request ceiling")
    args = parser.parse_args()

    print(f"Targeted fetch: {len(QUERIES)} queries")
    print(f"Estimated cost: ${len(QUERIES) * 0.01:.2f}")
    print()

    # Show plan
    from collections import defaultdict
    by_slot = defaultdict(list)
    for slot, term in QUERIES:
        by_slot[slot].append(term)

    for slot in sorted(by_slot):
        print(f"  {slot} ({len(by_slot[slot])} queries)")
        for t in by_slot[slot]:
            print(f"    \"{t}\"")
    print()

    if not args.go:
        print("Dry run — pass --go to execute.")
        return

    client = CanopyClient()

    total = len(QUERIES)
    requests_made = 0
    total_added = 0

    print(f"Executing {total} queries (ceiling: {args.max})...\n")

    for i, (slot_id, search_term) in enumerate(QUERIES, 1):
        if requests_made >= args.max:
            print(f"\n  CEILING HIT ({args.max}). Stopping.")
            break

        print(f"  [{i}/{total}] {slot_id}: \"{search_term}\"...", end=" ", flush=True)

        try:
            results = client.search_products(search_term, limit=args.limit)
            requests_made += 1

            products = []
            for raw in results:
                mapped = map_canopy_product(slot_id, raw)
                if mapped:
                    products.append(mapped)

            merged_total, newly_added = merge_cache(slot_id, products)
            total_added += newly_added
            print(f"{len(products)} fetched, {newly_added} new (total: {merged_total})")

        except Exception as exc:
            requests_made += 1
            print(f"ERROR: {exc}")

    print(f"\n{'─' * 72}")
    print(f"  Done. {requests_made} API request(s), {total_added} new products added.")
    print(f"{'─' * 72}")


if __name__ == "__main__":
    main()

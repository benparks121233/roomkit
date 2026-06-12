#!/usr/bin/env python3
"""
Catalog expansion — gamer_den aesthetic, cooler/sleeker products.
21 queries across wall_art, rug, ceiling_light, floor_lamp, table_lamp, plants.

Usage:
    python scripts/catalog_expansion_gamer_den.py            # execute (default)
    python scripts/catalog_expansion_gamer_den.py --dry-run  # show plan without fetching
"""
from __future__ import annotations

import argparse
import time
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.refresh_catalog import map_canopy_product
from services.sourcing.canopy_client import CanopyClient
from services.sourcing.catalog_cache import merge_cache

# ---------------------------------------------------------------------------
# 21 queries: gamer_den × 6 slots
# ---------------------------------------------------------------------------

QUERIES: list[tuple[str, str, str]] = [
    # wall_art (6)
    ("gamer_den", "wall_art", "abstract dark wall art"),
    ("gamer_den", "wall_art", "minimalist gaming poster vintage"),
    ("gamer_den", "wall_art", "sleek black white art print"),
    ("gamer_den", "wall_art", "dark abstract canvas art"),
    ("gamer_den", "wall_art", "retro video game art print"),
    ("gamer_den", "wall_art", "neon sign wall art"),

    # rug (4)
    ("gamer_den", "rug", "black area rug modern"),
    ("gamer_den", "rug", "dark charcoal rug"),
    ("gamer_den", "rug", "sleek black rug bedroom"),
    ("gamer_den", "rug", "matte black area rug"),

    # ceiling_light (3)
    ("gamer_den", "ceiling_light", "matte black pendant light"),
    ("gamer_den", "ceiling_light", "dark modern ceiling light"),
    ("gamer_den", "ceiling_light", "LED strip ceiling light"),

    # floor_lamp (3)
    ("gamer_den", "floor_lamp", "matte black floor lamp"),
    ("gamer_den", "floor_lamp", "dark modern floor lamp"),
    ("gamer_den", "floor_lamp", "LED floor lamp"),

    # table_lamp (3)
    ("gamer_den", "table_lamp", "matte black table lamp"),
    ("gamer_den", "table_lamp", "dark gaming desk lamp"),
    ("gamer_den", "table_lamp", "LED desk lamp"),

    # plants (2)
    ("gamer_den", "plants", "matte black planter"),
    ("gamer_den", "plants", "dark ceramic planter modern"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Catalog expansion — gamer_den (21 queries)")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show plan without fetching (default: execute)"
    )
    parser.add_argument("--limit", type=int, default=40, help="Results per query")
    parser.add_argument("--delay", type=float, default=0.3, help="Seconds between requests")
    args = parser.parse_args()

    total_queries = len(QUERIES)
    est_cost = total_queries * 0.01

    # Group by slot for plan display
    by_slot: dict[str, list[str]] = defaultdict(list)
    for _aesthetic, slot, term in QUERIES:
        by_slot[slot].append(term)

    print(f"Catalog Expansion — gamer_den (cooler/sleeker products)")
    print(f"{'─' * 72}")
    print(f"  Aesthetic      : gamer_den")
    print(f"  Total queries  : {total_queries}")
    print(f"  Limit per query: {args.limit}")
    print(f"  Est. API cost  : ${est_cost:.2f}")
    print()

    for slot in sorted(by_slot):
        print(f"  [{slot}] — {len(by_slot[slot])} queries")
        for term in by_slot[slot]:
            print(f"    \"{term}\"")
    print()

    if args.dry_run:
        print("Dry run — pass without --dry-run to execute.")
        return

    client = CanopyClient()

    slot_added: dict[str, int] = defaultdict(int)
    total_new = 0
    errors = 0

    print(f"Executing {total_queries} queries (limit={args.limit}, delay={args.delay}s)...\n")

    for i, (aesthetic, slot_id, search_term) in enumerate(QUERIES, 1):
        print(f"  [{i:2d}/{total_queries}] {aesthetic}/{slot_id}: \"{search_term}\"...", end=" ", flush=True)

        try:
            results = client.search_products(search_term, limit=args.limit)

            products = []
            for raw in results:
                mapped = map_canopy_product(slot_id, raw)
                if mapped:
                    products.append(mapped)

            merged_total, newly_added = merge_cache(slot_id, products)
            slot_added[slot_id] += newly_added
            total_new += newly_added
            print(f"{len(products)} fetched, +{newly_added} new (slot total: {merged_total})")

        except Exception as exc:
            errors += 1
            print(f"ERROR: {exc}")

        if i < total_queries:
            time.sleep(args.delay)

    # Final summary
    print(f"\n{'═' * 72}")
    print(f"  FINAL SUMMARY — gamer_den expansion")
    print(f"{'─' * 72}")
    print(f"  Total queries run : {total_queries}")
    print(f"  Errors            : {errors}")
    print(f"  Total new products: {total_new}")
    print(f"  Est. API cost     : ${total_queries * 0.01:.2f}")
    print()
    print(f"  New products added per slot:")
    for slot in sorted(slot_added):
        print(f"    {slot:20s}  +{slot_added[slot]}")
    print(f"{'═' * 72}")


if __name__ == "__main__":
    main()

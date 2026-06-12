#!/usr/bin/env python3
"""
Catalog expansion v3 — 132 queries spanning 6 aesthetics × multiple slots.
Fills aesthetic×slot gaps identified after targeted_fetch.py run.

Usage:
    python scripts/catalog_expansion_v3.py            # execute (default)
    python scripts/catalog_expansion_v3.py --dry-run  # show plan without fetching
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
# 132 queries grouped by aesthetic × slot
# ---------------------------------------------------------------------------

QUERIES: list[tuple[str, str, str]] = [
    # === poster_maximalist (39 queries) ===
    ("poster_maximalist", "bed_frame",      "colorful bed frame"),
    ("poster_maximalist", "bed_frame",      "eclectic bed frame"),
    ("poster_maximalist", "bed_frame",      "bohemian bed frame"),
    ("poster_maximalist", "ceiling_light",  "colorful pendant light"),
    ("poster_maximalist", "ceiling_light",  "eclectic ceiling light"),
    ("poster_maximalist", "ceiling_light",  "colorful chandelier"),
    ("poster_maximalist", "comforter",      "colorful comforter"),
    ("poster_maximalist", "comforter",      "eclectic bedding set"),
    ("poster_maximalist", "comforter",      "bohemian comforter"),
    ("poster_maximalist", "dresser",        "colorful dresser"),
    ("poster_maximalist", "dresser",        "eclectic dresser"),
    ("poster_maximalist", "dresser",        "bohemian dresser"),
    ("poster_maximalist", "floor_lamp",     "colorful floor lamp"),
    ("poster_maximalist", "floor_lamp",     "eclectic floor lamp"),
    ("poster_maximalist", "floor_lamp",     "bohemian floor lamp"),
    ("poster_maximalist", "mirror",         "colorful wall mirror"),
    ("poster_maximalist", "mirror",         "eclectic mirror"),
    ("poster_maximalist", "mirror",         "bohemian mirror"),
    ("poster_maximalist", "nightstand",     "colorful nightstand"),
    ("poster_maximalist", "nightstand",     "eclectic nightstand"),
    ("poster_maximalist", "nightstand",     "bohemian nightstand"),
    ("poster_maximalist", "pillows",        "colorful throw pillows"),
    ("poster_maximalist", "pillows",        "eclectic decorative pillows"),
    ("poster_maximalist", "pillows",        "bohemian pillows"),
    ("poster_maximalist", "rug",            "colorful area rug"),
    ("poster_maximalist", "rug",            "eclectic rug"),
    ("poster_maximalist", "rug",            "bohemian layered rug"),
    ("poster_maximalist", "sheets",         "colorful sheets set"),
    ("poster_maximalist", "sheets",         "eclectic sheets"),
    ("poster_maximalist", "sheets",         "bohemian bed sheets"),
    ("poster_maximalist", "table_lamp",     "colorful table lamp"),
    ("poster_maximalist", "table_lamp",     "eclectic table lamp"),
    ("poster_maximalist", "table_lamp",     "bohemian lamp"),
    ("poster_maximalist", "plants",         "colorful planter"),
    ("poster_maximalist", "plants",         "eclectic plant pot"),
    ("poster_maximalist", "plants",         "bohemian planter"),
    ("poster_maximalist", "throw_blanket",  "colorful throw blanket"),
    ("poster_maximalist", "throw_blanket",  "eclectic throw"),
    ("poster_maximalist", "throw_blanket",  "bohemian throw blanket"),

    # === quiet_luxury (30 queries) ===
    ("quiet_luxury", "bed_frame",    "upholstered bed frame cream"),
    ("quiet_luxury", "bed_frame",    "bouclé bed frame"),
    ("quiet_luxury", "bed_frame",    "tailored bed frame"),
    ("quiet_luxury", "ceiling_light","brushed gold pendant light"),
    ("quiet_luxury", "ceiling_light","brass ceiling light"),
    ("quiet_luxury", "ceiling_light","gold chandelier"),
    ("quiet_luxury", "comforter",    "cashmere comforter"),
    ("quiet_luxury", "comforter",    "cream linen duvet"),
    ("quiet_luxury", "comforter",    "bouclé bedding"),
    ("quiet_luxury", "dresser",      "marble top dresser"),
    ("quiet_luxury", "dresser",      "cream dresser gold"),
    ("quiet_luxury", "dresser",      "tailored dresser"),
    ("quiet_luxury", "nightstand",   "marble nightstand"),
    ("quiet_luxury", "nightstand",   "gold nightstand"),
    ("quiet_luxury", "nightstand",   "cream nightstand"),
    ("quiet_luxury", "table_lamp",   "marble table lamp"),
    ("quiet_luxury", "table_lamp",   "brushed gold lamp"),
    ("quiet_luxury", "table_lamp",   "brass table lamp"),
    ("quiet_luxury", "wall_art",     "fine art print framed"),
    ("quiet_luxury", "wall_art",     "understated wall art"),
    ("quiet_luxury", "wall_art",     "neutral abstract art"),
    ("quiet_luxury", "mirror",       "gold framed mirror"),
    ("quiet_luxury", "mirror",       "brushed gold mirror"),
    ("quiet_luxury", "mirror",       "brass wall mirror"),
    ("quiet_luxury", "plants",       "marble planter"),
    ("quiet_luxury", "plants",       "gold planter"),
    ("quiet_luxury", "plants",       "cream ceramic planter"),
    ("quiet_luxury", "sheets",       "linen sheets set"),
    ("quiet_luxury", "sheets",       "sateen sheets cream"),
    ("quiet_luxury", "sheets",       "fine grain cotton sheets"),

    # === dark_academia (21 queries) ===
    ("dark_academia", "bed_frame",  "dark walnut bed frame"),
    ("dark_academia", "bed_frame",  "velvet bed frame"),
    ("dark_academia", "bed_frame",  "dark wood bed frame"),
    ("dark_academia", "comforter",  "velvet comforter"),
    ("dark_academia", "comforter",  "dark green comforter set"),
    ("dark_academia", "comforter",  "moody bedding"),
    ("dark_academia", "curtains",   "velvet curtains dark"),
    ("dark_academia", "curtains",   "dark green curtains"),
    ("dark_academia", "curtains",   "moody velvet drapes"),
    ("dark_academia", "dresser",    "dark walnut dresser"),
    ("dark_academia", "dresser",    "antique dresser dark"),
    ("dark_academia", "dresser",    "dark wood dresser"),
    ("dark_academia", "mirror",     "antique brass mirror"),
    ("dark_academia", "mirror",     "dark framed mirror"),
    ("dark_academia", "mirror",     "vintage wall mirror"),
    ("dark_academia", "plants",     "dark ceramic planter"),
    ("dark_academia", "plants",     "antique brass planter"),
    ("dark_academia", "plants",     "moody planter"),
    ("dark_academia", "rug",        "dark area rug vintage"),
    ("dark_academia", "rug",        "moody rug"),
    ("dark_academia", "rug",        "dark green rug"),

    # === sports_den (21 queries) ===
    ("sports_den", "ceiling_light", "warm brass ceiling light"),
    ("sports_den", "ceiling_light", "dark pendant light"),
    ("sports_den", "ceiling_light", "masculine chandelier"),
    ("sports_den", "floor_lamp",    "leather floor lamp"),
    ("sports_den", "floor_lamp",    "dark brass floor lamp"),
    ("sports_den", "floor_lamp",    "warm wood floor lamp"),
    ("sports_den", "table_lamp",    "leather table lamp"),
    ("sports_den", "table_lamp",    "dark brass table lamp"),
    ("sports_den", "table_lamp",    "warm wood desk lamp"),
    ("sports_den", "comforter",     "dark comforter set"),
    ("sports_den", "comforter",     "masculine bedding"),
    ("sports_den", "comforter",     "dark leather accent bedding"),
    ("sports_den", "dresser",       "dark wood dresser"),
    ("sports_den", "dresser",       "warm wood dresser"),
    ("sports_den", "dresser",       "masculine dresser"),
    ("sports_den", "mirror",        "dark framed mirror"),
    ("sports_den", "mirror",        "leather wall mirror"),
    ("sports_den", "mirror",        "masculine mirror"),
    ("sports_den", "plants",        "dark planter ceramic"),
    ("sports_den", "plants",        "leather planter"),
    ("sports_den", "plants",        "masculine planter"),

    # === japandi (9 queries) ===
    ("japandi", "comforter",  "minimalist comforter"),
    ("japandi", "comforter",  "organic cotton duvet"),
    ("japandi", "comforter",  "zen bedding"),
    ("japandi", "dresser",    "ash wood dresser"),
    ("japandi", "dresser",    "minimalist dresser"),
    ("japandi", "dresser",    "japandi dresser"),
    ("japandi", "nightstand", "ash nightstand"),
    ("japandi", "nightstand", "minimalist nightstand"),
    ("japandi", "nightstand", "japandi nightstand"),

    # === jungle_oasis (6 queries) ===
    ("jungle_oasis", "bed_frame", "rattan bed frame"),
    ("jungle_oasis", "bed_frame", "tropical bed frame"),
    ("jungle_oasis", "bed_frame", "natural wood bed"),
    ("jungle_oasis", "dresser",   "rattan dresser"),
    ("jungle_oasis", "dresser",   "tropical dresser"),
    ("jungle_oasis", "dresser",   "natural wood dresser"),

    # === warm_minimalist (6 queries) ===
    ("warm_minimalist", "dresser", "natural wood dresser"),
    ("warm_minimalist", "dresser", "light oak dresser"),
    ("warm_minimalist", "dresser", "minimal dresser"),
    ("warm_minimalist", "mirror",  "natural wood mirror"),
    ("warm_minimalist", "mirror",  "minimal wall mirror"),
    ("warm_minimalist", "mirror",  "light oak mirror"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Catalog expansion v3 (132 queries)")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show plan without fetching (default: execute)"
    )
    parser.add_argument("--limit", type=int, default=40, help="Results per query")
    parser.add_argument("--delay", type=float, default=0.3, help="Seconds between requests")
    args = parser.parse_args()

    total_queries = len(QUERIES)
    est_cost = total_queries * 0.01

    # Group by aesthetic for plan display
    by_aesthetic: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for aesthetic, slot, term in QUERIES:
        by_aesthetic[aesthetic][slot].append(term)

    print(f"Catalog Expansion v3")
    print(f"{'─' * 72}")
    print(f"  Total queries : {total_queries}")
    print(f"  Limit per query: {args.limit}")
    print(f"  Est. API cost : ${est_cost:.2f}")
    print()

    for aesthetic in sorted(by_aesthetic):
        slots = by_aesthetic[aesthetic]
        q_count = sum(len(v) for v in slots.values())
        print(f"  [{aesthetic}] — {q_count} queries")
        for slot in sorted(slots):
            print(f"    {slot}:")
            for term in slots[slot]:
                print(f"      \"{term}\"")
    print()

    if args.dry_run:
        print("Dry run — pass without --dry-run to execute.")
        return

    client = CanopyClient()

    # Track per-slot additions
    slot_added: dict[str, int] = defaultdict(int)
    total_new = 0
    errors = 0

    print(f"Executing {total_queries} queries (limit={args.limit}, delay={args.delay}s)...\n")

    for i, (aesthetic, slot_id, search_term) in enumerate(QUERIES, 1):
        print(f"  [{i:3d}/{total_queries}] {aesthetic}/{slot_id}: \"{search_term}\"...", end=" ", flush=True)

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

        # Rate-limit courtesy delay
        if i < total_queries:
            time.sleep(args.delay)

    # Final summary
    print(f"\n{'═' * 72}")
    print(f"  FINAL SUMMARY")
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

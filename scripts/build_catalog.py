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
    # =================================================================
    # BED-GROUP CATEGORIES — already 200+ each, skip these entirely.
    # bed_frame (296), mattress (238), sheets (242), comforter (268).
    # =================================================================

    # -----------------------------------------------------------------
    # pillows — currently 40, target 150+
    # -----------------------------------------------------------------
    ("pillows", "memory foam pillow queen size"),
    ("pillows", "gel cooling pillow queen"),
    ("pillows", "firm bed pillow queen 2 pack"),
    ("pillows", "soft bed pillow queen 2 pack"),
    ("pillows", "hotel quality pillow queen"),
    ("pillows", "bamboo pillow queen size"),
    ("pillows", "shredded memory foam pillow"),
    ("pillows", "hypoallergenic pillow queen"),

    # -----------------------------------------------------------------
    # nightstand — currently 101, target 200+
    # -----------------------------------------------------------------
    ("nightstand", "mid century modern nightstand walnut"),
    ("nightstand", "industrial metal nightstand"),
    ("nightstand", "white nightstand coastal"),
    ("nightstand", "nightstand with charging station"),
    ("nightstand", "minimalist nightstand bedroom"),
    ("nightstand", "farmhouse nightstand wood"),

    # -----------------------------------------------------------------
    # dresser — currently 72, target 200+
    # -----------------------------------------------------------------
    ("dresser", "mid century modern dresser walnut"),
    ("dresser", "industrial metal dresser"),
    ("dresser", "white dresser coastal bedroom"),
    ("dresser", "tall dresser 5 drawer bedroom"),
    ("dresser", "small dresser bedroom compact"),
    ("dresser", "wide dresser 6 drawer"),

    # -----------------------------------------------------------------
    # ceiling_light — currently 73, target 200+
    # -----------------------------------------------------------------
    ("ceiling_light", "mid century modern ceiling light"),
    ("ceiling_light", "industrial ceiling light matte black"),
    ("ceiling_light", "coastal flush mount ceiling light"),
    ("ceiling_light", "minimalist flush mount ceiling light"),
    ("ceiling_light", "bedroom ceiling light fixture"),
    ("ceiling_light", "led flush mount light warm white"),

    # -----------------------------------------------------------------
    # table_lamp — currently 80, target 200+
    # -----------------------------------------------------------------
    ("table_lamp", "mid century modern table lamp brass"),
    ("table_lamp", "industrial table lamp matte black"),
    ("table_lamp", "rattan table lamp boho"),
    ("table_lamp", "small bedside lamp modern"),
    ("table_lamp", "touch table lamp bedroom"),
    ("table_lamp", "glass table lamp bedroom"),

    # -----------------------------------------------------------------
    # floor_lamp — currently 79, target 200+
    # -----------------------------------------------------------------
    ("floor_lamp", "mid century modern floor lamp brass"),
    ("floor_lamp", "industrial floor lamp black metal"),
    ("floor_lamp", "arc floor lamp minimalist"),
    ("floor_lamp", "tripod floor lamp bedroom"),
    ("floor_lamp", "reading floor lamp adjustable"),
    ("floor_lamp", "dimmable floor lamp living room"),

    # -----------------------------------------------------------------
    # wall_art — currently 98, target 250+ (style + interest variants)
    # -----------------------------------------------------------------
    # Style variants
    ("wall_art", "mid century modern wall art print"),
    ("wall_art", "industrial wall art metal"),
    ("wall_art", "coastal wall art ocean print"),
    ("wall_art", "japandi wall art minimalist print"),
    ("wall_art", "dark academia wall art vintage"),
    ("wall_art", "black and white photography wall art"),
    ("wall_art", "boho wall art set framed"),
    ("wall_art", "abstract wall art large canvas"),
    # Interest: music
    ("wall_art", "music wall art vinyl record print"),
    ("wall_art", "vinyl record wall art decor"),
    ("wall_art", "music notes wall art bedroom"),
    ("wall_art", "concert poster wall art vintage"),
    # Interest: sports
    ("wall_art", "sports wall art basketball poster"),
    ("wall_art", "sports wall art football baseball"),
    ("wall_art", "athletic wall art motivational"),
    # Interest: travel
    ("wall_art", "travel world map wall art print"),
    ("wall_art", "travel poster wall art vintage city"),
    ("wall_art", "destination prints wall art framed"),
    # Interest: art & film
    ("wall_art", "movie poster wall art classic film"),
    ("wall_art", "gallery wall art prints framed"),
    ("wall_art", "fine art photography print framed"),
    # Interest: books
    ("wall_art", "literary wall art book quote print"),
    ("wall_art", "library wall art vintage book print"),
    # Interest: gaming
    ("wall_art", "gaming wall art retro neon"),
    ("wall_art", "video game wall art poster"),
    # Interest: plants / nature
    ("wall_art", "nature photography wall art landscape"),
    ("wall_art", "botanical illustration wall art framed"),

    # -----------------------------------------------------------------
    # plants — currently 71, target 200+
    # -----------------------------------------------------------------
    ("plants", "artificial snake plant indoor"),
    ("plants", "faux eucalyptus plant"),
    ("plants", "fake pothos plant indoor"),
    ("plants", "artificial bird of paradise"),
    ("plants", "faux fiddle leaf fig tree"),
    ("plants", "small artificial succulent plant set"),
    ("plants", "artificial olive tree indoor"),
    ("plants", "faux monstera plant"),

    # -----------------------------------------------------------------
    # mirror — currently 39, target 200+
    # -----------------------------------------------------------------
    ("mirror", "mid century modern mirror brass"),
    ("mirror", "industrial mirror metal frame"),
    ("mirror", "arched mirror bedroom"),
    ("mirror", "full length floor mirror standing"),
    ("mirror", "round wall mirror gold"),
    ("mirror", "black framed wall mirror rectangle"),
    ("mirror", "vanity mirror bedroom"),
    ("mirror", "oval wall mirror bathroom"),

    # -----------------------------------------------------------------
    # rug — currently 89, target 200+
    # -----------------------------------------------------------------
    ("rug", "mid century modern area rug 5x8"),
    ("rug", "industrial area rug dark 5x8"),
    ("rug", "coastal area rug blue white 5x8"),
    ("rug", "boho area rug colorful 5x8"),
    ("rug", "neutral area rug bedroom 8x10"),
    ("rug", "washable area rug 5x8"),
    ("rug", "shag area rug bedroom 5x8"),
    ("rug", "geometric area rug modern 5x8"),

    # -----------------------------------------------------------------
    # curtains — currently 70, target 200+
    # -----------------------------------------------------------------
    ("curtains", "mid century modern curtains"),
    ("curtains", "velvet curtains bedroom"),
    ("curtains", "sheer curtains white bedroom"),
    ("curtains", "blackout curtains 84 inch"),
    ("curtains", "linen curtains natural beige"),
    ("curtains", "thermal insulated curtains bedroom"),

    # -----------------------------------------------------------------
    # throw_blanket — currently 66, target 200+
    # -----------------------------------------------------------------
    ("throw_blanket", "chunky knit throw blanket"),
    ("throw_blanket", "cotton throw blanket minimalist"),
    ("throw_blanket", "faux fur throw blanket"),
    ("throw_blanket", "waffle weave throw blanket"),
    ("throw_blanket", "fleece throw blanket soft"),
    ("throw_blanket", "woven throw blanket boho"),
    ("throw_blanket", "lightweight throw blanket summer"),
]

DEFAULT_LIMIT = 40
DEFAULT_MAX_REQUESTS = 120


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

#!/usr/bin/env python3
"""
Catalog gap analysis v2 — stricter criteria:
1. Total count < 150 per category
2. Price × aesthetic matrix: on-aesthetic items at low/mid/high/premium bands
3. Targeted fetch plan for both gaps
"""
from __future__ import annotations

import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.sourcing.catalog_cache import read_cache
from services.config_loader import load_style_profiles

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

SLOTS = [
    "bed_frame", "mattress", "sheets", "comforter", "pillows",
    "nightstand", "dresser", "ceiling_light", "table_lamp", "floor_lamp",
    "wall_art", "plants", "mirror", "rug", "curtains", "throw_blanket",
]

# Price bands per category — (low_max, mid_max, high_max, premium = above high_max)
# Based on realistic Amazon price tiers for each product type.
PRICE_BANDS: dict[str, tuple[float, float, float]] = {
    "bed_frame":      (100, 200, 400),
    "mattress":       (150, 300, 600),
    "sheets":         (25,  50, 100),
    "comforter":      (30,  50, 100),
    "pillows":        (20,  40,  80),
    "nightstand":     (50, 100, 200),
    "dresser":        (80, 150, 300),
    "ceiling_light":  (30,  60, 120),
    "table_lamp":     (25,  50, 100),
    "floor_lamp":     (40,  70, 130),
    "wall_art":       (15,  30,  60),
    "plants":         (15,  30,  60),
    "mirror":         (30,  60, 120),
    "rug":            (50, 100, 200),
    "curtains":       (20,  35,  60),
    "throw_blanket":  (20,  35,  60),
}

BAND_NAMES = ["low", "mid", "high", "premium"]

profiles = load_style_profiles()
CORES = {p.id: p.keywords for p in profiles.profiles if p.id != "warm_minimalist"}
CORE_IDS = list(CORES.keys())

catalogs: dict[str, list[dict]] = {}
for sid in SLOTS:
    data = read_cache(sid)
    catalogs[sid] = data if data else []

def get_band(price: float, slot_id: str) -> int:
    """Return band index: 0=low, 1=mid, 2=high, 3=premium."""
    thresholds = PRICE_BANDS[slot_id]
    if price <= thresholds[0]:
        return 0
    if price <= thresholds[1]:
        return 1
    if price <= thresholds[2]:
        return 2
    return 3

def is_aesthetic_match(name: str, keywords: list[str]) -> bool:
    name_lower = name.lower()
    return any(kw.lower() in name_lower for kw in keywords)


# ===========================================================================
# 1. CATEGORIES UNDER 150 TOTAL
# ===========================================================================

print("=" * 100)
print("  1. CATEGORY DEPTH (threshold: 150)")
print("=" * 100)
print()
print(f"  {'Category':<18} {'Total':>6}  {'Low':>6}  {'Mid':>6}  {'High':>6}  {'Prem':>6}  {'Status':>10}")
print(f"  {'─' * 75}")

thin_categories = []

for sid in SLOTS:
    products = catalogs[sid]
    n = len(products)
    bands = [0, 0, 0, 0]
    for p in products:
        b = get_band(float(p["normalized_price"]), sid)
        bands[b] += 1

    status = "OK" if n >= 150 else "THIN"
    if n < 150:
        thin_categories.append((sid, n))

    print(f"  {sid:<18} {n:>6}  {bands[0]:>6}  {bands[1]:>6}  {bands[2]:>6}  {bands[3]:>6}  {status:>10}")

print()
if thin_categories:
    print(f"  Categories under 150: {len(thin_categories)}")
    for sid, n in thin_categories:
        print(f"    {sid}: {n}")
else:
    print("  All categories at 150+")
print()

# ===========================================================================
# 2. PRICE × AESTHETIC MATRIX
# ===========================================================================

print("=" * 100)
print("  2. PRICE × AESTHETIC COVERAGE")
print("=" * 100)
print()

# For each aesthetic × slot × band: count on-aesthetic items.
# Flag: aesthetic has items but ONLY at low end (no mid/high/premium).

# Build the full data structure
# coverage[core][slot] = [low_count, mid_count, high_count, premium_count]
coverage: dict[str, dict[str, list[int]]] = {}
for core_id, keywords in CORES.items():
    coverage[core_id] = {}
    for sid in SLOTS:
        band_counts = [0, 0, 0, 0]
        for p in catalogs[sid]:
            if is_aesthetic_match(p["name"], keywords):
                b = get_band(float(p["normalized_price"]), sid)
                band_counts[b] += 1
        coverage[core_id][sid] = band_counts

# Print per-aesthetic tables
# Skip bedding slots (mattress, sheets, comforter, pillows) — they never keyword-match
FURNITURE_DECOR = [
    "bed_frame", "nightstand", "dresser", "ceiling_light", "table_lamp",
    "floor_lamp", "wall_art", "plants", "mirror", "rug", "curtains",
    "throw_blanket",
]

# Compact matrix: show band coverage as L/M/H/P with counts
for core_id in CORE_IDS:
    keywords = CORES[core_id]
    print(f"  {core_id} — keywords: {', '.join(keywords[:5])}...")
    print(f"  {'Slot':<18} {'Low':>6} {'Mid':>6} {'High':>6} {'Prem':>6} {'Total':>6}  Gaps")
    print(f"  {'─' * 70}")

    for sid in FURNITURE_DECOR:
        bc = coverage[core_id][sid]
        total = sum(bc)
        gaps = []
        if total == 0:
            gaps.append("NO ITEMS")
        else:
            if bc[1] + bc[2] + bc[3] == 0:
                gaps.append("LOW ONLY")
            else:
                if bc[2] == 0 and bc[3] == 0:
                    gaps.append("no high/prem")
                elif bc[3] == 0 and PRICE_BANDS[sid][2] < 999:
                    # Only flag missing premium if premium is realistic for this category
                    pass  # premium tier is optional for cheap categories
                if bc[1] == 0:
                    gaps.append("no mid")

        gap_str = ", ".join(gaps) if gaps else ""
        print(f"  {sid:<18} {bc[0]:>6} {bc[1]:>6} {bc[2]:>6} {bc[3]:>6} {bc[2]+bc[3]:>6}  {gap_str}")

    print()

# ===========================================================================
# Summary: which aesthetic×slot×band combos are missing?
# ===========================================================================

print("=" * 100)
print("  AESTHETIC × PRICE GAP SUMMARY")
print("=" * 100)
print()

# Focus on the "should be premium" aesthetics AND slots where they have SOME
# items but lack upper bands, plus any aesthetic with NO items at all in a slot.

# For the fetch plan: we care about furniture/decor slots where:
# (a) total on-aesthetic = 0 (no items at any price), OR
# (b) on-aesthetic items exist but high+premium = 0 (can't fill high budgets on-style)

fetch_needs: list[tuple[str, str, str]] = []  # (core, slot, reason)

for core_id in CORE_IDS:
    for sid in FURNITURE_DECOR:
        bc = coverage[core_id][sid]
        total = sum(bc)
        upper = bc[2] + bc[3]

        if total == 0:
            fetch_needs.append((core_id, sid, "zero"))
        elif upper == 0 and total >= 3:
            fetch_needs.append((core_id, sid, "low_only"))

# Group by core
by_core: dict[str, list[tuple[str, str]]] = defaultdict(list)
for core, slot, reason in fetch_needs:
    by_core[core].append((slot, reason))

print(f"  {'Core':<16} {'Zero coverage':>14} {'Low-only':>10} {'Total gaps':>11}")
print(f"  {'─' * 55}")
for core_id in CORE_IDS:
    items = by_core.get(core_id, [])
    zeros = sum(1 for _, r in items if r == "zero")
    lows = sum(1 for _, r in items if r == "low_only")
    print(f"  {core_id:<16} {zeros:>14} {lows:>10} {zeros + lows:>11}")

print()

# ===========================================================================
# 3. FETCH PLAN
# ===========================================================================

print("=" * 100)
print("  3. TARGETED FETCH PLAN")
print("=" * 100)
print()

# ---- Part A: thin categories (<150) ----

# Query templates for broadening thin categories
BROADENING_QUERIES: dict[str, list[tuple[str, str]]] = {
    "pillows": [
        ("pillows", "organic cotton pillow queen"),
        ("pillows", "down alternative pillow firm queen"),
        ("pillows", "luxury pillow queen hotel"),
        ("pillows", "cervical memory foam pillow"),
    ],
}

queries: list[tuple[str, str]] = []

print("  PART A: Broaden thin categories (< 150 total)")
print()
for sid, n in thin_categories:
    broadening = BROADENING_QUERIES.get(sid, [])
    if broadening:
        print(f"    {sid} ({n} products) — {len(broadening)} queries")
        queries.extend(broadening)

if not thin_categories:
    print("    None — all categories at 150+")
print()

# ---- Part B: aesthetic × price gaps ----

print("  PART B: Aesthetic-specific queries for price × coverage gaps")
print()

# Generate queries per core×slot gap.
# For "zero" gaps: 2 queries (one general, one premium).
# For "low_only" gaps: 1 query (premium/high-end specifically).

AESTHETIC_QUERY_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "quiet_luxury": {
        "bed_frame":      ["upholstered bed frame queen linen", "luxury bed frame queen velvet tufted"],
        "nightstand":     ["luxury nightstand marble top brass", "cream nightstand gold hardware"],
        "dresser":        ["luxury white dresser brass handles", "cream dresser gold accents high end"],
        "ceiling_light":  ["luxury brass flush mount ceiling light", "gold flush mount light modern"],
        "table_lamp":     ["marble table lamp brass accent", "luxury alabaster table lamp"],
        "floor_lamp":     ["luxury floor lamp brass marble base", "modern gold floor lamp premium"],
        "wall_art":       ["luxury abstract art gold framed", "neutral minimalist art print large framed"],
        "plants":         ["luxury artificial orchid arrangement", "faux olive tree premium indoor"],
        "mirror":         ["luxury gold mirror large decorative", "brass arched mirror premium"],
        "rug":            ["luxury wool area rug cream ivory 5x8", "high end neutral rug ivory 8x10"],
        "curtains":       ["luxury linen curtains ivory 96 inch", "silk curtains cream bedroom premium"],
        "throw_blanket":  ["cashmere throw blanket cream luxury", "merino wool throw blanket ivory"],
    },
    "dark_academia": {
        "bed_frame":      ["dark wood bed frame queen traditional", "mahogany bed frame queen"],
        "nightstand":     ["antique dark wood nightstand", "vintage mahogany nightstand drawer"],
        "dresser":        ["dark wood dresser traditional", "vintage mahogany dresser bedroom"],
        "ceiling_light":  ["antique brass ceiling light flush", "vintage dark flush mount light"],
        "table_lamp":     ["antique brass desk lamp green shade", "vintage banker lamp brass"],
        "floor_lamp":     ["antique brass floor lamp reading", "vintage library floor lamp bronze"],
        "wall_art":       ["dark academia wall art vintage framed", "antique botanical print set framed"],
        "plants":         ["artificial fern vintage planter", "faux ivy plant antique pot"],
        "mirror":         ["antique gold ornate mirror", "vintage dark wood frame mirror large"],
        "rug":            ["dark oriental area rug 5x8", "vintage persian rug dark red"],
        "curtains":       ["velvet curtains dark green 84 inch", "burgundy velvet curtains bedroom"],
        "throw_blanket":  ["velvet throw blanket dark green", "tartan plaid throw blanket wool"],
    },
    "sports_den": {
        "bed_frame":      ["dark upholstered bed frame queen leather", "platform bed frame dark charcoal queen"],
        "nightstand":     ["industrial nightstand dark metal wood", "dark leather nightstand bedroom"],
        "dresser":        ["industrial dresser dark metal wood", "dark masculine dresser bedroom"],
        "ceiling_light":  ["industrial flush mount ceiling light dark", "matte black ceiling light modern"],
        "table_lamp":     ["industrial table lamp matte black metal", "brass desk lamp dark masculine"],
        "floor_lamp":     ["industrial floor lamp dark metal", "brass floor lamp dark shade"],
        "wall_art":       ["dark moody wall art framed masculine", "vintage sports memorabilia wall art framed"],
        "plants":         ["artificial plant dark planter modern", "faux snake plant black pot"],
        "mirror":         ["large mirror dark frame industrial", "matte black wall mirror modern"],
        "rug":            ["dark area rug charcoal 5x8", "navy dark area rug masculine 8x10"],
        "curtains":       ["dark charcoal blackout curtains 84", "navy velvet curtains bedroom"],
        "throw_blanket":  ["dark charcoal throw blanket chunky", "leather accent throw blanket brown"],
    },
    "industrial": {
        "bed_frame":      ["industrial metal bed frame queen", "iron bed frame queen black"],
        "nightstand":     ["industrial metal nightstand pipe", "reclaimed wood nightstand metal"],
        "dresser":        ["industrial metal dresser", "reclaimed wood dresser metal frame"],
        "ceiling_light":  ["industrial cage ceiling light", "edison bulb flush mount ceiling"],
        "table_lamp":     ["industrial pipe table lamp", "edison bulb desk lamp metal"],
        "floor_lamp":     ["industrial tripod floor lamp metal", "pipe floor lamp edison"],
        "wall_art":       ["industrial metal wall art", "urban loft wall decor metal"],
        "plants":         ["artificial plant concrete planter", "faux plant industrial pot metal"],
        "mirror":         ["industrial metal frame mirror", "pipe frame mirror large"],
        "rug":            ["industrial area rug dark grey 5x8", "distressed urban area rug 5x8"],
        "curtains":       ["industrial curtains grey linen", "dark grey curtains industrial"],
        "throw_blanket":  ["grey knit throw blanket industrial", "charcoal woven throw blanket"],
    },
    "coastal": {
        "floor_lamp":     ["rattan floor lamp coastal", "white washed wood floor lamp beach"],
        "mirror":         ["coastal rope mirror round", "whitewash wood mirror beach"],
        "throw_blanket":  ["coastal throw blanket blue white", "cotton throw blanket seafoam"],
        "rug":            ["coastal area rug blue white 5x8", "jute area rug natural beach 5x8"],
    },
    "japandi": {
        "curtains":       ["japanese linen curtains natural", "minimalist sheer curtains organic cotton"],
        "plants":         ["artificial bonsai tree", "faux moss ball zen minimalist"],
    },
    "cottagecore": {
        "nightstand":     ["vintage nightstand floral distressed", "cottage nightstand white wood"],
        "dresser":        ["vintage dresser distressed white", "cottage dresser floral hardware"],
        "plants":         ["artificial lavender plant", "faux wildflower arrangement cottage"],
        "mirror":         ["vintage ornate mirror distressed white", "cottage mirror floral frame"],
    },
    "ski_lodge": {
        "rug":            ["rustic cabin area rug plaid 5x8", "lodge area rug bear moose 5x8"],
        "mirror":         ["rustic wood frame mirror cabin", "lodge mirror antler decor"],
    },
    # city_modern: well-covered, skip
}

for core_id in CORE_IDS:
    gaps = by_core.get(core_id, [])
    templates = AESTHETIC_QUERY_TEMPLATES.get(core_id, {})
    if not gaps or not templates:
        continue

    core_queries = []
    for slot, reason in gaps:
        slot_terms = templates.get(slot, [])
        if not slot_terms:
            continue
        if reason == "low_only":
            # Only need premium — take the last (more premium) query
            core_queries.append((slot, slot_terms[-1]))
        else:
            # Zero coverage — take all queries
            for term in slot_terms:
                core_queries.append((slot, term))

    if core_queries:
        print(f"    {core_id} ({len(core_queries)} queries):")
        by_slot = defaultdict(list)
        for slot, term in core_queries:
            by_slot[slot].append(term)
        for slot in FURNITURE_DECOR:
            if slot in by_slot:
                terms = by_slot[slot]
                bc = coverage[core_id][slot]
                reason = "zero" if sum(bc) == 0 else "low-only"
                print(f"      {slot:<18} [{reason:<8}] {len(terms)} queries")
                for t in terms:
                    print(f"        \"{t}\"")
        queries.extend(core_queries)
    print()

# ---- Part C: premium curtains (price ceiling fix) ----

print("  PART C: Premium price-band (curtains ceiling fix)")
print()
PREMIUM_CURTAINS = [
    ("curtains", "luxury velvet curtains 96 inch"),
    ("curtains", "premium linen curtains long 108 inch"),
    ("curtains", "silk curtains bedroom luxury"),
]
for sid, term in PREMIUM_CURTAINS:
    print(f"    \"{term}\"")
queries.extend(PREMIUM_CURTAINS)
print()

# ===========================================================================
# FINAL SUMMARY
# ===========================================================================

print("=" * 100)
print("  FETCH PLAN SUMMARY")
print("=" * 100)
print()

slot_counts: dict[str, int] = defaultdict(int)
for sid, term in queries:
    slot_counts[sid] += 1

print(f"  Total queries: {len(queries)}")
print(f"  Estimated Canopy cost: {len(queries)} × $0.01 = ${len(queries) * 0.01:.2f}")
print(f"  At limit=40/query: up to {len(queries) * 40:,} new candidate products (before dedup)")
print()

print(f"  By category:")
for sid in SLOTS:
    if sid in slot_counts:
        print(f"    {sid:<18} {slot_counts[sid]:>3} queries")
print()

# By purpose
part_a = sum(len(v) for v in BROADENING_QUERIES.values() if any(sid == s for s, _ in thin_categories for v_item in v if v_item[0] == s))
part_a_count = len([q for q in queries if q in [item for sublist in BROADENING_QUERIES.values() for item in sublist]])

# Count by core
core_query_counts: dict[str, int] = defaultdict(int)
for core_id in CORE_IDS:
    gaps = by_core.get(core_id, [])
    templates = AESTHETIC_QUERY_TEMPLATES.get(core_id, {})
    for slot, reason in gaps:
        slot_terms = templates.get(slot, [])
        if reason == "low_only":
            core_query_counts[core_id] += min(1, len(slot_terms))
        else:
            core_query_counts[core_id] += len(slot_terms)

print(f"  By aesthetic:")
for cid in CORE_IDS:
    if core_query_counts[cid]:
        print(f"    {cid:<18} {core_query_counts[cid]:>3} queries")
print(f"    {'premium curtains':<18} {len(PREMIUM_CURTAINS):>3} queries")
print(f"    {'thin categories':<18} {len([q for q in queries if q in [item for sublist in BROADENING_QUERIES.values() for item in sublist]]):>3} queries")
print()

# Dedup check
seen = set()
dupes = 0
for sid, term in queries:
    key = (sid, term)
    if key in seen:
        dupes += 1
    seen.add(key)
print(f"  Unique queries: {len(seen)} (dupes: {dupes})")
print(f"  Final request count: {len(seen)}")
print(f"  Final estimated cost: ${len(seen) * 0.01:.2f}")
print()

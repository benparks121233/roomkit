#!/usr/bin/env python3
"""
Catalog gap analysis: price bands, per-aesthetic coverage, targeted fetch plan.
No API calls — reads only from local catalog cache.
"""
from __future__ import annotations

import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.sourcing.catalog_cache import read_cache
from services.config_loader import load_style_profiles

# ---------------------------------------------------------------------------
# Load all catalog data + style profiles
# ---------------------------------------------------------------------------

SLOTS = [
    "bed_frame", "mattress", "sheets", "comforter", "pillows",
    "nightstand", "dresser", "ceiling_light", "table_lamp", "floor_lamp",
    "wall_art", "plants", "mirror", "rug", "curtains", "throw_blanket",
]

profiles = load_style_profiles()
CORES = {p.id: p.keywords for p in profiles.profiles if p.id != "warm_minimalist"}

catalogs: dict[str, list[dict]] = {}
for sid in SLOTS:
    data = read_cache(sid)
    catalogs[sid] = data if data else []

# ===========================================================================
# 1. PRICE BANDS
# ===========================================================================

print("=" * 100)
print("  1. PRICE DISTRIBUTION PER CATEGORY")
print("=" * 100)
print()

# Typical budget allocations at $1500 and $2500 budgets (approximate)
# These are rough — composition varies — but give a reference ceiling.
TYPICAL_ALLOC_1500 = {
    "bed_frame": 285, "mattress": 233, "sheets": 39, "comforter": 39,
    "pillows": 26, "nightstand": 116, "dresser": 116, "ceiling_light": 52,
    "table_lamp": 39, "floor_lamp": 65, "wall_art": 91, "plants": 26,
    "mirror": 39, "rug": 168, "curtains": 103, "throw_blanket": 52,
}
TYPICAL_ALLOC_2500 = {k: int(v * 2500 / 1500) for k, v in TYPICAL_ALLOC_1500.items()}

print(f"  {'Category':<18} {'Count':>6} {'Min':>7} {'P25':>7} {'P50':>7} {'P75':>7} "
      f"{'P90':>7} {'Max':>7}  {'$1500':>7} {'$2500':>7} {'Gap?':>12}")
print(f"  {'─' * 105}")

price_gaps = []

for sid in SLOTS:
    products = catalogs[sid]
    if not products:
        print(f"  {sid:<18} {'EMPTY':>6}")
        continue

    prices = sorted(float(p["normalized_price"]) for p in products)
    n = len(prices)

    def pct(percentile):
        idx = int(n * percentile / 100)
        return prices[min(idx, n - 1)]

    p25, p50, p75, p90 = pct(25), pct(50), pct(75), pct(90)
    alloc_1500 = TYPICAL_ALLOC_1500.get(sid, 100)
    alloc_2500 = TYPICAL_ALLOC_2500.get(sid, 166)

    # Count how many products exist above 70% of the $2500 allocation
    high_threshold = alloc_2500 * 0.7
    above_high = sum(1 for p in prices if p >= high_threshold)

    # Gap detection
    gap = ""
    if prices[-1] < alloc_2500 * 0.8:
        gap = "TOPS OUT LOW"
        price_gaps.append((sid, prices[-1], alloc_2500, above_high))
    elif above_high < 10:
        gap = f"THIN HIGH ({above_high})"
        price_gaps.append((sid, prices[-1], alloc_2500, above_high))

    print(f"  {sid:<18} {n:>6} ${prices[0]:>6.0f} ${p25:>6.0f} ${p50:>6.0f} ${p75:>6.0f} "
          f"${p90:>6.0f} ${prices[-1]:>6.0f}  ${alloc_1500:>6} ${alloc_2500:>6} {gap:>12}")

print()
if price_gaps:
    print("  Categories needing premium products:")
    for sid, max_price, alloc, count in price_gaps:
        print(f"    {sid}: max ${max_price:.0f}, $2500 budget allocates ${alloc}, "
              f"only {count} products above 70% threshold")
    print()

# ===========================================================================
# 2. PER-AESTHETIC COVERAGE
# ===========================================================================

print("=" * 100)
print("  2. PER-AESTHETIC COVERAGE (keyword matches per core × slot)")
print("=" * 100)
print()

# For each core's keywords, count products whose name contains at least one keyword.
# "On-aesthetic" = at least 1 keyword hit in the product name.

def count_aesthetic_matches(products, keywords):
    kw_lower = [k.lower() for k in keywords]
    matches = []
    for p in products:
        name = p["name"].lower()
        if any(kw in name for kw in kw_lower):
            matches.append(p)
    return matches

# Print header
core_ids = list(CORES.keys())
header = f"  {'Slot':<18}"
for cid in core_ids:
    header += f" {cid[:8]:>8}"
print(header)
print(f"  {'─' * (18 + 9 * len(core_ids))}")

thin_combos = []  # (core, slot, count) where count < 15

for sid in SLOTS:
    products = catalogs[sid]
    row = f"  {sid:<18}"
    for cid in core_ids:
        keywords = CORES[cid]
        matches = count_aesthetic_matches(products, keywords)
        count = len(matches)
        marker = ""
        if count < 5:
            marker = "!"
        elif count < 15:
            marker = "*"
        if count < 15:
            thin_combos.append((cid, sid, count))
        row += f" {count:>7}{marker}"
    print(row)

print()
print("  Legend: * = thin (5-14 matches), ! = critically thin (<5)")
print()

# Group thin combos by core
print("  Thin combinations (< 15 on-aesthetic items):")
by_core = defaultdict(list)
for core, slot, count in thin_combos:
    by_core[core].append((slot, count))

for core in core_ids:
    if core in by_core:
        slots_thin = by_core[core]
        total_thin = len(slots_thin)
        critical = sum(1 for _, c in slots_thin if c < 5)
        print(f"\n    {core} ({total_thin} thin slots, {critical} critical):")
        for slot, count in sorted(slots_thin, key=lambda x: x[1]):
            marker = " ← CRITICAL" if count < 5 else ""
            print(f"      {slot:<18} {count:>3} matches{marker}")

# ===========================================================================
# 3. TARGETED FETCH PLAN
# ===========================================================================

print()
print("=" * 100)
print("  3. TARGETED FETCH PLAN")
print("=" * 100)
print()

# Strategy:
# A. Premium queries for categories that top out too low
# B. Aesthetic-specific queries for critically thin core×slot combos
# Only propose queries where we're actually missing coverage.

queries = []

# --- A: Premium price band gaps ---
print("  A. PREMIUM PRICE-BAND QUERIES")
print("  (Categories where max price < 80% of $2500 budget allocation)")
print()

# Define premium search terms per slot
PREMIUM_TERMS = {
    "throw_blanket": [
        "luxury cashmere throw blanket",
        "premium alpaca throw blanket",
        "high end wool throw blanket",
    ],
    "curtains": [
        "luxury velvet curtains 84 inch",
        "premium linen curtains 96 inch",
        "silk curtains bedroom",
    ],
    "table_lamp": [
        "luxury table lamp brass marble",
        "designer table lamp bedroom premium",
        "high end bedside lamp crystal",
    ],
    "ceiling_light": [
        "luxury flush mount ceiling light brass",
        "premium ceiling light fixture gold",
        "designer ceiling light modern",
    ],
    "pillows": [
        "luxury down pillow queen",
        "premium goose down pillow",
        "silk pillow queen luxury",
    ],
    "plants": [
        "large artificial tree 5ft indoor",
        "premium artificial olive tree 6ft",
        "large faux fiddle leaf fig 5 feet",
    ],
    "mirror": [
        "large decorative wall mirror 40 inch",
        "premium arched mirror full length",
        "luxury floor mirror gold frame",
    ],
    "floor_lamp": [
        "luxury arc floor lamp brass",
        "designer floor lamp premium",
        "high end floor lamp marble base",
    ],
}

for sid, max_price, alloc, above_high in price_gaps:
    terms = PREMIUM_TERMS.get(sid, [])
    if terms:
        print(f"    {sid}: max ${max_price:.0f} vs ${alloc} budget → {len(terms)} queries")
        for t in terms:
            print(f"      \"{t}\"")
            queries.append((sid, t))
    print()

# --- B: Aesthetic-specific queries ---
print("  B. AESTHETIC-SPECIFIC QUERIES")
print("  (Core×slot combos with <5 on-aesthetic items)")
print()

# For critically thin combos, generate aesthetic-specific search terms
AESTHETIC_TERMS = {
    "quiet_luxury": {
        "nightstand": ["luxury marble nightstand", "bouclé nightstand cream"],
        "dresser": ["luxury white dresser marble top", "cream dresser brass handles"],
        "floor_lamp": ["luxury floor lamp marble brass", "bouclé floor lamp gold"],
        "table_lamp": ["marble table lamp brass", "luxury bedside lamp alabaster"],
        "ceiling_light": ["luxury brass flush mount ceiling light", "gold ceiling light flush mount"],
        "wall_art": ["luxury abstract wall art gold framed", "neutral minimalist art print framed"],
        "rug": ["luxury wool area rug cream 5x8", "high end neutral area rug ivory"],
        "throw_blanket": ["cashmere throw blanket cream", "luxury bouclé throw blanket ivory"],
        "curtains": ["luxury linen curtains ivory", "silk curtains cream bedroom"],
    },
    "ski_lodge": {
        "nightstand": ["rustic wood nightstand cabin", "log nightstand bedroom"],
        "dresser": ["rustic wood dresser cabin", "reclaimed wood dresser"],
        "ceiling_light": ["rustic cabin ceiling light", "lodge ceiling light wood"],
        "table_lamp": ["rustic cabin table lamp", "antler table lamp lodge"],
        "floor_lamp": ["rustic floor lamp wood", "cabin floor lamp wrought iron"],
        "wall_art": ["mountain landscape wall art framed", "cabin wall art rustic"],
        "rug": ["cabin area rug rustic 5x8", "plaid area rug lodge"],
        "throw_blanket": ["wool plaid throw blanket", "cabin knit blanket flannel"],
    },
    "city_modern": {
        "nightstand": ["modern chrome nightstand glass", "minimalist nightstand black glass"],
        "dresser": ["modern high gloss dresser white", "sleek dresser chrome"],
        "wall_art": ["modern abstract wall art black white", "city skyline wall art"],
        "rug": ["modern geometric area rug black white 5x8", "high contrast rug monochrome"],
        "throw_blanket": ["modern throw blanket grey geometric", "monochrome throw blanket black"],
    },
    "dark_academia": {
        "nightstand": ["antique dark wood nightstand", "vintage mahogany nightstand"],
        "dresser": ["dark wood dresser antique", "vintage apothecary cabinet"],
        "floor_lamp": ["antique brass floor lamp", "vintage library floor lamp"],
        "table_lamp": ["antique brass desk lamp green shade", "vintage banker lamp"],
        "ceiling_light": ["antique brass ceiling light", "vintage flush mount dark"],
        "wall_art": ["dark academia wall art vintage", "antique botanical print framed"],
        "rug": ["dark oriental area rug 5x8", "vintage persian rug dark"],
        "throw_blanket": ["velvet throw blanket dark green", "tartan plaid throw blanket"],
    },
    "sports_den": {
        "table_lamp": ["industrial table lamp matte black", "leather base table lamp masculine"],
        "nightstand": ["dark leather nightstand", "industrial metal nightstand dark"],
        "dresser": ["industrial dark dresser metal", "masculine dresser dark wood metal"],
    },
}

critical_combos = [(c, s, n) for c, s, n in thin_combos if n < 5]
# Group by core
by_core_critical = defaultdict(list)
for core, slot, count in critical_combos:
    by_core_critical[core].append((slot, count))

for core in sorted(by_core_critical.keys()):
    slots = by_core_critical[core]
    terms_for_core = AESTHETIC_TERMS.get(core, {})
    if not terms_for_core:
        continue
    print(f"    {core}:")
    for slot, count in sorted(slots, key=lambda x: x[1]):
        terms = terms_for_core.get(slot, [])
        if terms:
            for t in terms:
                queries.append((slot, t))
            print(f"      {slot:<18} ({count} matches) → {len(terms)} queries")
    print()

# --- Summary ---
print("=" * 100)
print("  FETCH PLAN SUMMARY")
print("=" * 100)
print()

# Count by slot
slot_counts = defaultdict(int)
for sid, term in queries:
    slot_counts[sid] += 1

print(f"  Total queries: {len(queries)}")
print(f"  Estimated cost: {len(queries)} × $0.01 = ${len(queries) * 0.01:.2f}")
print()
print(f"  By category:")
for sid in sorted(slot_counts.keys()):
    print(f"    {sid:<18} {slot_counts[sid]:>3} queries")

print()
print(f"  By purpose:")
premium_count = sum(len(PREMIUM_TERMS.get(sid, [])) for sid, _, _, _ in price_gaps)
aesthetic_count = len(queries) - premium_count
print(f"    Premium price-band:    {premium_count}")
print(f"    Aesthetic-specific:    {aesthetic_count}")
print(f"    Total:                {len(queries)}")
print()

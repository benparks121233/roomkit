#!/usr/bin/env python3
"""
Diagnose budget under-utilization: catalog gap vs. wiring issue.

1. Price depth matrix per aesthetic × category (on-aesthetic items by price band)
2. Wiring trace: what premium items did the LLM see vs. pick for quiet_luxury $2500
3. Sports_den shortlist verification: do dark/industrial items survive _build_shortlist?
"""
from __future__ import annotations

import json
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.sourcing.catalog_cache import read_cache
from services.sourcing.amazon_adapter import (
    AmazonAdapter, _MAX_CANDIDATES, _INTEREST_KEYWORDS, _INTEREST_SLOTS,
)
from services.config_loader import load_style_profiles
from services.intake_service import parse_intake
from services.style_service import interpret_style
from services.composition_service import plan_composition
from schemas.product import Product

profiles = load_style_profiles()
CORES = {p.id: p for p in profiles.profiles if p.id != "warm_minimalist"}

SLOTS = [
    "bed_frame", "mattress", "sheets", "comforter", "pillows",
    "nightstand", "dresser", "ceiling_light", "table_lamp", "floor_lamp",
    "wall_art", "plants", "mirror", "rug", "curtains", "throw_blanket",
]

FURNITURE_DECOR = [
    "bed_frame", "nightstand", "dresser", "ceiling_light", "table_lamp",
    "floor_lamp", "wall_art", "plants", "mirror", "rug", "curtains",
    "throw_blanket",
]

# ===========================================================================
# 1. PRICE DEPTH MATRIX — on-aesthetic items by price band
# ===========================================================================
# Use dollar bands aligned with real budget allocations, not percentile bands.
# At $2500, a bed_frame gets ~$475.  At $1500, ~$285.
# Show: $0-50, $50-100, $100-200, $200-400, $400+

BANDS = [(0, 50), (50, 100), (100, 200), (200, 400), (400, 9999)]
BAND_LABELS = ["$0-50", "$50-100", "$100-200", "$200-400", "$400+"]

# Typical per-slot allocation at $2500 budget (approx)
ALLOC_2500 = {
    "bed_frame": 475, "mattress": 388, "sheets": 65, "comforter": 65,
    "pillows": 43, "nightstand": 193, "dresser": 193, "ceiling_light": 87,
    "table_lamp": 65, "floor_lamp": 108, "wall_art": 152, "plants": 43,
    "mirror": 65, "rug": 280, "curtains": 172, "throw_blanket": 87,
}

# Also for $1500
ALLOC_1500 = {
    "bed_frame": 285, "mattress": 233, "sheets": 39, "comforter": 39,
    "pillows": 26, "nightstand": 116, "dresser": 116, "ceiling_light": 52,
    "table_lamp": 39, "floor_lamp": 65, "wall_art": 91, "plants": 26,
    "mirror": 39, "rug": 168, "curtains": 103, "throw_blanket": 52,
}


def is_aesthetic_match(name: str, keywords: list[str]) -> bool:
    name_lower = name.lower()
    return any(kw.lower() in name_lower for kw in keywords)


def get_band_idx(price: float) -> int:
    for i, (lo, hi) in enumerate(BANDS):
        if lo <= price < hi:
            return i
    return len(BANDS) - 1


print("=" * 110)
print("  1. PRICE DEPTH MATRIX — on-aesthetic items by absolute price band")
print("=" * 110)
print()

# Focus on the two aesthetics with under-spend: quiet_luxury and sports_den
for core_id in ["quiet_luxury", "sports_den"]:
    profile = CORES[core_id]
    keywords = profile.keywords

    print(f"  {core_id} — keywords: {', '.join(keywords)}")
    header = f"  {'Slot':<18} {'Alloc$2500':>10}"
    for label in BAND_LABELS:
        header += f" {label:>8}"
    header += f" {'Total':>6}  {'Can fill $2500?':>15}"
    print(header)
    print(f"  {'─' * 105}")

    can_fill_count = 0
    cannot_fill_count = 0

    for sid in FURNITURE_DECOR:
        raw = read_cache(sid) or []
        band_counts = [0] * len(BANDS)
        max_on_aesthetic_price = 0.0

        for p in raw:
            if is_aesthetic_match(p["name"], keywords):
                price = float(p["normalized_price"])
                band_counts[get_band_idx(price)] += 1
                max_on_aesthetic_price = max(max_on_aesthetic_price, price)

        total = sum(band_counts)
        alloc = ALLOC_2500.get(sid, 100)

        # Can fill = there's at least 1 on-aesthetic item >= 60% of the slot allocation
        threshold = alloc * 0.6
        can_fill = max_on_aesthetic_price >= threshold if total > 0 else False

        if can_fill:
            can_fill_count += 1
        else:
            cannot_fill_count += 1

        status = "YES" if can_fill else "NO"
        if total == 0:
            status = "EMPTY"

        row = f"  {sid:<18} ${alloc:>8}"
        for bc in band_counts:
            row += f" {bc:>8}"
        row += f" {total:>6}  {status:>15}"
        if total > 0:
            row += f"  (max ${max_on_aesthetic_price:.0f})"
        print(row)

    print()
    print(f"  Summary: {can_fill_count} slots can fill at $2500, "
          f"{cannot_fill_count} cannot (by keyword match)")
    print()

# ===========================================================================
# 2. WIRING TRACE — quiet_luxury $2500: what did the LLM see vs. pick?
# ===========================================================================

print("=" * 110)
print("  2. WIRING TRACE — quiet_luxury $2500 design")
print("     What premium items did the LLM SEE vs. PICK?")
print("=" * 110)
print()

# Run the pipeline up to selection, intercepting the shortlist and LLM choice.

req_ql = {
    "room_type": "bedroom", "budget": 2500.0,
    "style_description": (
        "I want a quiet luxury bedroom — understated elegance with cashmere, "
        "marble, and brushed gold accents. Creamy neutral palette."
    ),
    "bed_size": "queen", "density": "balanced",
    "interests": [], "full_room": True, "wants": [],
}

room_request = parse_intake(req_ql)
style_profile = interpret_style(room_request)
slot_plan = plan_composition(room_request, style_profile)
slot_map = {s.slot_id: s for s in slot_plan.slots}

print(f"  Style: {style_profile.style_name}, keywords: {style_profile.keywords}")
print(f"  Budget: ${slot_plan.target_budget:.2f}")
print()

adapter = AmazonAdapter()

# For each slot, show: allocation, shortlist price range, top-5 most expensive
# in shortlist, and what the LLM picked.

# Monkey-patch to capture the LLM's raw response
import anthropic.resources.messages
_original_create = anthropic.resources.messages.Messages.create
_last_responses = {}
_lock = threading.Lock()

def _capture_create(self, **kwargs):
    result = _original_create(self, **kwargs)
    # Store the raw text for later inspection
    with _lock:
        _last_responses[threading.current_thread().ident] = result.content[0].text
    return result

anthropic.resources.messages.Messages.create = _capture_create

from services.selection_service import select_product

print(f"  {'Slot':<18} {'Alloc':>7} {'Shortlist':>10} {'SL Range':>14} "
      f"{'Picked':>8} {'% of Alloc':>10}  Fit Reason")
print(f"  {'─' * 105}")

# Track totals
total_allocated = 0.0
total_spent = 0.0
wiring_suspects = []

for slot in sorted(slot_plan.slots, key=lambda s: s.slot_id):
    if slot.owned:
        continue

    spec_hints = {}
    if "bed_size" in slot.required_specs and room_request.bed_size:
        spec_hints["bed_size"] = room_request.bed_size

    candidates = adapter.fetch_candidates(
        slot.slot_id,
        style_profile.keywords,
        (0.0, slot.allocated_budget),
        spec_hints,
        interests=room_request.interests or None,
    )

    if not candidates:
        print(f"  {slot.slot_id:<18} ${slot.allocated_budget:>6.0f} {'EMPTY':>10}")
        continue

    prices = [c.normalized_price for c in candidates]
    sl_min, sl_max = min(prices), max(prices)

    # Run selection
    product, reason = select_product(slot, style_profile, candidates, room_request.interests)

    picked_price = product.normalized_price if product else 0
    pct = (picked_price / slot.allocated_budget * 100) if slot.allocated_budget > 0 else 0

    total_allocated += slot.allocated_budget
    total_spent += picked_price

    fit = reason or "—"
    if len(fit) > 40:
        fit = fit[:40]

    print(f"  {slot.slot_id:<18} ${slot.allocated_budget:>6.0f} {len(candidates):>10} "
          f"${sl_min:.0f}-${sl_max:.0f}".ljust(15) +
          f" ${picked_price:>7.0f} {pct:>9.0f}%  {fit}")

    # Flag wiring suspects: shortlist has items >= 60% of allocation but pick is < 40%
    high_items = [c for c in candidates if c.normalized_price >= slot.allocated_budget * 0.6]
    if picked_price < slot.allocated_budget * 0.4 and high_items:
        wiring_suspects.append((slot.slot_id, slot.allocated_budget, picked_price,
                                len(high_items), max(c.normalized_price for c in high_items)))

print()
print(f"  Total allocated: ${total_allocated:.0f}, total spent: ${total_spent:.0f} "
      f"({total_spent/total_allocated*100:.0f}%)")
print()

if wiring_suspects:
    print("  WIRING SUSPECTS — LLM picked cheap despite premium options in shortlist:")
    for sid, alloc, picked, n_high, max_high in wiring_suspects:
        print(f"    {sid}: alloc ${alloc:.0f}, picked ${picked:.0f} ({picked/alloc*100:.0f}%), "
              f"but {n_high} items >= 60% of alloc (max ${max_high:.0f})")
    print()

# Now show detailed shortlist for anchor slots
ANCHOR_SLOTS = ["bed_frame", "nightstand", "dresser", "rug", "curtains"]

print("  DETAILED SHORTLIST — anchor slots (top 10 most expensive in shortlist):")
print()

for sid in ANCHOR_SLOTS:
    slot = slot_map.get(sid)
    if not slot or slot.owned:
        continue

    spec_hints = {}
    if "bed_size" in slot.required_specs and room_request.bed_size:
        spec_hints["bed_size"] = room_request.bed_size

    candidates = adapter.fetch_candidates(
        sid,
        style_profile.keywords,
        (0.0, slot.allocated_budget),
        spec_hints,
        interests=room_request.interests or None,
    )

    product, reason = select_product(slot, style_profile, candidates, room_request.interests)

    top_by_price = sorted(candidates, key=lambda c: c.normalized_price, reverse=True)[:10]

    print(f"  {sid} — allocation: ${slot.allocated_budget:.0f}, "
          f"picked: ${product.normalized_price:.0f}" if product else f"  {sid} — picked: NONE")
    print(f"  Top 10 most expensive in shortlist:")
    for c in top_by_price:
        picked_marker = " ← PICKED" if product and c.product_id == product.product_id else ""
        on_aesthetic = is_aesthetic_match(c.name, style_profile.keywords)
        aes_marker = " [on-aes]" if on_aesthetic else ""
        print(f"    ${c.normalized_price:>7.2f}  {c.name[:65]}{aes_marker}{picked_marker}")
    print()


# ===========================================================================
# 3. SPORTS_DEN SHORTLIST CHECK
# ===========================================================================

print("=" * 110)
print("  3. SPORTS_DEN SHORTLIST CHECK")
print("     Do dark/industrial items survive _build_shortlist?")
print("=" * 110)
print()

req_sd = {
    "room_type": "bedroom", "budget": 1500.0,
    "style_description": (
        "I want a sports den bedroom — moody and atmospheric, with rich depth, "
        "in dark tones with charcoal, dark wood, and warm amber. "
        "I'm drawn to walnut and leather."
    ),
    "bed_size": "queen", "density": "balanced",
    "interests": ["music", "sports"],
    "full_room": True, "wants": [],
}

room_request_sd = parse_intake(req_sd)
style_profile_sd = interpret_style(room_request_sd)
slot_plan_sd = plan_composition(room_request_sd, style_profile_sd)
slot_map_sd = {s.slot_id: s for s in slot_plan_sd.slots}

print(f"  Style: {style_profile_sd.style_name}, keywords: {style_profile_sd.keywords}")
print(f"  Budget: ${slot_plan_sd.target_budget:.2f}")
print()

# Dark/masculine indicator keywords (broader than profile keywords)
DARK_KEYWORDS = [
    "dark", "black", "matte", "industrial", "masculine", "charcoal",
    "moody", "leather", "walnut", "iron", "metal", "bronze", "brass",
    "steel", "rustic", "mahogany", "espresso", "navy", "slate",
]

def dark_score(name: str) -> int:
    name_lower = name.lower()
    return sum(1 for kw in DARK_KEYWORDS if kw in name_lower)

def is_warm_mcm(name: str) -> bool:
    """Detect warm/MCM items that clash with sports_den."""
    name_lower = name.lower()
    warm_kw = ["natural", "rattan", "woven", "light wood", "boho", "bamboo",
               "cream", "beige", "white oak", "scandinavian", "mid century",
               "mid-century", "coastal"]
    return any(kw in name_lower for kw in warm_kw)

# Check key slots
CHECK_SLOTS = ["nightstand", "dresser", "ceiling_light", "table_lamp",
               "floor_lamp", "bed_frame", "curtains", "rug"]

print(f"  {'Slot':<18} {'Alloc':>7} {'SL Size':>8} {'Dark':>5} {'Warm/MCM':>9} "
      f"{'Dark%':>6}  Picked → Dark?")
print(f"  {'─' * 95}")

for sid in CHECK_SLOTS:
    slot = slot_map_sd.get(sid)
    if not slot or slot.owned:
        continue

    spec_hints = {}
    if "bed_size" in slot.required_specs and room_request_sd.bed_size:
        spec_hints["bed_size"] = room_request_sd.bed_size

    candidates = adapter.fetch_candidates(
        sid,
        style_profile_sd.keywords,
        (0.0, slot.allocated_budget),
        spec_hints,
        interests=room_request_sd.interests or None,
    )

    n_dark = sum(1 for c in candidates if dark_score(c.name) > 0)
    n_warm = sum(1 for c in candidates if is_warm_mcm(c.name))
    dark_pct = (n_dark / len(candidates) * 100) if candidates else 0

    product, reason = select_product(slot, style_profile_sd, candidates, room_request_sd.interests)

    pick_dark = ""
    if product:
        ds = dark_score(product.name)
        ws = is_warm_mcm(product.name)
        if ds > 0:
            pick_dark = f"DARK ({ds})"
        elif ws:
            pick_dark = "WARM/MCM ←!!"
        else:
            pick_dark = "NEUTRAL"
        pick_dark += f"  ${product.normalized_price:.0f} {product.name[:45]}"

    print(f"  {sid:<18} ${slot.allocated_budget:>6.0f} {len(candidates):>8} "
          f"{n_dark:>5} {n_warm:>9} {dark_pct:>5.0f}%  {pick_dark}")

print()

# Show shortlist composition for nightstand in detail
print("  NIGHTSTAND SHORTLIST DETAIL (top 20 by style_score, showing dark vs warm):")
print()

slot = slot_map_sd.get("nightstand")
if slot and not slot.owned:
    spec_hints = {}
    candidates = adapter.fetch_candidates(
        "nightstand",
        style_profile_sd.keywords,
        (0.0, slot.allocated_budget),
        spec_hints,
        interests=room_request_sd.interests or None,
    )

    kw_lower = [k.lower() for k in style_profile_sd.keywords]
    def style_score(p):
        name = p.name.lower()
        return sum(1 for kw in kw_lower if kw in name)

    by_style = sorted(candidates, key=lambda c: (style_score(c), c.normalized_price), reverse=True)

    for i, c in enumerate(by_style[:20]):
        ss = style_score(c)
        ds = dark_score(c.name)
        ws = is_warm_mcm(c.name)
        tag = "DARK" if ds > 0 else ("WARM" if ws else "neut")
        print(f"    [{i+1:>2}] style={ss} dark={ds} {tag:<5} ${c.normalized_price:>7.2f}  {c.name[:60]}")

print()

# ===========================================================================
# VERDICT
# ===========================================================================

print("=" * 110)
print("  VERDICT: CATALOG GAP vs. WIRING ISSUE")
print("=" * 110)
print()

# Restore original
anthropic.resources.messages.Messages.create = _original_create

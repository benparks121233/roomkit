#!/usr/bin/env python3
"""
Diagnose three problems that may share a root cause in the candidate cap:
1. Empty matches — why do some slots return no product?
2. Under-budget — is the cap cutting expensive items?
3. Interest prints not connecting — does relevance sort cut interest items?
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone
from services.intake_service import parse_intake
from services.style_service import interpret_style
from services.composition_service import plan_composition
from services.sourcing.amazon_adapter import AmazonAdapter, _MAX_CANDIDATES
from services.sourcing.catalog_cache import read_cache
from schemas.product import Product

# ---------------------------------------------------------------------------
# Helper: reproduce what the adapter does, step by step, with full visibility
# ---------------------------------------------------------------------------

def trace_candidates(slot_id, style_keywords, budget, spec_hints):
    """Return (all_in_budget, after_spec, ranked, capped) with full counts."""
    raw_products = read_cache(slot_id) or []
    now = datetime.now(tz=timezone.utc)

    # Step 1: all products in catalog
    total_catalog = len(raw_products)

    # Step 2: price filter
    in_budget = []
    for raw in raw_products:
        price = float(raw["normalized_price"])
        if 0.0 <= price <= budget:
            specs = raw.get("specs", {})
            in_budget.append(Product(
                product_id=raw["product_id"],
                name=raw["name"],
                normalized_price=price,
                buy_url=raw.get("buy_url", ""),
                specs=specs,
                source="amazon",
                image_url=raw.get("image_url", ""),
                slot_id=slot_id,
                fetched_at=now,
            ))

    # Step 3: spec filter
    after_spec = []
    for p in in_budget:
        ok = True
        for k, v in spec_hints.items():
            if k not in p.specs:
                ok = False
                break
            if v and p.specs[k].lower() != str(v).lower():
                ok = False
                break
        if ok:
            after_spec.append(p)

    # Step 4: relevance sort
    kw_lower = [k.lower() for k in style_keywords]
    def score(product):
        name = product.name.lower()
        return sum(1 for kw in kw_lower if kw in name)

    ranked = sorted(after_spec, key=score, reverse=True)

    # Step 5: cap
    capped = ranked[:_MAX_CANDIDATES]

    return total_catalog, in_budget, after_spec, ranked, capped


# ===========================================================================
# PROBLEM 1: EMPTY MATCHES
# ===========================================================================

print("=" * 90)
print("  PROBLEM 1: EMPTY MATCHES — which slots, and why?")
print("=" * 90)
print()

# Run a sports_den design and find the empty slots.
req = {
    "room_type": "bedroom", "budget": 1500.0,
    "style_description": (
        "I want a sports den bedroom — moody and atmospheric, with rich depth, "
        "in dark tones with charcoal, dark wood, and warm amber. "
        "I'm drawn to walnut and leather."
    ),
    "bed_size": "queen", "density": "balanced",
    "interests": ["sports"], "full_room": True, "wants": [],
}

room_request = parse_intake(req)
style_profile = interpret_style(room_request)
slot_plan = plan_composition(room_request, style_profile)
slot_map = {s.slot_id: s for s in slot_plan.slots}

print(f"  Style: {style_profile.style_name}")
print(f"  Keywords: {style_profile.keywords}")
print()

# Trace every slot
for slot in sorted(slot_plan.slots, key=lambda s: s.slot_id):
    if slot.owned:
        continue

    spec_hints = {}
    if "bed_size" in slot.required_specs and room_request.bed_size:
        spec_hints["bed_size"] = room_request.bed_size

    total_cat, in_budget, after_spec, ranked, capped = trace_candidates(
        slot.slot_id, style_profile.keywords, slot.allocated_budget, spec_hints,
    )

    marker = ""
    if len(after_spec) == 0:
        marker = " *** EMPTY (no spec match)"
    elif len(capped) == 0:
        marker = " *** EMPTY (capped to 0?)"

    prices = [p.normalized_price for p in capped] if capped else []
    price_range = f"${min(prices):.0f}-${max(prices):.0f}" if prices else "—"

    print(f"  {slot.slot_id:<18} budget=${slot.allocated_budget:>7.2f}  "
          f"catalog={total_cat:>4}  in_budget={len(in_budget):>4}  "
          f"after_spec={len(after_spec):>4}  capped={len(capped):>3}  "
          f"prices={price_range}{marker}")

    if len(after_spec) == 0 and len(in_budget) > 0:
        # Spec filter killed everything — show why
        print(f"    SPEC FILTER: required {spec_hints}")
        sample = in_budget[:3]
        for p in sample:
            print(f"      {p.name[:60]}  specs={p.specs}")

print()

# ===========================================================================
# PROBLEM 2: UNDER-BUDGET — does the cap cut expensive items?
# ===========================================================================

print("=" * 90)
print("  PROBLEM 2: UNDER-BUDGET — price range of capped vs full pool")
print("=" * 90)
print()

# Use a higher budget to make the effect visible
req2 = {**req, "budget": 2500.0}
room_request2 = parse_intake(req2)
style_profile2 = interpret_style(room_request2)
slot_plan2 = plan_composition(room_request2, style_profile2)

print(f"  Budget: $2500, style: {style_profile2.style_name}")
print()
print(f"  {'Slot':<18} {'Budget':>8}  {'Full Pool':>10}  {'Full Range':>14}  "
      f"{'Capped':>7}  {'Capped Range':>14}  {'Max Cut?':>9}  {'Avg Full':>9}  {'Avg Cap':>9}")
print(f"  {'─' * 110}")

total_full_spent = 0
total_cap_spent = 0

for slot in sorted(slot_plan2.slots, key=lambda s: s.slot_id):
    if slot.owned:
        continue

    spec_hints = {}
    if "bed_size" in slot.required_specs and room_request2.bed_size:
        spec_hints["bed_size"] = room_request2.bed_size

    total_cat, in_budget, after_spec, ranked, capped = trace_candidates(
        slot.slot_id, style_profile2.keywords, slot.allocated_budget, spec_hints,
    )

    if not after_spec:
        print(f"  {slot.slot_id:<18} ${slot.allocated_budget:>7.2f}  "
              f"{'EMPTY':>10}")
        continue

    full_prices = sorted(p.normalized_price for p in after_spec)
    cap_prices = sorted(p.normalized_price for p in capped) if capped else []

    full_range = f"${full_prices[0]:.0f}-${full_prices[-1]:.0f}"
    cap_range = f"${cap_prices[0]:.0f}-${cap_prices[-1]:.0f}" if cap_prices else "—"

    full_avg = sum(full_prices) / len(full_prices)
    cap_avg = sum(cap_prices) / len(cap_prices) if cap_prices else 0

    # Was the max price in the full pool cut by the cap?
    max_cut = full_prices[-1] > (cap_prices[-1] if cap_prices else 0)

    total_full_spent += full_avg
    total_cap_spent += cap_avg

    print(f"  {slot.slot_id:<18} ${slot.allocated_budget:>7.2f}  "
          f"{len(after_spec):>10}  {full_range:>14}  "
          f"{len(capped):>7}  {cap_range:>14}  "
          f"{'YES' if max_cut else 'no':>9}  "
          f"${full_avg:>8.2f}  ${cap_avg:>8.2f}")

print()

# ===========================================================================
# PROBLEM 3: INTEREST PRINTS NOT CONNECTING
# ===========================================================================

print("=" * 90)
print("  PROBLEM 3: INTEREST PRINTS — do music/sports items survive the cap?")
print("=" * 90)
print()

# Check wall_art with interests=["music"]
wall_art_slot = slot_map.get("wall_art")
if wall_art_slot and not wall_art_slot.owned:
    budget = wall_art_slot.allocated_budget

    total_cat, in_budget, after_spec, ranked, capped = trace_candidates(
        "wall_art", style_profile.keywords, budget, {},
    )

    # Find interest-themed items
    music_kw = ["music", "vinyl", "record", "concert", "guitar", "piano", "jazz", "notes"]
    sports_kw = ["sports", "basketball", "football", "baseball", "athletic", "soccer"]

    def has_interest(product, keywords):
        name = product.name.lower()
        return any(k in name for k in keywords)

    music_in_full = [p for p in after_spec if has_interest(p, music_kw)]
    music_in_capped = [p for p in capped if has_interest(p, music_kw)]
    sports_in_full = [p for p in after_spec if has_interest(p, sports_kw)]
    sports_in_capped = [p for p in capped if has_interest(p, sports_kw)]

    print(f"  wall_art: budget=${budget:.2f}, {len(after_spec)} in pool, "
          f"{len(capped)} after cap")
    print()
    print(f"  Music-themed products:")
    print(f"    In full pool: {len(music_in_full)}")
    print(f"    In capped 25: {len(music_in_capped)}")
    if music_in_full:
        print(f"    Full pool music items:")
        for p in music_in_full:
            # Show their relevance score
            kw_lower = [k.lower() for k in style_profile.keywords]
            sc = sum(1 for kw in kw_lower if kw in p.name.lower())
            in_cap = "✓ IN CAP" if p in capped else "✗ CUT"
            print(f"      score={sc}  {in_cap}  ${p.normalized_price:.2f}  {p.name[:65]}")

    print()
    print(f"  Sports-themed products:")
    print(f"    In full pool: {len(sports_in_full)}")
    print(f"    In capped 25: {len(sports_in_capped)}")
    if sports_in_full:
        print(f"    Full pool sports items:")
        for p in sports_in_full:
            kw_lower = [k.lower() for k in style_profile.keywords]
            sc = sum(1 for kw in kw_lower if kw in p.name.lower())
            in_cap = "✓ IN CAP" if p in capped else "✗ CUT"
            print(f"      score={sc}  {in_cap}  ${p.normalized_price:.2f}  {p.name[:65]}")

    print()
    # Show what DID make the cap — what scored highest?
    print(f"  Top 10 in capped list (by relevance score):")
    kw_lower = [k.lower() for k in style_profile.keywords]
    for p in capped[:10]:
        sc = sum(1 for kw in kw_lower if kw in p.name.lower())
        print(f"    score={sc}  ${p.normalized_price:.2f}  {p.name[:70]}")

    print()
    # Score distribution
    scores = [sum(1 for kw in kw_lower if kw in p.name.lower()) for p in after_spec]
    from collections import Counter
    dist = Counter(scores)
    print(f"  Relevance score distribution across full pool ({len(after_spec)} items):")
    for s in sorted(dist.keys(), reverse=True):
        pct = dist[s] / len(after_spec) * 100
        bar = "█" * int(pct / 2)
        print(f"    score={s}: {dist[s]:>4} ({pct:>5.1f}%)  {bar}")

    # The cap takes the top 25 by score — how many at each score?
    cap_scores = [sum(1 for kw in kw_lower if kw in p.name.lower()) for p in capped]
    cap_dist = Counter(cap_scores)
    print(f"  Score distribution in capped 25:")
    for s in sorted(cap_dist.keys(), reverse=True):
        print(f"    score={s}: {cap_dist[s]}")

print()
print("=" * 90)
print("  DIAGNOSIS COMPLETE")
print("=" * 90)

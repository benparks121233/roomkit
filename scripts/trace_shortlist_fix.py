#!/usr/bin/env python3
"""
Before/after comparison of the shortlist fix:
1. Interest items in capped list (was 0)
2. Price range reaching budget (was cut to ~half)
3. Cost impact at 100 vs old 25
4. Real picks via POST /design
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone
from collections import Counter

from services.intake_service import parse_intake
from services.style_service import interpret_style
from services.composition_service import plan_composition
from services.sourcing.amazon_adapter import (
    AmazonAdapter, _MAX_CANDIDATES, _INTEREST_KEYWORDS, _INTEREST_SLOTS,
)
from services.sourcing.catalog_cache import read_cache
from schemas.product import Product

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

req = {
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

room_request = parse_intake(req)
style_profile = interpret_style(room_request)
slot_plan = plan_composition(room_request, style_profile)
slot_map = {s.slot_id: s for s in slot_plan.slots}

print(f"Style: {style_profile.style_name}, keywords: {style_profile.keywords}")
print(f"Interests: {room_request.interests}")
print(f"Cap: {_MAX_CANDIDATES}")
print()

# ---------------------------------------------------------------------------
# 1. INTEREST ITEMS — are music/sports products in the capped list?
# ---------------------------------------------------------------------------

print("=" * 90)
print("  1. INTEREST ITEMS IN CAPPED LIST")
print("=" * 90)
print()

adapter = AmazonAdapter()

for sid in ["wall_art", "plants", "throw_blanket"]:
    slot = slot_map.get(sid)
    if not slot or slot.owned:
        continue

    spec_hints = {}
    candidates = adapter.fetch_candidates(
        sid, style_profile.keywords,
        (0.0, slot.allocated_budget), spec_hints,
        interests=room_request.interests,
    )

    # Count interest matches in capped list
    music_kw = _INTEREST_KEYWORDS.get("music", [])
    sports_kw = _INTEREST_KEYWORDS.get("sports", [])

    def has_kw(p, kws):
        name = p.name.lower()
        return any(k.lower() in name for k in kws)

    music_in = [p for p in candidates if has_kw(p, music_kw)]
    sports_in = [p for p in candidates if has_kw(p, sports_kw)]

    print(f"  {sid} — {len(candidates)} capped candidates (budget: ${slot.allocated_budget:.2f})")
    print(f"    Music items: {len(music_in)}  (was 0 with old cap)")
    print(f"    Sports items: {len(sports_in)}  (was 0 with old cap)")

    if music_in:
        print(f"    Sample music items now in shortlist:")
        for p in music_in[:5]:
            print(f"      ${p.normalized_price:.2f}  {p.name[:70]}")
    if sports_in:
        print(f"    Sample sports items now in shortlist:")
        for p in sports_in[:5]:
            print(f"      ${p.normalized_price:.2f}  {p.name[:70]}")
    print()

# ---------------------------------------------------------------------------
# 2. PRICE RANGE — does the capped list span the budget?
# ---------------------------------------------------------------------------

print("=" * 90)
print("  2. PRICE RANGE — capped list vs full pool")
print("=" * 90)
print()
print(f"  {'Slot':<18} {'Budget':>8}  {'Full Pool':>10}  {'Full Range':>14}  "
      f"{'Capped':>7}  {'Cap Range':>14}  {'Max Reached':>12}")
print(f"  {'─' * 95}")

for slot in sorted(slot_plan.slots, key=lambda s: s.slot_id):
    if slot.owned:
        continue

    spec_hints = {}
    if "bed_size" in slot.required_specs and room_request.bed_size:
        spec_hints["bed_size"] = room_request.bed_size

    # Full pool (no cap)
    raw_products = read_cache(slot.slot_id) or []
    now = datetime.now(tz=timezone.utc)
    full_pool = []
    for raw in raw_products:
        price = float(raw["normalized_price"])
        if price > slot.allocated_budget:
            continue
        specs = raw.get("specs", {})
        skip = False
        for k, v in spec_hints.items():
            if k not in specs:
                skip = True; break
            if v and specs[k].lower() != str(v).lower():
                skip = True; break
        if skip:
            continue
        full_pool.append(price)

    # Capped (actual adapter call)
    capped = adapter.fetch_candidates(
        slot.slot_id, style_profile.keywords,
        (0.0, slot.allocated_budget), spec_hints,
        interests=room_request.interests,
    )
    cap_prices = [p.normalized_price for p in capped]

    if not full_pool:
        print(f"  {slot.slot_id:<18} ${slot.allocated_budget:>7.2f}  EMPTY")
        continue

    full_range = f"${min(full_pool):.0f}-${max(full_pool):.0f}"
    cap_range = f"${min(cap_prices):.0f}-${max(cap_prices):.0f}" if cap_prices else "—"
    max_reached = max(cap_prices) >= max(full_pool) * 0.9 if cap_prices else False

    print(f"  {slot.slot_id:<18} ${slot.allocated_budget:>7.2f}  "
          f"{len(full_pool):>10}  {full_range:>14}  "
          f"{len(capped):>7}  {cap_range:>14}  "
          f"{'YES' if max_reached else 'NO':>12}")

print()

# ---------------------------------------------------------------------------
# 3. COST IMPACT — tokens at 100 vs old 25
# ---------------------------------------------------------------------------

print("=" * 90)
print("  3. COST IMPACT (estimated at 100 vs old 25)")
print("=" * 90)
print()

# Rough estimate: ~100 tokens per candidate in prompt
# Old: 25 candidates × ~100 tok = ~2,500 input tok/call × 16 calls = 40k
# New: avg candidates × ~100 tok × 16 calls
total_candidates = 0
slots_counted = 0
for slot in slot_plan.slots:
    if slot.owned:
        continue
    spec_hints = {}
    if "bed_size" in slot.required_specs and room_request.bed_size:
        spec_hints["bed_size"] = room_request.bed_size
    capped = adapter.fetch_candidates(
        slot.slot_id, style_profile.keywords,
        (0.0, slot.allocated_budget), spec_hints,
        interests=room_request.interests,
    )
    total_candidates += len(capped)
    slots_counted += 1

avg_per_slot = total_candidates / slots_counted if slots_counted else 0
est_tokens_per_candidate = 100
est_overhead_per_call = 400  # system prompt + formatting

old_input = slots_counted * (25 * est_tokens_per_candidate + est_overhead_per_call)
new_input = slots_counted * (avg_per_slot * est_tokens_per_candidate + est_overhead_per_call)

# Haiku: $0.80/M input, $4/M output, ~85 output tokens/call
output_per_call = 85
old_cost = (old_input * 0.80 + slots_counted * output_per_call * 4.0) / 1_000_000
new_cost = (new_input * 0.80 + slots_counted * output_per_call * 4.0) / 1_000_000
sonnet_overhead = 0.018  # style + composition

print(f"  Slots: {slots_counted}, avg candidates/slot: {avg_per_slot:.0f}")
print(f"  Old (cap=25):  ~{old_input:,} input tok, selection cost ~${old_cost:.4f}")
print(f"  New (cap=100): ~{new_input:,.0f} input tok, selection cost ~${new_cost:.4f}")
print(f"  + Sonnet overhead: ${sonnet_overhead:.3f}")
print(f"  Estimated total: ${new_cost + sonnet_overhead:.4f}/design")
print(f"  (Will verify with real token counts below)")
print()

# ---------------------------------------------------------------------------
# 4. REAL DESIGN — run through POST /design, show picks + cost
# ---------------------------------------------------------------------------

print("=" * 90)
print("  4. REAL DESIGN — POST /design with music+sports interests")
print("=" * 90)
print()

# Monkey-patch for cost tracking
import anthropic.resources.messages

PRICING = {
    "claude-sonnet-4-6":         {"input": 3.00,  "output": 15.00},
    "claude-haiku-4-5-20251001": {"input": 0.80,  "output":  4.00},
}

_lock = threading.Lock()
_calls = []
_total_cost = 0.0

_original_create = anthropic.resources.messages.Messages.create

def _patched_create(self, **kwargs):
    global _total_cost
    result = _original_create(self, **kwargs)
    model = kwargs.get("model", "unknown")
    usage = result.usage
    rates = PRICING.get(model, {"input": 3.00, "output": 15.00})
    c = (usage.input_tokens * rates["input"] + usage.output_tokens * rates["output"]) / 1_000_000
    with _lock:
        _total_cost += c
        _calls.append({
            "model": model, "input": usage.input_tokens,
            "output": usage.output_tokens, "cost": c,
        })
    return result

anthropic.resources.messages.Messages.create = _patched_create

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
t0 = time.monotonic()
resp = client.post("/design", json=req)
wall = time.monotonic() - t0

data = resp.json()
print(f"  Status: {resp.status_code}, wall time: {wall:.1f}s")
print(f"  Style: {data['style']['style_name']}")
print(f"  Budget: ${data['target_budget']:.2f}, spent: ${data['total_spent']:.2f} "
      f"({data['total_spent']/data['target_budget']*100:.0f}%)")
print(f"  Calls: {len(_calls)}, total cost: ${_total_cost:.5f}")
print()

# Breakdown
sonnet_calls = [c for c in _calls if "sonnet" in c["model"]]
haiku_calls = [c for c in _calls if "haiku" in c["model"]]
s_in = sum(c["input"] for c in sonnet_calls)
h_in = sum(c["input"] for c in haiku_calls)
s_cost = sum(c["cost"] for c in sonnet_calls)
h_cost = sum(c["cost"] for c in haiku_calls)
print(f"  Sonnet: {len(sonnet_calls)} calls, {s_in:,} input tok, ${s_cost:.5f}")
print(f"  Haiku:  {len(haiku_calls)} calls, {h_in:,} input tok, ${h_cost:.5f}")
print()

# Show picks — highlight interest matches and price
print(f"  {'Slot':<20} {'Price':>8}  {'Product':<55} {'Interest?':>10}")
print(f"  {'─' * 100}")

music_kw = _INTEREST_KEYWORDS.get("music", [])
sports_kw = _INTEREST_KEYWORDS.get("sports", [])

for s in sorted(data["slots"], key=lambda x: x["slot_id"]):
    if s["product"]:
        p = s["product"]
        name = p["name"][:55]
        name_lower = p["name"].lower()
        is_music = any(k.lower() in name_lower for k in music_kw)
        is_sports = any(k.lower() in name_lower for k in sports_kw)
        interest_tag = ""
        if is_music: interest_tag = "MUSIC"
        elif is_sports: interest_tag = "SPORTS"
        print(f"  {s['slot_id']:<20} ${p['normalized_price']:>7.2f}  {name:<55} {interest_tag:>10}")
    else:
        print(f"  {s['slot_id']:<20} {'—':>8}  {s['null_reason']}")

print()

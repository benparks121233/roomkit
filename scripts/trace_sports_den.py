#!/usr/bin/env python3
"""
Diagnostic trace of the Sports Den pipeline — replay with full visibility.
Captures: request payload, style LLM output, candidate pools, selection prompts/results.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.intake_service import parse_intake
from services.style_service import interpret_style, _build_prompts, load_style_profiles
from services.composition_service import plan_composition
from services.sourcing.amazon_adapter import AmazonAdapter
from services.selection_service import (
    select_product, _build_selection_prompts, _INTEREST_SLOTS,
)

# ---------------------------------------------------------------------------
# 1. Reconstruct the Sports Den DesignRequest
# ---------------------------------------------------------------------------
# A typical Sports Den quiz path: core=sports_den, mood=moody_deep,
# palette=dark_moody, materials=[walnut_leather], shape=clean_straight,
# density=balanced.
# assembleDescription() produces:
#   "I want a sports den bedroom — moody and atmospheric, with rich depth,
#    in dark tones with charcoal, dark wood, and warm amber.
#    I'm drawn to walnut and leather.
#    I lean toward clean, straight lines.
#    I want a full room, but not cluttered."

STYLE_DESC = (
    "I want a sports den bedroom — moody and atmospheric, with rich depth, "
    "in dark tones with charcoal, dark wood, and warm amber. "
    "I'm drawn to walnut and leather. "
    "I lean toward clean, straight lines. "
    "I want a full room, but not cluttered."
)

req_payload = {
    "room_type": "bedroom",
    "budget": 1500.0,
    "style_description": STYLE_DESC,
    "bed_size": "queen",
    "density": "balanced",
    "interests": ["sports"],  # <-- was this actually in the payload?
    "full_room": True,
    "wants": [],
}

print("=" * 72)
print("  1. REQUEST PAYLOAD")
print("=" * 72)
print(json.dumps(req_payload, indent=2))
print()

# Also show what happens WITHOUT interests (just core=sports_den)
req_no_interests = {**req_payload, "interests": []}
print("  NOTE: If the quiz only sets core=sports_den but user didn't pick")
print("  'Sports' as an interest category, interests=[] in the payload.")
print()

# ---------------------------------------------------------------------------
# 2. STYLE INTERPRETATION — what does the LLM produce?
# ---------------------------------------------------------------------------
print("=" * 72)
print("  2. STYLE LLM OUTPUT")
print("=" * 72)

room_request = parse_intake(req_payload)
style_profile = interpret_style(room_request)

print(f"  style_name:    {style_profile.style_name}")
print(f"  keywords:      {style_profile.keywords}")
print(f"  color_palette: {style_profile.color_palette}")
print(f"  mood:          {style_profile.mood}")
print(f"  confidence:    {style_profile.confidence}")
print(f"  fallback:      {style_profile.fallback}")
print()

# Show the sports_den profile from YAML for comparison.
profiles = load_style_profiles()
sd = next(p for p in profiles.profiles if p.id == "sports_den")
print("  YAML profile for comparison:")
print(f"    keywords:      {sd.keywords}")
print(f"    color_palette: {sd.color_palette}")
print(f"    mood:          {sd.mood}")
print()

# ---------------------------------------------------------------------------
# 3. COMPOSITION — slot plan + budgets
# ---------------------------------------------------------------------------
print("=" * 72)
print("  3. COMPOSITION (slot plan)")
print("=" * 72)

slot_plan = plan_composition(room_request, style_profile)
print(f"  Target budget: ${slot_plan.target_budget:.2f}")
print(f"  Is feasible:   {slot_plan.is_feasible}")
print(f"  Slots ({len(slot_plan.slots)}):")
for s in sorted(slot_plan.slots, key=lambda x: x.slot_id):
    status = "OWNED" if s.owned else f"${s.allocated_budget:.2f}"
    print(f"    {s.slot_id:20s} {status}")
print()

# ---------------------------------------------------------------------------
# 4. CANDIDATE POOLS — what does the selection LLM actually see?
# ---------------------------------------------------------------------------
print("=" * 72)
print("  4. CANDIDATE POOLS (dresser, nightstand, table_lamp)")
print("=" * 72)

adapter = AmazonAdapter()
TRACE_SLOTS = ["dresser", "nightstand", "table_lamp"]

slot_map = {s.slot_id: s for s in slot_plan.slots}
candidate_pools: dict[str, list] = {}

for sid in TRACE_SLOTS:
    slot = slot_map.get(sid)
    if not slot or slot.owned:
        print(f"\n  {sid}: OWNED (skipped)")
        continue

    spec_hints = {}
    candidates = adapter.fetch_candidates(
        sid,
        style_profile.keywords,
        (0.0, slot.allocated_budget),
        spec_hints,
    )
    candidate_pools[sid] = candidates

    print(f"\n  {sid} — {len(candidates)} candidates (budget: ${slot.allocated_budget:.2f})")
    print(f"  {'─' * 60}")

    # Categorize candidates by name keywords to see style distribution.
    dark_keywords = {"dark", "black", "charcoal", "espresso", "leather", "masculine", "industrial", "metal"}
    warm_keywords = {"walnut", "mid-century", "mid century", "warm", "natural", "oak", "modern", "mcm", "wood"}

    dark_count = 0
    warm_count = 0
    for c in candidates:
        name_lower = c.name.lower()
        if any(k in name_lower for k in dark_keywords):
            dark_count += 1
        if any(k in name_lower for k in warm_keywords):
            warm_count += 1

    print(f"  Style distribution (by name keywords):")
    print(f"    Dark/industrial/black/leather: {dark_count}/{len(candidates)}")
    print(f"    Warm/walnut/MCM/natural:       {warm_count}/{len(candidates)}")

    # Show first 10 candidates by name + price.
    print(f"  Sample candidates (first 15):")
    for c in candidates[:15]:
        print(f"    ${c.normalized_price:6.2f}  {c.name[:70]}")

# ---------------------------------------------------------------------------
# 5. SELECTION — what does the LLM pick and why?
# ---------------------------------------------------------------------------
print()
print("=" * 72)
print("  5. SELECTION RESULTS + FIT REASONS")
print("=" * 72)

interests = room_request.interests

for sid in TRACE_SLOTS:
    slot = slot_map.get(sid)
    if not slot or slot.owned or sid not in candidate_pools:
        continue

    candidates = candidate_pools[sid]
    if not candidates:
        print(f"\n  {sid}: no candidates")
        continue

    # Show the EXACT prompt the LLM sees.
    slot_interests = interests if interests and sid in _INTEREST_SLOTS else None
    system_prompt, user_message = _build_selection_prompts(
        slot, style_profile, candidates, interests=slot_interests,
    )

    print(f"\n  {sid}")
    print(f"  {'─' * 60}")
    print(f"  Selection prompt (user message, first 500 chars):")
    print(f"  {user_message[:500]}")
    print()

    # Run the actual selection.
    product, reason = select_product(slot, style_profile, candidates, interests)

    if product:
        print(f"  PICKED: {product.name}")
        print(f"  Price:  ${product.normalized_price:.2f}")
        print(f"  Reason: {reason}")
        # Check: is this a warm/MCM product?
        name_lower = product.name.lower()
        has_dark = any(k in name_lower for k in ["dark", "black", "charcoal", "espresso", "leather", "metal"])
        has_warm = any(k in name_lower for k in ["walnut", "mid-century", "mid century", "warm", "natural", "oak"])
        print(f"  Dark keywords in name: {has_dark}")
        print(f"  Warm/MCM keywords in name: {has_warm}")
    else:
        print(f"  NO PICK: {reason}")

print()
print("=" * 72)
print("  DONE — trace complete")
print("=" * 72)

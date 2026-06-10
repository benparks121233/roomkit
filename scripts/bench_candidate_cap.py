#!/usr/bin/env python3
"""
Benchmark: candidate cap impact on input tokens and selection quality.
Compares uncapped vs capped (25) candidate lists for a sports_den design.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic

from services.intake_service import parse_intake
from services.style_service import interpret_style
from services.composition_service import plan_composition
from services.sourcing.amazon_adapter import AmazonAdapter, _MAX_CANDIDATES
from services.selection_service import (
    select_product, _build_selection_prompts, _INTEREST_SLOTS, _LLM_MODEL,
)

# ---------------------------------------------------------------------------
# Sports Den request
# ---------------------------------------------------------------------------

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
    "interests": ["sports"],
    "full_room": True,
    "wants": [],
}

# ---------------------------------------------------------------------------
# Run pipeline up to composition
# ---------------------------------------------------------------------------

room_request = parse_intake(req_payload)
style_profile = interpret_style(room_request)
slot_plan = plan_composition(room_request, style_profile)
slot_map = {s.slot_id: s for s in slot_plan.slots}

print(f"Style: {style_profile.style_name} (confidence: {style_profile.confidence})")
print(f"Model: {_LLM_MODEL}")
print(f"Max candidates cap: {_MAX_CANDIDATES}")
print()

# ---------------------------------------------------------------------------
# Token counting helper
# ---------------------------------------------------------------------------

client = anthropic.Anthropic()

def count_input_tokens(system_prompt: str, user_message: str) -> int:
    """Use the Anthropic count_tokens API to get exact input token count."""
    resp = client.messages.count_tokens(
        model=_LLM_MODEL,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return resp.input_tokens


# ---------------------------------------------------------------------------
# Compare uncapped vs capped for every sourceable slot
# ---------------------------------------------------------------------------

adapter_capped = AmazonAdapter()  # uses _MAX_CANDIDATES

# For uncapped: temporarily get all candidates by using a huge cap
# We'll just load raw and filter manually
from services.sourcing.catalog_cache import read_cache
from datetime import datetime, timezone

print(f"{'Slot':<18} {'Uncapped':>8} {'Capped':>8} {'Uncap Tok':>10} {'Cap Tok':>10} {'Saved':>8}")
print("─" * 72)

total_uncapped_tokens = 0
total_capped_tokens = 0
interests = room_request.interests

selection_results = {}

for slot in sorted(slot_plan.slots, key=lambda s: s.slot_id):
    if slot.owned:
        continue

    spec_hints = {}
    if "bed_size" in slot.required_specs and room_request.bed_size:
        spec_hints["bed_size"] = room_request.bed_size

    # Get capped candidates (normal flow)
    capped = adapter_capped.fetch_candidates(
        slot.slot_id, style_profile.keywords,
        (0.0, slot.allocated_budget), spec_hints,
    )

    # Get uncapped: read raw, filter by price/spec manually
    raw_products = read_cache(slot.slot_id) or []
    from schemas.product import Product
    now = datetime.now(tz=timezone.utc)
    uncapped = []
    for raw in raw_products:
        price = float(raw["normalized_price"])
        if price > slot.allocated_budget:
            continue
        specs = raw.get("specs", {})
        skip = False
        for k, v in spec_hints.items():
            if k not in specs:
                skip = True
                break
            if v and specs[k].lower() != str(v).lower():
                skip = True
                break
        if skip:
            continue
        uncapped.append(Product(
            product_id=raw["product_id"],
            name=raw["name"],
            normalized_price=price,
            buy_url=raw.get("buy_url", ""),
            specs=specs,
            source="amazon",
            image_url=raw.get("image_url", ""),
            slot_id=slot.slot_id,
            fetched_at=now,
        ))

    # Build prompts for both to count tokens
    slot_interests = interests if interests and slot.slot_id in _INTEREST_SLOTS else None

    if uncapped:
        sys_u, user_u = _build_selection_prompts(slot, style_profile, uncapped, interests=slot_interests)
        tok_uncapped = count_input_tokens(sys_u, user_u)
    else:
        tok_uncapped = 0

    if capped:
        sys_c, user_c = _build_selection_prompts(slot, style_profile, capped, interests=slot_interests)
        tok_capped = count_input_tokens(sys_c, user_c)
    else:
        tok_capped = 0

    total_uncapped_tokens += tok_uncapped
    total_capped_tokens += tok_capped
    saved = tok_uncapped - tok_capped

    print(f"{slot.slot_id:<18} {len(uncapped):>8} {len(capped):>8} {tok_uncapped:>10,} {tok_capped:>10,} {saved:>+8,}")

    # Run actual selection with capped candidates
    if capped:
        product, reason = select_product(slot, style_profile, capped, interests)
        selection_results[slot.slot_id] = (product, reason)

print("─" * 72)
saved_total = total_uncapped_tokens - total_capped_tokens
print(f"{'TOTAL':<18} {'':>8} {'':>8} {total_uncapped_tokens:>10,} {total_capped_tokens:>10,} {saved_total:>+8,}")
print()

# ---------------------------------------------------------------------------
# Cost comparison
# ---------------------------------------------------------------------------

# Haiku pricing: $0.80/M input, $4/M output
# Estimate ~80 output tokens per selection call
num_slots = len(selection_results)
output_tokens_per = 80

uncapped_cost = (total_uncapped_tokens * 0.80 / 1_000_000) + (num_slots * output_tokens_per * 4.0 / 1_000_000)
capped_cost = (total_capped_tokens * 0.80 / 1_000_000) + (num_slots * output_tokens_per * 4.0 / 1_000_000)

# Add style (Sonnet) + composition (Sonnet) costs — ~2000 input tokens each
# Sonnet: $3/M input, $15/M output, ~200 output tokens each
sonnet_cost = 2 * (2000 * 3.0 / 1_000_000 + 200 * 15.0 / 1_000_000)

print(f"Selection cost (Haiku, {num_slots} slots):")
print(f"  Uncapped: ${uncapped_cost:.4f}  (input: {total_uncapped_tokens:,} tok)")
print(f"  Capped:   ${capped_cost:.4f}  (input: {total_capped_tokens:,} tok)")
print(f"  Savings:  ${uncapped_cost - capped_cost:.4f}  ({saved_total:,} fewer input tokens)")
print()
print(f"Sonnet overhead (style + composition): ${sonnet_cost:.4f}")
print(f"Total cost per design:")
print(f"  Before (uncapped): ${uncapped_cost + sonnet_cost:.4f}")
print(f"  After  (capped):   ${capped_cost + sonnet_cost:.4f}")
print()

# ---------------------------------------------------------------------------
# Selection results — show picks
# ---------------------------------------------------------------------------

print("=" * 72)
print("  SELECTION RESULTS (capped, sports_den)")
print("=" * 72)

for sid in sorted(selection_results.keys()):
    product, reason = selection_results[sid]
    if product:
        dark_kw = {"dark", "black", "charcoal", "espresso", "leather", "metal", "industrial", "iron", "steel"}
        name_lower = product.name.lower()
        has_dark = any(k in name_lower for k in dark_kw)
        marker = " [DARK]" if has_dark else ""
        print(f"  {sid:<20} ${product.normalized_price:>7.2f}  {product.name[:55]}{marker}")
        print(f"  {'':20} reason: {reason[:80]}")
    else:
        print(f"  {sid:<20} — {reason}")
print()

#!/usr/bin/env python3
"""
Real-LLM demo: full pipeline with LIVE Anthropic API calls for style
interpretation and per-slot product selection.

Composition is still mocked (deterministic budget math — no reason to
burn tokens on it).  Sourcing uses the real Canopy cache + fixture
fallback.

Requires:
  - ANTHROPIC_API_KEY in .env (loaded via python-dotenv)
  - Canopy cache in data/catalog/ for slots you've refreshed
  - Fixture files in data/fixtures/ for the rest

Usage:
    python scripts/demo_real_llm.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from unittest.mock import patch

from dotenv import load_dotenv

load_dotenv()

from services.config_loader import load_room_taxonomy  # noqa: E402

_TAXONOMY = load_room_taxonomy()
_BEDROOM = _TAXONOMY.room_presets["bedroom"]
_DEFAULT_WEIGHTS = _BEDROOM.flatten_weights()

# Composition is mocked — it's pure budget math, no need for LLM here.
COMPOSITION_LLM_RESPONSE = json.dumps({
    "slot_weights": _DEFAULT_WEIGHTS,
    "rationale": "Bed group anchors the warm minimalist room; rug and soft goods "
                 "provide texture warmth; lighting and decor add atmosphere.",
})


def main() -> None:
    from schemas.room_request import RoomRequest
    from services.composition_gate import validate_composition
    from services.composition_service import plan_composition
    from services.selection_service import select_product
    from services.sourcing.amazon_adapter import AmazonAdapter
    from services.style_service import interpret_style

    # 1. Build request.
    request = RoomRequest(
        run_id="real-llm-001",
        room_type="bedroom",
        budget=1500.0,
        style_description="warm and minimal, natural materials",
        bed_size="queen",
        qa_answers={"vibe": "calm and grounded"},
        created_at=datetime.now(tz=timezone.utc),
    )
    print(f"{'=' * 78}")
    print(f"  RoomKit Real-LLM Demo — {request.room_type}, "
          f"${request.budget:.0f}, bed_size={request.bed_size}")
    print(f"{'=' * 78}\n")

    # 2. Style interpretation — REAL LLM call.
    print("Calling Anthropic API for style interpretation...", flush=True)
    style = interpret_style(request)
    print(f"Style: {style.style_name}  (confidence={style.confidence:.2f})"
          f"{'  [FALLBACK]' if style.fallback else ''}")
    print(f"  Keywords: {', '.join(style.keywords)}")
    print(f"  Palette:  {', '.join(style.color_palette)}")
    print(f"  Mood:     {style.mood}\n")

    # 3. Composition (mocked — deterministic budget split).
    with patch("services.composition_service._call_composition_llm",
               return_value=COMPOSITION_LLM_RESPONSE):
        plan = plan_composition(request, style)

    # 4. Composition gate.
    plan, gate_reason = validate_composition(plan)
    if gate_reason:
        print(f"GATE FAILED: {gate_reason}")
        sys.exit(1)
    print(f"Composition: {len(plan.slots)} slots, "
          f"${plan.total_allocated:.2f} / ${plan.target_budget:.2f} allocated")
    print(f"  Feasible: {plan.is_feasible}  |  Gate: PASSED\n")

    # 5. Source + select per slot — REAL LLM calls for selection.
    adapter = AmazonAdapter()
    selections: list[tuple[str, float, str | None, str | None, str | None]] = []
    running_total = 0.0

    print(f"{'─' * 78}")
    print(f"  {'Slot':<16} {'Budget':>8}  {'Product':<32} {'Price':>8}")
    print(f"{'─' * 78}")

    for slot in sorted(plan.slots, key=lambda s: s.slot_id):
        if slot.owned:
            print(f"  {slot.slot_id:<16} {'$0.00':>8}  {'(owned)':^32} {'—':>8}")
            continue

        # Build required_specs dict for the adapter.
        spec_hints: dict[str, str] = {}
        if "bed_size" in slot.required_specs and request.bed_size:
            spec_hints["bed_size"] = request.bed_size

        candidates = adapter.fetch_candidates(
            slot.slot_id,
            style.keywords,
            (0.0, slot.allocated_budget),
            spec_hints,
        )

        # REAL LLM call — no mock.
        product, reason = select_product(slot, style, candidates)

        if product:
            running_total += product.normalized_price
            name_trunc = (product.name[:30] + ".."
                          if len(product.name) > 32 else product.name)
            print(f"  {slot.slot_id:<16} ${slot.allocated_budget:>7.2f}"
                  f"  {name_trunc:<32} ${product.normalized_price:>7.2f}")
            selections.append((
                slot.slot_id, product.normalized_price, product.name,
                product.buy_url, reason,
            ))
        else:
            label = f"— {reason or 'unknown'}"
            print(f"  {slot.slot_id:<16} ${slot.allocated_budget:>7.2f}"
                  f"  {label:<32} {'—':>8}")
            selections.append((slot.slot_id, 0.0, None, None, reason))

    print(f"{'─' * 78}")
    print(f"  {'TOTAL':<16} ${plan.target_budget:>7.2f}"
          f"  {'':32} ${running_total:>7.2f}")
    remaining = plan.target_budget - running_total
    print(f"  {'REMAINING':<16} {'':>8}  {'':32} ${remaining:>7.2f}")
    print()

    # 6. LLM fit reasons.
    print("LLM fit reasons:")
    for slot_id, price, name, url, reason in selections:
        if name:
            print(f"  {slot_id:<16} {reason}")
        else:
            print(f"  {slot_id:<16} (no selection: {reason})")
    print()

    # 7. Affiliate tag audit.
    print("Affiliate tag audit:")
    all_tagged = True
    for slot_id, price, name, url, _ in selections:
        if url:
            tagged = "roomkitai-20" in url
            status = "OK" if tagged else "MISSING"
            if not tagged:
                all_tagged = False
            print(f"  {slot_id:<16} {status}")
    print(f"  Result: {'ALL TAGGED' if all_tagged else 'TAG MISSING — BUG'}\n")

    # 8. Budget check.
    over = running_total > plan.target_budget
    print(f"Budget check: ${running_total:.2f} / ${plan.target_budget:.2f} "
          f"-> {'OVER BUDGET — BUG' if over else 'WITHIN BUDGET'}")
    print()


if __name__ == "__main__":
    main()

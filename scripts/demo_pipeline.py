#!/usr/bin/env python3
"""
Demo: full pipeline end-to-end with mocked LLM seams.

RoomRequest (bedroom, $1500, warm_minimalist, owns nothing)
  → interpret_style
  → plan_composition
  → composition gate
  → for each sourced slot: fetch_candidates → select_product

Prints a readable summary of the chosen board.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from unittest.mock import patch

from services.config_loader import load_room_taxonomy

# Load taxonomy to build dynamic mocked responses.
_TAXONOMY = load_room_taxonomy()
_BEDROOM = _TAXONOMY.room_presets["bedroom"]
_DEFAULT_WEIGHTS = _BEDROOM.flatten_weights()
_REQUIRED = set(_BEDROOM.required_items())

# --- Mocked LLM responses ---------------------------------------------------

STYLE_LLM_RESPONSE = json.dumps({
    "style_name": "warm_minimalist",
    "keywords": ["natural wood", "linen", "warm tones", "uncluttered"],
    "color_palette": ["#FAF3E0", "#D4C5A9", "#8B7355", "#F5F0E8"],
    "mood": "calm, grounded, uncluttered",
    "confidence": 0.92,
    "fallback": False,
})

COMPOSITION_LLM_RESPONSE = json.dumps({
    "slot_weights": _DEFAULT_WEIGHTS,
    "rationale": "Bed group anchors the warm minimalist room; rug and soft goods "
                 "provide texture warmth; lighting and decor add atmosphere.",
})

# Dynamic selection mock — reads the candidate list from the user_message
# prompt and picks the first product_id.  Works for any catalog (fixture IDs,
# real ASINs, anything).

def _mock_selection_llm(system_prompt: str, user_message: str) -> str:
    """Parse the candidates JSON from the prompt and pick the first one."""
    # The candidates JSON follows "Candidates:\n" in the user message.
    marker = "Candidates:\n"
    try:
        idx = user_message.index(marker)
        candidates_text = user_message[idx + len(marker):]
        candidates = json.loads(candidates_text.strip())
        if candidates:
            return json.dumps({
                "product_id": candidates[0]["product_id"],
                "fit_reason": "Best style match from candidates",
                "confidence": 0.88,
                "null_reason": None,
            })
    except (ValueError, json.JSONDecodeError, KeyError, IndexError):
        pass
    return json.dumps({
        "product_id": None,
        "fit_reason": "",
        "confidence": 0.0,
        "null_reason": "no_candidate",
    })


# --- Run the pipeline --------------------------------------------------------

def main() -> None:
    from schemas.room_request import RoomRequest
    from services.composition_gate import validate_composition
    from services.composition_service import plan_composition
    from services.selection_service import select_product
    from services.sourcing.amazon_adapter import AmazonAdapter
    from services.style_service import interpret_style

    # 1. Build request.
    request = RoomRequest(
        run_id="demo-001",
        room_type="bedroom",
        budget=1500.0,
        style_description="warm and minimal, natural materials",
        bed_size="queen",
        qa_answers={"vibe": "calm and grounded"},
        created_at=datetime.now(tz=timezone.utc),
    )
    print(f"{'=' * 72}")
    print(f"  RoomKit Demo Pipeline — {request.room_type}, ${request.budget:.0f}")
    print(f"{'=' * 72}\n")

    # 2. Style interpretation (mocked).
    with patch("services.style_service._call_llm", return_value=STYLE_LLM_RESPONSE):
        style = interpret_style(request)
    print(f"Style: {style.style_name}  (confidence={style.confidence:.2f})")
    print(f"  Keywords: {', '.join(style.keywords)}")
    print(f"  Mood: {style.mood}\n")

    # 3. Composition (mocked).
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

    # 5. Source + select per slot.
    adapter = AmazonAdapter()
    selections: list[tuple[str, float, str | None, str | None, str | None]] = []
    running_total = 0.0

    print(f"{'─' * 72}")
    print(f"  {'Slot':<18} {'Budget':>8}  {'Product':<30} {'Price':>8}")
    print(f"{'─' * 72}")

    for slot in sorted(plan.slots, key=lambda s: s.slot_id):
        if slot.owned:
            print(f"  {slot.slot_id:<18} {'$0.00':>8}  {'(owned)':^30} {'—':>8}")
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

        with patch("services.selection_service._call_selection_llm",
                   side_effect=_mock_selection_llm):
            product, reason = select_product(slot, style, candidates)

        if product:
            running_total += product.normalized_price
            name_trunc = product.name[:28] + ".." if len(product.name) > 30 else product.name
            print(f"  {slot.slot_id:<18} ${slot.allocated_budget:>7.2f}"
                  f"  {name_trunc:<30} ${product.normalized_price:>7.2f}")
            selections.append((
                slot.slot_id, product.normalized_price, product.name,
                product.buy_url, reason,
            ))
        else:
            print(f"  {slot.slot_id:<18} ${slot.allocated_budget:>7.2f}"
                  f"  {'— ' + (reason or 'unknown'):<30} {'—':>8}")
            selections.append((slot.slot_id, 0.0, None, None, reason))

    print(f"{'─' * 72}")
    print(f"  {'TOTAL':<18} ${plan.target_budget:>7.2f}"
          f"  {'':30} ${running_total:>7.2f}")
    remaining = plan.target_budget - running_total
    print(f"  {'REMAINING':<18} {'':>8}  {'':30} ${remaining:>7.2f}")
    print()

    # 6. Affiliate tag audit.
    print("Affiliate tag audit:")
    all_tagged = True
    for slot_id, price, name, url, _ in selections:
        if url:
            tagged = "roomkitai-20" in url
            status = "OK" if tagged else "MISSING"
            if not tagged:
                all_tagged = False
            print(f"  {slot_id:<18} {status}")
    print(f"  Result: {'ALL TAGGED' if all_tagged else 'TAG MISSING — BUG'}\n")

    # 7. Budget check.
    over = running_total > plan.target_budget
    print(f"Budget check: ${running_total:.2f} / ${plan.target_budget:.2f} "
          f"→ {'OVER BUDGET — BUG' if over else 'WITHIN BUDGET'}")
    print()


if __name__ == "__main__":
    main()

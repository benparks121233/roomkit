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

# Per-slot selection responses — map to fixture product IDs.
SELECTION_RESPONSES = {
    "bed_frame": json.dumps({
        "product_id": "BF-001",
        "fit_reason": "Clean wood platform frame fits warm minimalist perfectly",
        "confidence": 0.90,
        "null_reason": None,
    }),
    "mattress": json.dumps({
        "product_id": "MT-002",
        "fit_reason": "Affordable hybrid mattress fits the budget",
        "confidence": 0.88,
        "null_reason": None,
    }),
    "sheets": json.dumps({
        "product_id": "SH-001",
        "fit_reason": "Beige microfiber sheets match the warm palette",
        "confidence": 0.87,
        "null_reason": None,
    }),
    "comforter": json.dumps({
        "product_id": "CM-001",
        "fit_reason": "Beige all-season comforter matches the palette",
        "confidence": 0.86,
        "null_reason": None,
    }),
    "pillows": json.dumps({
        "product_id": "PL-003",
        "fit_reason": "Budget-friendly down alternative pillows",
        "confidence": 0.84,
        "null_reason": None,
    }),
    "nightstand": json.dumps({
        "product_id": "NS-001",
        "fit_reason": "Rustic brown nightstand complements natural wood",
        "confidence": 0.88,
        "null_reason": None,
    }),
    "dresser": json.dumps({
        "product_id": "DR-001",
        "fit_reason": "Rustic brown fabric dresser matches the mood",
        "confidence": 0.83,
        "null_reason": None,
    }),
    "ceiling_light": json.dumps({
        "product_id": "CL-002",
        "fit_reason": "Boho rattan ceiling light adds natural warmth",
        "confidence": 0.89,
        "null_reason": None,
    }),
    "table_lamp": json.dumps({
        "product_id": "TL-001",
        "fit_reason": "Linen shade table lamp provides warm ambient light",
        "confidence": 0.85,
        "null_reason": None,
    }),
    "floor_lamp": json.dumps({
        "product_id": "FL-002",
        "fit_reason": "Simple floor lamp with reading light adds function",
        "confidence": 0.84,
        "null_reason": None,
    }),
    "wall_art": json.dumps({
        "product_id": "WA-002",
        "fit_reason": "Botanical prints complement natural wood tones",
        "confidence": 0.83,
        "null_reason": None,
    }),
    "plants": json.dumps({
        "product_id": "PT-002",
        "fit_reason": "Macrame plant hangers add warmth without clutter",
        "confidence": 0.82,
        "null_reason": None,
    }),
    "mirror": json.dumps({
        "product_id": "MR-002",
        "fit_reason": "Round gold mirror adds a touch of elegance",
        "confidence": 0.80,
        "null_reason": None,
    }),
    "rug": json.dumps({
        "product_id": "RG-001",
        "fit_reason": "Braided jute adds natural texture",
        "confidence": 0.91,
        "null_reason": None,
    }),
    "curtains": json.dumps({
        "product_id": "CT-002",
        "fit_reason": "Linen sheer curtains let in natural light",
        "confidence": 0.85,
        "null_reason": None,
    }),
    "throw_blanket": json.dumps({
        "product_id": "TB-002",
        "fit_reason": "Ivory faux fur throw adds cozy texture",
        "confidence": 0.83,
        "null_reason": None,
    }),
}

# Track which slot the selection LLM is being called for.
_current_slot = {"id": ""}


def _mock_selection_llm(system_prompt: str, user_message: str) -> str:
    return SELECTION_RESPONSES.get(_current_slot["id"], json.dumps({
        "product_id": None,
        "fit_reason": "",
        "confidence": 0.0,
        "null_reason": "no_candidate",
    }))


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

        _current_slot["id"] = slot.slot_id
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

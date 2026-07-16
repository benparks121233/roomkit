# tests/test_composition_integration.py
# Integration tests: RoomRequest → interpret_style → plan_composition → validator gate.
#
# Both LLM seams are mocked:
#   - services.style_service._call_llm (style interpretation)
#   - services.composition_service._call_composition_llm (weight proposal)
#
# Coverage:
#   - Normal request → feasible, on-budget, all-required, no-duplicate plan
#     that passes every gate with reason=None.
#   - Sub-floor-budget request → is_feasible=False, caught by the feasibility
#     gate (reason starts with "plan_infeasible"), no downstream step attempted.

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from schemas.room_request import RoomRequest
from services.composition_gate import validate_composition
from services.composition_service import plan_composition
from services.config_loader import load_room_taxonomy
from services.style_service import interpret_style

TAXONOMY = load_room_taxonomy()
_BEDROOM_PRESET = TAXONOMY.room_presets["bedroom"]
BEDROOM_REQUIRED = set(_BEDROOM_PRESET.required_items())
_LIVING_PRESET = TAXONOMY.room_presets["living_room"]
LIVING_ROOM_REQUIRED = set(_LIVING_PRESET.required_items())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_request(budget: float = 1500.0, room_type: str = "bedroom") -> RoomRequest:
    return RoomRequest(
        run_id="integ-run-001",
        room_type=room_type,
        budget=budget,
        style_description="cozy and warm",
        created_at=datetime.now(tz=timezone.utc),
    )


_MOCK_USAGE = {"input_tokens": 0, "output_tokens": 0}


def _style_llm_response() -> tuple[str, dict]:
    return json.dumps({
        "style_name": "warm_minimalist",
        "keywords": ["natural wood", "linen"],
        "color_palette": ["#FAF3E0", "#D4C5A9"],
        "mood": "calm, grounded",
        "confidence": 0.9,
        "fallback": False,
    }), _MOCK_USAGE


def _composition_llm_response() -> tuple[str, dict]:
    weights = _BEDROOM_PRESET.flatten_weights()
    return json.dumps({
        "slot_weights": {sid: w for sid, w in weights.items()
                         if sid in BEDROOM_REQUIRED},
        "rationale": "Prioritized bed_frame for warm_minimalist anchoring.",
    }), _MOCK_USAGE


_STYLE_LLM = "services.style_service._call_llm"
_COMP_LLM = "services.composition_service._call_composition_llm"


# ---------------------------------------------------------------------------
# Normal request: full pipeline passes every gate
# ---------------------------------------------------------------------------

def test_normal_request_passes_all_gates():
    """A normal budget request flows through style → composition → gates cleanly."""
    with patch(_STYLE_LLM, return_value=_style_llm_response()), \
         patch(_COMP_LLM, return_value=_composition_llm_response()):
        request = _make_request(budget=1500.0)
        style, _su = interpret_style(request)
        plan, _cu = plan_composition(request, style)
        plan, reason = validate_composition(plan)

    # Gate passed — no failure reason.
    assert reason is None

    # Plan is feasible and on-budget.
    assert plan.is_feasible is True
    assert plan.total_allocated <= 1500.0
    assert plan.total_allocated > 0.0

    # All required bedroom slots present.
    slot_ids = {s.slot_id for s in plan.slots}
    for sid in BEDROOM_REQUIRED:
        assert sid in slot_ids, f"Required slot '{sid}' missing"

    # No duplicates (implicitly proven by gate passing, but explicit check).
    assert len(slot_ids) == len(plan.slots)

    # Metadata threaded correctly.
    assert plan.run_id == "integ-run-001"
    assert plan.room_preset == "bedroom"
    assert plan.target_budget == pytest.approx(1500.0)


def test_normal_request_style_profile_is_used():
    """The style profile returned by interpret_style reaches plan_composition."""
    with patch(_STYLE_LLM, return_value=_style_llm_response()), \
         patch(_COMP_LLM, return_value=_composition_llm_response()) as mock_comp:
        request = _make_request()
        style, _su = interpret_style(request)
        plan_composition(request, style)

    # The composition LLM was called (we can't inspect the prompt content
    # easily, but we can verify it was invoked exactly once).
    mock_comp.assert_called_once()


# ---------------------------------------------------------------------------
# Sub-floor-budget: feasibility gate catches it
# ---------------------------------------------------------------------------

def test_sub_floor_budget_caught_by_feasibility_gate():
    """Budget below MVB → is_feasible=False → gate returns plan_infeasible reason."""
    with patch(_STYLE_LLM, return_value=_style_llm_response()), \
         patch(_COMP_LLM, return_value=_composition_llm_response()):
        request = _make_request(budget=100.0)
        style, _su = interpret_style(request)
        plan, _cu = plan_composition(request, style)
        plan, reason = validate_composition(plan)

    assert plan.is_feasible is False
    assert reason is not None
    assert "plan_infeasible" in reason


def test_sub_floor_budget_carries_minimum_viable_budget():
    """The infeasible plan carries the honest MVB for the user."""
    with patch(_STYLE_LLM, return_value=_style_llm_response()), \
         patch(_COMP_LLM, return_value=_composition_llm_response()):
        request = _make_request(budget=100.0)
        style, _su = interpret_style(request)
        plan, _cu = plan_composition(request, style)

    assert plan.minimum_viable_budget is not None
    assert plan.minimum_viable_budget == pytest.approx(500.0, abs=1.0)


def test_sub_floor_budget_total_allocated_is_zero():
    """An infeasible plan has all slots at $0 — nothing was allocated."""
    with patch(_STYLE_LLM, return_value=_style_llm_response()), \
         patch(_COMP_LLM, return_value=_composition_llm_response()):
        request = _make_request(budget=100.0)
        style, _su = interpret_style(request)
        plan, _cu = plan_composition(request, style)

    assert plan.total_allocated == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Living room end-to-end
# ---------------------------------------------------------------------------

def test_living_room_passes_all_gates():
    """Living room preset flows through the same pipeline cleanly."""
    lr_weights = _LIVING_PRESET.flatten_weights()
    living_response = json.dumps({
        "slot_weights": {sid: w for sid, w in lr_weights.items()
                         if sid in LIVING_ROOM_REQUIRED},
        "rationale": "Sofa is the anchor in a living room.",
    })
    with patch(_STYLE_LLM, return_value=_style_llm_response()), \
         patch(_COMP_LLM, return_value=living_response):
        request = _make_request(budget=2000.0, room_type="living_room")
        style, _su = interpret_style(request)
        plan, _cu = plan_composition(request, style)
        plan, reason = validate_composition(plan)

    assert reason is None
    assert plan.is_feasible is True
    assert plan.room_preset == "living_room"
    slot_ids = {s.slot_id for s in plan.slots}
    for sid in LIVING_ROOM_REQUIRED:
        assert sid in slot_ids

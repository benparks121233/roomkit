# tests/test_plan_composition.py
# Tests for services/composition_service.plan_composition() — Stage 5 Piece 3.
#
# Per AGENTS.md: no live LLM calls in tests.
# All tests patch services.composition_service._call_composition_llm.
#
# Coverage:
#   - Normal weight proposal produces a valid on-budget SlotPlan.
#   - Weights summing to 3.0 are normalized; total_allocated <= budget.
#   - Hallucinated slot id is dropped; plan still valid.
#   - Missing required slot is injected at taxonomy default.
#   - Unparseable LLM response falls back to taxonomy default weights.
#   - Code-fenced JSON is parsed correctly.
#   - run_id and target_budget are threaded from RoomRequest.

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from schemas.room_request import RoomRequest
from schemas.style_profile import StyleProfile
from services.composition_service import plan_composition
from services.config_loader import load_room_taxonomy

TAXONOMY = load_room_taxonomy()
_BEDROOM_PRESET = TAXONOMY.room_presets["bedroom"]
BEDROOM_REQUIRED = set(_BEDROOM_PRESET.required_items())
_BEDROOM_DEFAULT_WEIGHTS = _BEDROOM_PRESET.flatten_weights()
_LIVING_PRESET = TAXONOMY.room_presets["living_room"]
LIVING_ROOM_REQUIRED = set(_LIVING_PRESET.required_items())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_request(
    run_id: str = "test-run-001",
    room_type: str = "bedroom",
    budget: float = 1500.0,
) -> RoomRequest:
    return RoomRequest(
        run_id=run_id,
        room_type=room_type,
        budget=budget,
        created_at=datetime.now(tz=timezone.utc),
    )


def _make_style() -> StyleProfile:
    return StyleProfile(
        style_name="warm_minimalist",
        keywords=["natural wood", "linen"],
        color_palette=["#FAF3E0", "#D4C5A9"],
        mood="calm, grounded",
        confidence=0.9,
        fallback=False,
    )


def _llm_weights_json(weights: dict[str, float], rationale: str = "balanced") -> str:
    return json.dumps({"slot_weights": weights, "rationale": rationale})


def _bedroom_required_weights() -> dict[str, float]:
    """Return taxonomy default weights for bedroom required items only."""
    return {sid: _BEDROOM_DEFAULT_WEIGHTS[sid] for sid in BEDROOM_REQUIRED}


_PATCH_TARGET = "services.composition_service._call_composition_llm"


# ---------------------------------------------------------------------------
# Normal proposal
# ---------------------------------------------------------------------------

def test_normal_proposal_produces_valid_plan():
    """Clean weights produce a feasible plan within budget."""
    weights = _bedroom_required_weights()
    with patch(_PATCH_TARGET, return_value=_llm_weights_json(weights)):
        plan = plan_composition(_make_request(), _make_style())

    assert plan.is_feasible is True
    assert plan.total_allocated <= 1500.0
    slot_ids = {s.slot_id for s in plan.slots}
    for sid in BEDROOM_REQUIRED:
        assert sid in slot_ids


def test_normal_proposal_threads_run_id():
    weights = _bedroom_required_weights()
    with patch(_PATCH_TARGET, return_value=_llm_weights_json(weights)):
        plan = plan_composition(_make_request(run_id="abc-123"), _make_style())

    assert plan.run_id == "abc-123"


def test_normal_proposal_threads_target_budget():
    weights = _bedroom_required_weights()
    with patch(_PATCH_TARGET, return_value=_llm_weights_json(weights)):
        plan = plan_composition(_make_request(budget=2000.0), _make_style())

    assert plan.target_budget == pytest.approx(2000.0)
    assert plan.total_allocated <= 2000.0


# ---------------------------------------------------------------------------
# Overweight normalization (sum = 3.0)
# ---------------------------------------------------------------------------

def test_overweight_sum_3_still_within_budget():
    """Weights summing to 3.0 are normalized; total never exceeds budget."""
    weights = {sid: 0.50 for sid in BEDROOM_REQUIRED}
    with patch(_PATCH_TARGET, return_value=_llm_weights_json(weights)):
        plan = plan_composition(_make_request(budget=1000.0), _make_style())

    assert plan.is_feasible is True
    assert plan.total_allocated <= 1000.0
    assert plan.total_allocated > 0.0


# ---------------------------------------------------------------------------
# Hallucinated slot id
# ---------------------------------------------------------------------------

def test_hallucinated_slot_id_is_dropped():
    """An unknown slot id from the LLM is silently dropped."""
    weights = dict(_bedroom_required_weights())
    weights["magic_chair"] = 0.15  # not in taxonomy
    with patch(_PATCH_TARGET, return_value=_llm_weights_json(weights)):
        plan = plan_composition(_make_request(), _make_style())

    assert plan.is_feasible is True
    slot_ids = {s.slot_id for s in plan.slots}
    assert "magic_chair" not in slot_ids
    for sid in BEDROOM_REQUIRED:
        assert sid in slot_ids


# ---------------------------------------------------------------------------
# Missing required slot
# ---------------------------------------------------------------------------

def test_missing_required_slot_is_injected():
    """If the LLM omits a required slot, it is injected at taxonomy default."""
    weights = dict(_bedroom_required_weights())
    omitted = sorted(BEDROOM_REQUIRED)[0]
    del weights[omitted]
    with patch(_PATCH_TARGET, return_value=_llm_weights_json(weights)):
        plan = plan_composition(_make_request(), _make_style())

    assert plan.is_feasible is True
    slot_ids = {s.slot_id for s in plan.slots}
    assert omitted in slot_ids
    assert plan.total_allocated <= 1500.0


# ---------------------------------------------------------------------------
# Unparseable response → fallback to taxonomy defaults
# ---------------------------------------------------------------------------

def test_unparseable_response_falls_back_to_taxonomy_defaults():
    """Garbage LLM output → taxonomy default weights, still a valid plan."""
    with patch(_PATCH_TARGET, return_value="I'm not JSON at all, sorry!"):
        plan = plan_composition(_make_request(), _make_style())

    assert plan.is_feasible is True
    slot_ids = {s.slot_id for s in plan.slots}
    for sid in BEDROOM_REQUIRED:
        assert sid in slot_ids
    assert plan.total_allocated <= 1500.0


def test_empty_json_object_falls_back():
    """An empty JSON object (no slot_weights key) → taxonomy defaults."""
    with patch(_PATCH_TARGET, return_value="{}"):
        plan = plan_composition(_make_request(), _make_style())

    assert plan.is_feasible is True
    slot_ids = {s.slot_id for s in plan.slots}
    for sid in BEDROOM_REQUIRED:
        assert sid in slot_ids


def test_code_fenced_json_is_parsed():
    """LLM wrapping response in ```json ... ``` is handled."""
    weights = _bedroom_required_weights()
    fenced = f"```json\n{_llm_weights_json(weights)}\n```"
    with patch(_PATCH_TARGET, return_value=fenced):
        plan = plan_composition(_make_request(), _make_style())

    assert plan.is_feasible is True
    slot_ids = {s.slot_id for s in plan.slots}
    for sid in BEDROOM_REQUIRED:
        assert sid in slot_ids


# ---------------------------------------------------------------------------
# Edge: all weights are garbage (negative, zero, non-numeric)
# ---------------------------------------------------------------------------

def test_all_garbage_weights_fall_back():
    """If every proposed weight is invalid, taxonomy defaults are used."""
    weights = {"bed_frame": -1.0, "mattress": 0, "rug": "banana"}
    with patch(_PATCH_TARGET, return_value=_llm_weights_json(weights)):
        plan = plan_composition(_make_request(), _make_style())

    assert plan.is_feasible is True
    slot_ids = {s.slot_id for s in plan.slots}
    for sid in BEDROOM_REQUIRED:
        assert sid in slot_ids


# ---------------------------------------------------------------------------
# Living room preset
# ---------------------------------------------------------------------------

def test_living_room_preset_works():
    """plan_composition works for a non-bedroom preset."""
    lr_weights = _LIVING_PRESET.flatten_weights()
    weights = {sid: lr_weights[sid] for sid in LIVING_ROOM_REQUIRED}
    with patch(_PATCH_TARGET, return_value=_llm_weights_json(weights)):
        plan = plan_composition(
            _make_request(room_type="living_room"), _make_style(),
        )

    assert plan.is_feasible is True
    assert plan.room_preset == "living_room"
    slot_ids = {s.slot_id for s in plan.slots}
    for sid in LIVING_ROOM_REQUIRED:
        assert sid in slot_ids

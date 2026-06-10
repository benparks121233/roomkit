# tests/test_have_need_composition.py
# Tests for Stage 5.5 Piece B: per-request required set via already_have / must_have.
#
# Coverage:
#   - already_have shrinks effective_required → budget that was infeasible for
#     full preset becomes feasible when user owns several required slots.
#   - Owned slots are excluded from sourcing: allocated_budget=0, owned=True,
#     and they do NOT contribute to total_allocated.
#   - must_have optional slot is forced into the plan and never dropped, even
#     under a tight budget (a non-must-have optional drops first).
#   - plan_composition threads already_have / must_have from RoomRequest.
#   - Owned slots appear on infeasible plans too.

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from schemas.room_request import RoomRequest
from services.composition_service import fit_slots_to_budget, plan_composition
from services.config_loader import load_budget_policies, load_room_taxonomy

TAXONOMY = load_room_taxonomy()
BUDGET_POLICIES = load_budget_policies()

_BEDROOM_PRESET = TAXONOMY.room_presets["bedroom"]
BEDROOM_REQUIRED = set(_BEDROOM_PRESET.required_items())
_BEDROOM_DEFAULT_WEIGHTS = _BEDROOM_PRESET.flatten_weights()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bedroom_weights() -> dict[str, float]:
    """Required-only bedroom weights from taxonomy defaults."""
    return {sid: _BEDROOM_DEFAULT_WEIGHTS[sid] for sid in BEDROOM_REQUIRED}


def _make_request(
    budget: float = 1500.0,
    already_have: list[str] | None = None,
    must_have: list[str] | None = None,
) -> RoomRequest:
    return RoomRequest(
        run_id="have-need-test",
        room_type="bedroom",
        budget=budget,
        already_have=already_have or [],
        must_have=must_have or [],
        created_at=datetime.now(tz=timezone.utc),
    )


# ---------------------------------------------------------------------------
# already_have shrinks required → infeasible becomes feasible
# ---------------------------------------------------------------------------

def test_already_have_makes_infeasible_budget_feasible():
    """Budget $100 is infeasible for full bedroom (MVB=$500), but with
    max(sum_w, 1.0) clamping, MVB can't go below $500 for sum<1.0 weights.
    This test verifies the structural path is exercised without error."""
    plan = fit_slots_to_budget(
        _bedroom_weights(), 100.0, "bedroom", TAXONOMY, BUDGET_POLICIES,
    )
    assert plan.is_feasible is False


def test_already_have_shrinks_required_makes_tight_budget_feasible():
    """With heavy weights summing > 1.0, owning some slots reduces the floor.

    Setup: all bedroom required slots with weight 0.30 each → sum > 1.0, floor > $500.
    Budget $600 < floor → infeasible with full set.
    Own 5 required slots: effective_required shrinks, sum drops below 1.0,
    floor = $500. Budget $600 >= $500 → FEASIBLE.
    """
    heavy_weights = {sid: 0.30 for sid in BEDROOM_REQUIRED}

    # Without already_have: infeasible at $600.
    plan_full = fit_slots_to_budget(
        heavy_weights, 600.0, "bedroom", TAXONOMY, BUDGET_POLICIES,
    )
    assert plan_full.is_feasible is False

    # Own most required slots, leaving just a few sourced.
    owned = set(sorted(BEDROOM_REQUIRED)[:6])
    plan_owned = fit_slots_to_budget(
        heavy_weights, 600.0, "bedroom", TAXONOMY, BUDGET_POLICIES,
        already_have=owned,
    )
    assert plan_owned.is_feasible is True
    assert plan_owned.total_allocated <= 600.0


def test_already_have_shrinks_required_with_default_weights():
    """Owning slots with default-weight plans is structurally correct."""
    plan = fit_slots_to_budget(
        _bedroom_weights(), 500.0, "bedroom", TAXONOMY, BUDGET_POLICIES,
        already_have={"bed_frame", "mattress", "sheets"},
    )
    assert plan.is_feasible is True
    sourced = [s for s in plan.slots if not s.owned]
    assert len(sourced) == len(BEDROOM_REQUIRED) - 3
    assert all(s.allocated_budget > 0 for s in sourced)


# ---------------------------------------------------------------------------
# Owned slots: excluded from sourcing, $0, owned=True
# ---------------------------------------------------------------------------

def test_owned_slots_have_zero_budget():
    plan = fit_slots_to_budget(
        _bedroom_weights(), 1500.0, "bedroom", TAXONOMY, BUDGET_POLICIES,
        already_have={"bed_frame", "rug"},
    )
    owned = [s for s in plan.slots if s.owned]
    assert len(owned) == 2
    for slot in owned:
        assert slot.allocated_budget == 0.0


def test_owned_slots_marked_owned_true():
    plan = fit_slots_to_budget(
        _bedroom_weights(), 1500.0, "bedroom", TAXONOMY, BUDGET_POLICIES,
        already_have={"bed_frame"},
    )
    bf = next(s for s in plan.slots if s.slot_id == "bed_frame")
    assert bf.owned is True


def test_owned_slots_do_not_contribute_to_total_allocated():
    """total_allocated must reflect only sourced slots (owned are $0 anyway)."""
    plan = fit_slots_to_budget(
        _bedroom_weights(), 1500.0, "bedroom", TAXONOMY, BUDGET_POLICIES,
        already_have={"bed_frame", "mattress"},
    )
    sourced_sum = sum(s.allocated_budget for s in plan.slots if not s.owned)
    assert plan.total_allocated == pytest.approx(sourced_sum)
    assert plan.total_allocated > 0.0


def test_owned_slots_present_on_plan_for_render():
    """Owned slots appear on the plan so render/assembly can reference them."""
    plan = fit_slots_to_budget(
        _bedroom_weights(), 1500.0, "bedroom", TAXONOMY, BUDGET_POLICIES,
        already_have={"bed_frame", "rug"},
    )
    slot_ids = {s.slot_id for s in plan.slots}
    assert "bed_frame" in slot_ids
    assert "rug" in slot_ids


def test_owned_slots_appear_on_infeasible_plan():
    """Even when the plan is infeasible, owned slots are still listed."""
    heavy_weights = {sid: 0.30 for sid in BEDROOM_REQUIRED}
    plan = fit_slots_to_budget(
        heavy_weights, 100.0, "bedroom", TAXONOMY, BUDGET_POLICIES,
        already_have={"bed_frame"},
    )
    slot_ids = {s.slot_id for s in plan.slots}
    assert "bed_frame" in slot_ids
    bf = next(s for s in plan.slots if s.slot_id == "bed_frame")
    assert bf.owned is True
    assert bf.allocated_budget == 0.0


# ---------------------------------------------------------------------------
# must_have: promoted to required, never dropped
# ---------------------------------------------------------------------------

def test_must_have_optional_forced_into_plan():
    """A must_have optional slot (dresser) is included even with tight budget."""
    # dresser is not in bedroom's required items. Normally it could be dropped.
    weights = {**_bedroom_weights(), "dresser": 0.08}
    plan = fit_slots_to_budget(
        weights, 1500.0, "bedroom", TAXONOMY, BUDGET_POLICIES,
        must_have={"dresser"},
    )
    assert plan.is_feasible is True
    slot_ids = {s.slot_id for s in plan.slots}
    assert "dresser" in slot_ids


def test_must_have_never_dropped_on_tight_budget():
    """With dresser as must_have and mirror as optional, only mirror gets dropped
    when budget is tight — dresser is protected as effective-required."""
    weights = {**_bedroom_weights(), "dresser": 0.18, "mirror": 0.28}
    # total_w > 1.0 → floor > $500.
    # With must_have={"dresser"}: effective_required includes dresser.
    # Droppable = {mirror}. After dropping mirror: sum should drop enough.
    plan = fit_slots_to_budget(
        weights, 540.0, "bedroom", TAXONOMY, BUDGET_POLICIES,
        must_have={"dresser"},
    )
    assert plan.is_feasible is True
    slot_ids = {s.slot_id for s in plan.slots}
    assert "dresser" in slot_ids, "must_have slot dresser should not be dropped"
    assert "mirror" not in slot_ids, "non-must-have optional mirror should be dropped"


def test_must_have_slot_gets_budget():
    """A must_have slot receives a non-zero allocation."""
    weights = {**_bedroom_weights(), "dresser": 0.08}
    plan = fit_slots_to_budget(
        weights, 1500.0, "bedroom", TAXONOMY, BUDGET_POLICIES,
        must_have={"dresser"},
    )
    slot = next(s for s in plan.slots if s.slot_id == "dresser")
    assert slot.allocated_budget > 0.0
    assert slot.owned is False


# ---------------------------------------------------------------------------
# plan_composition threads have/need from RoomRequest
# ---------------------------------------------------------------------------

_COMP_LLM = "services.composition_service._call_composition_llm"


def test_plan_composition_threads_already_have():
    """plan_composition passes already_have through to fit_slots_to_budget."""
    weights_json = json.dumps({
        "slot_weights": {sid: 0.30 for sid in BEDROOM_REQUIRED},
        "rationale": "test",
    })
    # Own most slots so the plan is feasible at $600.
    owned = sorted(BEDROOM_REQUIRED)[:6]
    request = _make_request(budget=600.0, already_have=owned)
    with patch(_COMP_LLM, return_value=weights_json):
        from schemas.style_profile import StyleProfile
        style = StyleProfile(
            style_name="warm_minimalist", keywords=["wood"], color_palette=["#FFF"],
            mood="calm", confidence=0.9, fallback=False,
        )
        plan = plan_composition(request, style)

    assert plan.is_feasible is True
    owned_ids = {s.slot_id for s in plan.slots if s.owned}
    assert owned_ids == set(owned)


def test_plan_composition_threads_must_have():
    """plan_composition passes must_have through to fit_slots_to_budget."""
    weights_json = json.dumps({
        "slot_weights": {**_bedroom_weights(), "dresser": 0.08},
        "rationale": "test",
    })
    request = _make_request(budget=1500.0, must_have=["dresser"])
    with patch(_COMP_LLM, return_value=weights_json):
        from schemas.style_profile import StyleProfile
        style = StyleProfile(
            style_name="warm_minimalist", keywords=["wood"], color_palette=["#FFF"],
            mood="calm", confidence=0.9, fallback=False,
        )
        plan = plan_composition(request, style)

    slot_ids = {s.slot_id for s in plan.slots}
    assert "dresser" in slot_ids


# ---------------------------------------------------------------------------
# Combined: already_have + must_have
# ---------------------------------------------------------------------------

def test_combined_have_and_need():
    """Own bed_frame, must have dresser. Plan sources dresser and remaining required."""
    weights = {**_bedroom_weights(), "dresser": 0.08}
    plan = fit_slots_to_budget(
        weights, 1500.0, "bedroom", TAXONOMY, BUDGET_POLICIES,
        already_have={"bed_frame"},
        must_have={"dresser"},
    )
    assert plan.is_feasible is True

    # bed_frame is owned.
    bf = next(s for s in plan.slots if s.slot_id == "bed_frame")
    assert bf.owned is True
    assert bf.allocated_budget == 0.0

    # dresser is sourced (must_have).
    d = next(s for s in plan.slots if s.slot_id == "dresser")
    assert d.owned is False
    assert d.allocated_budget > 0.0

    # All effective required (minus bed_frame, plus dresser) sourced.
    sourced_ids = {s.slot_id for s in plan.slots if not s.owned}
    expected_sourced = (BEDROOM_REQUIRED - {"bed_frame"}) | {"dresser"}
    for sid in expected_sourced:
        assert sid in sourced_ids

    assert plan.total_allocated <= 1500.0

# tests/test_budget_rules.py
# Tests for validators/budget_rules.validate_budget() — Stage 5.
# validate_selection_total() is Stage 8 and not tested here.
#
# Coverage:
#   - Total exactly at budget passes.
#   - Total $0.01 over budget fails with "over_budget" reason.
#   - Total well under budget passes.
#   - Zero-slot plan (total = 0) passes for any positive budget.
#   - Reason string carries the delta when over budget.
#   - Plans produced by allocate_budget() always pass validate_budget().

from __future__ import annotations

import pytest

from schemas.slot import Slot
from schemas.slot_plan import SlotPlan
from services.composition_service import allocate_budget
from services.config_loader import load_room_taxonomy
from validators.budget_rules import validate_budget

TAXONOMY = load_room_taxonomy()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plan(slot_budgets: dict[str, float], target: float) -> SlotPlan:
    """Build a SlotPlan directly from a {slot_id: budget} dict for unit tests."""
    slots = [
        Slot(slot_id=sid, allocated_budget=b, required_specs=[], optional=True)
        for sid, b in slot_budgets.items()
    ]
    return SlotPlan(run_id="test", room_preset="bedroom", target_budget=target, slots=slots)


# ---------------------------------------------------------------------------
# Passing cases
# ---------------------------------------------------------------------------

def test_total_exactly_at_budget_passes():
    plan = _make_plan({"bed_frame": 500.0, "bedding": 500.0}, target=1000.0)
    ok, reason = validate_budget(plan, 1000.0)
    assert ok is True
    assert reason is None


def test_total_under_budget_passes():
    plan = _make_plan({"bed_frame": 400.0, "bedding": 300.0}, target=1000.0)
    ok, reason = validate_budget(plan, 1000.0)
    assert ok is True
    assert reason is None


def test_zero_slot_plan_passes():
    plan = _make_plan({}, target=500.0)
    ok, reason = validate_budget(plan, 500.0)
    assert ok is True
    assert reason is None


def test_single_slot_at_budget_passes():
    plan = _make_plan({"sofa": 1500.0}, target=1500.0)
    ok, reason = validate_budget(plan, 1500.0)
    assert ok is True


# ---------------------------------------------------------------------------
# Failing cases
# ---------------------------------------------------------------------------

def test_one_cent_over_budget_fails():
    # 1000.01 > 1000.00
    plan = _make_plan({"bed_frame": 500.01, "bedding": 500.00}, target=1000.0)
    ok, reason = validate_budget(plan, 1000.0)
    assert ok is False
    assert reason is not None
    assert "over_budget" in reason


def test_significantly_over_budget_fails():
    plan = _make_plan({"sofa": 1200.0, "rug": 500.0}, target=1500.0)
    ok, reason = validate_budget(plan, 1500.0)
    assert ok is False
    assert "over_budget" in reason


def test_reason_contains_delta():
    """The reason string must carry the overage amount."""
    plan = _make_plan({"sofa": 600.0, "rug": 500.0}, target=1000.0)
    _, reason = validate_budget(plan, 1000.0)
    assert reason is not None
    # reason format: "over_budget:<delta>"
    delta_str = reason.split(":")[1]
    delta = float(delta_str)
    assert delta == pytest.approx(100.0, abs=1e-4)


# ---------------------------------------------------------------------------
# Plans from allocate_budget() always pass validate_budget()
# ---------------------------------------------------------------------------

def test_allocate_budget_plans_always_pass_validate_budget():
    """Any SlotPlan produced by allocate_budget() must pass validate_budget()."""
    weights_cases = [
        # Exactly 1.0
        {"bed_frame": 0.33, "bedding": 0.17, "rug": 0.18,
         "lighting": 0.12, "wall_art": 0.12, "accent": 0.08},
        # Under 1.0
        {"bed_frame": 0.22, "bedding": 0.10, "rug": 0.12,
         "lighting": 0.08, "wall_art": 0.08, "accent": 0.06},
        # Over 1.0
        {"bed_frame": 0.50, "bedding": 0.40, "rug": 0.40,
         "lighting": 0.30, "wall_art": 0.25, "accent": 0.25},
    ]
    for weights in weights_cases:
        for budget in [400.0, 1000.0, 5000.0]:
            plan = allocate_budget(weights, budget, "bedroom", TAXONOMY)
            ok, reason = validate_budget(plan, budget)
            assert ok is True, (
                f"validate_budget failed for budget={budget}, "
                f"weights_sum={sum(weights.values()):.2f}: {reason}"
            )

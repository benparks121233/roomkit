# tests/test_composition_rules.py
# Tests for validators/composition_rules — validate_required_slots,
# validate_no_duplicate_slots, and validate_feasibility.
#
# All tests are pure: no LLM, no DB, no external I/O.

from __future__ import annotations

import pytest

from schemas.slot import Slot
from schemas.slot_plan import SlotPlan
from validators.composition_rules import (
    validate_feasibility,
    validate_no_duplicate_slots,
    validate_required_slots,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_slot(slot_id: str, budget: float = 100.0, optional: bool = False) -> Slot:
    return Slot(slot_id=slot_id, allocated_budget=budget, required_specs=[], optional=optional)


def _make_plan(
    slots: list[Slot],
    is_feasible: bool = True,
    minimum_viable_budget: float | None = None,
) -> SlotPlan:
    return SlotPlan(
        run_id="test",
        room_preset="bedroom",
        target_budget=1000.0,
        slots=slots,
        is_feasible=is_feasible,
        minimum_viable_budget=minimum_viable_budget,
    )


# ---------------------------------------------------------------------------
# validate_required_slots
# ---------------------------------------------------------------------------

def test_required_slots_all_present_passes():
    plan = _make_plan([_make_slot("bed_frame"), _make_slot("bedding")])
    ok, reason = validate_required_slots(plan, ["bed_frame", "bedding"])
    assert ok is True
    assert reason is None


def test_required_slots_missing_one_fails():
    plan = _make_plan([_make_slot("bed_frame")])
    ok, reason = validate_required_slots(plan, ["bed_frame", "bedding"])
    assert ok is False
    assert reason == "missing_slots:bedding"


def test_required_slots_all_missing_fails():
    plan = _make_plan([])
    ok, reason = validate_required_slots(plan, ["bed_frame", "bedding"])
    assert ok is False
    assert "bed_frame" in reason
    assert "bedding" in reason


def test_required_slots_extra_slots_ignored():
    """Extra slots in the plan beyond required do not cause failure."""
    plan = _make_plan([_make_slot("bed_frame"), _make_slot("tv")])
    ok, reason = validate_required_slots(plan, ["bed_frame"])
    assert ok is True


def test_required_slots_empty_required_list_passes():
    plan = _make_plan([_make_slot("bed_frame")])
    ok, reason = validate_required_slots(plan, [])
    assert ok is True


# ---------------------------------------------------------------------------
# validate_no_duplicate_slots
# ---------------------------------------------------------------------------

def test_no_duplicates_passes():
    plan = _make_plan([_make_slot("bed_frame"), _make_slot("bedding")])
    ok, reason = validate_no_duplicate_slots(plan)
    assert ok is True
    assert reason is None


def test_single_duplicate_fails():
    plan = _make_plan([_make_slot("bed_frame"), _make_slot("bed_frame")])
    ok, reason = validate_no_duplicate_slots(plan)
    assert ok is False
    assert "duplicate_slots" in reason
    assert "bed_frame" in reason


def test_multiple_duplicates_reported():
    plan = _make_plan([
        _make_slot("bed_frame"), _make_slot("bed_frame"),
        _make_slot("rug"), _make_slot("rug"),
    ])
    ok, reason = validate_no_duplicate_slots(plan)
    assert ok is False
    assert "bed_frame" in reason
    assert "rug" in reason


def test_empty_plan_no_duplicates_passes():
    plan = _make_plan([])
    ok, reason = validate_no_duplicate_slots(plan)
    assert ok is True


# ---------------------------------------------------------------------------
# validate_feasibility
# ---------------------------------------------------------------------------

def test_feasible_plan_passes():
    plan = _make_plan([_make_slot("bed_frame", 300.0), _make_slot("bedding", 200.0)])
    ok, reason = validate_feasibility(plan)
    assert ok is True
    assert reason is None


def test_infeasible_plan_fails():
    plan = _make_plan(
        [_make_slot("bed_frame", 0.0), _make_slot("bedding", 0.0)],
        is_feasible=False,
        minimum_viable_budget=500.0,
    )
    ok, reason = validate_feasibility(plan)
    assert ok is False
    assert reason is not None


def test_infeasible_reason_contains_sentinel():
    plan = _make_plan([], is_feasible=False, minimum_viable_budget=500.0)
    ok, reason = validate_feasibility(plan)
    assert ok is False
    assert "plan_infeasible" in reason


def test_infeasible_reason_carries_mvb():
    plan = _make_plan([], is_feasible=False, minimum_viable_budget=500.0)
    _, reason = validate_feasibility(plan)
    assert reason is not None
    # Format: "plan_infeasible:<mvb>"
    mvb_str = reason.split(":")[1]
    assert float(mvb_str) == pytest.approx(500.0, abs=1e-2)


def test_infeasible_without_mvb_carries_unknown():
    """An infeasible plan with no minimum_viable_budget still signals clearly."""
    plan = _make_plan([], is_feasible=False, minimum_viable_budget=None)
    _, reason = validate_feasibility(plan)
    assert reason is not None
    assert "unknown" in reason


def test_feasible_plan_with_zero_slots_passes():
    """Edge case: a zero-slot feasible plan is not infeasible."""
    plan = _make_plan([], is_feasible=True)
    ok, reason = validate_feasibility(plan)
    assert ok is True

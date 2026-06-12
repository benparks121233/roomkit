# tests/test_budget_rules.py
# Tests for validators/budget_rules — budget validation gates.
#
# Coverage:
#   - validate_budget: total exactly at budget, one-cent-over, under, zero-slot.
#   - Plans produced by allocate_budget() always pass validate_budget().
#   - max_quantity threading: taxonomy values flow through to Slot objects.

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
    # Use real item IDs from v2 taxonomy.
    preset = TAXONOMY.room_presets["bedroom"]
    default_w = preset.flatten_weights()
    required_ids = preset.required_items()

    weights_cases = [
        # All items at default weights (sum = 1.0)
        dict(default_w),
        # Required-only (sum < 1.0)
        {sid: default_w[sid] for sid in required_ids},
        # Over 1.0
        {sid: w * 3 for sid, w in default_w.items()},
    ]
    for weights in weights_cases:
        for budget in [400.0, 1000.0, 5000.0]:
            plan = allocate_budget(weights, budget, "bedroom", TAXONOMY)
            ok, reason = validate_budget(plan, budget)
            assert ok is True, (
                f"validate_budget failed for budget={budget}, "
                f"weights_sum={sum(weights.values()):.2f}: {reason}"
            )


# ---------------------------------------------------------------------------
# max_quantity threading: taxonomy → Slot
# ---------------------------------------------------------------------------

def test_allocate_budget_carries_max_quantity():
    """Slots built by allocate_budget() carry max_quantity from taxonomy."""
    preset = TAXONOMY.room_presets["bedroom"]
    default_w = preset.flatten_weights()
    plan = allocate_budget(default_w, 1500.0, "bedroom", TAXONOMY)

    slot_map = {s.slot_id: s for s in plan.slots}

    # Multi-select decor slots.
    assert slot_map["wall_art"].max_quantity == 6
    assert slot_map["plants"].max_quantity == 3
    assert slot_map["throw_blanket"].max_quantity == 1

    # Single-select slots default to 1.
    assert slot_map["bed_frame"].max_quantity == 1
    assert slot_map["rug"].max_quantity == 1
    assert slot_map["ceiling_light"].max_quantity == 1


def test_taxonomy_max_quantity_defaults_to_one():
    """Items without explicit max_quantity in YAML default to 1."""
    for item_id, item_def in TAXONOMY.items.items():
        if item_id in ("wall_art", "plants"):
            assert item_def.max_quantity > 1, f"{item_id} should be multi-select"
        else:
            assert item_def.max_quantity == 1, f"{item_id} should default to 1"

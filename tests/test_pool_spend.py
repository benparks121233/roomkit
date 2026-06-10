# tests/test_pool_spend.py
# Tests for validators.budget_rules.validate_pool_spend() — multi-select
# pool budget enforcement.
#
# Coverage:
#   - Single item within pool → valid
#   - Multiple items summing to exactly pool → valid
#   - Multiple items summing over pool → invalid, "over_pool"
#   - Exceeding max_quantity → invalid, "exceeds_max_quantity"
#   - Unknown slot_id → invalid, "unknown_slot"
#   - Single-select slot (max_quantity=1) with 2 items → invalid
#   - Empty selections → valid (vacuously)
#   - Mix of valid + invalid → per-slot results correct
#   - total_spent is sum of all slot totals

from __future__ import annotations

from schemas.slot import Slot
from schemas.slot_plan import SlotPlan
from validators.budget_rules import validate_pool_spend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plan(
    slots: list[tuple[str, float, int]],  # (slot_id, budget, max_quantity)
    target_budget: float = 1500.0,
) -> SlotPlan:
    return SlotPlan(
        run_id="test",
        room_preset="bedroom",
        target_budget=target_budget,
        slots=[
            Slot(
                slot_id=sid,
                allocated_budget=budget,
                required_specs=[],
                optional=False,
                max_quantity=mq,
            )
            for sid, budget, mq in slots
        ],
    )


# ---------------------------------------------------------------------------
# Basic valid cases
# ---------------------------------------------------------------------------

def test_single_item_within_pool():
    plan = _make_plan([("wall_art", 60.0, 6)])
    ok, total, results = validate_pool_spend({"wall_art": [10.0]}, plan)
    assert ok is True
    assert total == 10.0
    assert results[0] == ("wall_art", True, 10.0, None)


def test_multiple_items_sum_exactly_at_pool():
    plan = _make_plan([("wall_art", 60.0, 6)])
    prices = [10.0, 15.0, 20.0, 15.0]  # sum = 60.0
    ok, total, results = validate_pool_spend({"wall_art": prices}, plan)
    assert ok is True
    assert total == 60.0


def test_multiple_items_under_pool():
    plan = _make_plan([("plants", 45.0, 3)])
    prices = [12.0, 8.0, 10.0]  # sum = 30.0
    ok, total, results = validate_pool_spend({"plants": prices}, plan)
    assert ok is True
    assert total == 30.0


def test_empty_selections():
    plan = _make_plan([("wall_art", 60.0, 6)])
    ok, total, results = validate_pool_spend({}, plan)
    assert ok is True
    assert total == 0.0
    assert results == []


# ---------------------------------------------------------------------------
# Over-pool
# ---------------------------------------------------------------------------

def test_sum_over_pool_is_invalid():
    plan = _make_plan([("wall_art", 60.0, 6)])
    prices = [20.0, 25.0, 20.0]  # sum = 65.0 > 60.0
    ok, total, results = validate_pool_spend({"wall_art": prices}, plan)
    assert ok is False
    assert results[0][1] is False  # ok
    assert results[0][3] is not None
    assert results[0][3].startswith("over_pool:")


# ---------------------------------------------------------------------------
# Exceeds max_quantity
# ---------------------------------------------------------------------------

def test_exceeds_max_quantity():
    plan = _make_plan([("throw_blanket", 86.0, 2)])
    prices = [20.0, 25.0, 15.0]  # 3 items, max is 2
    ok, total, results = validate_pool_spend({"throw_blanket": prices}, plan)
    assert ok is False
    assert "exceeds_max_quantity:2" in results[0][3]


def test_single_select_slot_rejects_two_items():
    """A slot with max_quantity=1 must reject 2 selections."""
    plan = _make_plan([("bed_frame", 270.0, 1)])
    prices = [100.0, 120.0]  # 2 items, max is 1
    ok, total, results = validate_pool_spend({"bed_frame": prices}, plan)
    assert ok is False
    assert "exceeds_max_quantity:1" in results[0][3]


# ---------------------------------------------------------------------------
# Unknown slot
# ---------------------------------------------------------------------------

def test_unknown_slot():
    plan = _make_plan([("wall_art", 60.0, 6)])
    ok, total, results = validate_pool_spend({"fake_slot": [10.0]}, plan)
    assert ok is False
    assert results[0] == ("fake_slot", False, 0.0, "unknown_slot")


# ---------------------------------------------------------------------------
# Mixed valid + invalid
# ---------------------------------------------------------------------------

def test_mixed_valid_and_invalid():
    plan = _make_plan([
        ("wall_art", 60.0, 6),
        ("plants", 45.0, 3),
        ("bed_frame", 270.0, 1),
    ])
    selections = {
        "wall_art": [10.0, 12.0],        # valid: 22 <= 60, 2 <= 6
        "plants": [20.0, 15.0, 12.0],    # invalid: 47 > 45
        "bed_frame": [200.0],             # valid: 200 <= 270, 1 <= 1
    }
    ok, total, results = validate_pool_spend(selections, plan)
    assert ok is False  # plants failed

    result_map = {r[0]: r for r in results}
    assert result_map["wall_art"][1] is True
    assert result_map["plants"][1] is False
    assert result_map["plants"][3].startswith("over_pool:")
    assert result_map["bed_frame"][1] is True


def test_total_spent_sums_all_slots():
    plan = _make_plan([
        ("wall_art", 60.0, 6),
        ("plants", 45.0, 3),
    ])
    selections = {
        "wall_art": [10.0, 15.0],  # 25
        "plants": [8.0, 12.0],     # 20
    }
    ok, total, results = validate_pool_spend(selections, plan)
    assert ok is True
    assert total == 45.0


# ---------------------------------------------------------------------------
# Quantity exactly at max is valid
# ---------------------------------------------------------------------------

def test_exactly_max_quantity_is_valid():
    plan = _make_plan([("plants", 45.0, 3)])
    prices = [10.0, 10.0, 10.0]  # exactly 3
    ok, total, results = validate_pool_spend({"plants": prices}, plan)
    assert ok is True

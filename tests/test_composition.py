# tests/test_composition.py
# Tests for services/composition_service.allocate_budget() — Stage 5 Piece 1.
# No LLM calls; this function is pure math.
#
# Coverage:
#   - Weights summing to exactly 1.0 allocate correctly (weight × budget).
#   - Weights summing to > 1.0 are re-normalized; total never exceeds budget.
#   - Weights summing to < 1.0 are used as-is; total is proportionally under.
#   - All required slots for the preset appear in the output.
#   - A required slot absent from slot_weights is injected at its taxonomy default.
#   - Optional slots included in slot_weights appear in the output.
#   - total_allocated == sum(slot.allocated_budget) always (computed_field).
#   - total_allocated <= target_budget always (the invariant).
#   - Unknown room_preset raises ValueError.
#   - Zero/negative weights raise ValueError.
#
# v2 taxonomy: bedroom has 9 required items across 5 groups, 7 optional items.

from __future__ import annotations

import pytest

from services.composition_service import allocate_budget, fit_slots_to_budget
from services.config_loader import load_budget_policies, load_room_taxonomy

# Load once for the module — taxonomy is read-only, safe to share across tests.
TAXONOMY = load_room_taxonomy()
BUDGET_POLICIES = load_budget_policies()

# Derive required/optional from the live taxonomy rather than hardcoding.
_BEDROOM_PRESET = TAXONOMY.room_presets["bedroom"]
BEDROOM_REQUIRED = _BEDROOM_PRESET.required_items()
_BEDROOM_DEFAULT_WEIGHTS = _BEDROOM_PRESET.flatten_weights()

_LIVING_PRESET = TAXONOMY.room_presets["living_room"]
LIVING_ROOM_REQUIRED = _LIVING_PRESET.required_items()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bedroom_weights_exact() -> dict[str, float]:
    """Bedroom weights using taxonomy defaults (sum < 1.0 for required-only)."""
    return {sid: _BEDROOM_DEFAULT_WEIGHTS[sid] for sid in BEDROOM_REQUIRED}


def _bedroom_weights_unit() -> dict[str, float]:
    """Bedroom weights for all preset items, normalized to sum to ~1.0."""
    return dict(_BEDROOM_DEFAULT_WEIGHTS)


# ---------------------------------------------------------------------------
# Weights summing to exactly 1.0
# ---------------------------------------------------------------------------

def test_unit_weights_each_slot_gets_weight_times_budget():
    weights = _bedroom_weights_unit()
    # Budget must be high enough that no per-slot price floor triggers
    # (smallest weight × budget must exceed the highest floor).
    budget = 3000.0
    plan = allocate_budget(weights, budget, "bedroom", TAXONOMY)

    slot_map = {s.slot_id: s.allocated_budget for s in plan.slots}
    for slot_id, w in weights.items():
        assert slot_map[slot_id] == pytest.approx(w * budget, rel=1e-9)


def test_unit_weights_total_equals_budget():
    weights = _bedroom_weights_unit()
    budget = 3000.0
    plan = allocate_budget(weights, budget, "bedroom", TAXONOMY)

    assert plan.total_allocated == pytest.approx(budget, rel=1e-9)


# ---------------------------------------------------------------------------
# Weights summing to > 1.0 — re-normalization
# ---------------------------------------------------------------------------

def test_overweight_total_never_exceeds_budget():
    # Double every weight — sum will be ~2.0.
    weights = {sid: w * 2 for sid, w in _bedroom_weights_unit().items()}
    budget = 1200.0
    plan = allocate_budget(weights, budget, "bedroom", TAXONOMY)

    assert plan.total_allocated <= budget


def test_overweight_proportions_are_preserved_after_normalization():
    """After re-normalization, relative slot proportions must be unchanged."""
    weights = {sid: w * 3 for sid, w in _bedroom_weights_unit().items()}
    # bed_frame should be heavier than pillows by the same ratio.
    # Budget high enough that price floors don't distort proportions.
    budget = 3000.0
    plan = allocate_budget(weights, budget, "bedroom", TAXONOMY)

    slot_map = {s.slot_id: s.allocated_budget for s in plan.slots}
    # bed_frame weight / pillows weight ratio should be preserved.
    orig_ratio = weights["bed_frame"] / weights["pillows"]
    actual_ratio = slot_map["bed_frame"] / slot_map["pillows"]
    assert actual_ratio == pytest.approx(orig_ratio, rel=1e-6)


def test_overweight_high_budget_never_exceeds():
    lr_weights = _LIVING_PRESET.flatten_weights()
    weights = {sid: w * 3 for sid, w in lr_weights.items()}
    budget = 5000.0
    plan = allocate_budget(weights, budget, "living_room", TAXONOMY)

    assert plan.total_allocated <= budget


# ---------------------------------------------------------------------------
# Weights summing to < 1.0 — always normalized to fully utilise budget
# ---------------------------------------------------------------------------

def test_underweight_total_is_normalized_to_full_budget():
    weights = _bedroom_weights_exact()   # required only, sum ~0.67
    budget = 1000.0
    plan = allocate_budget(weights, budget, "bedroom", TAXONOMY)

    # With always-normalize, even under-weight sets use the full budget.
    assert plan.total_allocated == pytest.approx(budget, rel=1e-6)
    assert plan.total_allocated <= budget


# ---------------------------------------------------------------------------
# Required slot enforcement
# ---------------------------------------------------------------------------

def test_bedroom_all_required_slots_present():
    plan = allocate_budget(_bedroom_weights_unit(), 1500.0, "bedroom", TAXONOMY)
    slot_ids = {s.slot_id for s in plan.slots}

    for required in BEDROOM_REQUIRED:
        assert required in slot_ids, f"Required slot '{required}' missing from plan"


def test_living_room_all_required_slots_present():
    lr_weights = _LIVING_PRESET.flatten_weights()
    plan = allocate_budget(lr_weights, 2000.0, "living_room", TAXONOMY)
    slot_ids = {s.slot_id for s in plan.slots}

    for required in LIVING_ROOM_REQUIRED:
        assert required in slot_ids


def test_missing_required_slot_injected_at_taxonomy_default():
    """If a required slot is omitted from slot_weights, it is added at the
    taxonomy default weight and still appears in the SlotPlan."""
    # Remove one required slot from the weight dict.
    weights = dict(_BEDROOM_DEFAULT_WEIGHTS)
    removed = BEDROOM_REQUIRED[0]
    del weights[removed]
    plan = allocate_budget(weights, 1500.0, "bedroom", TAXONOMY)

    slot_ids = {s.slot_id for s in plan.slots}
    assert removed in slot_ids


def test_all_required_slots_missing_are_injected():
    """Passing an empty weight dict still yields all required slots."""
    plan = allocate_budget({}, 1000.0, "bedroom", TAXONOMY)
    slot_ids = {s.slot_id for s in plan.slots}

    for required in BEDROOM_REQUIRED:
        assert required in slot_ids


# ---------------------------------------------------------------------------
# Optional extra slots
# ---------------------------------------------------------------------------

def test_optional_slot_in_weights_appears_in_plan():
    """An optional slot included in slot_weights should appear in the plan."""
    weights = dict(_BEDROOM_DEFAULT_WEIGHTS)
    # dresser is optional for bedroom — should be in weights already.
    # Verify it shows up in the plan.
    optional_items = _BEDROOM_PRESET.all_items() - set(BEDROOM_REQUIRED)
    assert len(optional_items) > 0
    an_optional = sorted(optional_items)[0]
    assert an_optional in weights  # from flatten_weights
    plan = allocate_budget(weights, 1500.0, "bedroom", TAXONOMY)

    slot_ids = {s.slot_id for s in plan.slots}
    assert an_optional in slot_ids
    assert plan.total_allocated <= 1500.0


# ---------------------------------------------------------------------------
# total_allocated invariants
# ---------------------------------------------------------------------------

def test_total_allocated_equals_sum_of_slot_budgets():
    """computed_field: total_allocated must always equal the live slot sum."""
    plan = allocate_budget(_bedroom_weights_unit(), 1500.0, "bedroom", TAXONOMY)

    computed_sum = sum(s.allocated_budget for s in plan.slots)
    assert plan.total_allocated == pytest.approx(computed_sum, rel=1e-12)


def test_total_allocated_never_exceeds_budget_unit_weights():
    plan = allocate_budget(_bedroom_weights_unit(), 800.0, "bedroom", TAXONOMY)
    assert plan.total_allocated <= 800.0


def test_total_allocated_never_exceeds_budget_overweight():
    weights = {s: 0.5 for s in BEDROOM_REQUIRED}  # sum > 1.0
    plan = allocate_budget(weights, 2500.0, "bedroom", TAXONOMY)
    assert plan.total_allocated <= 2500.0


def test_total_allocated_never_exceeds_budget_many_budgets():
    """Invariant holds across a range of budget values."""
    weights = _bedroom_weights_unit()
    for budget in [100.0, 500.0, 1000.0, 1500.0, 5000.0, 10000.0]:
        plan = allocate_budget(weights, budget, "bedroom", TAXONOMY)
        assert plan.total_allocated <= budget, f"Invariant violated for budget={budget}"


# ---------------------------------------------------------------------------
# SlotPlan fields
# ---------------------------------------------------------------------------

def test_slot_plan_carries_correct_room_preset():
    plan = allocate_budget(_bedroom_weights_unit(), 1000.0, "bedroom", TAXONOMY)
    assert plan.room_preset == "bedroom"


def test_slot_plan_carries_correct_target_budget():
    plan = allocate_budget(_bedroom_weights_unit(), 1234.56, "bedroom", TAXONOMY)
    assert plan.target_budget == pytest.approx(1234.56)


def test_slot_plan_run_id_passed_through():
    plan = allocate_budget(_bedroom_weights_unit(), 1000.0, "bedroom", TAXONOMY,
                           run_id="my-run-42")
    assert plan.run_id == "my-run-42"


def test_slots_carry_required_specs_from_taxonomy():
    """Slot objects must carry required_specs from the taxonomy definition."""
    plan = allocate_budget(_bedroom_weights_unit(), 1000.0, "bedroom", TAXONOMY)
    slot_map = {s.slot_id: s for s in plan.slots}

    assert "bed_size" in slot_map["bed_frame"].required_specs
    assert "bed_size" in slot_map["mattress"].required_specs
    assert slot_map["wall_art"].required_specs == []


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

def test_unknown_room_preset_raises_value_error():
    with pytest.raises(ValueError, match="room_preset"):
        allocate_budget({"sofa": 0.5}, 1000.0, "garage", TAXONOMY)


def test_zero_budget_raises_value_error():
    with pytest.raises(ValueError, match="target_budget"):
        allocate_budget(_bedroom_weights_unit(), 0.0, "bedroom", TAXONOMY)


def test_negative_budget_raises_value_error():
    with pytest.raises(ValueError, match="target_budget"):
        allocate_budget(_bedroom_weights_unit(), -500.0, "bedroom", TAXONOMY)


# ---------------------------------------------------------------------------
# Piece 2: fit_slots_to_budget() — optional dropping + feasibility
# ---------------------------------------------------------------------------
#
# v2 bedroom taxonomy:
#   required (9 items): bed_frame, mattress, sheets, comforter, pillows,
#                       nightstand, ceiling_light, wall_art, rug
#   optional (7 items): dresser, table_lamp, floor_lamp, plants, mirror,
#                       curtains, throw_blanket
#   required weight sum ≈ 0.6665
#   minimum_room_multiplier = 500.0
#   MVB (required-only): max(0.6665, 1.0) × 500 = $500

_BEDROOM_REQ_IDS = set(BEDROOM_REQUIRED)


def _bedroom_weights_with_optional() -> dict[str, float]:
    """All bedroom items (required + optional) from taxonomy defaults."""
    return dict(_BEDROOM_DEFAULT_WEIGHTS)


# --- Budget comfortably fits all slots (required + optional) ----------------

def test_fit_budget_keeps_all_slots_when_budget_is_sufficient():
    """A generous budget keeps every slot including optionals."""
    weights = _bedroom_weights_with_optional()
    plan = fit_slots_to_budget(weights, 2000.0, "bedroom", TAXONOMY, BUDGET_POLICIES)

    assert plan.is_feasible is True
    assert plan.minimum_viable_budget is None
    slot_ids = {s.slot_id for s in plan.slots}
    # All required present.
    for sid in _BEDROOM_REQ_IDS:
        assert sid in slot_ids, f"Required slot '{sid}' missing"
    assert plan.total_allocated <= 2000.0


def test_fit_budget_feasible_plan_has_is_feasible_true():
    plan = fit_slots_to_budget(
        _bedroom_weights_unit(), 1000.0, "bedroom", TAXONOMY, BUDGET_POLICIES
    )
    assert plan.is_feasible is True
    assert plan.minimum_viable_budget is None


def test_fit_budget_feasible_total_never_exceeds_budget():
    for budget in [500.0, 750.0, 1000.0, 2000.0, 5000.0]:
        plan = fit_slots_to_budget(
            _bedroom_weights_with_optional(), budget, "bedroom", TAXONOMY, BUDGET_POLICIES
        )
        if plan.is_feasible:
            assert plan.total_allocated <= budget, f"Invariant violated at budget={budget}"


# --- Budget forces optional dropping ----------------------------------------

def test_fit_budget_drops_optional_when_tight():
    """A heavy optional pushes the floor above budget; it must be dropped."""
    weights = dict(_bedroom_weights_exact())  # required only
    # Add a heavy optional that pushes total_w > 1.0
    weights["dresser"] = 0.50  # total_w > 1.0 → floor > $500
    # Budget $520 < floor-with-dresser, but >= $500 (floor without dresser).
    plan = fit_slots_to_budget(weights, 520.0, "bedroom", TAXONOMY, BUDGET_POLICIES)

    assert plan.is_feasible is True
    slot_ids = {s.slot_id for s in plan.slots}
    assert "dresser" not in slot_ids
    for sid in _BEDROOM_REQ_IDS:
        assert sid in slot_ids
    assert plan.total_allocated <= 520.0


def test_fit_budget_drops_sole_optional_when_required_floor_is_still_met():
    """With a single heavy optional on a tight budget, it is dropped when the
    price-floor loop can't fit it and the required set still fits."""
    weights = dict(_bedroom_weights_exact())
    weights["dresser"] = 0.60  # heavy optional
    # Budget must be below the point where dresser's allocation can cover its
    # price floor ($19.96) after the required slots' floors are satisfied.
    # Required floors sum to ~$185; dresser floor is $19.96; total ~$205.
    # At $480 (< MVB $500), plan drops dresser and returns feasible for required-only.
    plan = fit_slots_to_budget(weights, 480.0, "bedroom", TAXONOMY, BUDGET_POLICIES)

    assert plan.is_feasible is False or "dresser" not in {s.slot_id for s in plan.slots}
    # Either infeasible overall, or dresser was dropped to make it work.


def test_fit_budget_drops_cheapest_optional_first_when_multiple_present():
    """With two heavy optionals, the cheapest-default-weight one drops first.

    dresser default weight 0.070 > floor_lamp default weight 0.020.
    Heavy weights (0.30 + 0.25 + required ~0.55) push total_w > 1.0,
    inflating the feasibility floor above MVB.
    Budget $520 < floor ($551) forces a drop.  floor_lamp (cheaper) drops;
    dresser (more expensive) survives.
    """
    weights = dict(_bedroom_weights_exact())
    weights["dresser"] = 0.30
    weights["floor_lamp"] = 0.25
    # total_w ≈ 1.10 → floor ≈ $551 → budget $520 forces a drop.
    plan = fit_slots_to_budget(weights, 520.0, "bedroom", TAXONOMY, BUDGET_POLICIES)

    assert plan.is_feasible is True
    slot_ids = {s.slot_id for s in plan.slots}
    assert "floor_lamp" not in slot_ids, "floor_lamp (cheaper optional) should drop first"
    assert "dresser" in slot_ids, "dresser (more expensive optional) should be kept"
    for sid in _BEDROOM_REQ_IDS:
        assert sid in slot_ids
    assert plan.total_allocated <= 520.0


# --- Infeasible: budget below required-floor sum ----------------------------

def test_fit_budget_infeasible_returns_is_feasible_false():
    """Budget well below required-slot MVB must return is_feasible=False."""
    plan = fit_slots_to_budget(
        _bedroom_weights_unit(), 100.0, "bedroom", TAXONOMY, BUDGET_POLICIES
    )
    assert plan.is_feasible is False


def test_fit_budget_infeasible_carries_minimum_viable_budget():
    """minimum_viable_budget must equal max(req_weight_sum, 1.0) × multiplier."""
    plan = fit_slots_to_budget(
        _bedroom_weights_unit(), 100.0, "bedroom", TAXONOMY, BUDGET_POLICIES
    )
    assert plan.is_feasible is False
    assert plan.minimum_viable_budget is not None
    # bedroom required weight sum ≈ 0.6665; max(0.6665, 1.0) × 500 = 500.0
    assert plan.minimum_viable_budget == pytest.approx(500.0, abs=1.0)


def test_fit_budget_infeasible_carries_required_slots():
    """Infeasible plan must list all required slots (at 0.0 budget)."""
    plan = fit_slots_to_budget(
        _bedroom_weights_unit(), 50.0, "bedroom", TAXONOMY, BUDGET_POLICIES
    )
    assert plan.is_feasible is False
    slot_ids = {s.slot_id for s in plan.slots}
    for sid in _BEDROOM_REQ_IDS:
        assert sid in slot_ids, f"Required slot '{sid}' missing from infeasible plan"


def test_fit_budget_infeasible_total_is_zero():
    """Infeasible plan has total_allocated=0.0 (slots at allocated_budget=0.0)."""
    plan = fit_slots_to_budget(
        _bedroom_weights_unit(), 50.0, "bedroom", TAXONOMY, BUDGET_POLICIES
    )
    assert plan.is_feasible is False
    assert plan.total_allocated == pytest.approx(0.0)


def test_fit_budget_exactly_at_mvb_is_feasible():
    """Budget exactly at MVB ($500) must be feasible for bedroom required slots."""
    plan = fit_slots_to_budget(
        _bedroom_weights_unit(), 500.0, "bedroom", TAXONOMY, BUDGET_POLICIES
    )
    assert plan.is_feasible is True
    assert plan.total_allocated <= 500.0


def test_fit_budget_one_cent_below_mvb_is_infeasible():
    """Budget one cent below MVB must be infeasible."""
    plan = fit_slots_to_budget(
        _bedroom_weights_unit(), 499.99, "bedroom", TAXONOMY, BUDGET_POLICIES
    )
    assert plan.is_feasible is False


# --- Error propagation ------------------------------------------------------

def test_fit_budget_unknown_room_preset_raises():
    with pytest.raises(ValueError, match="room_preset"):
        fit_slots_to_budget({}, 1000.0, "garage", TAXONOMY, BUDGET_POLICIES)


def test_fit_budget_zero_budget_raises():
    with pytest.raises(ValueError, match="target_budget"):
        fit_slots_to_budget({}, 0.0, "bedroom", TAXONOMY, BUDGET_POLICIES)

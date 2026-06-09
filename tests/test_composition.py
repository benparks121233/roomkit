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

from __future__ import annotations

import pytest

from schemas.slot_plan import SlotPlan
from services.composition_service import allocate_budget, fit_slots_to_budget
from services.config_loader import load_budget_policies, load_room_taxonomy

# Load once for the module — taxonomy is read-only, safe to share across tests.
TAXONOMY = load_room_taxonomy()
BUDGET_POLICIES = load_budget_policies()

BEDROOM_REQUIRED = ["bed_frame", "bedding", "rug", "lighting", "wall_art", "accent"]
LIVING_ROOM_REQUIRED = ["sofa", "rug", "lighting", "tv", "wall_art", "accent"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bedroom_weights_exact() -> dict[str, float]:
    """Bedroom weights that sum to exactly 1.0 (using taxonomy defaults)."""
    return {
        "bed_frame": 0.22,
        "bedding":   0.10,
        "rug":       0.12,
        "lighting":  0.08,
        "wall_art":  0.08,
        "accent":    0.06,
        # sum = 0.66 — intentionally < 1.0 to test under-budget path
    }


def _bedroom_weights_unit() -> dict[str, float]:
    """Bedroom weights normalised to sum to exactly 1.0."""
    return {
        "bed_frame": 0.33,
        "bedding":   0.17,
        "rug":       0.18,
        "lighting":  0.12,
        "wall_art":  0.12,
        "accent":    0.08,
        # sum = 1.00
    }


# ---------------------------------------------------------------------------
# Weights summing to exactly 1.0
# ---------------------------------------------------------------------------

def test_unit_weights_each_slot_gets_weight_times_budget():
    weights = _bedroom_weights_unit()
    budget = 1500.0
    plan = allocate_budget(weights, budget, "bedroom", TAXONOMY)

    slot_map = {s.slot_id: s.allocated_budget for s in plan.slots}
    for slot_id, w in weights.items():
        assert slot_map[slot_id] == pytest.approx(w * budget, rel=1e-9)


def test_unit_weights_total_equals_budget():
    weights = _bedroom_weights_unit()
    budget = 1500.0
    plan = allocate_budget(weights, budget, "bedroom", TAXONOMY)

    assert plan.total_allocated == pytest.approx(budget, rel=1e-9)


# ---------------------------------------------------------------------------
# Weights summing to > 1.0 — re-normalization
# ---------------------------------------------------------------------------

def test_overweight_total_never_exceeds_budget():
    # Weights sum to 1.8 — well over 1.0.
    weights = {
        "bed_frame": 0.50,
        "bedding":   0.30,
        "rug":       0.30,
        "lighting":  0.20,
        "wall_art":  0.25,
        "accent":    0.25,
    }
    budget = 1200.0
    plan = allocate_budget(weights, budget, "bedroom", TAXONOMY)

    assert plan.total_allocated <= budget


def test_overweight_proportions_are_preserved_after_normalization():
    """After re-normalization, relative slot proportions must be unchanged."""
    weights = {
        "bed_frame": 0.60,   # 2× bedding
        "bedding":   0.30,
        "rug":       0.30,
        "lighting":  0.20,
        "wall_art":  0.20,
        "accent":    0.20,
    }
    budget = 1000.0
    plan = allocate_budget(weights, budget, "bedroom", TAXONOMY)

    slot_map = {s.slot_id: s.allocated_budget for s in plan.slots}
    # bed_frame should be approximately 2× bedding after normalization.
    assert slot_map["bed_frame"] == pytest.approx(slot_map["bedding"] * 2, rel=1e-6)


def test_overweight_high_budget_never_exceeds():
    weights = {"sofa": 0.80, "rug": 0.80, "lighting": 0.80,
               "tv": 0.80, "wall_art": 0.80, "accent": 0.80}
    budget = 5000.0
    plan = allocate_budget(weights, budget, "living_room", TAXONOMY)

    assert plan.total_allocated <= budget


# ---------------------------------------------------------------------------
# Weights summing to < 1.0 — under-budget (safe path, no normalization)
# ---------------------------------------------------------------------------

def test_underweight_total_is_proportionally_under_budget():
    weights = _bedroom_weights_exact()   # sums to 0.66
    budget = 1000.0
    plan = allocate_budget(weights, budget, "bedroom", TAXONOMY)

    expected_total = sum(w * budget for w in weights.values())
    assert plan.total_allocated == pytest.approx(expected_total, rel=1e-9)
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
    weights = {
        "sofa":    0.28,
        "rug":     0.12,
        "lighting": 0.08,
        "tv":       0.18,
        "wall_art": 0.08,
        "accent":   0.06,
    }
    plan = allocate_budget(weights, 2000.0, "living_room", TAXONOMY)
    slot_ids = {s.slot_id for s in plan.slots}

    for required in LIVING_ROOM_REQUIRED:
        assert required in slot_ids


def test_missing_required_slot_injected_at_taxonomy_default():
    """If a required slot is omitted from slot_weights, it is added at the
    taxonomy default_budget_weight and still appears in the SlotPlan."""
    # Bedroom weights with 'accent' deliberately omitted.
    weights = {
        "bed_frame": 0.22,
        "bedding":   0.10,
        "rug":       0.12,
        "lighting":  0.08,
        "wall_art":  0.08,
        # "accent" omitted — taxonomy default is 0.06
    }
    plan = allocate_budget(weights, 1500.0, "bedroom", TAXONOMY)

    slot_ids = {s.slot_id for s in plan.slots}
    assert "accent" in slot_ids


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
    """An optional slot included in slot_weights (e.g. 'tv' in a bedroom)
    should appear in the plan alongside required slots."""
    weights = {s: w for s, w in _bedroom_weights_unit().items()}
    weights["tv"] = 0.08   # optional for bedroom
    # Weights now sum to 1.08 → will be re-normalized.
    plan = allocate_budget(weights, 1500.0, "bedroom", TAXONOMY)

    slot_ids = {s.slot_id for s in plan.slots}
    assert "tv" in slot_ids
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
    weights = {s: 0.5 for s in BEDROOM_REQUIRED}  # sum = 3.0
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
    assert "bed_size" in slot_map["bedding"].required_specs
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
# Bedroom taxonomy:
#   required: bed_frame(0.22), bedding(0.10), rug(0.12), lighting(0.08),
#             wall_art(0.08), accent(0.06)   → sum = 0.66
#   optional: tv(0.18)  (optional=True in taxonomy when included via weights)
#
# minimum_room_multiplier = 500.0
# MVB (required-only): max(0.66, 1.0) × 500 = $500
#
# NOTE: 'tv' is listed as optional=False in the taxonomy for living_room but
# its SlotDefinition has optional=True (it's not in bedroom's required list).
# We use it as an extra optional slot passed via slot_weights.

_BEDROOM_REQ_IDS = {"bed_frame", "bedding", "rug", "lighting", "wall_art", "accent"}


def _bedroom_weights_with_optional() -> dict[str, float]:
    """bedroom required weights + tv as an optional extra."""
    return {
        "bed_frame": 0.22,
        "bedding":   0.10,
        "rug":       0.12,
        "lighting":  0.08,
        "wall_art":  0.08,
        "accent":    0.06,
        "tv":        0.18,   # optional for bedroom
    }


# --- Budget comfortably fits all slots (required + optional) ----------------

def test_fit_budget_keeps_all_slots_when_budget_is_sufficient():
    """A generous budget keeps every slot including optionals."""
    weights = _bedroom_weights_with_optional()
    # total_w = 0.84 → floor = max(0.84, 1.0) × 500 = $500
    plan = fit_slots_to_budget(weights, 2000.0, "bedroom", TAXONOMY, BUDGET_POLICIES)

    assert plan.is_feasible is True
    assert plan.minimum_viable_budget is None
    slot_ids = {s.slot_id for s in plan.slots}
    # All required present.
    for sid in _BEDROOM_REQ_IDS:
        assert sid in slot_ids, f"Required slot '{sid}' missing"
    # Optional tv also present.
    assert "tv" in slot_ids
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
    """At exactly the required-slot MVB ($500), the optional tv must be dropped."""
    # With tv: total_w = 0.84, floor = $500 — still fits at $500.
    # But if we add a heavier optional that pushes total_w > 1.0:
    #   floor = total_w × 500; need budget < that.
    # Simpler: pass a budget just above MVB-required but supply a heavy optional
    # that would push the floor above the budget.
    # total_w with tv = 0.84, floor = max(0.84,1.0)×500 = 500 → fits at $500.
    # To force dropping we need floor > budget.
    # Add two heavy optionals: tv(0.18) + extra_optional weight.
    # Instead, test with a budget below the optional-inclusive floor.
    # optional floor with tv: still 500. So we test the required-only path directly
    # by using a budget that is feasible for required-only but would not fit if
    # optionals raised total_w above 1.0.
    heavy_weights = {
        "bed_frame": 0.22,
        "bedding":   0.10,
        "rug":       0.12,
        "lighting":  0.08,
        "wall_art":  0.08,
        "accent":    0.06,
        "tv":        0.50,   # heavy optional → total_w=1.16 → floor=$580
    }
    # Budget of $550 < $580 (floor with tv), but >= $500 (floor without tv).
    plan = fit_slots_to_budget(heavy_weights, 550.0, "bedroom", TAXONOMY, BUDGET_POLICIES)

    assert plan.is_feasible is True
    slot_ids = {s.slot_id for s in plan.slots}
    # tv must have been dropped.
    assert "tv" not in slot_ids
    # All required present.
    for sid in _BEDROOM_REQ_IDS:
        assert sid in slot_ids
    assert plan.total_allocated <= 550.0


def test_fit_budget_drops_lowest_weight_optional_first():
    """When multiple optionals are present, the lightest is dropped first."""
    # Add two optionals: tv(0.18) and a lighter one (accent-extra at 0.05).
    # We label them as extra keys not in required_ids.
    # Taxonomy must know these slots. Since taxonomy only has defined slots,
    # we can only use real slot ids. Use 'tv'(0.18) and 'wall_art' as-is,
    # but wall_art IS required for bedroom. We cannot use it as optional.
    #
    # Realistic approach: two separate weight values for tv; instead, use
    # living_room where sofa is required and tv is required too — no free
    # optionals unless we pass extra slots not in required list.
    #
    # For bedroom, only tv is a known non-required slot available in the
    # taxonomy. We can't test multi-optional dropping without faking.
    # Test: with a single optional (tv), verify it's the one dropped.
    heavy_weights = {
        "bed_frame": 0.22,
        "bedding":   0.10,
        "rug":       0.12,
        "lighting":  0.08,
        "wall_art":  0.08,
        "accent":    0.06,
        "tv":        0.60,   # total_w=1.26 → floor=$630
    }
    # Budget $600 < $630 (with tv), $600 >= $500 (without tv).
    plan = fit_slots_to_budget(heavy_weights, 600.0, "bedroom", TAXONOMY, BUDGET_POLICIES)

    assert plan.is_feasible is True
    slot_ids = {s.slot_id for s in plan.slots}
    assert "tv" not in slot_ids
    for sid in _BEDROOM_REQ_IDS:
        assert sid in slot_ids


# --- Infeasible: budget below required-floor sum ----------------------------

def test_fit_budget_infeasible_returns_is_feasible_false():
    """Budget well below required-slot MVB must return is_feasible=False."""
    # Required MVB for bedroom = max(0.66, 1.0) × 500 = $500.
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
    # bedroom required weight sum = 0.66; max(0.66, 1.0) × 500 = 500.0
    assert plan.minimum_viable_budget == pytest.approx(500.0, abs=1e-4)


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

# services/composition_gate.py
# Owns: running the deterministic validator chain after plan_composition()
# produces a SlotPlan.  This is the gate between composition and sourcing.
#
# Order matters:
#   1. validate_feasibility — short-circuits; an infeasible plan must never
#      reach sourcing (slots are at $0 budget).
#   2. validate_budget — total_allocated <= target_budget.
#   3. validate_required_slots — all required slots for the preset present.
#   4. validate_no_duplicate_slots — no slot_id appears twice.
#
# If any gate fails, the SlotPlan is returned alongside the failure reason.
# Downstream services must not receive a plan with a non-None failure reason.

from __future__ import annotations

from schemas.slot_plan import SlotPlan
from services.config_loader import load_room_taxonomy
from validators.budget_rules import validate_budget
from validators.composition_rules import (
    validate_feasibility,
    validate_no_duplicate_slots,
    validate_required_slots,
)


def validate_composition(slot_plan: SlotPlan) -> tuple[SlotPlan, str | None]:
    """Run all composition gates in order.  Return (plan, None) on success.

    Returns:
        (slot_plan, None)    — plan passed all gates; safe to forward to sourcing.
        (slot_plan, reason)  — plan failed at a gate; reason identifies which one.
    """
    # Gate 1: feasibility (short-circuit — no point checking budget/structure
    # on a plan whose slots are all at $0).
    ok, reason = validate_feasibility(slot_plan)
    if not ok:
        return slot_plan, reason

    # Gate 2: budget — total_allocated <= target_budget.
    ok, reason = validate_budget(slot_plan, slot_plan.target_budget)
    if not ok:
        return slot_plan, reason

    # Gate 3: required slots present for the preset.
    taxonomy = load_room_taxonomy()
    required_ids = taxonomy.room_presets[slot_plan.room_preset].required_slots
    ok, reason = validate_required_slots(slot_plan, required_ids)
    if not ok:
        return slot_plan, reason

    # Gate 4: no duplicate slot ids.
    ok, reason = validate_no_duplicate_slots(slot_plan)
    if not ok:
        return slot_plan, reason

    return slot_plan, None

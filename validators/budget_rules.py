# validators/budget_rules.py
# Owns: ensuring that budget totals never exceed the target.
# Called twice in the pipeline:
#   - After composition (validate_budget):   SlotPlan total ≤ target_budget
#   - After selection  (validate_selection_total): snapshot sum ≤ target_budget
#
# These are the most critical deterministic gates.  Any failure blocks the
# design from being shown.  Business rules live here, never in prompts.

from __future__ import annotations

from schemas.slot_plan import SlotPlan


def validate_budget(slot_plan: SlotPlan, target_budget: float) -> tuple[bool, str | None]:
    """Return (True, None) if slot_plan.total_allocated ≤ target_budget.

    Uses the computed total_allocated field so the check is always consistent
    with the actual slot data — there is no separate stored total to diverge.

    Returns:
        (True, None)                    — plan is within budget
        (False, "over_budget:<delta>")  — plan exceeds budget by <delta> USD
    """
    total = slot_plan.total_allocated
    if total > target_budget:
        delta = total - target_budget
        return False, f"over_budget:{delta:.4f}"
    return True, None


def validate_selection_total(snapshots: list, target_budget: float) -> tuple[bool, str | None]:
    """Return (True, None) if sum of snapshot prices ≤ target_budget.

    Stage 8: implemented when ProductSnapshot schema has normalized_price.
    """
    raise NotImplementedError("Stage 8")

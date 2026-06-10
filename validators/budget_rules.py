# validators/budget_rules.py
# Owns: ensuring that budget totals never exceed the target.
# Called twice in the pipeline:
#   - After composition (validate_budget):   SlotPlan total ≤ target_budget
#   - After selection  (validate_pool_spend): per-slot spend ≤ allocated_budget
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


def validate_pool_spend(
    selections: dict[str, list[float]],
    slot_plan: SlotPlan,
) -> tuple[bool, float, list[tuple[str, bool, float, str | None]]]:
    """Validate that per-slot selections respect pool budget and max_quantity.

    Args:
        selections: {slot_id: [price_1, price_2, ...]} — prices looked up
                    server-side from the stored design, never trusted from client.
        slot_plan:  The original SlotPlan with allocated_budget and max_quantity.

    Returns:
        (all_valid, total_spent, per_slot_results) where each result is
        (slot_id, ok, slot_total, reason).
    """
    budget_map = {s.slot_id: s.allocated_budget for s in slot_plan.slots}
    qty_map = {s.slot_id: s.max_quantity for s in slot_plan.slots}

    results: list[tuple[str, bool, float, str | None]] = []
    total_spent = 0.0
    all_valid = True

    for slot_id, prices in selections.items():
        pool = budget_map.get(slot_id)
        if pool is None:
            results.append((slot_id, False, 0.0, "unknown_slot"))
            all_valid = False
            continue

        max_q = qty_map.get(slot_id, 1)
        slot_total = sum(prices)
        total_spent += slot_total

        if len(prices) > max_q:
            results.append((slot_id, False, slot_total, f"exceeds_max_quantity:{max_q}"))
            all_valid = False
        elif slot_total > pool:
            delta = slot_total - pool
            results.append((slot_id, False, slot_total, f"over_pool:{delta:.2f}"))
            all_valid = False
        else:
            results.append((slot_id, True, slot_total, None))

    return all_valid, total_spent, results

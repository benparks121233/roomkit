# validators/budget_rules.py
# Owns: ensuring a design's product total never exceeds the target budget.
# This is the single most critical deterministic gate — called after composition
# and again after selection. Any failure here blocks the design from being shown.
# Stage 5/8: implement.


def validate_budget(slot_plan, target_budget: float) -> tuple[bool, str | None]:
    """Return (True, None) if total allocated ≤ target_budget, else (False, reason)."""
    # Stage 5: sum slot allocated budgets; reject if over target.
    raise NotImplementedError("Stage 5")


def validate_selection_total(snapshots: list, target_budget: float) -> tuple[bool, str | None]:
    """Return (True, None) if sum of snapshot prices ≤ target_budget."""
    # Stage 8: sum snapshot prices; reject if over target.
    raise NotImplementedError("Stage 8")

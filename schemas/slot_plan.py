# schemas/slot_plan.py
# Owns: the full composition — list of slots with per-slot budgets.
# Total of allocated budgets must never exceed target_budget (code-enforced upstream).
# Stage 5: add fields.

from pydantic import BaseModel


class SlotPlan(BaseModel):
    # Stage 5: run_id, room_preset, target_budget, slots (list[Slot]), total_allocated
    pass

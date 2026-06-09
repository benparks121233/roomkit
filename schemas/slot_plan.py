# schemas/slot_plan.py
# Owns: the full composition — list of slots with per-slot budget allocations.
#
# Design rules:
#   - total_allocated is a computed_field (Pydantic v2 property) that always
#     reflects the live sum of slot.allocated_budget values.  It can never
#     diverge from the slots list because it is never stored separately.
#   - The invariant (total_allocated <= target_budget) is enforced by
#     composition_service.allocate_budget(), not by the schema.  The schema
#     holds the data; the service enforces the constraint.
#   - Downstream services (selection, snapshot, assembly) read from this object.
#     They must not re-sum or re-interpret budget math.

from __future__ import annotations

from pydantic import BaseModel, computed_field

from schemas.slot import Slot


class SlotPlan(BaseModel):
    # Identity — threaded from the RoomRequest run_id.
    run_id: str

    # Which room type this plan is for (e.g. "bedroom", "living_room").
    room_preset: str

    # The user's stated budget ceiling.  No slot total may exceed this.
    target_budget: float

    # One Slot per included room slot, each carrying its allocated budget
    # and spec requirements pulled from the taxonomy.
    slots: list[Slot]

    # False when no allocation exists that respects required slot floors.
    # Set by fit_slots_to_budget(); allocate_budget() always leaves this True.
    is_feasible: bool = True

    # Populated only when is_feasible=False: the sum of required slot floors
    # (default_budget_weight × minimum_room_multiplier for each required slot).
    # Shows the user the minimum budget that would make the design feasible.
    minimum_viable_budget: float | None = None

    @computed_field
    @property
    def total_allocated(self) -> float:
        """Sum of all slot allocated_budgets.

        Computed from the slots list on every access — never stored separately.
        This makes it structurally impossible for total_allocated to diverge
        from the actual slot data.
        """
        return sum(s.allocated_budget for s in self.slots)

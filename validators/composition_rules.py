# validators/composition_rules.py
# Owns: structural correctness of the slot plan — required slots present,
# no duplicates.  Called after allocate_budget() returns a SlotPlan.
#
# Required slot lists come from context/slot_taxonomy.yaml room_presets;
# the caller is responsible for passing the right list for the preset.

from __future__ import annotations

from schemas.slot_plan import SlotPlan


def validate_required_slots(
    slot_plan: SlotPlan, required_slots: list[str]
) -> tuple[bool, str | None]:
    """Return (True, None) if every slot id in required_slots is in the plan.

    Returns:
        (True, None)                        — all required slots present
        (False, "missing_slots:<csv-list>") — one or more slots absent
    """
    present = {s.slot_id for s in slot_plan.slots}
    missing = [slot_id for slot_id in required_slots if slot_id not in present]
    if missing:
        return False, f"missing_slots:{','.join(sorted(missing))}"
    return True, None


def validate_no_duplicate_slots(slot_plan: SlotPlan) -> tuple[bool, str | None]:
    """Return (True, None) if every slot_id in the plan is unique.

    Returns:
        (True, None)                             — no duplicates
        (False, "duplicate_slots:<csv-list>")    — duplicated slot ids
    """
    seen: set[str] = set()
    duplicates: set[str] = set()
    for slot in slot_plan.slots:
        if slot.slot_id in seen:
            duplicates.add(slot.slot_id)
        seen.add(slot.slot_id)
    if duplicates:
        return False, f"duplicate_slots:{','.join(sorted(duplicates))}"
    return True, None

# validators/composition_rules.py
# Owns: ensuring the slot plan covers all required slots for the room preset
# and contains no duplicate slot IDs.
# Required slot list comes from context/slot_taxonomy.yaml room_presets.
# Stage 5: implement.


def validate_required_slots(slot_plan, required_slots: list[str]) -> tuple[bool, str | None]:
    """Return (True, None) if all required_slots are present in slot_plan."""
    # Stage 5: compare slot_plan slot IDs against required_slots.
    raise NotImplementedError("Stage 5")


def validate_no_duplicate_slots(slot_plan) -> tuple[bool, str | None]:
    """Return (True, None) if no slot_id appears more than once."""
    # Stage 5: check for duplicates in slot_plan.slots.
    raise NotImplementedError("Stage 5")

# schemas/slot.py
# Owns: a single slot within a composition — id, allocated budget, required specs.
# Populated by composition_service.py after taxonomy + budget allocation.

from pydantic import BaseModel


class Slot(BaseModel):
    slot_id: str
    allocated_budget: float
    required_specs: list[str]
    optional: bool
    # True when the user already owns this item.  Owned slots are recorded
    # on the plan for render/coherence but are never sourced; their
    # allocated_budget is always 0.0.
    owned: bool = False
    max_quantity: int = 1  # >1 enables multi-select (e.g. wall_art: 6)

# schemas/slot.py
# Owns: a single slot within a composition — id, allocated budget, required specs.
# Populated by composition_service.py after taxonomy + budget allocation.

from pydantic import BaseModel


class Slot(BaseModel):
    slot_id: str
    allocated_budget: float
    required_specs: list[str]
    optional: bool

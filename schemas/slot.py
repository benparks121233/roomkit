# schemas/slot.py
# Owns: a single slot within a composition — id, allocated budget, required specs.
# Stage 2: add fields.

from pydantic import BaseModel


class Slot(BaseModel):
    # Stage 2: slot_id, allocated_budget, required_specs, optional
    pass

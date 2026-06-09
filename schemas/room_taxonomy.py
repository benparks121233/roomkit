# schemas/room_taxonomy.py
# Owns: Pydantic models for slot definitions and room presets.
# Loaded from context/slot_taxonomy.yaml at startup.
# Stage 2: add fields and loader.

from pydantic import BaseModel


class SlotDefinition(BaseModel):
    # Stage 2: id, optional, default_budget_weight, required_specs
    pass


class RoomTaxonomy(BaseModel):
    # Stage 2: version, country_scope, slots, room_presets, budget_rules
    pass

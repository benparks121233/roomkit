# schemas/room_taxonomy.py
# Owns: Pydantic models for the slot taxonomy loaded from context/slot_taxonomy.yaml.
# RoomTaxonomy is the top-level validated config object; services read from it,
# never from raw dicts. SlotDefinition is a single row in the taxonomy.

from pydantic import BaseModel, field_validator


class SlotDefinition(BaseModel):
    """One slot in the taxonomy: id, whether it's optional, its default budget
    weight (0–1 fraction of target budget), and its required spec keys."""

    id: str
    optional: bool
    default_budget_weight: float
    required_specs: list[str]

    @field_validator("default_budget_weight")
    @classmethod
    def weight_must_be_positive(cls, v: float) -> float:
        if not (0.0 < v <= 1.0):
            raise ValueError(
                f"default_budget_weight must be in (0, 1], got {v}"
            )
        return v


class RoomPreset(BaseModel):
    """A named room type (e.g. 'bedroom') with its required slot ids."""

    required_slots: list[str]


class BudgetRules(BaseModel):
    """Top-level budget enforcement directives."""

    total_must_not_exceed: str   # sentinel value name, always 'target_budget'
    per_slot_overflow_flag: bool


class RoomTaxonomy(BaseModel):
    """Validated in-memory representation of context/slot_taxonomy.yaml.

    Services must read from an instance of this class, not from the raw YAML
    dict. The loader (services/config_loader.py) is the single entry point.
    """

    version: int
    country_scope: str
    slots: list[SlotDefinition]
    room_presets: dict[str, RoomPreset]
    budget_rules: BudgetRules

    def slot_ids(self) -> set[str]:
        """Convenience: the full set of defined slot ids."""
        return {s.id for s in self.slots}

    def slot_by_id(self, slot_id: str) -> SlotDefinition:
        """Return the SlotDefinition for slot_id, or raise KeyError."""
        for s in self.slots:
            if s.id == slot_id:
                return s
        raise KeyError(f"Slot '{slot_id}' not found in taxonomy")

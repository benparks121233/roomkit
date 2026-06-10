# schemas/room_taxonomy.py
# Owns: Pydantic models for the slot taxonomy loaded from context/slot_taxonomy.yaml.
# RoomTaxonomy is the top-level validated config object; services read from it,
# never from raw dicts.
#
# v2 taxonomy: items are a flat registry (id → required_specs only).
# Budget weights live in room_presets → groups → items.
# Groups sit between room-budget and individual items.

from __future__ import annotations

from pydantic import BaseModel, field_validator


class ItemDefinition(BaseModel):
    """One item in the flat registry: id + required specs only.
    Budget weight info lives in GroupItem within each room preset."""

    required_specs: list[str]


class GroupItem(BaseModel):
    """An item's role within a specific group: required flag + sub-weight."""

    required: bool
    sub_weight: float

    @field_validator("sub_weight")
    @classmethod
    def sub_weight_must_be_positive(cls, v: float) -> float:
        if v <= 0.0:
            raise ValueError(f"sub_weight must be > 0, got {v}")
        return v


class GroupDefinition(BaseModel):
    """A budget group within a room preset (e.g. 'bed', 'seating').
    budget_weight is the fraction of room budget allocated to this group."""

    budget_weight: float
    items: dict[str, GroupItem]

    @field_validator("budget_weight")
    @classmethod
    def weight_must_be_positive(cls, v: float) -> float:
        if not (0.0 < v <= 1.0):
            raise ValueError(f"budget_weight must be in (0, 1], got {v}")
        return v


class RoomPreset(BaseModel):
    """A named room type (e.g. 'bedroom') with its groups and items."""

    groups: dict[str, GroupDefinition]

    def required_items(self) -> list[str]:
        """Return all item ids marked required: true across all groups."""
        return [
            item_id
            for group in self.groups.values()
            for item_id, item in group.items.items()
            if item.required
        ]

    def all_items(self) -> set[str]:
        """Return all item ids across all groups."""
        return {
            item_id
            for group in self.groups.values()
            for item_id in group.items
        }

    def flatten_weights(self) -> dict[str, float]:
        """Convert groups into flat {item_id: effective_weight} dict.

        effective_weight(item) = group.budget_weight * (item.sub_weight / sub_total)
        Sub-weights within a group are normalized to sum to 1.0.
        """
        flat: dict[str, float] = {}
        for group in self.groups.values():
            sub_total = sum(gi.sub_weight for gi in group.items.values())
            for item_id, gi in group.items.items():
                normalized_sub = gi.sub_weight / sub_total if sub_total > 0 else 0
                flat[item_id] = group.budget_weight * normalized_sub
        return flat


class BudgetRules(BaseModel):
    """Top-level budget enforcement directives."""

    min_slot_dollars: float
    max_slot_share: float


class RoomTaxonomy(BaseModel):
    """Validated in-memory representation of context/slot_taxonomy.yaml (v2).

    Services must read from an instance of this class, not from the raw YAML
    dict. The loader (services/config_loader.py) is the single entry point.
    """

    version: int
    items: dict[str, ItemDefinition]
    room_presets: dict[str, RoomPreset]
    budget_rules: BudgetRules

    def item_ids(self) -> set[str]:
        """The full set of defined item ids."""
        return set(self.items.keys())

    def item_by_id(self, item_id: str) -> ItemDefinition:
        """Return the ItemDefinition for item_id, or raise KeyError."""
        if item_id not in self.items:
            raise KeyError(f"Item '{item_id}' not found in taxonomy")
        return self.items[item_id]

    # --- Backward-compat aliases for callers that still say "slot" -----------
    def slot_ids(self) -> set[str]:
        """Alias for item_ids() — backward compat."""
        return self.item_ids()

    def slot_by_id(self, slot_id: str) -> ItemDefinition:
        """Alias for item_by_id() — backward compat."""
        return self.item_by_id(slot_id)

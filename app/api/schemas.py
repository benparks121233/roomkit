# app/api/schemas.py
# Pydantic models for the /design API contract.
# This is the single source of truth for the JSON shape between backend and frontend.

from __future__ import annotations

from pydantic import BaseModel


class DesignRequest(BaseModel):
    """Input to POST /design."""
    room_type: str = "bedroom"
    budget: float = 1500.0
    style_description: str = ""
    core_aesthetic: str | None = None  # Direct style profile id from quiz (e.g. "quiet_luxury")
    bed_size: str | None = None
    qa_answers: dict[str, str] = {}
    density: str = "balanced"
    interests: list[str] = []
    full_room: bool = True
    wants: list[str] = []
    excluded_slots: list[str] = []
    mirror_type: str | None = None  # "full_length", "round", "wall", "arched", or None


class ProductResult(BaseModel):
    """A selected product for a slot."""
    product_id: str
    name: str
    normalized_price: float
    image_url: str
    buy_url: str
    fit_reason: str


class SlotResult(BaseModel):
    """One slot on the board."""
    slot_id: str
    allocated_budget: float
    owned: bool
    max_quantity: int = 1  # >1 enables multi-select (e.g. wall_art: 6)
    product: ProductResult | None = None
    alternatives: list[ProductResult] = []
    null_reason: str | None = None  # "owned" | "no_candidate" | "no_spec_match" | "llm_error"


class StyleResult(BaseModel):
    """Style interpretation summary."""
    style_name: str
    keywords: list[str]
    mood: str
    confidence: float
    fallback: bool


class DesignResponse(BaseModel):
    """Output of POST /design and GET /design/{run_id}."""
    run_id: str
    room_type: str
    style: StyleResult
    target_budget: float
    total_spent: float
    is_feasible: bool
    slots: list[SlotResult]


# ---------------------------------------------------------------------------
# Selection validation (multi-select pool spend check)
# ---------------------------------------------------------------------------

class SlotSelection(BaseModel):
    """User's product picks for one slot."""
    slot_id: str
    selected_product_ids: list[str]


class ValidateSelectionsRequest(BaseModel):
    """Input to POST /design/{run_id}/validate-selections."""
    selections: list[SlotSelection]


class SlotValidationResult(BaseModel):
    """Per-slot validation outcome."""
    slot_id: str
    valid: bool
    total: float = 0.0
    reason: str | None = None  # "over_pool" | "exceeds_max_quantity" | "unknown_product"


class ValidateSelectionsResponse(BaseModel):
    """Output of POST /design/{run_id}/validate-selections."""
    valid: bool
    total_spent: float
    slots: list[SlotValidationResult]

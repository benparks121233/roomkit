# app/api/schemas.py
# Pydantic models for the /design API contract.
# This is the single source of truth for the JSON shape between backend and frontend.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class DesignRequest(BaseModel):
    """Input to POST /design."""
    room_type: Literal["bedroom", "living_room"] = "bedroom"
    budget: float = Field(1500.0, ge=100, le=25000)
    style_description: str = Field("", max_length=2000)
    core_aesthetic: str | None = Field(None, max_length=100)
    bed_size: str | None = Field(None, max_length=50)
    qa_answers: dict[str, str] = {}
    density: str = Field("balanced", max_length=50)
    interests: list[str] = Field(default=[])
    full_room: bool = True
    wants: list[str] = Field(default=[])
    excluded_slots: list[str] = Field(default=[])
    mirror_type: str | None = Field(None, max_length=50)
    screen_size: str | None = Field(None, max_length=50)
    tv_priority: bool = False

    @field_validator("interests", "wants", "excluded_slots")
    @classmethod
    def cap_list_length(cls, v: list[str]) -> list[str]:
        if len(v) > 30:
            raise ValueError("List exceeds maximum of 30 items")
        return v

    @field_validator("qa_answers")
    @classmethod
    def cap_qa_answers(cls, v: dict[str, str]) -> dict[str, str]:
        if len(v) > 30:
            raise ValueError("Too many QA answers (max 30)")
        for key, val in v.items():
            if len(key) > 100 or len(val) > 500:
                raise ValueError("QA key or value too long")
        return v


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
    selected_products: list[ProductResult] = []  # user's final picks (set at finalize)
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
    finalized_at: str | None = None  # ISO timestamp; set once at finalize, never cleared
    user_id: str | None = None
    is_paid: bool = False


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

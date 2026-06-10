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
    bed_size: str | None = None
    qa_answers: dict[str, str] = {}
    already_have: list[str] = []
    must_have: list[str] = []


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
    product: ProductResult | None = None
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

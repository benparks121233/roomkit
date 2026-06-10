# tests/test_selection.py
# Tests for services/selection_service.select_product() — Stage 6 Piece 2.
#
# Per AGENTS.md: no live LLM calls in tests.
# All tests patch services.selection_service._call_selection_llm.
#
# Coverage:
#   - Best style-fit product chosen from candidates via LLM.
#   - Empty candidates → (None, "no_candidate").
#   - LLM returning a product_id NOT in the candidate list → (None, "llm_error").
#   - Returned product's buy_url still contains roomkitai-20 (unmodified).
#   - Owned slot returns (None, "owned_slot") without calling LLM.
#   - Candidates that fail required-spec double-check → (None, "no_spec_match").
#   - LLM explicitly returning null product_id → (None, null_reason).

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch

from schemas.product import Product
from schemas.slot import Slot
from schemas.style_profile import StyleProfile
from services.selection_service import select_product

_PATCH_TARGET = "services.selection_service._call_selection_llm"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_slot(
    slot_id: str = "lighting",
    budget: float = 100.0,
    required_specs: list[str] | None = None,
    owned: bool = False,
) -> Slot:
    return Slot(
        slot_id=slot_id,
        allocated_budget=budget,
        required_specs=required_specs or [],
        optional=False,
        owned=owned,
    )


def _make_style() -> StyleProfile:
    return StyleProfile(
        style_name="warm_minimalist",
        keywords=["natural wood", "linen"],
        color_palette=["#FAF3E0"],
        mood="calm, grounded",
        confidence=0.9,
        fallback=False,
    )


def _make_product(
    product_id: str = "LT-001",
    name: str = "HAITRAL Bedside Table Lamp",
    price: float = 29.99,
    specs: dict | None = None,
    slot_id: str = "lighting",
) -> Product:
    return Product(
        product_id=product_id,
        name=name,
        normalized_price=price,
        buy_url=f"https://www.amazon.com/dp/{product_id}?tag=roomkitai-20",
        specs=specs or {},
        source="amazon",
        image_url=f"https://m.media-amazon.com/images/I/{product_id}.jpg",
        slot_id=slot_id,
        fetched_at=datetime.now(tz=timezone.utc),
    )


def _llm_response(product_id: str | None, reason: str | None = None) -> str:
    """Simulate a valid LLM JSON response."""
    return json.dumps({
        "product_id": product_id,
        "fit_reason": "Best warmth and texture match" if product_id else "",
        "confidence": 0.85 if product_id else 0.0,
        "null_reason": reason,
    })


# ---------------------------------------------------------------------------
# Normal selection: LLM picks a valid candidate
# ---------------------------------------------------------------------------

def test_selects_best_style_fit_from_candidates():
    """LLM picks LT-002 from 3 candidates; returned product is correct."""
    candidates = [
        _make_product("LT-001", "Table Lamp A", 29.99),
        _make_product("LT-002", "Floor Lamp B", 55.99),
        _make_product("LT-003", "Desk Lamp C", 42.99),
    ]
    with patch(_PATCH_TARGET, return_value=_llm_response("LT-002")):
        product, reason = select_product(_make_slot(), _make_style(), candidates)

    assert product is not None
    assert product.product_id == "LT-002"
    assert product.name == "Floor Lamp B"
    assert reason is not None  # fit_reason string


def test_returned_product_is_unmodified():
    """Selection does not alter the product's price, buy_url, or specs."""
    original = _make_product("LT-001", "Lamp", 29.99, {"color": "white"})
    candidates = [original]
    with patch(_PATCH_TARGET, return_value=_llm_response("LT-001")):
        product, _ = select_product(_make_slot(), _make_style(), candidates)

    assert product is not None
    assert product.normalized_price == 29.99
    assert product.buy_url == original.buy_url
    assert product.specs == {"color": "white"}


def test_returned_buy_url_contains_affiliate_tag():
    """The product returned by selection still has the affiliate tag intact."""
    candidates = [_make_product("LT-001")]
    with patch(_PATCH_TARGET, return_value=_llm_response("LT-001")):
        product, _ = select_product(_make_slot(), _make_style(), candidates)

    assert product is not None
    assert "roomkitai-20" in product.buy_url


# ---------------------------------------------------------------------------
# Empty candidates
# ---------------------------------------------------------------------------

def test_empty_candidates_returns_no_candidate():
    """Empty candidate list → (None, 'no_candidate') without calling LLM."""
    product, reason = select_product(_make_slot(), _make_style(), [])
    assert product is None
    assert reason == "no_candidate"


# ---------------------------------------------------------------------------
# LLM returns invalid product_id
# ---------------------------------------------------------------------------

def test_hallucinated_product_id_returns_llm_error():
    """If LLM returns a product_id not in candidates → (None, 'llm_error').
    Rationale: the LLM's job is to pick from the list, not invent. A
    hallucinated ID could map to a product with a different price or missing
    affiliate tag — accepting it would violate the 'never modify' rule."""
    candidates = [_make_product("LT-001"), _make_product("LT-002")]
    # LLM returns "FAKE-999" which isn't in the list.
    with patch(_PATCH_TARGET, return_value=_llm_response("FAKE-999")):
        product, reason = select_product(_make_slot(), _make_style(), candidates)

    assert product is None
    assert reason == "llm_error"


# ---------------------------------------------------------------------------
# LLM explicitly returns null (no fit)
# ---------------------------------------------------------------------------

def test_llm_returns_null_with_no_spec_match():
    """LLM can explicitly signal no match by returning null product_id."""
    candidates = [_make_product("LT-001")]
    response = _llm_response(None, reason="no_spec_match")
    with patch(_PATCH_TARGET, return_value=response):
        product, reason = select_product(_make_slot(), _make_style(), candidates)

    assert product is None
    assert reason == "no_spec_match"


# ---------------------------------------------------------------------------
# Owned slot — skipped entirely
# ---------------------------------------------------------------------------

def test_owned_slot_skipped():
    """An owned slot returns (None, 'owned_slot') without sourcing or LLM."""
    slot = _make_slot(owned=True)
    candidates = [_make_product("LT-001")]
    # LLM should NOT be called — no patch needed, but if it were called
    # it would raise since we don't patch.
    product, reason = select_product(slot, _make_style(), candidates)
    assert product is None
    assert reason == "owned_slot"


# ---------------------------------------------------------------------------
# Required-spec double-check (defensive)
# ---------------------------------------------------------------------------

def test_candidates_missing_required_spec_returns_no_spec_match():
    """If all candidates lack a required spec, return (None, 'no_spec_match')."""
    # Slot requires 'bed_size' but product has no specs.
    slot = _make_slot(slot_id="bedding", required_specs=["bed_size"])
    candidates = [_make_product("BD-X", "Bad Bedding", 30.0, specs={})]
    product, reason = select_product(slot, _make_style(), candidates)

    assert product is None
    assert reason == "no_spec_match"


def test_spec_double_check_still_passes_valid_candidates():
    """Products that DO have the required spec proceed to LLM selection."""
    slot = _make_slot(slot_id="bedding", budget=100.0, required_specs=["bed_size"])
    candidates = [
        _make_product("BD-001", "Queen Set", 39.99, specs={"bed_size": "queen"}),
    ]
    with patch(_PATCH_TARGET, return_value=_llm_response("BD-001")):
        product, _ = select_product(slot, _make_style(), candidates)

    assert product is not None
    assert product.product_id == "BD-001"


# ---------------------------------------------------------------------------
# Unparseable LLM response
# ---------------------------------------------------------------------------

def test_unparseable_llm_response_returns_llm_error():
    """Garbage LLM output → (None, 'llm_error')."""
    candidates = [_make_product("LT-001")]
    with patch(_PATCH_TARGET, return_value="totally not json!!!"):
        product, reason = select_product(_make_slot(), _make_style(), candidates)

    assert product is None
    assert reason == "llm_error"


def test_code_fenced_json_is_parsed():
    """LLM wrapping response in ```json fence still works."""
    candidates = [_make_product("LT-001")]
    fenced = f"```json\n{_llm_response('LT-001')}\n```"
    with patch(_PATCH_TARGET, return_value=fenced):
        product, _ = select_product(_make_slot(), _make_style(), candidates)

    assert product is not None
    assert product.product_id == "LT-001"


# ---------------------------------------------------------------------------
# Price-band double-check
# ---------------------------------------------------------------------------

def test_over_budget_candidate_excluded_by_double_check():
    """A candidate priced above allocated_budget is excluded defensively."""
    slot = _make_slot(budget=30.0)  # $30 max
    candidates = [_make_product("LT-002", "Expensive Lamp", 55.99)]
    product, reason = select_product(slot, _make_style(), candidates)

    assert product is None
    assert reason == "no_candidate"  # price filter, not spec filter

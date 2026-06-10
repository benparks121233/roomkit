# tests/test_selection_ranked.py
# Tests for the ranked selection API (select_products).
#
# Coverage:
#   - Ranked response returns multiple products in order.
#   - Hallucinated IDs in ranked_picks are silently skipped.
#   - Duplicate product_ids in ranked_picks are deduplicated.
#   - All returned products are within the slot's price band.
#   - Empty ranked_picks with null_reason propagates correctly.
#   - Legacy single-pick format still works through select_products.
#   - select_product wrapper returns rank-1 from ranked response.

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch

from schemas.product import Product
from schemas.slot import Slot
from schemas.style_profile import StyleProfile
from services.selection_service import select_product, select_products

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
    name: str = "Table Lamp",
    price: float = 29.99,
    specs: dict | None = None,
) -> Product:
    return Product(
        product_id=product_id,
        name=name,
        normalized_price=price,
        buy_url=f"https://www.amazon.com/dp/{product_id}?tag=roomkitai-20",
        specs=specs or {},
        source="amazon",
        image_url=f"https://m.media-amazon.com/images/I/{product_id}.jpg",
        slot_id="lighting",
        fetched_at=datetime.now(tz=timezone.utc),
    )


def _ranked_response(
    picks: list[tuple[str, str]] | None = None,
    null_reason: str | None = None,
) -> str:
    """Build a ranked LLM response JSON string."""
    if picks is None:
        picks = []
    return json.dumps({
        "ranked_picks": [
            {"product_id": pid, "fit_reason": reason, "confidence": 0.9 - i * 0.1}
            for i, (pid, reason) in enumerate(picks)
        ],
        "null_reason": null_reason,
    })


# ---------------------------------------------------------------------------
# Ranked response: multiple products returned in order
# ---------------------------------------------------------------------------

def test_ranked_response_returns_multiple_products():
    candidates = [
        _make_product("LT-001", "Lamp A", 29.99),
        _make_product("LT-002", "Lamp B", 55.99),
        _make_product("LT-003", "Lamp C", 42.99),
    ]
    response = _ranked_response([
        ("LT-002", "Best style match"),
        ("LT-003", "Good runner-up"),
        ("LT-001", "Budget option"),
    ])
    with patch(_PATCH_TARGET, return_value=response):
        products, reasons, null_reason = select_products(
            _make_slot(), _make_style(), candidates,
        )

    assert null_reason is None
    assert len(products) == 3
    assert products[0].product_id == "LT-002"
    assert products[1].product_id == "LT-003"
    assert products[2].product_id == "LT-001"
    assert reasons[0] == "Best style match"
    assert reasons[1] == "Good runner-up"


def test_ranked_response_preserves_order():
    candidates = [
        _make_product("A", "A", 10),
        _make_product("B", "B", 20),
        _make_product("C", "C", 30),
    ]
    response = _ranked_response([("C", "r1"), ("A", "r2"), ("B", "r3")])
    with patch(_PATCH_TARGET, return_value=response):
        products, _, _ = select_products(_make_slot(), _make_style(), candidates)

    assert [p.product_id for p in products] == ["C", "A", "B"]


# ---------------------------------------------------------------------------
# Hallucinated IDs are skipped, valid ones kept
# ---------------------------------------------------------------------------

def test_hallucinated_ids_skipped_in_ranked():
    candidates = [
        _make_product("LT-001", "Lamp A", 29.99),
        _make_product("LT-002", "Lamp B", 55.99),
    ]
    # "FAKE-999" is not in candidates — should be silently skipped.
    response = _ranked_response([
        ("LT-002", "Best"),
        ("FAKE-999", "Hallucinated"),
        ("LT-001", "Fallback"),
    ])
    with patch(_PATCH_TARGET, return_value=response):
        products, reasons, null_reason = select_products(
            _make_slot(), _make_style(), candidates,
        )

    assert null_reason is None
    assert len(products) == 2
    assert products[0].product_id == "LT-002"
    assert products[1].product_id == "LT-001"


def test_all_hallucinated_ids_returns_llm_error():
    candidates = [_make_product("LT-001")]
    response = _ranked_response([("FAKE-1", "x"), ("FAKE-2", "y")])
    with patch(_PATCH_TARGET, return_value=response):
        products, _, null_reason = select_products(
            _make_slot(), _make_style(), candidates,
        )

    assert len(products) == 0
    assert null_reason == "llm_error"


# ---------------------------------------------------------------------------
# Duplicate product_ids are deduplicated
# ---------------------------------------------------------------------------

def test_duplicate_ids_deduplicated():
    candidates = [
        _make_product("LT-001", "Lamp A", 29.99),
        _make_product("LT-002", "Lamp B", 55.99),
    ]
    response = _ranked_response([
        ("LT-001", "First"),
        ("LT-001", "Duplicate"),
        ("LT-002", "Second"),
    ])
    with patch(_PATCH_TARGET, return_value=response):
        products, _, _ = select_products(
            _make_slot(), _make_style(), candidates,
        )

    assert len(products) == 2
    assert products[0].product_id == "LT-001"
    assert products[1].product_id == "LT-002"


# ---------------------------------------------------------------------------
# All returned products are within price band
# ---------------------------------------------------------------------------

def test_over_budget_candidates_excluded_before_llm():
    """Products above allocated_budget are filtered out before the LLM sees them."""
    slot = _make_slot(budget=40.0)
    candidates = [
        _make_product("LT-001", "Cheap", 29.99),
        _make_product("LT-002", "Expensive", 55.99),  # Over budget
    ]
    response = _ranked_response([("LT-001", "Only option")])
    with patch(_PATCH_TARGET, return_value=response):
        products, _, _ = select_products(slot, _make_style(), candidates)

    # LT-002 should have been filtered before the LLM call.
    assert len(products) == 1
    assert products[0].product_id == "LT-001"
    assert products[0].normalized_price <= 40.0


# ---------------------------------------------------------------------------
# Empty ranked_picks with null_reason
# ---------------------------------------------------------------------------

def test_empty_ranked_picks_with_null_reason():
    candidates = [_make_product("LT-001")]
    response = json.dumps({
        "ranked_picks": [],
        "null_reason": "no_spec_match",
    })
    with patch(_PATCH_TARGET, return_value=response):
        products, _, null_reason = select_products(
            _make_slot(), _make_style(), candidates,
        )

    assert len(products) == 0
    assert null_reason == "no_spec_match"


# ---------------------------------------------------------------------------
# Legacy single-pick format works through select_products
# ---------------------------------------------------------------------------

def test_legacy_single_pick_format():
    candidates = [_make_product("LT-001", "Lamp A", 29.99)]
    response = json.dumps({
        "product_id": "LT-001",
        "fit_reason": "Good match",
        "confidence": 0.9,
        "null_reason": None,
    })
    with patch(_PATCH_TARGET, return_value=response):
        products, reasons, null_reason = select_products(
            _make_slot(), _make_style(), candidates,
        )

    assert null_reason is None
    assert len(products) == 1
    assert products[0].product_id == "LT-001"
    assert reasons[0] == "Good match"


# ---------------------------------------------------------------------------
# select_product wrapper returns rank-1 from ranked response
# ---------------------------------------------------------------------------

def test_select_product_returns_rank1_from_ranked():
    candidates = [
        _make_product("LT-001", "Lamp A", 29.99),
        _make_product("LT-002", "Lamp B", 55.99),
    ]
    response = _ranked_response([
        ("LT-002", "Best style match"),
        ("LT-001", "Runner-up"),
    ])
    with patch(_PATCH_TARGET, return_value=response):
        product, reason = select_product(
            _make_slot(), _make_style(), candidates,
        )

    assert product is not None
    assert product.product_id == "LT-002"
    assert reason == "Best style match"


# ---------------------------------------------------------------------------
# Code-fenced ranked response
# ---------------------------------------------------------------------------

def test_code_fenced_ranked_response():
    candidates = [_make_product("LT-001")]
    body = _ranked_response([("LT-001", "Match")])
    fenced = f"```json\n{body}\n```"
    with patch(_PATCH_TARGET, return_value=fenced):
        products, _, null_reason = select_products(
            _make_slot(), _make_style(), candidates,
        )

    assert null_reason is None
    assert len(products) == 1
    assert products[0].product_id == "LT-001"


# ---------------------------------------------------------------------------
# Owned slot and empty candidates through select_products
# ---------------------------------------------------------------------------

def test_owned_slot_returns_empty():
    slot = _make_slot(owned=True)
    products, _, null_reason = select_products(
        slot, _make_style(), [_make_product()],
    )
    assert len(products) == 0
    assert null_reason == "owned_slot"


def test_empty_candidates_returns_empty():
    products, _, null_reason = select_products(
        _make_slot(), _make_style(), [],
    )
    assert len(products) == 0
    assert null_reason == "no_candidate"

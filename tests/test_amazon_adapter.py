# tests/test_amazon_adapter.py
# Tests for services/sourcing/amazon_adapter.AmazonAdapter — Stage 6 Piece 1.
# All tests read from fixture files only; no network calls.
#
# Coverage:
#   - Adapter returns products within price_band.
#   - Products outside price_band are excluded.
#   - Products missing required specs are excluded.
#   - Required spec value mismatch excludes the product.
#   - Every returned buy_url contains the affiliate tag (roomkitai-20).
#   - Empty result when no candidate fits price_band.
#   - Empty result when no candidate fits required_specs.
#   - Slot with no required specs returns all in-band products.
#   - Missing fixture file returns empty list.

from __future__ import annotations

import pytest

from schemas.product import Product
from services.sourcing.amazon_adapter import AmazonAdapter


@pytest.fixture
def adapter() -> AmazonAdapter:
    """Use the real fixture files in data/fixtures/."""
    return AmazonAdapter()


AFFILIATE_TAG = "roomkitai-20"


# ---------------------------------------------------------------------------
# Price-band filtering
# ---------------------------------------------------------------------------

def test_returns_products_within_price_band(adapter: AmazonAdapter):
    """Lighting fixtures range ~$15–$56; band $20–$50 should return a subset."""
    results = adapter.fetch_candidates("lighting", ["warm"], (20.0, 50.0), {})
    assert len(results) > 0
    for p in results:
        assert 20.0 <= p.normalized_price <= 50.0


def test_excludes_products_outside_price_band(adapter: AmazonAdapter):
    """Band $0–$10 should exclude all lighting products (cheapest is ~$30)."""
    results = adapter.fetch_candidates("lighting", ["warm"], (0.0, 10.0), {})
    assert len(results) == 0


def test_price_band_inclusive_on_exact_match(adapter: AmazonAdapter):
    """A product priced exactly at the band boundary should be included."""
    # Accent AC-003 is $12.99.
    results = adapter.fetch_candidates("accent", [], (12.99, 12.99), {})
    assert any(p.normalized_price == pytest.approx(12.99) for p in results)


# ---------------------------------------------------------------------------
# Spec filtering
# ---------------------------------------------------------------------------

def test_required_specs_filter_matches(adapter: AmazonAdapter):
    """Bedding with bed_size=queen should only return queen products."""
    results = adapter.fetch_candidates(
        "bedding", ["cozy"], (0.0, 500.0), {"bed_size": "queen"},
    )
    assert len(results) > 0
    for p in results:
        assert p.specs.get("bed_size", "").lower() == "queen"


def test_required_specs_exclude_mismatch(adapter: AmazonAdapter):
    """Bedding with bed_size=twin should return 0 (no twin bedding in fixtures)."""
    results = adapter.fetch_candidates(
        "bedding", ["cozy"], (0.0, 500.0), {"bed_size": "twin"},
    )
    assert len(results) == 0


def test_missing_required_spec_excludes_product(adapter: AmazonAdapter):
    """Requesting a spec key that no product carries returns nothing.
    Lighting has no specs; requiring 'color_temp' should return empty."""
    results = adapter.fetch_candidates(
        "lighting", ["warm"], (0.0, 500.0), {"color_temp": "3000K"},
    )
    assert len(results) == 0


def test_no_required_specs_returns_all_in_band(adapter: AmazonAdapter):
    """Slots with no required specs (e.g. wall_art) return all in-band products."""
    results = adapter.fetch_candidates("wall_art", ["abstract"], (0.0, 500.0), {})
    assert len(results) >= 3  # fixture has 3 wall_art products


def test_tv_screen_size_filtering(adapter: AmazonAdapter):
    """TV with screen_size='55 inch' should only return 55\" TVs."""
    results = adapter.fetch_candidates(
        "tv", ["modern"], (0.0, 500.0), {"screen_size": "55 inch"},
    )
    assert len(results) >= 1
    for p in results:
        assert p.specs.get("screen_size") == "55 inch"


# ---------------------------------------------------------------------------
# Affiliate tag — the most critical check
# ---------------------------------------------------------------------------

def test_every_buy_url_contains_affiliate_tag(adapter: AmazonAdapter):
    """EVERY product returned by the adapter must have the affiliate tag."""
    for slot_id in ["bed_frame", "bedding", "rug", "lighting", "wall_art",
                     "accent", "sofa", "tv"]:
        results = adapter.fetch_candidates(slot_id, [], (0.0, 99999.0), {})
        for p in results:
            assert AFFILIATE_TAG in p.buy_url, (
                f"buy_url for {p.product_id} missing affiliate tag: {p.buy_url}"
            )


def test_affiliate_tag_is_url_parameter(adapter: AmazonAdapter):
    """The tag should appear as a proper URL query parameter, not just a substring."""
    results = adapter.fetch_candidates("accent", [], (0.0, 500.0), {})
    assert len(results) > 0
    for p in results:
        assert f"tag={AFFILIATE_TAG}" in p.buy_url


def test_affiliate_tag_preserves_existing_url_path(adapter: AmazonAdapter):
    """The original URL path (e.g. /dp/B07...) must be preserved."""
    results = adapter.fetch_candidates("accent", [], (0.0, 500.0), {})
    for p in results:
        assert "/dp/" in p.buy_url


# ---------------------------------------------------------------------------
# Product schema correctness
# ---------------------------------------------------------------------------

def test_returns_product_instances(adapter: AmazonAdapter):
    """Every result must be a Product model instance."""
    results = adapter.fetch_candidates("sofa", ["modern"], (0.0, 500.0), {})
    assert len(results) > 0
    for p in results:
        assert isinstance(p, Product)


def test_product_carries_correct_fields(adapter: AmazonAdapter):
    results = adapter.fetch_candidates("bed_frame", [], (0.0, 500.0), {"bed_size": "queen"})
    assert len(results) > 0
    p = results[0]
    assert p.source == "amazon"
    assert p.slot_id == "bed_frame"
    assert p.product_id != ""
    assert p.name != ""
    assert p.image_url != ""
    assert p.fetched_at is not None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_missing_fixture_file_returns_empty(adapter: AmazonAdapter):
    """A slot with no fixture file returns an empty candidate list."""
    results = adapter.fetch_candidates("nonexistent_slot", [], (0.0, 500.0), {})
    assert results == []


def test_combined_price_and_spec_filter(adapter: AmazonAdapter):
    """Price band + spec filter applied together narrows results correctly."""
    # Bed frames: BF-001 queen $189.99, BF-003 queen $69.99.
    # Band $100–$200 + queen should return only BF-001.
    results = adapter.fetch_candidates(
        "bed_frame", ["minimalist"], (100.0, 200.0), {"bed_size": "queen"},
    )
    assert len(results) == 1
    assert results[0].product_id == "BF-001"

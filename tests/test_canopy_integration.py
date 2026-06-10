# tests/test_canopy_integration.py
# Tests for the Canopy API integration layer:
#   - CanopyClient (mocked HTTP — never live calls)
#   - catalog_cache read/write
#   - AmazonAdapter cache-hit and cache-miss paths
#   - Spec extraction from title/bullets
#   - Affiliate tag on cached products
#   - refresh_catalog field mapping

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from schemas.product import Product
from services.sourcing.amazon_adapter import AmazonAdapter
from services.sourcing.canopy_client import CanopyClient
from services.sourcing.catalog_cache import read_cache, write_cache

AFFILIATE_TAG = "roomkitai-20"

# ---------------------------------------------------------------------------
# Sample Canopy API response data (matches real Canopy shape)
# ---------------------------------------------------------------------------

# URLs deliberately use the messy /sspa/click and ?ref= forms that Canopy
# actually returns — our mapper must ignore these and build clean /dp/{asin} URLs.
CANOPY_SEARCH_RESPONSE = {
    "data": {
        "amazonProductSearchResults": {
            "productResults": {
                "results": [
                    {
                        "title": "Solid Wood Queen Platform Bed Frame",
                        "url": "https://www.amazon.com/sspa/click?ie=UTF8&sp_csd=d2lkZ2V0&ref=B09TEST001",
                        "asin": "B09TEST001",
                        "price": {"value": 189.99, "currency": "USD",
                                  "display": "$189.99", "symbol": "$"},
                        "mainImageUrl": "https://m.media-amazon.com/images/I/test1.jpg",
                        "rating": 4.5,
                        "ratingsTotal": 1200,
                        "isPrime": True,
                    },
                    {
                        "title": "King Size Metal Bed Frame with Headboard",
                        "url": "https://www.amazon.com/dp/B09TEST002?ref=sr_1_2&qid=1234",
                        "asin": "B09TEST002",
                        "price": {"value": 129.99, "currency": "USD",
                                  "display": "$129.99", "symbol": "$"},
                        "mainImageUrl": "https://m.media-amazon.com/images/I/test2.jpg",
                        "rating": 4.2,
                        "ratingsTotal": 800,
                        "isPrime": False,
                    },
                    {
                        "title": "Budget Twin Bed Frame",
                        "url": "https://www.amazon.com/dp/B09TEST003?ref=sr_1_3",
                        "asin": "B09TEST003",
                        "price": {"value": 69.99, "currency": "USD",
                                  "display": "$69.99", "symbol": "$"},
                        "mainImageUrl": "https://m.media-amazon.com/images/I/test3.jpg",
                        "rating": 4.0,
                        "ratingsTotal": 500,
                        "isPrime": True,
                    },
                ],
            },
        },
    },
}

CANOPY_PRODUCT_RESPONSE = {
    "data": {
        "amazonProduct": {
            "title": "Solid Wood Queen Platform Bed Frame",
            "url": "https://www.amazon.com/dp/B09TEST001?ref=dp_prsubs_1",
            "asin": "B09TEST001",
            "price": {"value": 189.99, "currency": "USD",
                      "display": "$189.99", "symbol": "$"},
            "mainImageUrl": "https://m.media-amazon.com/images/I/test1.jpg",
            "featureBullets": [
                "Queen size solid pine wood construction",
                "No box spring needed",
            ],
            "brand": "TestBrand",
            "isPrime": True,
            "isInStock": True,
            "rating": 4.5,
            "ratingsTotal": 1200,
        },
    },
}

# Products already in our internal cache format.
CACHED_BED_FRAMES = [
    {
        "product_id": "B09CACHE01",
        "name": "Cached Queen Platform Bed Frame",
        "normalized_price": 199.99,
        "buy_url": "https://www.amazon.com/dp/B09CACHE01",
        "specs": {"bed_size": "queen"},
        "image_url": "https://m.media-amazon.com/images/I/cached1.jpg",
        "source": "canopy",
    },
    {
        "product_id": "B09CACHE02",
        "name": "Cached King Platform Bed Frame",
        "normalized_price": 249.99,
        "buy_url": "https://www.amazon.com/dp/B09CACHE02",
        "specs": {"bed_size": "king"},
        "image_url": "https://m.media-amazon.com/images/I/cached2.jpg",
        "source": "canopy",
    },
]


# ---------------------------------------------------------------------------
# CanopyClient tests (mocked HTTP)
# ---------------------------------------------------------------------------

class TestCanopyClient:
    def test_requires_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="CANOPY_API_KEY"):
                CanopyClient(api_key="")

    def test_api_key_from_env(self):
        with patch.dict("os.environ", {"CANOPY_API_KEY": "test-key-123"}):
            client = CanopyClient()
            assert client._api_key == "test-key-123"

    def test_search_products_parses_response(self):
        client = CanopyClient(api_key="test-key")
        mock_resp = MagicMock()
        mock_resp.json.return_value = CANOPY_SEARCH_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_resp) as mock_get:
            results = client.search_products("queen bed frame", limit=10)

        assert len(results) == 3
        assert results[0]["asin"] == "B09TEST001"
        assert results[0]["price"]["value"] == 189.99

        # Verify correct URL and headers.
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args
        headers = call_kwargs.kwargs.get("headers", call_kwargs[1].get("headers", {}))
        assert "API-KEY" in headers

    def test_no_content_type_header(self):
        """GET requests must NOT send Content-Type — Canopy 500s on it."""
        client = CanopyClient(api_key="test-key")
        mock_resp = MagicMock()
        mock_resp.json.return_value = CANOPY_SEARCH_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_resp) as mock_get:
            client.search_products("bed frame")

        headers = mock_get.call_args.kwargs.get(
            "headers", mock_get.call_args[1].get("headers", {}),
        )
        assert "Content-Type" not in headers

    def test_search_products_with_price_filters(self):
        client = CanopyClient(api_key="test-key")
        mock_resp = MagicMock()
        mock_resp.json.return_value = CANOPY_SEARCH_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_resp) as mock_get:
            client.search_products("bed", min_price=50.0, max_price=200.0)

        call_kwargs = mock_get.call_args
        params = call_kwargs.kwargs.get("params", call_kwargs[1].get("params", {}))
        assert params["minPrice"] == 50.0
        assert params["maxPrice"] == 200.0

    def test_get_product_parses_response(self):
        client = CanopyClient(api_key="test-key")
        mock_resp = MagicMock()
        mock_resp.json.return_value = CANOPY_PRODUCT_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_resp):
            result = client.get_product("B09TEST001")

        assert result is not None
        assert result["asin"] == "B09TEST001"
        assert result["title"] == "Solid Wood Queen Platform Bed Frame"

    def test_search_returns_empty_on_no_results(self):
        client = CanopyClient(api_key="test-key")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {"amazonProductSearchResults": {"productResults": {"results": []}}},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_resp):
            results = client.search_products("nonexistent xyz")

        assert results == []


# ---------------------------------------------------------------------------
# Catalog cache tests
# ---------------------------------------------------------------------------

class TestCatalogCache:
    def test_write_and_read(self, tmp_path: Path):
        write_cache("bed_frame", CACHED_BED_FRAMES, catalog_dir=tmp_path)
        result = read_cache("bed_frame", catalog_dir=tmp_path)
        assert result is not None
        assert len(result) == 2
        assert result[0]["product_id"] == "B09CACHE01"

    def test_read_returns_none_on_miss(self, tmp_path: Path):
        result = read_cache("nonexistent", catalog_dir=tmp_path)
        assert result is None

    def test_write_creates_directory(self, tmp_path: Path):
        nested = tmp_path / "deep" / "catalog"
        write_cache("rug", [{"product_id": "R1"}], catalog_dir=nested)
        assert (nested / "rug.json").exists()

    def test_read_returns_none_on_non_list(self, tmp_path: Path):
        path = tmp_path / "bad.json"
        path.write_text(json.dumps({"not": "a list"}))
        result = read_cache("bad", catalog_dir=tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# AmazonAdapter: cache hit path
# ---------------------------------------------------------------------------

class TestAdapterCacheHit:
    """When cache has data, adapter reads from cache (not fixtures)."""

    def test_cache_hit_returns_products(self, tmp_path: Path):
        write_cache("bed_frame", CACHED_BED_FRAMES, catalog_dir=tmp_path)
        adapter = AmazonAdapter(catalog_dir=tmp_path)

        results = adapter.fetch_candidates(
            "bed_frame", ["modern"], (0.0, 500.0), {},
        )
        assert len(results) == 2
        assert all(isinstance(p, Product) for p in results)

    def test_cache_hit_filters_by_price_band(self, tmp_path: Path):
        write_cache("bed_frame", CACHED_BED_FRAMES, catalog_dir=tmp_path)
        adapter = AmazonAdapter(catalog_dir=tmp_path)

        results = adapter.fetch_candidates(
            "bed_frame", ["modern"], (200.0, 300.0), {},
        )
        # Only the king frame at $249.99 is in band.
        assert len(results) == 1
        assert results[0].product_id == "B09CACHE02"

    def test_cache_hit_filters_by_required_specs(self, tmp_path: Path):
        write_cache("bed_frame", CACHED_BED_FRAMES, catalog_dir=tmp_path)
        adapter = AmazonAdapter(catalog_dir=tmp_path)

        results = adapter.fetch_candidates(
            "bed_frame", ["modern"], (0.0, 500.0), {"bed_size": "queen"},
        )
        assert len(results) == 1
        assert results[0].product_id == "B09CACHE01"

    def test_cache_hit_injects_affiliate_tag(self, tmp_path: Path):
        write_cache("bed_frame", CACHED_BED_FRAMES, catalog_dir=tmp_path)
        adapter = AmazonAdapter(catalog_dir=tmp_path)

        results = adapter.fetch_candidates(
            "bed_frame", ["modern"], (0.0, 500.0), {},
        )
        for p in results:
            assert f"tag={AFFILIATE_TAG}" in p.buy_url, (
                f"buy_url missing affiliate tag: {p.buy_url}"
            )

    def test_cache_hit_buy_url_is_clean_tagged_form(self, tmp_path: Path):
        """Every buy_url must be https://www.amazon.com/dp/{asin}?tag=roomkitai-20."""
        write_cache("bed_frame", CACHED_BED_FRAMES, catalog_dir=tmp_path)
        adapter = AmazonAdapter(catalog_dir=tmp_path)

        results = adapter.fetch_candidates(
            "bed_frame", ["modern"], (0.0, 500.0), {},
        )
        for p in results:
            assert p.buy_url.startswith("https://www.amazon.com/dp/"), (
                f"buy_url not clean /dp/ form: {p.buy_url}"
            )
            assert f"tag={AFFILIATE_TAG}" in p.buy_url
            # No extra junk params from Canopy.
            assert "ref=" not in p.buy_url
            assert "sspa" not in p.buy_url

    def test_cache_hit_skips_fixtures(self, tmp_path: Path):
        """If cache exists, fixtures dir is never read."""
        catalog_dir = tmp_path / "catalog"
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()

        write_cache("bed_frame", CACHED_BED_FRAMES, catalog_dir=catalog_dir)
        # No fixture file for bed_frame — but shouldn't matter.
        adapter = AmazonAdapter(
            catalog_dir=catalog_dir, fixtures_dir=fixtures_dir,
        )
        results = adapter.fetch_candidates(
            "bed_frame", ["modern"], (0.0, 500.0), {},
        )
        assert len(results) == 2  # from cache, not empty fixtures


# ---------------------------------------------------------------------------
# AmazonAdapter: cache miss → fixture fallback
# ---------------------------------------------------------------------------

class TestAdapterCacheMiss:
    """When cache misses, adapter falls back to fixtures."""

    def test_cache_miss_reads_fixtures(self, tmp_path: Path):
        """Empty catalog dir → falls back to real fixture files."""
        adapter = AmazonAdapter(catalog_dir=tmp_path)
        # tmp_path has no cache files, so adapter falls back to real fixtures.
        results = adapter.fetch_candidates(
            "bed_frame", [], (0.0, 500.0), {},
        )
        assert len(results) > 0  # real fixture data

    def test_cache_miss_no_fixture_returns_empty(self, tmp_path: Path):
        adapter = AmazonAdapter(
            catalog_dir=tmp_path, fixtures_dir=tmp_path,
        )
        results = adapter.fetch_candidates(
            "nonexistent_slot", [], (0.0, 500.0), {},
        )
        assert results == []


# ---------------------------------------------------------------------------
# Spec extraction (refresh_catalog.py)
# ---------------------------------------------------------------------------

class TestSpecExtraction:
    """Test the regex-based spec extractor used by the refresh script."""

    def setup_method(self):
        from scripts.refresh_catalog import extract_specs
        self.extract = extract_specs

    def test_extracts_queen_from_title(self):
        specs = self.extract("bed_frame", "Solid Wood Queen Platform Bed Frame", [])
        assert specs["bed_size"] == "queen"

    def test_extracts_king_from_title(self):
        specs = self.extract("bed_frame", "King Size Metal Bed Frame", [])
        assert specs["bed_size"] == "king"

    def test_extracts_twin_from_bullets(self):
        specs = self.extract("mattress", "Memory Foam Mattress", ["Twin size comfort"])
        assert specs["bed_size"] == "twin"

    def test_extracts_screen_size(self):
        specs = self.extract("tv", "Samsung 55 inch 4K Smart TV", [])
        assert specs["screen_size"] == "55 inch"

    def test_extracts_screen_size_with_quotes(self):
        specs = self.extract("tv", 'LG 65" OLED TV', [])
        assert specs["screen_size"] == "65 inch"

    def test_extracts_rug_dimensions(self):
        specs = self.extract("rug", "Area Rug 8x10 feet", [])
        assert specs["dimensions"] == "8x10"

    def test_no_specs_for_wall_art(self):
        specs = self.extract("wall_art", "Abstract Canvas Print", [])
        assert specs == {}

    def test_no_bed_size_when_missing(self):
        specs = self.extract("bed_frame", "Industrial Metal Bed Frame", [])
        assert "bed_size" not in specs

    def test_california_king_normalizes(self):
        specs = self.extract("bed_frame", "California King Bed Frame", [])
        assert specs["bed_size"] == "king"


# ---------------------------------------------------------------------------
# Canopy → cache format mapping (refresh_catalog.py)
# ---------------------------------------------------------------------------

def _first_canopy_result() -> dict:
    """Extract the first product from the sample Canopy search response."""
    search = CANOPY_SEARCH_RESPONSE["data"]["amazonProductSearchResults"]
    return search["productResults"]["results"][0]


class TestCanopyProductMapping:
    def setup_method(self):
        from scripts.refresh_catalog import map_canopy_product
        self.map_product = map_canopy_product

    def test_maps_basic_fields(self):
        raw = _first_canopy_result()
        mapped = self.map_product("bed_frame", raw)

        assert mapped["product_id"] == "B09TEST001"
        assert mapped["name"] == "Solid Wood Queen Platform Bed Frame"
        assert mapped["normalized_price"] == 189.99
        assert mapped["buy_url"] == "https://www.amazon.com/dp/B09TEST001"
        assert mapped["image_url"] == "https://m.media-amazon.com/images/I/test1.jpg"
        assert mapped["source"] == "canopy"

    def test_buy_url_is_clean_asin_url_not_raw_response_url(self):
        """Mapper must build /dp/{asin} URL, ignoring messy /sspa/click URL."""
        raw = _first_canopy_result()
        assert "/sspa/click" in raw["url"]  # confirm test data is messy
        mapped = self.map_product("bed_frame", raw)
        assert mapped["buy_url"] == "https://www.amazon.com/dp/B09TEST001"

    def test_extracts_bed_size_spec(self):
        raw = _first_canopy_result()
        mapped = self.map_product("bed_frame", raw)
        assert mapped["specs"].get("bed_size") == "queen"

    def test_skips_product_with_no_price(self):
        raw = {"title": "No Price Item", "asin": "B000", "url": "http://x"}
        mapped = self.map_product("bed_frame", raw)
        assert mapped == {}

    def test_handles_missing_optional_fields(self):
        raw = {
            "asin": "B09MINIMAL",
            "title": "Minimal Product",
            "price": {"value": 49.99},
            "url": "https://www.amazon.com/dp/B09MINIMAL",
        }
        mapped = self.map_product("wall_art", raw)
        assert mapped["product_id"] == "B09MINIMAL"
        assert mapped["buy_url"] == "https://www.amazon.com/dp/B09MINIMAL"
        assert mapped["image_url"] == ""
        assert mapped["source"] == "canopy"

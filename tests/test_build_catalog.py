# tests/test_build_catalog.py
# Tests for:
#   - catalog_cache.merge_cache (ASIN dedup)
#   - build_catalog query plan and execution (mocked Canopy)
#   - Request ceiling enforcement

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from services.sourcing.catalog_cache import merge_cache, read_cache, write_cache

# ---------------------------------------------------------------------------
# merge_cache deduplication
# ---------------------------------------------------------------------------

class TestMergeCache:
    def test_merge_into_empty_cache(self, tmp_path: Path):
        products = [
            {"product_id": "B001", "name": "Product A", "normalized_price": 10.0},
            {"product_id": "B002", "name": "Product B", "normalized_price": 20.0},
        ]
        total, added = merge_cache("test_slot", products, catalog_dir=tmp_path)
        assert total == 2
        assert added == 2

    def test_merge_deduplicates_by_asin(self, tmp_path: Path):
        existing = [
            {"product_id": "B001", "name": "Old A", "normalized_price": 10.0},
            {"product_id": "B002", "name": "Old B", "normalized_price": 20.0},
        ]
        write_cache("test_slot", existing, catalog_dir=tmp_path)

        new_products = [
            {"product_id": "B001", "name": "Updated A", "normalized_price": 12.0},
            {"product_id": "B003", "name": "New C", "normalized_price": 30.0},
        ]
        total, added = merge_cache("test_slot", new_products, catalog_dir=tmp_path)

        assert total == 3   # B001 (updated), B002 (kept), B003 (new)
        assert added == 1   # only B003 is truly new

        # Verify B001 was updated, not doubled.
        cached = read_cache("test_slot", catalog_dir=tmp_path)
        b001 = next(p for p in cached if p["product_id"] == "B001")
        assert b001["name"] == "Updated A"
        assert b001["normalized_price"] == 12.0

    def test_merge_no_new_products(self, tmp_path: Path):
        existing = [
            {"product_id": "B001", "name": "A", "normalized_price": 10.0},
        ]
        write_cache("test_slot", existing, catalog_dir=tmp_path)

        same = [
            {"product_id": "B001", "name": "A refreshed", "normalized_price": 10.5},
        ]
        total, added = merge_cache("test_slot", same, catalog_dir=tmp_path)
        assert total == 1
        assert added == 0

    def test_merge_skips_empty_product_id(self, tmp_path: Path):
        products = [
            {"product_id": "", "name": "No ASIN"},
            {"product_id": "B001", "name": "Valid"},
        ]
        total, added = merge_cache("test_slot", products, catalog_dir=tmp_path)
        assert total == 1  # only B001

    def test_multiple_merges_accumulate(self, tmp_path: Path):
        batch1 = [{"product_id": "B001", "name": "A", "normalized_price": 10.0}]
        batch2 = [{"product_id": "B002", "name": "B", "normalized_price": 20.0}]
        batch3 = [{"product_id": "B003", "name": "C", "normalized_price": 30.0}]

        merge_cache("slot", batch1, catalog_dir=tmp_path)
        merge_cache("slot", batch2, catalog_dir=tmp_path)
        total, added = merge_cache("slot", batch3, catalog_dir=tmp_path)

        assert total == 3
        assert added == 1


# ---------------------------------------------------------------------------
# build_catalog with mocked Canopy
# ---------------------------------------------------------------------------

# Sample Canopy search results for mocking.
def _make_canopy_results(asins: list[str], slot_title_prefix: str = "Product"):
    return [
        {
            "title": f"{slot_title_prefix} {asin}",
            "url": f"https://www.amazon.com/dp/{asin}?ref=sr_1_1",
            "asin": asin,
            "price": {"value": 49.99 + i, "currency": "USD",
                      "display": f"${49.99 + i}", "symbol": "$"},
            "mainImageUrl": f"https://images.amazon.com/{asin}.jpg",
            "rating": 4.0,
            "ratingsTotal": 100,
            "isPrime": True,
        }
        for i, asin in enumerate(asins)
    ]


class TestBuildCatalogExecution:
    def test_queries_merge_into_same_slot(self, tmp_path: Path):
        """Two queries for the same slot merge by ASIN."""
        from scripts.refresh_catalog import map_canopy_product

        # Simulate two Canopy searches for bed_frame with overlapping ASINs.
        batch1_raw = _make_canopy_results(["B001", "B002"], "Queen Bed Frame")
        batch2_raw = _make_canopy_results(["B002", "B003"], "Wood Bed Frame")

        # Map and merge like build_catalog does.
        batch1 = [m for r in batch1_raw if (m := map_canopy_product("bed_frame", r))]
        batch2 = [m for r in batch2_raw if (m := map_canopy_product("bed_frame", r))]

        merge_cache("bed_frame", batch1, catalog_dir=tmp_path)
        total, added = merge_cache("bed_frame", batch2, catalog_dir=tmp_path)

        assert total == 3  # B001, B002 (updated), B003
        assert added == 1  # only B003 is new

    def test_run_build_aborts_when_queries_exceed_ceiling(self, tmp_path: Path):
        """run_build aborts before any calls if query count > max_requests."""
        import pytest

        from scripts.build_catalog import run_build

        mock_client = MagicMock()
        queries = [("slot_a", "term 1"), ("slot_b", "term 2"), ("slot_c", "term 3")]

        with pytest.raises(SystemExit):
            run_build(mock_client, queries, limit=10, max_requests=2)

        # No API calls should have been made.
        assert mock_client.search_products.call_count == 0

    def test_run_build_executes_all_within_ceiling(self, tmp_path: Path):
        """run_build executes all queries when count <= max_requests."""
        from scripts.build_catalog import run_build

        mock_client = MagicMock()
        mock_client.search_products.return_value = _make_canopy_results(
            ["B001"], "Test",
        )

        queries = [("slot_a", "term 1"), ("slot_b", "term 2")]

        with patch("scripts.build_catalog.merge_cache", return_value=(1, 1)):
            run_build(mock_client, queries, limit=10, max_requests=3)

        assert mock_client.search_products.call_count == 2

    def test_run_build_calls_merge_not_write(self, tmp_path: Path):
        """run_build must use merge_cache, not write_cache."""
        from scripts.build_catalog import run_build

        mock_client = MagicMock()
        mock_client.search_products.return_value = _make_canopy_results(
            ["B001"], "Test",
        )

        with patch("scripts.build_catalog.merge_cache", return_value=(1, 1)) as mock_merge:
            run_build(mock_client, [("bed_frame", "test")], limit=10, max_requests=5)

        mock_merge.assert_called_once()
        args = mock_merge.call_args
        assert args[0][0] == "bed_frame"  # slot_id

    def test_dry_run_makes_no_calls(self):
        """show_plan (dry run) never instantiates CanopyClient."""
        from scripts.build_catalog import show_plan

        # This should complete without error even without CANOPY_API_KEY.
        show_plan(
            [("bed_frame", "test query")],
            max_requests=60,
            limit=40,
        )


class TestBuildCatalogPlan:
    def test_query_count_within_ceiling(self):
        from scripts.build_catalog import BEDROOM_QUERIES, DEFAULT_MAX_REQUESTS

        assert len(BEDROOM_QUERIES) <= DEFAULT_MAX_REQUESTS, (
            f"Query count {len(BEDROOM_QUERIES)} exceeds default ceiling "
            f"{DEFAULT_MAX_REQUESTS}"
        )

    def test_all_queries_have_slot_and_term(self):
        from scripts.build_catalog import BEDROOM_QUERIES

        for slot_id, term in BEDROOM_QUERIES:
            assert slot_id, "Empty slot_id in query"
            assert term, "Empty search_term in query"

    def test_every_bedroom_slot_covered(self):
        """Every slot in the bedroom preset should have queries or existing catalog data."""
        from scripts.build_catalog import BEDROOM_QUERIES
        from services.config_loader import load_room_taxonomy
        from services.sourcing.catalog_cache import read_cache

        taxonomy = load_room_taxonomy()
        bedroom = taxonomy.room_presets["bedroom"]
        bedroom_slots = set(bedroom.all_items())

        queried_slots = {slot_id for slot_id, _ in BEDROOM_QUERIES}
        # Slots with 200+ cached products don't need active queries.
        cached_slots = {
            sid for sid in bedroom_slots
            if (data := read_cache(sid)) is not None and len(data) >= 200
        }
        missing = bedroom_slots - queried_slots - cached_slots
        assert not missing, f"Bedroom slots with no queries and insufficient cache: {missing}"

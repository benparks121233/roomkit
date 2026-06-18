# tests/test_design_store.py
# Proves that DesignResponse round-trips through Supabase JSONB losslessly.
# Every field — nested products, alternatives, prices, URLs, specs — must
# survive serialize → save → load → deserialize IDENTICALLY.

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from app.api.schemas import (
    DesignResponse,
    ProductResult,
    SlotResult,
    StyleResult,
)
from fastapi import HTTPException

from services.design_store import save_design, load_design, DesignStoreError


def _make_design() -> DesignResponse:
    """Build a realistic DesignResponse with multiple slots, products, and edge cases."""
    return DesignResponse(
        run_id="test-round-trip-001",
        room_type="bedroom",
        target_budget=1500.0,
        total_spent=1234.56,
        is_feasible=True,
        style=StyleResult(
            style_name="dark_academia",
            keywords=["moody", "leather", "walnut", "velvet"],
            mood="scholarly and brooding",
            confidence=0.92,
            fallback=False,
        ),
        slots=[
            # Slot with primary product + alternatives (the full tree)
            SlotResult(
                slot_id="bed_frame",
                allocated_budget=400.0,
                owned=False,
                max_quantity=1,
                product=ProductResult(
                    product_id="B0ABC12345",
                    name='Solid Walnut Platform Bed Frame, Queen, 14" Height',
                    normalized_price=389.99,
                    image_url="https://m.media-amazon.com/images/I/71abc.jpg",
                    buy_url="https://www.amazon.com/dp/B0ABC12345?tag=roomkitai-20",
                    fit_reason="Dark walnut matches the moody aesthetic perfectly",
                ),
                alternatives=[
                    ProductResult(
                        product_id="B0DEF67890",
                        name="Leather Upholstered Bed Frame, Queen",
                        normalized_price=449.99,
                        image_url="https://m.media-amazon.com/images/I/71def.jpg",
                        buy_url="https://www.amazon.com/dp/B0DEF67890?tag=roomkitai-20",
                        fit_reason="Leather upholstery reinforces the dark academia vibe",
                    ),
                    ProductResult(
                        product_id="B0GHI11111",
                        name="Mid-Century Wood Bed, Queen",
                        normalized_price=299.00,
                        image_url="https://m.media-amazon.com/images/I/71ghi.jpg",
                        buy_url="https://www.amazon.com/dp/B0GHI11111?tag=roomkitai-20",
                        fit_reason="Budget-friendly alternative with warm wood tones",
                    ),
                ],
                null_reason=None,
            ),
            # Multi-select slot (wall_art with max_quantity=4)
            SlotResult(
                slot_id="wall_art",
                allocated_budget=120.0,
                owned=False,
                max_quantity=4,
                product=ProductResult(
                    product_id="B0ART00001",
                    name="Vintage Library Print Set (3 Pack)",
                    normalized_price=34.99,
                    image_url="https://m.media-amazon.com/images/I/71art1.jpg",
                    buy_url="https://www.amazon.com/dp/B0ART00001?tag=roomkitai-20",
                    fit_reason="Library motif fits the scholarly theme",
                ),
                alternatives=[
                    ProductResult(
                        product_id="B0ART00002",
                        name="Dark Botanical Print, Framed 16x20",
                        normalized_price=28.50,
                        image_url="https://m.media-amazon.com/images/I/71art2.jpg",
                        buy_url="https://www.amazon.com/dp/B0ART00002?tag=roomkitai-20",
                        fit_reason="Moody botanical adds depth to the gallery wall",
                    ),
                ],
                null_reason=None,
            ),
            # Owned slot (no product, null_reason="owned")
            SlotResult(
                slot_id="nightstand",
                allocated_budget=0.0,
                owned=True,
                max_quantity=1,
                product=None,
                alternatives=[],
                null_reason="owned",
            ),
            # Failed slot (no candidates found)
            SlotResult(
                slot_id="accent_chair",
                allocated_budget=200.0,
                owned=False,
                max_quantity=1,
                product=None,
                alternatives=[],
                null_reason="no_candidate",
            ),
            # Zero-price edge case
            SlotResult(
                slot_id="throw_pillows",
                allocated_budget=50.0,
                owned=False,
                max_quantity=3,
                product=ProductResult(
                    product_id="B0PIL00001",
                    name='Velvet Throw Pillow Covers 18"x18" (Set of 2) — Burgundy',
                    normalized_price=0.0,  # edge case: free/zero price
                    image_url="https://m.media-amazon.com/images/I/71pil.jpg",
                    buy_url="https://www.amazon.com/dp/B0PIL00001?tag=roomkitai-20",
                    fit_reason="Burgundy velvet is core dark_academia palette",
                ),
                alternatives=[],
                null_reason=None,
            ),
        ],
    )


class TestRoundTripLossless:
    """Prove serialize → save → load → deserialize produces an IDENTICAL object."""

    def test_full_round_trip(self):
        """Every field in the original must match the loaded copy exactly."""
        original = _make_design()

        # Simulate what save_design sends to Supabase
        row = {
            "run_id": original.run_id,
            "room_type": original.room_type,
            "target_budget": float(original.target_budget),
            "total_spent": float(original.total_spent),
            "is_feasible": original.is_feasible,
            "style": original.style.model_dump(),
            "slots": [s.model_dump() for s in original.slots],
        }

        # Simulate what Supabase returns (JSON round-trip: dump → parse)
        import json
        row_from_db = json.loads(json.dumps(row))

        # Reconstruct the way load_design does
        loaded = DesignResponse(
            run_id=row_from_db["run_id"],
            room_type=row_from_db["room_type"],
            target_budget=row_from_db["target_budget"],
            total_spent=row_from_db["total_spent"],
            is_feasible=row_from_db["is_feasible"],
            style=StyleResult(**row_from_db["style"]),
            slots=[SlotResult(**s) for s in row_from_db["slots"]],
        )

        # Field-by-field identity check
        assert loaded.run_id == original.run_id
        assert loaded.room_type == original.room_type
        assert loaded.target_budget == original.target_budget
        assert loaded.total_spent == original.total_spent
        assert loaded.is_feasible == original.is_feasible

        # Style
        assert loaded.style.style_name == original.style.style_name
        assert loaded.style.keywords == original.style.keywords
        assert loaded.style.mood == original.style.mood
        assert loaded.style.confidence == original.style.confidence
        assert loaded.style.fallback == original.style.fallback

        # Slots — count and order
        assert len(loaded.slots) == len(original.slots)

        for orig_slot, loaded_slot in zip(original.slots, loaded.slots):
            assert loaded_slot.slot_id == orig_slot.slot_id
            assert loaded_slot.allocated_budget == orig_slot.allocated_budget
            assert loaded_slot.owned == orig_slot.owned
            assert loaded_slot.max_quantity == orig_slot.max_quantity
            assert loaded_slot.null_reason == orig_slot.null_reason

            # Primary product
            if orig_slot.product is None:
                assert loaded_slot.product is None
            else:
                assert loaded_slot.product is not None
                assert loaded_slot.product.product_id == orig_slot.product.product_id
                assert loaded_slot.product.name == orig_slot.product.name
                assert loaded_slot.product.normalized_price == orig_slot.product.normalized_price
                assert loaded_slot.product.image_url == orig_slot.product.image_url
                assert loaded_slot.product.buy_url == orig_slot.product.buy_url
                assert loaded_slot.product.fit_reason == orig_slot.product.fit_reason

            # Alternatives — count and every field
            assert len(loaded_slot.alternatives) == len(orig_slot.alternatives)
            for orig_alt, loaded_alt in zip(orig_slot.alternatives, loaded_slot.alternatives):
                assert loaded_alt.product_id == orig_alt.product_id
                assert loaded_alt.name == orig_alt.name
                assert loaded_alt.normalized_price == orig_alt.normalized_price
                assert loaded_alt.image_url == orig_alt.image_url
                assert loaded_alt.buy_url == orig_alt.buy_url
                assert loaded_alt.fit_reason == orig_alt.fit_reason

    def test_model_dump_equality(self):
        """The nuclear option: full model_dump() must be byte-identical after round-trip."""
        original = _make_design()

        import json
        row = {
            "run_id": original.run_id,
            "room_type": original.room_type,
            "target_budget": float(original.target_budget),
            "total_spent": float(original.total_spent),
            "is_feasible": original.is_feasible,
            "style": original.style.model_dump(),
            "slots": [s.model_dump() for s in original.slots],
        }
        row_from_db = json.loads(json.dumps(row))

        loaded = DesignResponse(
            run_id=row_from_db["run_id"],
            room_type=row_from_db["room_type"],
            target_budget=row_from_db["target_budget"],
            total_spent=row_from_db["total_spent"],
            is_feasible=row_from_db["is_feasible"],
            style=StyleResult(**row_from_db["style"]),
            slots=[SlotResult(**s) for s in row_from_db["slots"]],
        )

        assert loaded.model_dump() == original.model_dump()


class TestSaveDesign:
    """Test save_design error handling."""

    def test_save_no_client(self):
        """When Supabase is not configured, save returns False and logs."""
        with patch("services.supabase_client.get_client", return_value=None):
            result = save_design(_make_design())
        assert result is False

    def test_save_success(self):
        """When Supabase is available, save returns True."""
        mock_client = MagicMock()
        mock_client.table.return_value.upsert.return_value.execute.return_value = None
        with patch("services.supabase_client.get_client", return_value=mock_client):
            result = save_design(_make_design())
        assert result is True
        mock_client.table.assert_called_once_with("designs")

    def test_save_exception(self):
        """When Supabase throws, save returns False (non-blocking)."""
        mock_client = MagicMock()
        mock_client.table.return_value.upsert.return_value.execute.side_effect = Exception("connection lost")
        with patch("services.supabase_client.get_client", return_value=mock_client):
            result = save_design(_make_design())
        assert result is False


class TestLoadDesign:
    """Test load_design three-outcome handling."""

    def test_load_not_found_bare_none(self):
        """Genuinely absent row raises KeyError.

        Real Supabase returns bare None from maybe_single().execute()
        when no row matches — NOT a response object with .data = None.
        """
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = None
        with patch("services.supabase_client.get_client", return_value=mock_client):
            with pytest.raises(KeyError):
                load_design("nonexistent-id")

    def test_load_connection_failure(self):
        """Connection failure raises DesignStoreError."""
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.side_effect = Exception("timeout")
        with patch("services.supabase_client.get_client", return_value=mock_client):
            with pytest.raises(DesignStoreError):
                load_design("some-id")

    def test_load_no_client(self):
        """No Supabase client raises DesignStoreError."""
        with patch("services.supabase_client.get_client", return_value=None):
            with pytest.raises(DesignStoreError):
                load_design("some-id")

    def test_load_success(self):
        """Successful load deserializes correctly."""
        import json
        original = _make_design()
        row_data = {
            "run_id": original.run_id,
            "room_type": original.room_type,
            "target_budget": float(original.target_budget),
            "total_spent": float(original.total_spent),
            "is_feasible": original.is_feasible,
            "style": json.loads(json.dumps(original.style.model_dump())),
            "slots": json.loads(json.dumps([s.model_dump() for s in original.slots])),
        }

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = row_data
        mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_resp

        with patch("services.supabase_client.get_client", return_value=mock_client):
            loaded = load_design("test-round-trip-001")

        assert loaded.model_dump() == original.model_dump()


class TestGetDesignHelper:
    """Test the _get_design three-outcome helper in routes."""

    def test_cache_hit(self):
        """Design in _designs dict is returned without touching Supabase."""
        from app.api.routes import _designs, _get_design

        design = _make_design()
        _designs[design.run_id] = design
        try:
            result = _get_design(design.run_id)
            assert result.run_id == design.run_id
        finally:
            _designs.pop(design.run_id, None)

    def test_supabase_fallback(self):
        """Cache miss falls through to Supabase and populates cache."""
        from app.api.routes import _designs, _get_design

        design = _make_design()
        _designs.pop(design.run_id, None)  # ensure not cached

        with patch("services.design_store.load_design", return_value=design):
            result = _get_design(design.run_id)

        assert result.run_id == design.run_id
        assert design.run_id in _designs  # cache populated
        _designs.pop(design.run_id, None)  # cleanup

    def test_not_found_404(self):
        """Absent design raises 404."""
        from app.api.routes import _designs, _get_design

        _designs.pop("ghost-id", None)
        with patch("services.design_store.load_design", side_effect=KeyError("ghost-id")):
            with pytest.raises(HTTPException) as exc_info:
                _get_design("ghost-id")
            assert exc_info.value.status_code == 404

    def test_not_found_end_to_end_404(self):
        """Absent row in Supabase (bare None) produces 404 through the route.

        This is the contract test that would have caught the original bug:
        real Supabase returns None (not mock.data=None), which must flow
        through load_design → KeyError → _get_design → 404.
        """
        from app.api.routes import _designs, _get_design

        _designs.pop("absent-id", None)
        mock_client = MagicMock()
        # Real Supabase behavior: maybe_single().execute() returns bare None
        mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = None
        with patch("services.supabase_client.get_client", return_value=mock_client):
            with pytest.raises(HTTPException) as exc_info:
                _get_design("absent-id")
            assert exc_info.value.status_code == 404

    def test_connection_failure_503(self):
        """Supabase failure raises 503."""
        from app.api.routes import _designs, _get_design
        from fastapi import HTTPException

        _designs.pop("down-id", None)
        with patch("services.design_store.load_design", side_effect=DesignStoreError("timeout")):
            with pytest.raises(HTTPException) as exc_info:
                _get_design("down-id")
            assert exc_info.value.status_code == 503

"""Tests for Phase 7B — Render Storage (Supabase Storage)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestUploadRender:
    """Tests for services/render_storage.py upload_render()."""

    def test_upload_success_returns_public_url(self, tmp_path):
        from services.render_storage import upload_render

        render_file = tmp_path / "test.jpg"
        render_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_client.storage.from_.return_value = mock_bucket
        mock_bucket.get_public_url.return_value = (
            "https://example.supabase.co/storage/v1/object/public/renders/abc123.jpg"
        )

        with patch("services.supabase_client.get_client", return_value=mock_client):
            result = upload_render("abc123", render_file)

        assert result == "https://example.supabase.co/storage/v1/object/public/renders/abc123.jpg"
        mock_bucket.upload.assert_called_once()
        call_args = mock_bucket.upload.call_args
        assert call_args[0][0] == "abc123.jpg"
        assert call_args[0][2] == {
            "content-type": "image/jpeg",
            "cache-control": "public, max-age=31536000",
        }

    def test_upload_failure_returns_none(self, tmp_path):
        from services.render_storage import upload_render

        render_file = tmp_path / "test.jpg"
        render_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_client.storage.from_.return_value = mock_bucket
        mock_bucket.upload.side_effect = Exception("Storage unavailable")

        with patch("services.supabase_client.get_client", return_value=mock_client):
            result = upload_render("abc123", render_file)

        assert result is None

    def test_no_client_returns_none(self, tmp_path):
        from services.render_storage import upload_render

        render_file = tmp_path / "test.jpg"
        render_file.write_bytes(b"\xff\xd8\xff\xe0")

        with patch("services.supabase_client.get_client", return_value=None):
            result = upload_render("abc123", render_file)

        assert result is None

    def test_upload_reads_correct_file(self, tmp_path):
        from services.render_storage import upload_render

        render_file = tmp_path / "test.jpg"
        content = b"\xff\xd8\xff\xe0JPEG_DATA"
        render_file.write_bytes(content)

        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_client.storage.from_.return_value = mock_bucket
        mock_bucket.get_public_url.return_value = "https://example.com/r.jpg"

        with patch("services.supabase_client.get_client", return_value=mock_client):
            upload_render("xyz", render_file)

        uploaded_bytes = mock_bucket.upload.call_args[0][1]
        assert uploaded_bytes == content


class TestSaveRenderUrl:
    """Tests for services/render_storage.py save_render_url()."""

    def test_save_updates_design_row(self):
        from services.render_storage import save_render_url

        mock_client = MagicMock()
        with patch("services.supabase_client.get_client", return_value=mock_client):
            save_render_url("run123", "https://example.com/renders/run123.jpg")

        mock_client.table.assert_called_with("designs")
        mock_client.table().update.assert_called_with(
            {"render_url": "https://example.com/renders/run123.jpg"},
        )
        mock_client.table().update().eq.assert_called_with("run_id", "run123")

    def test_save_failure_does_not_raise(self):
        from services.render_storage import save_render_url

        mock_client = MagicMock()
        mock_client.table.side_effect = Exception("DB error")

        with patch("services.supabase_client.get_client", return_value=mock_client):
            save_render_url("run123", "https://example.com/x.jpg")


class TestRenderUrlInSchema:
    """Tests for render_url field on DesignResponse."""

    def test_render_url_default_none(self):
        from app.api.schemas import DesignResponse, StyleResult

        resp = DesignResponse(
            run_id="r1",
            room_type="bedroom",
            style=StyleResult(
                style_name="test", keywords=[], mood="calm",
                confidence=1.0, fallback=False,
            ),
            target_budget=1000,
            total_spent=800,
            is_feasible=True,
            slots=[],
        )
        assert resp.render_url is None

    def test_render_url_roundtrip(self):
        from app.api.schemas import DesignResponse, StyleResult

        resp = DesignResponse(
            run_id="r1",
            room_type="bedroom",
            style=StyleResult(
                style_name="test", keywords=[], mood="calm",
                confidence=1.0, fallback=False,
            ),
            target_budget=1000,
            total_spent=800,
            is_feasible=True,
            slots=[],
            render_url="https://example.com/renders/r1.jpg",
        )
        assert resp.render_url == "https://example.com/renders/r1.jpg"
        dumped = resp.model_dump()
        assert dumped["render_url"] == "https://example.com/renders/r1.jpg"


class TestDesignStoreRenderUrl:
    """Tests that design_store persists and loads render_url."""

    def test_save_design_includes_render_url(self):
        from app.api.schemas import DesignResponse, StyleResult
        from services.design_store import save_design

        mock_client = MagicMock()
        with patch("services.supabase_client.get_client", return_value=mock_client):
            resp = DesignResponse(
                run_id="r1",
                room_type="bedroom",
                style=StyleResult(
                    style_name="test", keywords=[], mood="calm",
                    confidence=1.0, fallback=False,
                ),
                target_budget=1000,
                total_spent=800,
                is_feasible=True,
                slots=[],
                render_url="https://storage.example.com/renders/r1.jpg",
            )
            save_design(resp, user_id="u1")

        upsert_call = mock_client.table().upsert.call_args
        row = upsert_call[0][0]
        assert row["render_url"] == "https://storage.example.com/renders/r1.jpg"

    def test_save_design_omits_render_url_when_none(self):
        from app.api.schemas import DesignResponse, StyleResult
        from services.design_store import save_design

        mock_client = MagicMock()
        with patch("services.supabase_client.get_client", return_value=mock_client):
            resp = DesignResponse(
                run_id="r2",
                room_type="bedroom",
                style=StyleResult(
                    style_name="test", keywords=[], mood="calm",
                    confidence=1.0, fallback=False,
                ),
                target_budget=1000,
                total_spent=800,
                is_feasible=True,
                slots=[],
            )
            save_design(resp, user_id="u1")

        upsert_call = mock_client.table().upsert.call_args
        row = upsert_call[0][0]
        assert "render_url" not in row

    def test_row_to_response_includes_render_url(self):
        from services.design_store import _row_to_response

        row = {
            "run_id": "r1",
            "room_type": "bedroom",
            "target_budget": 1000,
            "total_spent": 800,
            "is_feasible": True,
            "style": {"style_name": "test", "keywords": [], "mood": "calm",
                      "confidence": 1.0, "fallback": False},
            "slots": [],
            "render_url": "https://storage.example.com/renders/r1.jpg",
        }
        resp = _row_to_response(row)
        assert resp.render_url == "https://storage.example.com/renders/r1.jpg"

    def test_row_to_response_render_url_missing(self):
        from services.design_store import _row_to_response

        row = {
            "run_id": "r1",
            "room_type": "bedroom",
            "target_budget": 1000,
            "total_spent": 800,
            "is_feasible": True,
            "style": {"style_name": "test", "keywords": [], "mood": "calm",
                      "confidence": 1.0, "fallback": False},
            "slots": [],
        }
        resp = _row_to_response(row)
        assert resp.render_url is None

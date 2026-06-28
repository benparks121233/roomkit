"""Tests for async render: 202 polling, cache hit 200, sync fallback, status endpoint."""

from __future__ import annotations

import os
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("TESTING", "1")

from app.api.routes import _designs, _render_worker
from app.api.schemas import DesignResponse, SlotResult, StyleResult
from app.auth import get_current_user
from app.main import app

_USER = {"user_id": "render-user-1", "email": "r@test.com", "token": "tok"}


def _make_design(run_id: str, finalized: bool = True) -> DesignResponse:
    d = DesignResponse(
        run_id=run_id,
        room_type="bedroom",
        style=StyleResult(
            style_name="warm_minimalist",
            keywords=["wood"],
            mood="calm",
            confidence=0.9,
            fallback=False,
        ),
        target_budget=1000.0,
        total_spent=800.0,
        is_feasible=True,
        slots=[],
        user_id=_USER["user_id"],
    )
    if finalized:
        d.finalized_at = "2026-01-01T00:00:00Z"
    return d


@pytest.fixture(autouse=True)
def _setup():
    _designs.clear()
    prev = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: _USER
    yield
    _designs.clear()
    if prev is not None:
        app.dependency_overrides[get_current_user] = prev
    else:
        app.dependency_overrides.pop(get_current_user, None)


client = TestClient(app)


class TestCacheHit:
    """When render already exists on disk, return 200 immediately."""

    @patch("services.render_service.render_exists", return_value=True)
    def test_returns_200_with_complete(self, _mock_exists):
        _designs["run-cached"] = _make_design("run-cached")
        resp = client.post("/design/run-cached/render", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "complete"
        assert body["cached"] is True
        assert body["render_url"] == "/renders/run-cached.jpg"

    @patch("services.render_service.render_exists", return_value=True)
    def test_cache_hit_no_redis_needed(self, _mock_exists):
        """Cache hit path doesn't touch Redis at all."""
        _designs["run-cached2"] = _make_design("run-cached2")
        with patch("services.redis_client.get_redis", return_value=None):
            resp = client.post("/design/run-cached2/render", json={})
        assert resp.status_code == 200
        assert resp.json()["status"] == "complete"


class TestAsyncRender:
    """When Redis is available and no cache hit, return 202 with job_id."""

    @patch("services.render_service.render_exists", return_value=False)
    @patch("services.render_service.render_room", return_value="/fake/path.jpg")
    def test_returns_202_with_job_id(self, _mock_render, _mock_exists):
        _designs["run-async"] = _make_design("run-async")
        mock_redis = MagicMock()
        with patch("services.redis_client.get_redis", return_value=mock_redis):
            resp = client.post("/design/run-async/render", json={})
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "pending"
        assert "job_id" in body
        assert body["run_id"] == "run-async"
        # Redis should have been written to
        mock_redis.hset.assert_called()
        mock_redis.expire.assert_called()

    @patch("services.render_service.render_exists", return_value=False)
    def test_not_finalized_returns_400(self, _mock_exists):
        _designs["run-unfin"] = _make_design("run-unfin", finalized=False)
        resp = client.post("/design/run-unfin/render", json={})
        assert resp.status_code == 400
        assert "finalized" in resp.json()["detail"].lower()


class TestSyncFallback:
    """When Redis is unavailable, fall back to synchronous render."""

    @patch("services.render_service.render_exists", return_value=False)
    @patch("services.render_service.render_room", return_value="/fake/path.jpg")
    def test_sync_returns_200(self, _mock_render, _mock_exists):
        _designs["run-sync"] = _make_design("run-sync")
        with patch("services.redis_client.get_redis", return_value=None):
            resp = client.post("/design/run-sync/render", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "complete"
        assert body["cached"] is False
        assert body["render_url"] == "/renders/run-sync.jpg"

    @patch("services.render_service.render_exists", return_value=False)
    @patch("services.render_service.render_room", return_value=None)
    def test_sync_failure_returns_500(self, _mock_render, _mock_exists):
        _designs["run-fail"] = _make_design("run-fail")
        with patch("services.redis_client.get_redis", return_value=None):
            resp = client.post("/design/run-fail/render", json={})
        assert resp.status_code == 500


class TestRenderWorker:
    """Test the background _render_worker function directly."""

    @patch("services.render_service.render_room", return_value="/fake/path.jpg")
    def test_updates_redis_to_complete(self, _mock_render):
        mock_redis = MagicMock()
        with patch("services.redis_client.get_redis", return_value=mock_redis):
            _render_worker(
                job_id="job-1", run_id="run-w1", room_type="bedroom",
                style_name="warm_minimalist", mood="calm", keywords=["wood"],
                products={}, user_id="u1",
            )
        calls = [str(c) for c in mock_redis.hset.call_args_list]
        assert any("rendering" in c for c in calls)
        assert any("complete" in c for c in calls)

    @patch("services.render_service.render_room", return_value=None)
    def test_sets_failed_on_none_return(self, _mock_render):
        mock_redis = MagicMock()
        with patch("services.redis_client.get_redis", return_value=mock_redis):
            _render_worker(
                job_id="job-2", run_id="run-w2", room_type="bedroom",
                style_name="warm_minimalist", mood="calm", keywords=["wood"],
                products={}, user_id="u1",
            )
        calls = [str(c) for c in mock_redis.hset.call_args_list]
        assert any("failed" in c for c in calls)

    @patch("services.render_service.render_room", side_effect=RuntimeError("boom"))
    def test_sets_failed_on_exception(self, _mock_render):
        mock_redis = MagicMock()
        with patch("services.redis_client.get_redis", return_value=mock_redis):
            _render_worker(
                job_id="job-3", run_id="run-w3", room_type="bedroom",
                style_name="warm_minimalist", mood="calm", keywords=["wood"],
                products={}, user_id="u1",
            )
        calls = [str(c) for c in mock_redis.hset.call_args_list]
        assert any("failed" in c for c in calls)


class TestRenderStatusEndpoint:
    """GET /design/{run_id}/render/status."""

    @patch("services.render_service.render_exists", return_value=True)
    def test_complete_when_file_exists(self, _mock_exists):
        _designs["run-s1"] = _make_design("run-s1")
        resp = client.get("/design/run-s1/render/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "complete"
        assert resp.json()["render_url"] == "/renders/run-s1.jpg"

    @patch("services.render_service.render_exists", return_value=False)
    def test_unknown_without_job_id(self, _mock_exists):
        _designs["run-s2"] = _make_design("run-s2")
        resp = client.get("/design/run-s2/render/status")
        assert resp.json()["status"] == "unknown"

    @patch("services.render_service.render_exists", return_value=False)
    def test_returns_redis_status(self, _mock_exists):
        _designs["run-s3"] = _make_design("run-s3")
        mock_redis = MagicMock()
        mock_redis.hgetall.return_value = {"status": "rendering", "run_id": "run-s3"}
        with patch("services.redis_client.get_redis", return_value=mock_redis):
            resp = client.get("/design/run-s3/render/status?job_id=job-abc")
        assert resp.json()["status"] == "rendering"

    @patch("services.render_service.render_exists", return_value=False)
    def test_returns_complete_with_url(self, _mock_exists):
        _designs["run-s4"] = _make_design("run-s4")
        mock_redis = MagicMock()
        mock_redis.hgetall.return_value = {
            "status": "complete",
            "render_url": "/renders/run-s4.jpg",
        }
        with patch("services.redis_client.get_redis", return_value=mock_redis):
            resp = client.get("/design/run-s4/render/status?job_id=job-xyz")
        body = resp.json()
        assert body["status"] == "complete"
        assert body["render_url"] == "/renders/run-s4.jpg"

    @patch("services.render_service.render_exists", return_value=False)
    def test_returns_failed_with_error(self, _mock_exists):
        _designs["run-s5"] = _make_design("run-s5")
        mock_redis = MagicMock()
        mock_redis.hgetall.return_value = {
            "status": "failed",
            "error": "Room render generation failed",
        }
        with patch("services.redis_client.get_redis", return_value=mock_redis):
            resp = client.get("/design/run-s5/render/status?job_id=job-err")
        body = resp.json()
        assert body["status"] == "failed"
        assert body["error"] == "Room render generation failed"

    @patch("services.render_service.render_exists", return_value=False)
    def test_unknown_when_redis_unavailable(self, _mock_exists):
        _designs["run-s6"] = _make_design("run-s6")
        with patch("services.redis_client.get_redis", return_value=None):
            resp = client.get("/design/run-s6/render/status?job_id=job-noredis")
        assert resp.json()["status"] == "unknown"

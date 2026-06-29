"""Tests for sub-phase 6: Redis counting semaphore + local fallback."""

from __future__ import annotations

import os
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("TESTING", "1")


# ---------------------------------------------------------------------------
# Redis path: acquire / release / cap / crash safety
# ---------------------------------------------------------------------------

class TestRedisAcquireRelease:
    """Redis-backed counting semaphore."""

    def test_acquire_under_cap(self):
        mock_redis = MagicMock()
        mock_redis.incrby.return_value = 5  # well under default cap of 30

        with patch("services.redis_client.get_redis", return_value=mock_redis):
            from services.concurrency import acquire_llm_slots
            assert acquire_llm_slots(5) is True

        mock_redis.incrby.assert_called_once_with("roomkit:llm_active", 5)
        mock_redis.expire.assert_called_once_with("roomkit:llm_active", 120)

    def test_release_decrements(self):
        mock_redis = MagicMock()
        mock_redis.decrby.return_value = 10

        with patch("services.redis_client.get_redis", return_value=mock_redis):
            from services.concurrency import release_llm_slots
            release_llm_slots(5)

        mock_redis.decrby.assert_called_once_with("roomkit:llm_active", 5)

    def test_release_floors_at_zero(self):
        mock_redis = MagicMock()
        mock_redis.decrby.return_value = -3  # went negative (crash recovery)

        with patch("services.redis_client.get_redis", return_value=mock_redis):
            from services.concurrency import release_llm_slots
            release_llm_slots(5)

        mock_redis.set.assert_called_once_with("roomkit:llm_active", 0)
        mock_redis.expire.assert_called_once()


class TestRedisCapEnforcement:
    """Acquire respects the concurrency cap."""

    def test_over_cap_backs_off_then_succeeds(self):
        mock_redis = MagicMock()
        # First attempt: over cap (returns 35, cap is 30). Second: under cap.
        mock_redis.incrby.side_effect = [35, 10]

        with patch("services.redis_client.get_redis", return_value=mock_redis), \
             patch("services.concurrency.time.sleep") as mock_sleep:
            from services.concurrency import acquire_llm_slots
            assert acquire_llm_slots(10) is True

        assert mock_redis.incrby.call_count == 2
        # First attempt over cap -> decrby to undo
        mock_redis.decrby.assert_called_once_with("roomkit:llm_active", 10)
        mock_sleep.assert_called_once()

    def test_over_cap_timeout_returns_false(self):
        mock_redis = MagicMock()
        # Always over cap
        mock_redis.incrby.return_value = 50

        with patch("services.redis_client.get_redis", return_value=mock_redis), \
             patch("services.concurrency.time.sleep"):
            from services.concurrency import acquire_llm_slots
            result = acquire_llm_slots(15, timeout=1.0)

        assert result is False


class TestRedisCrashSafety:
    """Key TTL prevents leaked slots from crashed workers."""

    def test_ttl_set_on_acquire(self):
        mock_redis = MagicMock()
        mock_redis.incrby.return_value = 5

        with patch("services.redis_client.get_redis", return_value=mock_redis):
            from services.concurrency import acquire_llm_slots
            acquire_llm_slots(5)

        mock_redis.expire.assert_called_with("roomkit:llm_active", 120)

    def test_redis_exception_falls_back_to_local(self):
        """If Redis raises during acquire, fall back to local semaphore."""
        mock_redis = MagicMock()
        mock_redis.incrby.side_effect = Exception("connection lost")

        with patch("services.redis_client.get_redis", return_value=mock_redis):
            import services.concurrency as sc
            sc._local_semaphore = None  # reset
            with patch.dict(os.environ, {"LLM_CONCURRENCY_CAP": "30", "UVICORN_WORKERS": "1"}):
                result = sc.acquire_llm_slots(5)

        assert result is True
        sc._local_semaphore = None  # cleanup


# ---------------------------------------------------------------------------
# Local fallback: bounded threading.Semaphore
# ---------------------------------------------------------------------------

class TestLocalFallback:
    """When Redis is unavailable, local semaphore caps per-worker."""

    def test_local_semaphore_bounded(self):
        """CAP=30, WORKERS=2 -> 15 slots per worker."""
        import services.concurrency as sc
        sc._local_semaphore = None

        with patch("services.redis_client.get_redis", return_value=None), \
             patch.dict(os.environ, {"LLM_CONCURRENCY_CAP": "30", "UVICORN_WORKERS": "2"}):
            sc._local_semaphore = None  # force re-creation
            # Acquire 15 should succeed
            assert sc.acquire_llm_slots(15) is True
            sc.release_llm_slots(15)

        sc._local_semaphore = None

    def test_local_semaphore_not_unlimited(self):
        """Local fallback is NOT 'return True' — it actually blocks."""
        import services.concurrency as sc
        sc._local_semaphore = None

        with patch("services.redis_client.get_redis", return_value=None), \
             patch.dict(os.environ, {"LLM_CONCURRENCY_CAP": "4", "UVICORN_WORKERS": "1"}):
            sc._local_semaphore = None
            # Acquire 4 (full cap)
            assert sc.acquire_llm_slots(4) is True
            # Acquire 1 more should timeout (all slots taken)
            assert sc.acquire_llm_slots(1, timeout=0.5) is False
            sc.release_llm_slots(4)

        sc._local_semaphore = None

    def test_local_acquire_release_cycle(self):
        """Acquire, release, acquire again — slots are reusable."""
        import services.concurrency as sc
        sc._local_semaphore = None

        with patch("services.redis_client.get_redis", return_value=None), \
             patch.dict(os.environ, {"LLM_CONCURRENCY_CAP": "2", "UVICORN_WORKERS": "1"}):
            sc._local_semaphore = None
            assert sc.acquire_llm_slots(2) is True
            sc.release_llm_slots(2)
            assert sc.acquire_llm_slots(2) is True
            sc.release_llm_slots(2)

        sc._local_semaphore = None

    def test_local_per_worker_sizing(self):
        """Verify per-worker calculation: CAP=30, WORKERS=3 -> 10."""
        import services.concurrency as sc
        sc._local_semaphore = None

        with patch("services.redis_client.get_redis", return_value=None), \
             patch.dict(os.environ, {"LLM_CONCURRENCY_CAP": "30", "UVICORN_WORKERS": "3"}):
            sc._local_semaphore = None
            assert sc.acquire_llm_slots(10) is True
            assert sc.acquire_llm_slots(1, timeout=0.5) is False
            sc.release_llm_slots(10)

        sc._local_semaphore = None

    def test_local_minimum_one_slot(self):
        """Even with extreme settings, at least 1 slot is available."""
        import services.concurrency as sc
        sc._local_semaphore = None

        with patch("services.redis_client.get_redis", return_value=None), \
             patch.dict(os.environ, {"LLM_CONCURRENCY_CAP": "1", "UVICORN_WORKERS": "10"}):
            sc._local_semaphore = None
            # 1 // 10 = 0, but floored to 1
            assert sc.acquire_llm_slots(1) is True
            sc.release_llm_slots(1)

        sc._local_semaphore = None


# ---------------------------------------------------------------------------
# Integration: 503 on timeout in create_design
# ---------------------------------------------------------------------------

class TestRouteIntegration:
    """Semaphore timeout produces 503 in the design endpoint."""

    def test_503_when_semaphore_full(self):
        from app.auth import get_current_user
        from app.main import app
        from fastapi.testclient import TestClient

        _user = {"user_id": "00000000-0000-0000-0000-000000000002", "email": "s@test.com", "token": "tok"}
        app.dependency_overrides[get_current_user] = lambda: _user

        with patch("services.supabase_client.get_client", return_value=None), \
             patch("services.concurrency.acquire_llm_slots", return_value=False):
            client = TestClient(app)
            resp = client.post("/design", json={
                "room_type": "bedroom",
                "budget": 2000,
                "style_description": "warm minimalist",
            })

        assert resp.status_code == 503
        assert "busy" in resp.json()["detail"].lower()

        app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Render semaphore: Redis + local fallback
# ---------------------------------------------------------------------------

class TestRenderSemaphoreRedis:
    """Redis-backed render concurrency semaphore (1 slot per render)."""

    def test_acquire_under_cap(self):
        mock_redis = MagicMock()
        mock_redis.incrby.return_value = 2  # under default cap of 4

        with patch("services.redis_client.get_redis", return_value=mock_redis):
            from services.concurrency import acquire_render_slot
            assert acquire_render_slot() is True

        mock_redis.incrby.assert_called_once_with("roomkit:render_active", 1)
        mock_redis.expire.assert_called_once_with("roomkit:render_active", 300)

    def test_release_decrements(self):
        mock_redis = MagicMock()
        mock_redis.decrby.return_value = 1

        with patch("services.redis_client.get_redis", return_value=mock_redis):
            from services.concurrency import release_render_slot
            release_render_slot()

        mock_redis.decrby.assert_called_once_with("roomkit:render_active", 1)

    def test_release_floors_at_zero(self):
        mock_redis = MagicMock()
        mock_redis.decrby.return_value = -1

        with patch("services.redis_client.get_redis", return_value=mock_redis):
            from services.concurrency import release_render_slot
            release_render_slot()

        mock_redis.set.assert_called_once_with("roomkit:render_active", 0)

    def test_over_cap_backs_off_then_succeeds(self):
        mock_redis = MagicMock()
        mock_redis.incrby.side_effect = [5, 3]  # first over cap=4, second under

        with patch("services.redis_client.get_redis", return_value=mock_redis), \
             patch("services.concurrency.time.sleep"):
            from services.concurrency import acquire_render_slot
            assert acquire_render_slot() is True

        assert mock_redis.incrby.call_count == 2
        mock_redis.decrby.assert_called_once_with("roomkit:render_active", 1)

    def test_over_cap_timeout_returns_false(self):
        mock_redis = MagicMock()
        mock_redis.incrby.return_value = 10  # always over cap

        with patch("services.redis_client.get_redis", return_value=mock_redis), \
             patch("services.concurrency.time.sleep"):
            from services.concurrency import acquire_render_slot
            # Pass short timeout — default is 600s (renders queue, not fail)
            assert acquire_render_slot(timeout=1.0) is False

    def test_redis_exception_falls_back_to_local(self):
        mock_redis = MagicMock()
        mock_redis.incrby.side_effect = Exception("connection lost")

        with patch("services.redis_client.get_redis", return_value=mock_redis):
            import services.concurrency as sc
            sc._render_local_semaphore = None
            with patch.dict(os.environ, {"RENDER_CONCURRENCY_CAP": "4", "UVICORN_WORKERS": "1"}):
                result = sc.acquire_render_slot()

        assert result is True
        sc._render_local_semaphore = None


class TestRenderSemaphoreLocal:
    """Local fallback for render semaphore."""

    def test_local_bounded(self):
        import services.concurrency as sc
        sc._render_local_semaphore = None

        with patch("services.redis_client.get_redis", return_value=None), \
             patch.dict(os.environ, {"RENDER_CONCURRENCY_CAP": "2", "UVICORN_WORKERS": "1"}):
            sc._render_local_semaphore = None
            assert sc.acquire_render_slot() is True
            assert sc.acquire_render_slot() is True
            assert sc.acquire_render_slot(timeout=0.3) is False
            sc.release_render_slot()
            sc.release_render_slot()

        sc._render_local_semaphore = None

    def test_local_per_worker_sizing(self):
        import services.concurrency as sc
        sc._render_local_semaphore = None

        with patch("services.redis_client.get_redis", return_value=None), \
             patch.dict(os.environ, {"RENDER_CONCURRENCY_CAP": "4", "UVICORN_WORKERS": "2"}):
            sc._render_local_semaphore = None
            # 4 // 2 = 2 per worker
            assert sc.acquire_render_slot() is True
            assert sc.acquire_render_slot() is True
            assert sc.acquire_render_slot(timeout=0.3) is False
            sc.release_render_slot()
            sc.release_render_slot()

        sc._render_local_semaphore = None

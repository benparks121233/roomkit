"""Tests for Redis client module and health endpoint."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _reset_redis_singleton():
    """Reset the redis_client module singleton between tests."""
    import services.redis_client as mod
    orig_client = mod._client
    orig_init = mod._initialized
    yield
    mod._client = orig_client
    mod._initialized = orig_init


class TestGetRedis:
    def test_returns_none_when_url_not_set(self):
        import services.redis_client as mod
        mod._initialized = False
        mod._client = None
        with patch.dict("os.environ", {}, clear=True):
            result = mod.get_redis()
        assert result is None
        assert mod._initialized is True

    def test_returns_client_when_url_set(self):
        import services.redis_client as mod
        mod._initialized = False
        mod._client = None
        mock_redis_cls = MagicMock()
        mock_client = MagicMock()
        mock_redis_cls.from_url.return_value = mock_client
        with patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379/0"}):
            with patch("redis.Redis", mock_redis_cls):
                result = mod.get_redis()
        assert result is mock_client
        mock_client.ping.assert_called_once()

    def test_returns_none_on_connection_failure(self):
        import services.redis_client as mod
        mod._initialized = False
        mod._client = None
        mock_redis_cls = MagicMock()
        mock_client = MagicMock()
        mock_client.ping.side_effect = ConnectionError("refused")
        mock_redis_cls.from_url.return_value = mock_client
        with patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379/0"}):
            with patch("redis.Redis", mock_redis_cls):
                result = mod.get_redis()
        assert result is None

    def test_caches_after_first_call(self):
        import services.redis_client as mod
        mod._initialized = True
        sentinel = object()
        mod._client = sentinel
        assert mod.get_redis() is sentinel


class TestRedisHealthEndpoint:
    def test_not_configured(self):
        from app.main import app
        with patch("services.redis_client.get_redis", return_value=None):
            client = TestClient(app)
            resp = client.get("/health/redis")
        assert resp.status_code == 200
        assert resp.json()["status"] == "not_configured"

    def test_ok(self):
        from app.main import app
        mock_r = MagicMock()
        with patch("services.redis_client.get_redis", return_value=mock_r):
            client = TestClient(app)
            resp = client.get("/health/redis")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        mock_r.ping.assert_called_once()

    def test_error(self):
        from app.main import app
        mock_r = MagicMock()
        mock_r.ping.side_effect = ConnectionError("connection lost")
        with patch("services.redis_client.get_redis", return_value=mock_r):
            client = TestClient(app)
            resp = client.get("/health/redis")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "error"
        assert "connection lost" in body["detail"]

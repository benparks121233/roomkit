"""Tests for rate limiter Redis/fallback configuration."""

from unittest.mock import patch

from app.rate_limit import _get_real_ip


class TestGetRealIp:
    def test_uses_x_forwarded_for(self):
        from starlette.requests import Request
        from starlette.datastructures import Headers

        scope = {"type": "http", "headers": [(b"x-forwarded-for", b"1.2.3.4, 5.6.7.8")]}
        request = Request(scope)
        assert _get_real_ip(request) == "1.2.3.4"

    def test_falls_back_to_client_host(self):
        from starlette.requests import Request

        scope = {"type": "http", "headers": [], "client": ("9.9.9.9", 1234)}
        request = Request(scope)
        assert _get_real_ip(request) == "9.9.9.9"


class TestLimiterConfig:
    def test_uses_redis_when_url_set(self):
        with patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379/0"}):
            import importlib
            import app.rate_limit as mod
            importlib.reload(mod)
            assert mod.limiter._storage_uri == "redis://localhost:6379/0"

    def test_uses_memory_when_url_not_set(self):
        with patch.dict("os.environ", {}, clear=False):
            import os
            old = os.environ.pop("REDIS_URL", None)
            try:
                import importlib
                import app.rate_limit as mod
                importlib.reload(mod)
                assert mod.limiter._storage_uri == "memory://"
            finally:
                if old is not None:
                    os.environ["REDIS_URL"] = old

    def test_fallback_enabled(self):
        import app.rate_limit as mod
        assert mod.limiter._in_memory_fallback_enabled is True

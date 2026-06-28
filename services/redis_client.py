from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_client = None
_initialized = False


def get_redis():
    """Return a shared Redis client, or None if REDIS_URL is not configured.

    Lazy-initializes on first call. Returns None (graceful degradation) if
    the URL is missing or the connection fails — callers must handle None.
    """
    global _client, _initialized
    if _initialized:
        return _client

    _initialized = True
    url = os.environ.get("REDIS_URL")
    if not url:
        logger.info("REDIS_URL not set — Redis features disabled")
        return None

    try:
        import redis

        _client = redis.Redis.from_url(url, decode_responses=True)
        _client.ping()
        logger.info("Redis client connected")
        return _client
    except Exception:
        logger.warning("Redis connection failed — features disabled", exc_info=True)
        _client = None
        return None

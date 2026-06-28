import os

from slowapi import Limiter
from starlette.requests import Request


def _get_real_ip(request: Request) -> str:
    """Extract client IP behind a reverse proxy (Railway, etc.)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


_redis_url = os.environ.get("REDIS_URL")

limiter = Limiter(
    key_func=_get_real_ip,
    enabled=os.environ.get("TESTING") != "1",
    storage_uri=_redis_url or "memory://",
    in_memory_fallback_enabled=True,
)

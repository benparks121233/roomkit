import logging
import os
from typing import Annotated

import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, Request

logger = logging.getLogger(__name__)

_SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
_JWKS_URL = f"{_SUPABASE_URL}/auth/v1/.well-known/jwks.json" if _SUPABASE_URL else ""

_jwks_client: PyJWKClient | None = None

# Local fast-path cache — always checked first (no Redis round-trip).
# Redis extends this across workers; local set is the single-worker fallback.
_deleted_users: set[str] = set()

_DELETED_USER_TTL = 7200  # 2 hours — matches JWT max lifetime


def _redis_mark_deleted(user_id: str) -> None:
    try:
        from services.redis_client import get_redis
        r = get_redis()
        if r is not None:
            r.setex(f"deleted_user:{user_id}", _DELETED_USER_TTL, "1")
    except Exception:
        logger.warning("Redis write failed for deleted_user:%s", user_id, exc_info=True)


def _redis_is_deleted(user_id: str) -> bool:
    try:
        from services.redis_client import get_redis
        r = get_redis()
        if r is not None:
            return bool(r.exists(f"deleted_user:{user_id}"))
    except Exception:
        logger.warning("Redis read failed for deleted_user:%s", user_id, exc_info=True)
    return False


def mark_user_deleted(user_id: str) -> None:
    """Block future requests from this user_id across all workers."""
    _deleted_users.add(user_id)
    _redis_mark_deleted(user_id)


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is not None:
        return _jwks_client
    if not _JWKS_URL:
        raise HTTPException(500, "Auth not configured (SUPABASE_URL missing)")
    _jwks_client = PyJWKClient(_JWKS_URL, cache_keys=True, lifespan=300)
    return _jwks_client


def _extract_token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")
    return auth[7:]


def get_current_user(request: Request) -> dict:
    """FastAPI dependency: verify Supabase ES256 JWT via JWKS and return user claims.

    Fetches the signing key from Supabase's JWKS endpoint, matched by the
    token's kid header. Verifies with ES256 (asymmetric). Cached per key.

    Returns dict with 'user_id' (UUID), 'email', and 'token' (raw JWT).
    Raises 401 if token is missing, expired, or invalid.
    """
    token = _extract_token(request)

    try:
        jwks = _get_jwks_client()
        signing_key = jwks.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning("JWT validation failed: %s", e)
        raise HTTPException(401, "Authentication failed")
    except Exception as e:
        logger.warning("JWT verification error: %s", e)
        raise HTTPException(401, "Authentication failed")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(401, "Token missing sub claim")

    if user_id in _deleted_users or _redis_is_deleted(user_id):
        _deleted_users.add(user_id)  # cache locally to avoid future Redis round-trips
        raise HTTPException(401, "Account has been deleted")

    return {"user_id": user_id, "email": payload.get("email", ""), "token": token}


CurrentUser = Annotated[dict, Depends(get_current_user)]

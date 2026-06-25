import os
from typing import Annotated

import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, Request


_SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
_JWKS_URL = f"{_SUPABASE_URL}/auth/v1/.well-known/jwks.json" if _SUPABASE_URL else ""

# PyJWKClient caches the JWKS response (cache_keys=True, 5-min lifespan).
# One fetch per key rotation, not per request.
_jwks_client: PyJWKClient | None = None


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
        raise HTTPException(401, f"Invalid token: {e}")
    except Exception as e:
        raise HTTPException(401, f"Token verification failed: {e}")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(401, "Token missing sub claim")

    return {"user_id": user_id, "email": payload.get("email", ""), "token": token}


CurrentUser = Annotated[dict, Depends(get_current_user)]

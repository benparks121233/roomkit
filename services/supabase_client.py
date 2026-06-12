# services/supabase_client.py
# Singleton Supabase client for server-side writes (service key).
# Used by the tracking module — never exposed to the frontend.

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_client = None


def get_client():
    """Return the Supabase client, creating it on first call.

    Returns None if env vars are missing (graceful degradation —
    tracking is non-blocking so a missing client just means no logging).
    """
    global _client
    if _client is not None:
        return _client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")

    if not url or not key:
        logger.warning("SUPABASE_URL or SUPABASE_SERVICE_KEY not set — tracking disabled")
        return None

    try:
        from supabase import create_client
        _client = create_client(url, key)
        logger.info("Supabase client initialized")
        return _client
    except Exception:
        logger.exception("Failed to initialize Supabase client")
        return None


def health_check() -> dict:
    """Quick connectivity check — tries a simple query.

    Returns {"status": "ok"} or {"status": "error", "detail": "..."}.
    """
    client = get_client()
    if client is None:
        return {"status": "error", "detail": "Client not initialized (missing env vars?)"}

    try:
        # Try to read from a table — will fail if table doesn't exist yet,
        # but the connection itself succeeding proves auth + connectivity.
        client.table("events").select("id").limit(1).execute()
        return {"status": "ok"}
    except Exception as e:
        err = str(e)
        # "relation does not exist" means connection works, table just isn't created yet
        if "does not exist" in err or "42P01" in err:
            return {"status": "ok", "detail": "Connected (tables not yet created)"}
        return {"status": "error", "detail": err[:200]}

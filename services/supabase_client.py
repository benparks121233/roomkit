# services/supabase_client.py
# Two-tier Supabase access:
#   get_client()        → service key (bypasses RLS) — for WRITES only
#   get_user_client(jwt)→ anon key + user JWT (RLS enforced) — for READS
#
# This split ensures RLS SELECT policies are real enforcement,
# not decorative. The service key never touches user-facing reads.

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_client = None
_schema = "public"


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
        from supabase import ClientOptions, create_client
        global _schema
        _schema = os.environ.get("SUPABASE_SCHEMA", "public")
        _client = create_client(url, key, options=ClientOptions(schema=_schema))
        logger.info("Supabase client initialized (schema=%s)", _schema)
        return _client
    except Exception:
        logger.exception("Failed to initialize Supabase client")
        return None


def get_user_postgrest(user_jwt: str):
    """Return a per-request PostgREST client using the ANON key + user JWT.

    RLS policies fire on this client — auth.uid() is set from the JWT.
    Use for all user-facing READS. Never use for writes (use get_client()).
    Returns None if anon key is not configured.
    """
    url = os.environ.get("SUPABASE_URL")
    anon_key = os.environ.get("SUPABASE_ANON_KEY")
    if not url or not anon_key:
        logger.warning("SUPABASE_URL or SUPABASE_ANON_KEY not set — RLS reads unavailable")
        return None

    from postgrest import SyncPostgrestClient

    schema = os.environ.get("SUPABASE_SCHEMA", "public")
    client = SyncPostgrestClient(
        base_url=f"{url}/rest/v1",
        headers={"apikey": anon_key, "Authorization": f"Bearer {user_jwt}"},
        schema=schema,
    )
    return client


def delete_user(user_id: str) -> bool:
    """Delete a user from Supabase auth.users via admin API.

    Returns True on success, False if the client is unavailable.
    Raises Exception on API failure (caller handles).
    Treats 'user not found' as success (idempotent).
    """
    client = get_client()
    if client is None:
        raise RuntimeError("Supabase client not configured")

    try:
        client.auth.admin.delete_user(user_id)
        logger.info("supabase_client: deleted auth user %s", user_id)
        return True
    except Exception as exc:
        if "not found" in str(exc).lower() or "404" in str(exc):
            logger.info("supabase_client: auth user %s already deleted (idempotent)", user_id)
            return True
        raise


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
        return {"status": "ok", "schema": _schema}
    except Exception as e:
        err = str(e)
        # "relation does not exist" means connection works, table just isn't created yet
        if "does not exist" in err or "42P01" in err:
            return {"status": "ok", "detail": "Connected (tables not yet created)"}
        return {"status": "error", "detail": err[:200]}

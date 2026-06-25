# services/design_store.py
# Persistent design storage via Supabase (write-through, read-through).
# The in-memory cache in routes.py remains the fast path; this module
# handles durable persistence so designs survive server restarts.

from __future__ import annotations

import logging

from app.api.schemas import DesignResponse, SlotResult, StyleResult

logger = logging.getLogger(__name__)


class DesignStoreError(Exception):
    """Raised when a Supabase operation fails (connection, query, etc.)."""


def save_design(response: DesignResponse, user_id: str | None = None) -> bool:
    """Persist a design to Supabase.  Returns True on success, False on failure.

    Never raises — callers should log the failure but not block the response.
    Uses the SERVICE KEY (bypasses RLS) — this is a write path.
    """
    from services.supabase_client import get_client

    client = get_client()
    if client is None:
        logger.warning(
            "design_store: Supabase not configured — design %s NOT persisted "
            "(will be lost on restart)",
            response.run_id,
        )
        return False

    row = {
        "run_id": response.run_id,
        "room_type": response.room_type,
        "target_budget": float(response.target_budget),
        "total_spent": float(response.total_spent),
        "is_feasible": response.is_feasible,
        "style": response.style.model_dump(),
        "slots": [s.model_dump() for s in response.slots],
        "finalized_at": response.finalized_at,
    }
    if user_id:
        row["user_id"] = user_id

    try:
        client.table("designs").upsert(row).execute()
        logger.info("design_store: persisted design %s", response.run_id)
        return True
    except Exception as exc:
        # If finalized_at column doesn't exist yet, retry without it.
        if "finalized_at" in str(exc):
            logger.warning(
                "design_store: finalized_at column missing — persisting without it. "
                "Run: ALTER TABLE designs ADD COLUMN finalized_at text;"
            )
            row.pop("finalized_at", None)
            try:
                client.table("designs").upsert(row).execute()
                logger.info("design_store: persisted design %s (without finalized_at)", response.run_id)
                return True
            except Exception:
                pass
        logger.warning(
            "design_store: FAILED to persist design %s — design is in memory "
            "but will be lost on restart",
            response.run_id,
            exc_info=True,
        )
        return False


def load_design(run_id: str) -> DesignResponse:
    """Load a design from Supabase using the SERVICE KEY (no RLS).

    For internal/admin use only. User-facing reads should use
    load_design_as_user() which enforces RLS.

    Raises:
        DesignStoreError: on connection/query failure (caller should 503).
        KeyError: when the row genuinely doesn't exist (caller should 404).
    """
    from services.supabase_client import get_client

    client = get_client()
    if client is None:
        raise DesignStoreError("Supabase not configured")

    try:
        resp = (
            client.table("designs")
            .select("*")
            .eq("run_id", run_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        raise DesignStoreError(f"Supabase query failed: {exc}") from exc

    if resp is None or resp.data is None:
        raise KeyError(run_id)

    return _row_to_response(resp.data)


def load_design_as_user(run_id: str, user_jwt: str) -> DesignResponse:
    """Load a design using the ANON KEY + user JWT (RLS enforced).

    The RLS SELECT policy filters by auth.uid() = user_id, so this
    returns KeyError if the design belongs to a different user — the
    database enforces isolation, not app code.

    Raises:
        DesignStoreError: on connection/query failure (caller should 503).
        KeyError: when the row doesn't exist OR belongs to another user.
    """
    from services.supabase_client import get_user_postgrest

    pg = get_user_postgrest(user_jwt)
    if pg is None:
        raise DesignStoreError("Supabase anon key not configured")

    try:
        resp = (
            pg.from_("designs")
            .select("*")
            .eq("run_id", run_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        raise DesignStoreError(f"Supabase query failed: {exc}") from exc

    if resp is None or resp.data is None:
        raise KeyError(run_id)

    return _row_to_response(resp.data)


def _row_to_response(row: dict) -> DesignResponse:
    return DesignResponse(
        run_id=row["run_id"],
        room_type=row["room_type"],
        target_budget=row["target_budget"],
        total_spent=row["total_spent"],
        is_feasible=row["is_feasible"],
        style=StyleResult(**row["style"]),
        slots=[SlotResult(**s) for s in row["slots"]],
        finalized_at=row.get("finalized_at"),
        user_id=row.get("user_id"),
    )

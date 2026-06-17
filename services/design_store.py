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


def save_design(response: DesignResponse) -> bool:
    """Persist a design to Supabase.  Returns True on success, False on failure.

    Never raises — callers should log the failure but not block the response.
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
    }

    try:
        client.table("designs").upsert(row).execute()
        logger.info("design_store: persisted design %s", response.run_id)
        return True
    except Exception:
        logger.warning(
            "design_store: FAILED to persist design %s — design is in memory "
            "but will be lost on restart",
            response.run_id,
            exc_info=True,
        )
        return False


def load_design(run_id: str) -> DesignResponse:
    """Load a design from Supabase.

    Returns the deserialized DesignResponse on success.

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

    if resp.data is None:
        raise KeyError(run_id)

    row = resp.data
    return DesignResponse(
        run_id=row["run_id"],
        room_type=row["room_type"],
        target_budget=row["target_budget"],
        total_spent=row["total_spent"],
        is_feasible=row["is_feasible"],
        style=StyleResult(**row["style"]),
        slots=[SlotResult(**s) for s in row["slots"]],
    )

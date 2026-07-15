# services/tracking.py
# Non-blocking event and selection logging to Supabase.
#
# CRITICAL: Every public function here is fire-and-forget. A Supabase write
# failure must NEVER crash the request or slow the UX. All writes are wrapped
# in try/except with logged warnings.

from __future__ import annotations

import logging
import os
import threading
from typing import Any

logger = logging.getLogger(__name__)

def _is_disabled() -> bool:
    """Check at call time — pytest sets PYTEST_CURRENT_TEST per-test."""
    return os.environ.get("TESTING") == "1" or "PYTEST_CURRENT_TEST" in os.environ


def _bg(fn, *args, **kwargs):
    """Run fn in a background thread — true fire-and-forget."""
    t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
    t.start()


def _get_client():
    """Import lazily to avoid circular imports at module load."""
    from services.supabase_client import get_client
    return get_client()


# ---------------------------------------------------------------------------
# Event logging (funnel events)
# ---------------------------------------------------------------------------

def log_event(
    run_id: str,
    event_type: str,
    data: dict[str, Any] | None = None,
    api_cost: float | None = None,
    user_id: str | None = None,
) -> None:
    """Log a funnel event. Non-blocking — returns immediately."""
    if _is_disabled():
        return
    _bg(_log_event_sync, run_id, event_type, data or {}, api_cost, user_id)


def _log_event_sync(
    run_id: str,
    event_type: str,
    data: dict[str, Any],
    api_cost: float | None,
    user_id: str | None,
) -> None:
    try:
        client = _get_client()
        if client is None:
            return
        row: dict[str, Any] = {
            "run_id": run_id,
            "event_type": event_type,
            "data": data,
        }
        if api_cost is not None:
            row["api_cost"] = api_cost
        if user_id:
            row["user_id"] = user_id
        client.table("events").insert(row).execute()
    except Exception:
        logger.error("Failed to log event %s for %s", event_type, run_id, exc_info=True)


# ---------------------------------------------------------------------------
# Selection logging (one row per slot)
# ---------------------------------------------------------------------------

def log_selections(
    run_id: str,
    room_type: str,
    aesthetic: str,
    mood: str | None,
    color_palette: list[str],
    keywords: list[str],
    budget: float,
    slot_products: list[dict[str, Any]],
    user_id: str | None = None,
) -> None:
    """Log all slot selections for a design run. Non-blocking."""
    if _is_disabled():
        return
    _bg(
        _log_selections_sync,
        run_id, room_type, aesthetic, mood,
        color_palette, keywords, budget, slot_products, user_id,
    )


def _log_selections_sync(
    run_id: str,
    room_type: str,
    aesthetic: str,
    mood: str | None,
    color_palette: list[str],
    keywords: list[str],
    budget: float,
    slot_products: list[dict[str, Any]],
    user_id: str | None,
) -> None:
    try:
        client = _get_client()
        if client is None:
            return
        rows = []
        for sp in slot_products:
            row: dict[str, Any] = {
                "run_id": run_id,
                "room_type": room_type,
                "aesthetic": aesthetic,
                "mood": mood or "",
                "color_palette": color_palette,
                "keywords": keywords,
                "budget": budget,
                "slot_id": sp["slot_id"],
                "product_id": sp["product_id"],
                "product_name": sp["product_name"],
                "product_price": sp["product_price"],
                "retailer": sp.get("retailer", "amazon"),
                "is_multiselect": sp.get("is_multiselect", False),
            }
            if user_id:
                row["user_id"] = user_id
            rows.append(row)
        if rows:
            client.table("selections").insert(rows).execute()
            logger.info("Logged %d selections for run %s", len(rows), run_id)
    except Exception:
        logger.error("Failed to log selections for %s", run_id, exc_info=True)

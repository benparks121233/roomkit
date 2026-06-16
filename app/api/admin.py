# app/api/admin.py
# Internal admin endpoints — dashboard data aggregations from Supabase.
# Protected by a simple shared secret (ADMIN_SECRET env var or query param).

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

_ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "roomkit-internal-2024")


def _check_auth(secret: str | None):
    if secret != _ADMIN_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _get_client():
    from services.supabase_client import get_client
    client = get_client()
    if client is None:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    return client


# ---------------------------------------------------------------------------
# GET /admin/stats — main dashboard data (single call, returns everything)
# ---------------------------------------------------------------------------

@router.get("/stats")
async def admin_stats(secret: str | None = Query(None)) -> dict:
    """Return all dashboard metrics in one response."""
    _check_auth(secret)
    client = _get_client()

    # Fetch all events and selections in parallel-ish (sync client, sequential)
    events_resp = client.table("events").select("*").order("created_at", desc=True).limit(5000).execute()
    events = events_resp.data or []

    selections_resp = client.table("selections").select("*").order("created_at", desc=True).limit(10000).execute()
    selections = selections_resp.data or []

    # --- Funnel metrics ---
    event_counts: dict[str, int] = {}
    unique_runs: dict[str, set] = {}
    total_cost = 0.0
    cost_events = 0

    for e in events:
        et = e["event_type"]
        event_counts[et] = event_counts.get(et, 0) + 1
        unique_runs.setdefault(et, set()).add(e["run_id"])
        if e.get("api_cost"):
            total_cost += float(e["api_cost"])
            cost_events += 1

    funnel_order = [
        "design_started", "design_completed", "render_requested",
        "render_generated", "render_viewed", "hotspot_clicked",
        "buy_link_clicked", "export_cart_clicked",
    ]
    funnel = []
    for step in funnel_order:
        runs = len(unique_runs.get(step, set()))
        funnel.append({"step": step, "unique_runs": runs, "total_events": event_counts.get(step, 0)})

    started = len(unique_runs.get("design_started", set()))
    completed = len(unique_runs.get("design_completed", set()))

    # --- Top aesthetics ---
    aesthetic_counts: dict[str, int] = {}
    for s in selections:
        a = s.get("aesthetic", "unknown")
        if a not in aesthetic_counts:
            aesthetic_counts[a] = 0
        # Count unique runs per aesthetic
        aesthetic_counts[a] = aesthetic_counts.get(a, 0)
    # Re-count by unique run_ids
    aesthetic_runs: dict[str, set] = {}
    for s in selections:
        aesthetic_runs.setdefault(s.get("aesthetic", "unknown"), set()).add(s["run_id"])
    top_aesthetics = sorted(
        [{"aesthetic": k, "runs": len(v)} for k, v in aesthetic_runs.items()],
        key=lambda x: x["runs"], reverse=True,
    )[:15]

    # --- Top products per slot ---
    product_counts: dict[str, dict[str, dict]] = {}  # slot → product_id → {count, name, price}
    for s in selections:
        slot = s["slot_id"]
        pid = s["product_id"]
        if slot not in product_counts:
            product_counts[slot] = {}
        if pid not in product_counts[slot]:
            product_counts[slot][pid] = {
                "product_id": pid,
                "name": s["product_name"],
                "price": float(s["product_price"]),
                "count": 0,
            }
        product_counts[slot][pid]["count"] += 1

    top_products_by_slot: dict[str, list] = {}
    for slot, products in product_counts.items():
        top_products_by_slot[slot] = sorted(
            products.values(), key=lambda x: x["count"], reverse=True,
        )[:5]

    # --- Recent runs ---
    recent_runs: list[dict] = []
    seen_runs: set[str] = set()
    for e in events:
        rid = e["run_id"]
        if rid in seen_runs:
            continue
        seen_runs.add(rid)
        # Find this run's events
        run_events = [ev for ev in events if ev["run_id"] == rid]
        run_types = {ev["event_type"] for ev in run_events}
        run_cost = sum(float(ev["api_cost"]) for ev in run_events if ev.get("api_cost"))
        # Get aesthetic from started event data
        started_data = next(
            (ev.get("data", {}) for ev in run_events if ev["event_type"] == "design_started"),
            {},
        )
        recent_runs.append({
            "run_id": rid,
            "created_at": e["created_at"],
            "aesthetic": started_data.get("aesthetic", ""),
            "budget": started_data.get("budget", 0),
            "events": sorted(run_types),
            "cost": round(run_cost, 4),
        })
        if len(recent_runs) >= 20:
            break

    return {
        "summary": {
            "total_runs": started,
            "completed_runs": completed,
            "completion_pct": round(completed / started * 100, 1) if started > 0 else 0,
            "avg_cost_per_run": round(total_cost / cost_events, 4) if cost_events > 0 else 0,
            "total_cost": round(total_cost, 4),
            "total_events": len(events),
            "total_selections": len(selections),
        },
        "funnel": funnel,
        "top_aesthetics": top_aesthetics,
        "top_products_by_slot": top_products_by_slot,
        "recent_runs": recent_runs,
    }

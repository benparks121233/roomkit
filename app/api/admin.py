# app/api/admin.py
# Internal admin endpoints — dashboard data aggregations from Supabase.
# Protected by a simple shared secret (ADMIN_SECRET env var or query param).

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

_ADMIN_SECRET = os.environ.get("ADMIN_SECRET")


def _check_auth(secret: str | None):
    if not _ADMIN_SECRET:
        raise HTTPException(status_code=503, detail="Admin not configured")
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

    # Fetch all events and selections (sync client, sequential)
    events_resp = (
        client.table("events").select("*")
        .order("created_at", desc=True).limit(5000).execute()
    )
    events = events_resp.data or []

    selections_resp = (
        client.table("selections").select("*")
        .order("created_at", desc=True).limit(10000).execute()
    )
    selections = selections_resp.data or []

    # Fetch designs and user_packs
    designs_resp = (
        client.table("designs").select("*")
        .order("created_at", desc=True).limit(5000).execute()
    )
    designs = designs_resp.data or []

    packs_resp = client.table("user_packs").select("*").execute()
    user_packs = packs_resp.data or []

    # Fetch auth users
    try:
        users_result = client.auth.admin.list_users()
        if isinstance(users_result, list):
            auth_users = users_result
        elif hasattr(users_result, "users"):
            auth_users = users_result.users or []
        else:
            auth_users = list(users_result) if users_result else []
    except Exception:
        logger.warning("Failed to fetch auth users for admin stats")
        auth_users = []

    # Build designs lookup by run_id
    designs_by_run_id: dict[str, dict] = {}
    for d in designs:
        rid = d.get("run_id")
        if rid:
            designs_by_run_id[rid] = d

    # --- Funnel metrics ---
    event_counts: dict[str, int] = {}
    unique_runs: dict[str, set] = {}
    total_cost = 0.0
    cost_events = 0
    cost_run_ids: set[str] = set()

    for e in events:
        et = e["event_type"]
        event_counts[et] = event_counts.get(et, 0) + 1
        unique_runs.setdefault(et, set()).add(e["run_id"])
        if e.get("api_cost"):
            total_cost += float(e["api_cost"])
            cost_events += 1
            cost_run_ids.add(e["run_id"])

    funnel_order = [
        "design_started", "design_completed", "render_requested",
        "render_generated", "render_viewed", "hotspot_clicked",
        "buy_link_clicked", "export_cart_clicked",
    ]
    funnel = []
    for step in funnel_order:
        runs = len(unique_runs.get(step, set()))
        funnel.append({
            "step": step,
            "unique_runs": runs,
            "total_events": event_counts.get(step, 0),
        })

    started = len(unique_runs.get("design_started", set()))
    completed = len(unique_runs.get("design_completed", set()))

    # --- Top aesthetics ---
    aesthetic_runs: dict[str, set] = {}
    for s in selections:
        aesthetic_runs.setdefault(s.get("aesthetic", "unknown"), set()).add(s["run_id"])
    top_aesthetics = sorted(
        [{"aesthetic": k, "runs": len(v)} for k, v in aesthetic_runs.items()],
        key=lambda x: x["runs"], reverse=True,
    )[:15]

    # --- Top products per slot ---
    product_counts: dict[str, dict[str, dict]] = {}
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

    # --- Users ---
    total_signups = len(auth_users)
    design_user_ids = {d["user_id"] for d in designs if d.get("user_id")}
    users_with_designs = len(design_user_ids)
    pack_user_ids = {p["user_id"] for p in user_packs if p.get("user_id")}
    users_with_packs = len(pack_user_ids)

    users_section = {
        "total_signups": total_signups,
        "users_with_designs": users_with_designs,
        "users_with_packs": users_with_packs,
        "signup_to_design_pct": (
            round(users_with_designs / total_signups * 100, 1)
            if total_signups > 0 else 0
        ),
        "design_to_purchase_pct": (
            round(users_with_packs / users_with_designs * 100, 1)
            if users_with_designs > 0 else 0
        ),
    }

    # --- Revenue / Packs ---
    total_packs_purchased = event_counts.get("pack_purchased", 0)
    packs_remaining = sum(int(p.get("rooms_remaining", 0)) for p in user_packs)

    revenue_section = {
        "total_packs_purchased": total_packs_purchased,
        "total_revenue": round(total_packs_purchased * 4.99, 2),
        "packs_remaining": packs_remaining,
    }

    # --- Room type breakdown ---
    room_groups: dict[str, list[dict]] = {}
    for d in designs:
        rt = d.get("room_type", "unknown")
        room_groups.setdefault(rt, []).append(d)

    room_breakdown = []
    for rt, group in sorted(room_groups.items()):
        total_in_group = len(group)
        paid = sum(1 for d in group if d.get("is_paid"))
        budgets = [float(d["target_budget"]) for d in group if d.get("target_budget") is not None]
        spends = [float(d["total_spent"]) for d in group if d.get("total_spent") is not None]
        room_breakdown.append({
            "room_type": rt,
            "total": total_in_group,
            "paid": paid,
            "free": total_in_group - paid,
            "avg_budget": round(sum(budgets) / len(budgets), 2) if budgets else 0,
            "avg_spent": round(sum(spends) / len(spends), 2) if spends else 0,
        })

    # --- Cost tracking ---
    run_id_to_room_type: dict[str, str] = {}
    for d in designs:
        rid = d.get("run_id")
        if rid:
            run_id_to_room_type[rid] = d.get("room_type", "unknown")

    cost_by_room_type: dict[str, float] = {}
    for e in events:
        if e.get("api_cost"):
            rt = run_id_to_room_type.get(e["run_id"], "unknown")
            cost_by_room_type[rt] = cost_by_room_type.get(rt, 0.0) + float(e["api_cost"])
    cost_by_room_type = {k: round(v, 4) for k, v in sorted(cost_by_room_type.items())}

    unique_cost_runs = len(cost_run_ids)

    cost_tracking = {
        "total_api_cost": round(total_cost, 4),
        "cost_by_room_type": cost_by_room_type,
        "avg_cost_per_design": (
            round(total_cost / unique_cost_runs, 4)
            if unique_cost_runs > 0 else 0
        ),
    }

    # --- Engagement ---
    started_runs = unique_runs.get("design_started", set())
    started_count = len(started_runs)

    def _rate(event_type: str) -> float:
        if started_count == 0:
            return 0
        matched = len(unique_runs.get(event_type, set()) & started_runs)
        return round(matched / started_count * 100, 1)

    engagement = {
        "render_rate": _rate("render_generated"),
        "finalization_rate": _rate("design_finalized"),
        "cart_export_rate": _rate("export_cart_clicked"),
        "buy_link_click_rate": _rate("buy_link_clicked"),
    }

    # --- Recent runs (enhanced with room_type and is_paid) ---
    recent_runs: list[dict] = []
    seen_runs: set[str] = set()
    for e in events:
        rid = e["run_id"]
        if rid in seen_runs:
            continue
        seen_runs.add(rid)
        run_events = [ev for ev in events if ev["run_id"] == rid]
        run_types = {ev["event_type"] for ev in run_events}
        run_cost = sum(float(ev["api_cost"]) for ev in run_events if ev.get("api_cost"))
        started_data = next(
            (ev.get("data", {}) for ev in run_events if ev["event_type"] == "design_started"),
            {},
        )
        design_row = designs_by_run_id.get(rid)
        recent_runs.append({
            "run_id": rid,
            "created_at": e["created_at"],
            "aesthetic": started_data.get("aesthetic", ""),
            "budget": started_data.get("budget", 0),
            "room_type": (
                design_row.get("room_type", "")
                if design_row
                else started_data.get("room_type", "")
            ),
            "is_paid": bool(design_row.get("is_paid")) if design_row else False,
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
        "users": users_section,
        "revenue": revenue_section,
        "room_breakdown": room_breakdown,
        "cost_tracking": cost_tracking,
        "engagement": engagement,
        "funnel": funnel,
        "top_aesthetics": top_aesthetics,
        "top_products_by_slot": top_products_by_slot,
        "recent_runs": recent_runs,
    }

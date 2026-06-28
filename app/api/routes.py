# app/api/routes.py
# HTTP route handlers for the RoomKit API.
# Owns: request parsing, delegating to services, assembling responses.
# Business logic lives in services/ and validators/, not here.
#
# Timeout note: POST /design makes ~17 real LLM calls (1 style + 1 composition
# + ~15 selection).  Selection calls run in parallel via ThreadPoolExecutor,
# so wall time is ~10-15s rather than 60-90s.  The Next.js fetch in Piece 2
# must still set a generous timeout (120s) for safety.

from __future__ import annotations

import logging
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from app.auth import CurrentUser
from app.rate_limit import limiter

from services.tracking import log_event, log_selections

from app.api.schemas import (
    DesignRequest,
    DesignResponse,
    ProductResult,
    SlotResult,
    SlotValidationResult,
    StyleResult,
    ValidateSelectionsRequest,
    ValidateSelectionsResponse,
)
from schemas.product import Product
from services.composition_gate import validate_composition
from services.composition_service import plan_composition
from services.intake_service import parse_intake
from services.selection_service import select_products, pick_count_for_slot
from services.sourcing.amazon_adapter import AmazonAdapter
from services.style_service import interpret_style
from validators.budget_rules import validate_pool_spend

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory design cache + Supabase persistence (Phase 3)
# _designs is the fast in-process cache.  Supabase is the durable store.
# Write path: save to both.  Read path: cache first, Supabase fallback.
# ---------------------------------------------------------------------------
_designs: dict[str, DesignResponse] = {}


def _get_design(run_id: str, user: dict | None = None) -> DesignResponse:
    """Retrieve a design: cache first, then Supabase, with three-outcome handling.

    If user is provided, enforces ownership:
      - Cache hit: checks user_id matches (defense-in-depth)
      - Cache miss: uses RLS-enforced read (anon key + JWT, database enforces)

    Returns the DesignResponse on success.
    Raises HTTPException 404 if the design doesn't exist or belongs to another user.
    Raises HTTPException 503 if the Supabase query failed (retry-able).
    """
    from services.design_store import DesignStoreError, load_design, load_design_as_user

    # 1. Fast path: in-memory cache
    if run_id in _designs:
        cached = _designs[run_id]
        if user and hasattr(cached, "user_id") and cached.user_id:
            if cached.user_id != user["user_id"]:
                raise HTTPException(status_code=404, detail=f"Design {run_id} not found")
        return cached

    # 2. Slow path: Supabase lookup
    # RLS-enforced read (anon key + JWT) is the ONLY path in staging/prod.
    # If the anon key is missing outside tests, that's a 503 — never
    # silently fall back to service key, which would bypass RLS.
    try:
        if user and user.get("token"):
            try:
                design = load_design_as_user(run_id, user["token"])
            except DesignStoreError:
                if os.environ.get("TESTING") == "1":
                    design = load_design(run_id)
                    if design.user_id and design.user_id != user["user_id"]:
                        raise KeyError(run_id)
                else:
                    raise
        else:
            design = load_design(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Design {run_id} not found")
    except DesignStoreError as exc:
        logger.warning("_get_design: Supabase read failed for %s: %s", run_id, exc)
        raise HTTPException(
            status_code=503,
            detail="Storage temporarily unavailable — please retry",
        )

    _designs[run_id] = design
    return design


# ---------------------------------------------------------------------------
# POST /design — run the full pipeline
# ---------------------------------------------------------------------------

@router.post("/design", response_model=DesignResponse)
@limiter.limit("5/minute")
async def create_design(request: Request, req: DesignRequest, user: CurrentUser) -> DesignResponse:
    """Run the full RoomKit pipeline and return a shoppable board.

    This makes real LLM calls (~17 total) and can take 60-90 seconds.
    Requires authentication — user_id is stamped on the design.
    """
    # 0. Free-room enforcement: count user's existing designs.
    # App-layer check. Race window is sub-second; blast radius is $0.27.
    # 6E adds a DB-level unique partial index for airtight enforcement.
    from services.supabase_client import get_client as _get_svc_client
    _svc = _get_svc_client()
    if _svc:
        try:
            _count_resp = (
                _svc.table("designs")
                .select("run_id", count="exact")
                .eq("user_id", user["user_id"])
                .execute()
            )
            _free_limit = int(os.environ.get("FREE_ROOM_LIMIT", "1"))
            if _count_resp.count and _count_resp.count >= _free_limit:
                raise HTTPException(
                    status_code=403,
                    detail="Free tier: 1 room limit. Upgrade for more.",
                )
        except HTTPException:
            raise
        except Exception:
            logger.warning("Free-room count check failed — allowing request", exc_info=True)

    _start_time = time.monotonic()
    _timing: dict[str, float] = {}

    # 1. Intake — validate and produce a RoomRequest.
    _t = time.monotonic()
    try:
        room_request = parse_intake(req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    _timing["intake_ms"] = round((time.monotonic() - _t) * 1000, 1)

    log_event(room_request.run_id, "design_started", {
        "room_type": room_request.room_type or "bedroom",
        "budget": req.budget,
        "aesthetic": req.core_aesthetic or "",
    }, user_id=user["user_id"])

    # 2. Style interpretation — real LLM call.
    _t = time.monotonic()
    style_profile = interpret_style(room_request)
    _timing["style_ms"] = round((time.monotonic() - _t) * 1000, 1)

    # 3. Composition — real LLM call for weight proposal, deterministic budget math.
    _t = time.monotonic()
    slot_plan = plan_composition(room_request, style_profile)
    _timing["composition_ms"] = round((time.monotonic() - _t) * 1000, 1)

    # 4. Composition gate — deterministic validation.
    slot_plan, gate_error = validate_composition(slot_plan)
    if gate_error:
        # Return the response with is_feasible=False rather than a hard error,
        # so the UI can show a meaningful message.
        return _build_response(
            room_request.run_id,
            room_request.room_type or "bedroom",
            style_profile,
            slot_plan,
            slots_results=[],
            gate_error=gate_error,
        )

    # 5. Sourcing + selection — parallel LLM calls for non-owned slots.
    _t = time.monotonic()
    adapter = AmazonAdapter()
    slot_results: list[SlotResult] = []

    # Decor single-item cap: no single decor item may exceed 50% of the
    # total decor group budget. Prevents one expensive item eating the pool.
    _DECOR_SLOTS = {"wall_art", "plants", "mirror", "throw_blanket"}
    decor_total_budget = sum(
        s.allocated_budget for s in slot_plan.slots
        if s.slot_id in _DECOR_SLOTS and not s.owned
    )
    decor_item_cap = decor_total_budget * 0.50

    # Owned slots don't need LLM calls — collect them immediately.
    owned_results: list[SlotResult] = []
    sourceable_slots: list[object] = []  # (slot, candidates) pairs

    for slot in slot_plan.slots:
        if slot.owned:
            owned_results.append(SlotResult(
                slot_id=slot.slot_id,
                allocated_budget=slot.allocated_budget,
                owned=True,
                max_quantity=slot.max_quantity,
                product=None,
                null_reason="owned",
            ))
            continue

        # Build spec hints and fetch candidates (local file reads, fast).
        spec_hints: dict[str, str] = {}
        if "bed_size" in slot.required_specs and room_request.bed_size:
            spec_hints["bed_size"] = room_request.bed_size

        # Fetch candidates up to 1.5x the slot budget so the user sees more
        # variety. The LLM and UI will handle budget enforcement — items above
        # the slot budget are shown but flagged if they'd blow the total.
        # Duvet slots get 2.0x to widen the thin pool (insert is hidden inside
        # the cover; both benefit from seeing more price range).
        # For decor slots, cap at 50% of the total decor pool to prevent
        # one expensive item eating the entire decor allocation.
        _WIDE_SOURCING_SLOTS = {"duvet_insert", "duvet_cover"}
        sourcing_mult = 2.0 if slot.slot_id in _WIDE_SOURCING_SLOTS else 1.5
        max_price = slot.allocated_budget * sourcing_mult
        if slot.slot_id in _DECOR_SLOTS and decor_item_cap > 0:
            max_price = min(max_price, decor_item_cap)

        # Use sourcing_terms (product-name-friendly) for adapter scoring,
        # falling back to keywords if sourcing_terms not set.
        sourcing_kw = style_profile.sourcing_terms or style_profile.keywords
        candidates = adapter.fetch_candidates(
            slot.slot_id,
            sourcing_kw,
            (0.0, max_price),
            spec_hints,
            interests=room_request.interests or None,
            priority_terms=style_profile.priority_terms or None,
        )
        logger.info("Sourced %s: %d candidates (budget $%.2f)", slot.slot_id, len(candidates), slot.allocated_budget)

        # Mirror type filter: if user selected a mirror type (e.g. "round",
        # "full_length"), prefer candidates whose name matches that type.
        # Synonyms cover common product-name vocabulary variations.
        _MIRROR_SYNONYMS: dict[str, list[str]] = {
            "round": ["round", "circular", "circle"],
            "full_length": ["full length", "full-length", "standing", "floor"],
            "rectangular": ["rectangular", "rectangle", "square"],
            "wall": ["wall"],
            "arched": ["arched", "arch"],
        }
        if slot.slot_id == "mirror" and room_request.mirror_type:
            mtype = room_request.mirror_type.lower()
            synonyms = _MIRROR_SYNONYMS.get(mtype, [mtype.replace("_", " ")])
            typed = [
                c for c in candidates
                if any(syn in c.name.lower() for syn in synonyms)
            ]
            if typed:
                candidates = typed

        # Screen size range filter: map user's bucket to inch ranges and
        # keep only TVs whose screen_size spec falls within the range.
        # Catalog stores screen_size as e.g. "55 inch"; we parse the number.
        _SCREEN_SIZE_RANGES: dict[str, tuple[int, int]] = {
            "small":  (32, 43),
            "medium": (50, 55),
            "large":  (65, 65),
            "xl":     (75, 85),
        }
        if slot.slot_id == "tv" and room_request.screen_size:
            size_range = _SCREEN_SIZE_RANGES.get(room_request.screen_size)
            if size_range:
                lo, hi = size_range
                def _in_range(c: Product) -> bool:
                    raw = c.specs.get("screen_size", "")
                    m = re.match(r"(\d+)", raw)
                    return lo <= int(m.group(1)) <= hi if m else False
                filtered = [c for c in candidates if _in_range(c)]
                if filtered:
                    candidates = filtered

        sourceable_slots.append((slot, candidates))

    _timing["sourcing_ms"] = round((time.monotonic() - _t) * 1000, 1)

    # Fire all selection LLM calls in parallel.
    # Each call returns (ranked_products, fit_reasons, null_reason).
    selection_results: dict[str, tuple[list, list, str | None]] = {}
    _t = time.monotonic()

    interests = room_request.interests

    from services.concurrency import acquire_llm_slots, release_llm_slots
    slot_count = len(sourceable_slots) or 1
    if not acquire_llm_slots(slot_count):
        raise HTTPException(status_code=503, detail="Server busy — too many concurrent design requests. Please retry in a moment.")

    _timing["semaphore_wait_ms"] = round((time.monotonic() - _t) * 1000, 1)
    _t_llm = time.monotonic()

    try:
        with ThreadPoolExecutor(max_workers=slot_count) as pool:
            futures = {
                pool.submit(
                    select_products, slot, style_profile, cands, interests,
                    pick_count_for_slot(slot.slot_id),
                ): slot.slot_id
                for slot, cands in sourceable_slots
            }
            for future in as_completed(futures):
                sid = futures[future]
                selection_results[sid] = future.result()
    finally:
        release_llm_slots(slot_count)

    _timing["selection_llm_ms"] = round((time.monotonic() - _t_llm) * 1000, 1)
    _timing["selection_ms"] = round((time.monotonic() - _t) * 1000, 1)
    logger.info(
        "Selected %d slots in %.1fs (parallel)",
        len(sourceable_slots),
        _timing["selection_ms"] / 1000,
    )

    # Build SlotResults for sourceable slots.
    sourceable_results: list[SlotResult] = []
    for slot, _cands in sourceable_slots:
        products, fit_reasons, null_reason = selection_results[slot.slot_id]
        if products:
            # Rank 1 = primary product, ranks 2+ = alternatives.
            primary = products[0]
            alts = [
                ProductResult(
                    product_id=p.product_id,
                    name=p.name,
                    normalized_price=p.normalized_price,
                    image_url=p.image_url,
                    buy_url=p.buy_url,
                    fit_reason=fit_reasons[i + 1],
                )
                for i, p in enumerate(products[1:])
            ]
            sourceable_results.append(SlotResult(
                slot_id=slot.slot_id,
                allocated_budget=slot.allocated_budget,
                owned=False,
                max_quantity=slot.max_quantity,
                product=ProductResult(
                    product_id=primary.product_id,
                    name=primary.name,
                    normalized_price=primary.normalized_price,
                    image_url=primary.image_url,
                    buy_url=primary.buy_url,
                    fit_reason=fit_reasons[0],
                ),
                alternatives=alts,
                null_reason=None,
            ))
        else:
            sourceable_results.append(SlotResult(
                slot_id=slot.slot_id,
                allocated_budget=slot.allocated_budget,
                owned=False,
                max_quantity=slot.max_quantity,
                product=None,
                alternatives=[],
                null_reason=null_reason or "no_candidate",
            ))

    # Merge and sort by slot_id for deterministic output order.
    slot_results = sorted(
        owned_results + sourceable_results,
        key=lambda s: s.slot_id,
    )

    # 6. Assemble response and store.
    response = _build_response(
        room_request.run_id,
        room_request.room_type or "bedroom",
        style_profile,
        slot_plan,
        slots_results=slot_results,
    )
    response.user_id = user["user_id"]
    _designs[response.run_id] = response

    # Persist to Supabase (write-through). Failure is logged but non-blocking.
    from services.design_store import save_design
    save_design(response, user_id=user["user_id"])

    # Track: design completed + selections.
    _elapsed = time.monotonic() - _start_time
    _timing["total_ms"] = round(_elapsed * 1000, 1)

    # Estimate API cost: ~16 Haiku selection calls + 1 Sonnet style + 1 Sonnet composition.
    _sel_count = len(sourceable_slots)
    _est_cost = round(0.012 * _sel_count + 0.02, 4)  # ~$0.012/selection + ~$0.02 style+comp

    logger.info(
        "Pipeline timing for %s: %s",
        response.run_id,
        " | ".join(f"{k}={v}" for k, v in _timing.items()),
    )

    log_event(response.run_id, "design_completed", {
        "slot_count": len(slot_results),
        "total_spent": response.total_spent,
        "elapsed_s": round(_elapsed, 1),
        "api_cost": _est_cost,
        "timing": _timing,
    }, api_cost=_est_cost, user_id=user["user_id"])

    return response


# ---------------------------------------------------------------------------
# GET /design/{run_id} — retrieve a saved board
# ---------------------------------------------------------------------------

@router.get("/design/{run_id}", response_model=DesignResponse)
async def get_design(run_id: str, user: CurrentUser) -> DesignResponse:
    """Re-fetch a previously generated design board. Auth-required, user-scoped."""
    return _get_design(run_id, user)


# ---------------------------------------------------------------------------
# POST /design/{run_id}/validate-selections — multi-select pool check
# ---------------------------------------------------------------------------

@router.post(
    "/design/{run_id}/validate-selections",
    response_model=ValidateSelectionsResponse,
)
async def validate_selections(
    run_id: str,
    req: ValidateSelectionsRequest,
    user: CurrentUser,
) -> ValidateSelectionsResponse:
    """Validate user's product selections against per-slot pool budgets.

    Prices are looked up from the stored design — the client sends only
    product_ids, never prices.  Unknown or tampered product_ids are rejected.
    """
    design = _get_design(run_id, user)

    # Build product price lookup from the stored design (source of truth).
    # Keys: (slot_id, product_id) → price.  Includes primary + alternatives.
    price_lookup: dict[tuple[str, str], float] = {}
    slot_map: dict[str, SlotResult] = {}
    for slot in design.slots:
        slot_map[slot.slot_id] = slot
        if slot.product:
            price_lookup[(slot.slot_id, slot.product.product_id)] = (
                slot.product.normalized_price
            )
        for alt in slot.alternatives:
            price_lookup[(slot.slot_id, alt.product_id)] = alt.normalized_price

    # Rebuild a lightweight SlotPlan for the validator.
    from schemas.slot import Slot
    from schemas.slot_plan import SlotPlan

    validator_slots = [
        Slot(
            slot_id=s.slot_id,
            allocated_budget=s.allocated_budget,
            required_specs=[],
            optional=False,
            max_quantity=s.max_quantity,
        )
        for s in design.slots
    ]
    slot_plan = SlotPlan(
        run_id=run_id,
        room_preset=design.room_type,
        target_budget=design.target_budget,
        slots=validator_slots,
    )

    # Resolve product_ids to server-side prices.  Reject unknown ids.
    slot_results: list[SlotValidationResult] = []
    resolved: dict[str, list[float]] = {}

    for sel in req.selections:
        unknown_ids = [
            pid for pid in sel.selected_product_ids
            if (sel.slot_id, pid) not in price_lookup
        ]
        if unknown_ids:
            slot_results.append(SlotValidationResult(
                slot_id=sel.slot_id,
                valid=False,
                total=0.0,
                reason=f"unknown_product:{','.join(unknown_ids)}",
            ))
            continue
        resolved[sel.slot_id] = [
            price_lookup[(sel.slot_id, pid)]
            for pid in sel.selected_product_ids
        ]

    # If any slots had unknown products, short-circuit with those errors.
    if slot_results:
        return ValidateSelectionsResponse(
            valid=False,
            total_spent=0.0,
            slots=slot_results,
        )

    # Run the pool validator on resolved prices.
    all_valid, total_spent, per_slot = validate_pool_spend(resolved, slot_plan)

    return ValidateSelectionsResponse(
        valid=all_valid,
        total_spent=total_spent,
        slots=[
            SlotValidationResult(
                slot_id=sid, valid=ok, total=slot_total, reason=reason,
            )
            for sid, ok, slot_total, reason in per_slot
        ],
    )


# ---------------------------------------------------------------------------
# PATCH /design/{run_id}/finalize — freeze the user's curated selections
# ---------------------------------------------------------------------------

class FinalizeRequest(BaseModel):
    """Body for PATCH /design/{run_id}/finalize."""
    selections: dict[str, list[str]]  # slot_id → [product_id, ...]
    skipped_slots: list[str] = []


@router.patch("/design/{run_id}/finalize")
async def finalize_design(run_id: str, body: FinalizeRequest, user: CurrentUser) -> DesignResponse:
    """Freeze the user's curated selections as the authoritative design.

    This is the single persist point for the settled room — called once when
    the user finishes selection (auto-fill or guided curation).  Sets
    selected_products on each slot, recomputes total_spent, and marks the
    design as finalized.  Subsequent calls return 409 (already frozen).
    """
    from datetime import datetime, timezone
    from services.design_store import save_design

    design = _get_design(run_id, user)  # 404 or 503 if unavailable

    # Already finalized — idempotent reject.
    if design.finalized_at is not None:
        raise HTTPException(status_code=409, detail="Design already finalized")

    # Build product lookup: all products (primary + alternatives) by (slot_id, product_id).
    product_lookup: dict[tuple[str, str], ProductResult] = {}
    for slot in design.slots:
        if slot.product:
            product_lookup[(slot.slot_id, slot.product.product_id)] = slot.product
        for alt in slot.alternatives:
            product_lookup[(slot.slot_id, alt.product_id)] = alt

    skipped = set(body.skipped_slots)

    # Resolve selections to full ProductResult objects per slot.
    for slot in design.slots:
        if slot.owned or slot.product is None:
            continue
        if slot.slot_id in skipped:
            slot.selected_products = []
            continue
        selected_ids = body.selections.get(slot.slot_id, [])
        if not selected_ids:
            continue
        resolved = []
        for pid in selected_ids:
            prod = product_lookup.get((slot.slot_id, pid))
            if prod:
                resolved.append(prod)
        slot.selected_products = resolved

    # Recompute total_spent from curated selections.
    design.total_spent = sum(
        p.normalized_price
        for slot in design.slots
        for p in slot.selected_products
    )
    design.finalized_at = datetime.now(timezone.utc).isoformat()

    # Persist to both in-memory cache and Supabase.
    _designs[run_id] = design
    save_design(design, user_id=user["user_id"])

    log_event(run_id, "design_finalized", {
        "total_spent": design.total_spent,
        "slot_count": sum(1 for s in design.slots if s.selected_products),
        "skipped_count": len(skipped),
    }, user_id=user["user_id"])

    _slot_products = []
    for slot in design.slots:
        for p in slot.selected_products:
            _slot_products.append({
                "slot_id": slot.slot_id,
                "product_id": p.product_id,
                "product_name": p.name,
                "product_price": float(p.normalized_price),
                "is_multiselect": len(slot.selected_products) > 1,
            })
    log_selections(
        run_id=run_id,
        room_type=design.room_type,
        aesthetic=design.style.style_name,
        mood=design.style.mood,
        color_palette=design.style.keywords[:3],
        keywords=design.style.keywords,
        budget=design.target_budget,
        slot_products=_slot_products,
        user_id=user["user_id"],
    )

    return design


# ---------------------------------------------------------------------------
# POST /design/{run_id}/render — generate AI room render
# ---------------------------------------------------------------------------

class RenderRequest(BaseModel):
    """Body for POST /design/{run_id}/render."""
    selections: dict[str, list[str]] = {}  # slot_id → [product_id, ...] (legacy, ignored if finalized)


def _render_worker(
    job_id: str,
    run_id: str,
    room_type: str,
    style_name: str,
    mood: str,
    keywords: list[str],
    products: dict[str, list[dict]],
    user_id: str,
) -> None:
    """Background thread: wait for render semaphore slot, run render, update Redis.

    Renders are async (user already has 202, frontend polls). The worker just
    waits for a slot — no hard failure on contention. The 600s acquire timeout
    is a safety net for stuck keys, not a normal path. If it somehow fires,
    we log it as an error but still don't set status="failed" — we proceed
    without the semaphore so the render completes (OpenAI may 429 us, but
    that's better than a dead-end error for the user).
    """
    from services.redis_client import get_redis
    from services.render_service import render_room
    from services.concurrency import acquire_render_slot, release_render_slot

    r = get_redis()
    acquired = False
    try:
        acquired = acquire_render_slot()
        if not acquired:
            logger.error(
                "Render semaphore 600s timeout for job %s (run %s) — proceeding without slot",
                job_id, run_id,
            )

        if r:
            r.hset(f"render_job:{job_id}", "status", "rendering")

        _render_t = time.monotonic()
        render_path = render_room(
            run_id=run_id,
            room_type=room_type,
            style_name=style_name,
            mood=mood,
            keywords=keywords,
            products=products,
        )
        _render_ms = round((time.monotonic() - _render_t) * 1000, 1)

        if render_path is None:
            if r:
                r.hset(f"render_job:{job_id}", mapping={
                    "status": "failed",
                    "error": "Room render generation failed",
                })
            logger.info("Render failed for %s in %.1fms", run_id, _render_ms)
            return

        _render_quality = os.environ.get("RENDER_QUALITY", "medium")
        _render_cost = 0.10 if _render_quality == "medium" else 0.30
        logger.info("Render completed for %s: render_ms=%.1f", run_id, _render_ms)
        log_event(run_id, "render_generated", {
            "render_cost": _render_cost, "cached": False,
            "render_ms": _render_ms,
        }, api_cost=_render_cost, user_id=user_id)

        if r:
            r.hset(f"render_job:{job_id}", mapping={
                "status": "complete",
                "render_url": f"/renders/{run_id}.jpg",
            })
    except Exception:
        logger.exception("Render worker failed for job %s (run %s)", job_id, run_id)
        try:
            if r:
                r.hset(f"render_job:{job_id}", mapping={
                    "status": "failed",
                    "error": "Room render generation failed",
                })
        except Exception:
            pass
    finally:
        if acquired:
            release_render_slot()


@router.post("/design/{run_id}/render")
@limiter.limit("3/minute")
async def generate_render(request: Request, run_id: str, user: CurrentUser, body: RenderRequest | None = None) -> dict:
    """Generate a photorealistic AI room render from the finalized design.

    Returns 200 with render_url if cached, or 202 with job_id if queued
    for async generation. Falls back to synchronous if Redis unavailable.
    """
    from services.redis_client import get_redis
    from services.render_service import render_room, render_exists

    design = _get_design(run_id, user)

    log_event(run_id, "render_requested", user_id=user["user_id"])

    if render_exists(run_id):
        log_event(run_id, "render_generated", {"render_cost": 0.0, "cached": True}, api_cost=0.0, user_id=user["user_id"])
        return {"run_id": run_id, "render_url": f"/renders/{run_id}.jpg", "status": "complete", "cached": True}

    if design.finalized_at is None:
        raise HTTPException(status_code=400, detail="Design must be finalized before rendering")

    products: dict[str, list[dict]] = {}
    for slot in design.slots:
        if slot.selected_products:
            products[slot.slot_id] = [
                {"name": p.name, "image_url": p.image_url}
                for p in slot.selected_products
            ]

    r = get_redis()
    if r is not None:
        job_id = str(uuid.uuid4())
        r.hset(f"render_job:{job_id}", mapping={
            "status": "pending",
            "run_id": run_id,
        })
        r.expire(f"render_job:{job_id}", 3600)

        t = threading.Thread(
            target=_render_worker,
            args=(job_id, run_id, design.room_type, design.style.style_name,
                  design.style.mood, design.style.keywords, products, user["user_id"]),
            daemon=True,
        )
        t.start()

        from starlette.responses import JSONResponse
        return JSONResponse(
            status_code=202,
            content={"job_id": job_id, "run_id": run_id, "status": "pending"},
        )

    # Fallback: no Redis → synchronous render (current behavior for local dev)
    render_path = render_room(
        run_id=run_id,
        room_type=design.room_type,
        style_name=design.style.style_name,
        mood=design.style.mood,
        keywords=design.style.keywords,
        products=products,
    )

    if render_path is None:
        raise HTTPException(status_code=500, detail="Room render generation failed")

    _render_quality = os.environ.get("RENDER_QUALITY", "medium")
    _render_cost = 0.10 if _render_quality == "medium" else 0.30
    log_event(run_id, "render_generated", {
        "render_cost": _render_cost, "cached": False,
    }, api_cost=_render_cost, user_id=user["user_id"])

    return {"run_id": run_id, "render_url": f"/renders/{run_id}.jpg", "status": "complete", "cached": False}


@router.get("/design/{run_id}/render/status")
@limiter.limit("10/minute")
async def render_status(request: Request, run_id: str, user: CurrentUser, job_id: str | None = Query(None)) -> dict:
    """Poll render job status. Returns current state of an async render."""
    from services.redis_client import get_redis
    from services.render_service import render_exists

    if render_exists(run_id):
        return {"status": "complete", "render_url": f"/renders/{run_id}.jpg"}

    if job_id is None:
        return {"status": "unknown"}

    r = get_redis()
    if r is None:
        return {"status": "unknown"}

    data = r.hgetall(f"render_job:{job_id}")
    if not data:
        return {"status": "unknown"}

    result: dict = {"status": data.get("status", "unknown")}
    if data.get("render_url"):
        result["render_url"] = data["render_url"]
    if data.get("error"):
        result["error"] = data["error"]
    return result


# ---------------------------------------------------------------------------
# POST /design/{run_id}/hotspots — detect product locations in the render
# ---------------------------------------------------------------------------

@router.post("/design/{run_id}/hotspots")
@limiter.limit("3/minute")
async def detect_hotspots(request: Request, run_id: str, user: CurrentUser) -> dict:
    """Use a vision model to detect product bounding boxes in the room render.

    Returns approximate hotspot coordinates (0-1 fractions) for each
    detected hero product, mapped to their buy links and prices.
    Cached per run_id alongside the render.
    """
    from services.render_service import render_exists, get_render_path
    from services.hotspot_service import detect_product_hotspots, hotspots_exist, load_hotspots

    design = _get_design(run_id, user)  # 404 or 503 if unavailable

    if not render_exists(run_id):
        raise HTTPException(status_code=400, detail="Render not yet generated")

    # Return cached hotspots.
    if hotspots_exist(run_id):
        return {"run_id": run_id, "hotspots": load_hotspots(run_id), "cached": True}

    # Build product info for the hotspot detector.
    products: dict[str, dict] = {}
    for slot in design.slots:
        if slot.product:
            products[slot.slot_id] = {
                "name": slot.product.name,
                "price": slot.product.normalized_price,
                "buy_url": slot.product.buy_url,
            }

    render_path = str(get_render_path(run_id))
    hotspots = detect_product_hotspots(run_id, render_path, products, room_type=design.room_type)

    if hotspots is None:
        raise HTTPException(status_code=500, detail="Hotspot detection failed")

    return {"run_id": run_id, "hotspots": hotspots, "cached": False}


# ---------------------------------------------------------------------------
# DELETE /account — full account + data deletion cascade
# ---------------------------------------------------------------------------

class DeleteAccountResponse(BaseModel):
    deleted: bool
    completed_steps: list[str]
    failed_step: str | None = None
    message: str


def _invalidate_user_cache(user_id: str) -> int:
    """Remove all designs belonging to user_id from the in-memory cache."""
    to_remove = [
        rid for rid, design in _designs.items()
        if hasattr(design, "user_id") and design.user_id == user_id
    ]
    for rid in to_remove:
        del _designs[rid]
    return len(to_remove)


@router.delete("/account", response_model=DeleteAccountResponse)
async def delete_account(user: CurrentUser) -> DeleteAccountResponse:
    """Delete the caller's account and all associated data.

    Cascade order (designed for safe partial failure):
      1. Query run_ids from designs (read-only, needed for render cleanup)
      2. Delete auth user (PII first — email + password hash)
      3. Delete render files from disk (idempotent)
      4. DELETE selections WHERE user_id
      5. DELETE events WHERE user_id
      6. DELETE designs WHERE user_id
      7. Invalidate in-memory cache (can't fail)

    Auth is deleted BEFORE app data so PII is removed even if later
    steps fail. The JWT remains valid (~1h) for retry after auth deletion.
    """
    from pathlib import Path
    from app.auth import mark_user_deleted
    from services.supabase_client import get_client, delete_user

    user_id = user["user_id"]
    user_token = user["token"]
    completed: list[str] = []
    auth_deleted = False

    # Step 1: Query run_ids (need these before deleting designs rows)
    run_ids: list[str] = []
    client = get_client()
    if client is None:
        return DeleteAccountResponse(
            deleted=False,
            completed_steps=[],
            failed_step="init",
            message="Account deletion failed — storage unavailable. Please try again or contact support.",
        )

    try:
        resp = (
            client.table("designs")
            .select("run_id")
            .eq("user_id", user_id)
            .execute()
        )
        run_ids = [row["run_id"] for row in (resp.data or [])]
        completed.append("query_run_ids")
    except Exception as exc:
        logger.error("delete_account: failed to query run_ids for %s: %s", user_id, exc)
        return DeleteAccountResponse(
            deleted=False,
            completed_steps=completed,
            failed_step="query_run_ids",
            message="Account deletion failed and could not complete. No data was removed. Please try again or contact support.",
        )

    # Step 2: Revoke sessions + delete auth user (PII — email, password hash, metadata)
    try:
        try:
            client.auth.admin.sign_out(user_token, scope="global")
        except Exception:
            pass  # Best-effort; delete_user is the critical call
        delete_user(user_id)
        mark_user_deleted(user_id)
        auth_deleted = True
        completed.append("auth_delete")
    except Exception as exc:
        logger.error("delete_account: auth deletion failed for %s: %s", user_id, exc)
        return DeleteAccountResponse(
            deleted=False,
            completed_steps=completed,
            failed_step="auth_delete",
            message="Account deletion failed and could not complete. No data was removed. Please try again or contact support.",
        )

    # From here on, auth IS deleted. Failure message changes accordingly.
    def _partial_failure(step: str) -> DeleteAccountResponse:
        return DeleteAccountResponse(
            deleted=False,
            completed_steps=completed,
            failed_step=step,
            message="Your login credentials have been removed. Please try again to clean up remaining data, or contact support.",
        )

    # Step 3: Delete render files (idempotent — missing_ok)
    renders_dir = Path(__file__).parent.parent.parent / "data" / "renders"
    try:
        for rid in run_ids:
            (renders_dir / f"{rid}.jpg").unlink(missing_ok=True)
            (renders_dir / f"{rid}_hotspots.json").unlink(missing_ok=True)
        completed.append("render_files")
    except Exception as exc:
        logger.error("delete_account: render cleanup failed for %s: %s", user_id, exc)
        return _partial_failure("render_files")

    # Step 4: DELETE selections
    try:
        client.table("selections").delete().eq("user_id", user_id).execute()
        completed.append("selections")
    except Exception as exc:
        if "does not exist" in str(exc) or "42P01" in str(exc):
            completed.append("selections")
        else:
            logger.error("delete_account: selections delete failed for %s: %s", user_id, exc)
            return _partial_failure("selections")

    # Step 5: DELETE events
    try:
        client.table("events").delete().eq("user_id", user_id).execute()
        completed.append("events")
    except Exception as exc:
        if "does not exist" in str(exc) or "42P01" in str(exc):
            completed.append("events")
        else:
            logger.error("delete_account: events delete failed for %s: %s", user_id, exc)
            return _partial_failure("events")

    # Step 6: DELETE designs
    try:
        client.table("designs").delete().eq("user_id", user_id).execute()
        completed.append("designs")
    except Exception as exc:
        if "does not exist" in str(exc) or "42P01" in str(exc):
            completed.append("designs")
        else:
            logger.error("delete_account: designs delete failed for %s: %s", user_id, exc)
            return _partial_failure("designs")

    # Step 7: Invalidate in-memory cache (can't fail)
    evicted = _invalidate_user_cache(user_id)
    completed.append("cache_invalidate")
    logger.info("delete_account: fully deleted user %s (%d cached designs evicted)", user_id, evicted)

    return DeleteAccountResponse(
        deleted=True,
        completed_steps=completed,
        failed_step=None,
        message="Your account and all associated data have been permanently deleted.",
    )


# ---------------------------------------------------------------------------
# POST /click — stub for later
# ---------------------------------------------------------------------------

@router.post("/click")
async def record_click(event: dict) -> dict:
    raise NotImplementedError("Stage 10: implement click logging")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# POST /track — client-side event logging (fire-and-forget)
# ---------------------------------------------------------------------------

class TrackEventRequest(BaseModel):
    run_id: str
    event_type: str
    data: dict = {}


_ALLOWED_CLIENT_EVENTS = {
    "render_viewed", "hotspot_clicked", "buy_link_clicked", "export_cart_clicked",
}


@router.post("/track")
async def track_event(req: TrackEventRequest, user: CurrentUser) -> dict:
    """Log a client-side funnel event. Always returns 200 — never fails the client."""
    if req.event_type not in _ALLOWED_CLIENT_EVENTS:
        return {"ok": False, "reason": "unknown_event_type"}
    log_event(req.run_id, req.event_type, req.data, user_id=user["user_id"])
    return {"ok": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_response(
    run_id: str,
    room_type: str,
    style_profile: object,
    slot_plan: object,
    *,
    slots_results: list[SlotResult],
    gate_error: str | None = None,
) -> DesignResponse:
    """Assemble a DesignResponse from pipeline outputs."""
    total_spent = sum(
        s.product.normalized_price
        for s in slots_results
        if s.product is not None
    )

    return DesignResponse(
        run_id=run_id,
        room_type=room_type,
        style=StyleResult(
            style_name=style_profile.style_name,  # type: ignore[attr-defined]
            keywords=style_profile.keywords,  # type: ignore[attr-defined]
            mood=style_profile.mood,  # type: ignore[attr-defined]
            confidence=style_profile.confidence,  # type: ignore[attr-defined]
            fallback=style_profile.fallback,  # type: ignore[attr-defined]
        ),
        target_budget=slot_plan.target_budget,  # type: ignore[attr-defined]
        total_spent=total_spent,
        is_feasible=slot_plan.is_feasible if not gate_error else False,  # type: ignore[attr-defined]
        slots=slots_results,
    )

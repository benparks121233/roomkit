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
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

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


def _get_design(run_id: str) -> DesignResponse:
    """Retrieve a design: cache first, then Supabase, with three-outcome handling.

    Returns the DesignResponse on success.
    Raises HTTPException 404 if the design genuinely doesn't exist anywhere.
    Raises HTTPException 503 if the Supabase query failed (retry-able).
    """
    # 1. Fast path: in-memory cache
    if run_id in _designs:
        return _designs[run_id]

    # 2. Slow path: Supabase lookup
    from services.design_store import DesignStoreError, load_design

    try:
        design = load_design(run_id)
    except KeyError:
        # Row genuinely absent — nowhere to find it
        raise HTTPException(status_code=404, detail=f"Design {run_id} not found")
    except DesignStoreError as exc:
        # Connection/query failure — might exist but we can't reach it
        logger.warning("_get_design: Supabase read failed for %s: %s", run_id, exc)
        raise HTTPException(
            status_code=503,
            detail="Storage temporarily unavailable — please retry",
        )

    # Populate cache for subsequent fast reads
    _designs[run_id] = design
    return design


# ---------------------------------------------------------------------------
# POST /design — run the full pipeline
# ---------------------------------------------------------------------------

@router.post("/design", response_model=DesignResponse)
async def create_design(req: DesignRequest) -> DesignResponse:
    """Run the full RoomKit pipeline and return a shoppable board.

    This makes real LLM calls (~17 total) and can take 60-90 seconds.
    """
    # 0. Track: design started.
    _start_time = time.monotonic()

    # 1. Intake — validate and produce a RoomRequest.
    try:
        room_request = parse_intake(req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    log_event(room_request.run_id, "design_started", {
        "room_type": room_request.room_type or "bedroom",
        "budget": req.budget,
        "aesthetic": req.core_aesthetic or "",
    })

    # 2. Style interpretation — real LLM call.
    style_profile = interpret_style(room_request)

    # 3. Composition — real LLM call for weight proposal, deterministic budget math.
    slot_plan = plan_composition(room_request, style_profile)

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
        # For decor slots, cap at 50% of the total decor pool to prevent
        # one expensive item eating the entire decor allocation.
        max_price = slot.allocated_budget * 1.5
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

    # Fire all selection LLM calls in parallel.
    # Each call returns (ranked_products, fit_reasons, null_reason).
    selection_results: dict[str, tuple[list, list, str | None]] = {}
    t0 = time.monotonic()

    interests = room_request.interests

    with ThreadPoolExecutor(max_workers=len(sourceable_slots) or 1) as pool:
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

    elapsed = time.monotonic() - t0
    logger.info(
        "Selected %d slots in %.1fs (parallel)",
        len(sourceable_slots),
        elapsed,
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
    _designs[response.run_id] = response

    # Persist to Supabase (write-through). Failure is logged but non-blocking.
    from services.design_store import save_design
    save_design(response)

    # Track: design completed + selections.
    _elapsed = time.monotonic() - _start_time
    # Estimate API cost: ~16 Haiku selection calls + 1 Sonnet style + 1 Sonnet composition.
    _sel_count = len(sourceable_slots)
    _est_cost = round(0.012 * _sel_count + 0.02, 4)  # ~$0.012/selection + ~$0.02 style+comp

    log_event(response.run_id, "design_completed", {
        "slot_count": len(slot_results),
        "total_spent": response.total_spent,
        "elapsed_s": round(_elapsed, 1),
        "api_cost": _est_cost,
    }, api_cost=_est_cost)

    # Log per-slot selections (default rank-1 picks).
    _slot_products = []
    for sr in slot_results:
        if sr.product:
            _slot_products.append({
                "slot_id": sr.slot_id,
                "product_id": sr.product.product_id,
                "product_name": sr.product.name,
                "product_price": float(sr.product.normalized_price),
                "is_multiselect": (sr.max_quantity or 1) > 1,
            })
    log_selections(
        run_id=response.run_id,
        room_type=response.room_type,
        aesthetic=response.style.style_name,
        mood=response.style.mood,
        color_palette=getattr(style_profile, "color_palette", []),
        keywords=response.style.keywords,
        budget=response.target_budget,
        slot_products=_slot_products,
    )

    return response


# ---------------------------------------------------------------------------
# GET /design/{run_id} — retrieve a saved board
# ---------------------------------------------------------------------------

@router.get("/design/{run_id}", response_model=DesignResponse)
async def get_design(run_id: str) -> DesignResponse:
    """Re-fetch a previously generated design board."""
    return _get_design(run_id)


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
) -> ValidateSelectionsResponse:
    """Validate user's product selections against per-slot pool budgets.

    Prices are looked up from the stored design — the client sends only
    product_ids, never prices.  Unknown or tampered product_ids are rejected.
    """
    design = _get_design(run_id)

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
async def finalize_design(run_id: str, body: FinalizeRequest) -> DesignResponse:
    """Freeze the user's curated selections as the authoritative design.

    This is the single persist point for the settled room — called once when
    the user finishes selection (auto-fill or guided curation).  Sets
    selected_products on each slot, recomputes total_spent, and marks the
    design as finalized.  Subsequent calls return 409 (already frozen).
    """
    from datetime import datetime, timezone
    from services.design_store import save_design

    design = _get_design(run_id)  # 404 or 503 if unavailable

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
    save_design(design)

    log_event(run_id, "design_finalized", {
        "total_spent": design.total_spent,
        "slot_count": sum(1 for s in design.slots if s.selected_products),
        "skipped_count": len(skipped),
    })

    return design


# ---------------------------------------------------------------------------
# POST /design/{run_id}/render — generate AI room render
# ---------------------------------------------------------------------------

class RenderRequest(BaseModel):
    """Body for POST /design/{run_id}/render."""
    selections: dict[str, list[str]] = {}  # slot_id → [product_id, ...] (legacy, ignored if finalized)


@router.post("/design/{run_id}/render")
async def generate_render(run_id: str, body: RenderRequest | None = None) -> dict:
    """Generate a photorealistic AI room render from the finalized design.

    Reads selected_products from the persisted design — the render always
    matches the frozen, finalized room.  Returns 400 if design is not
    yet finalized.
    """
    from services.render_service import render_room, render_exists, get_render_path

    design = _get_design(run_id)  # 404 or 503 if unavailable

    log_event(run_id, "render_requested")

    # Return cached render if it exists.
    if render_exists(run_id):
        log_event(run_id, "render_generated", {"render_cost": 0.0, "cached": True}, api_cost=0.0)
        return {"run_id": run_id, "render_url": f"/renders/{run_id}.jpg", "cached": True}

    # Require finalized design — render operates on frozen state only.
    if design.finalized_at is None:
        raise HTTPException(status_code=400, detail="Design must be finalized before rendering")

    # Build render product list from persisted selected_products.
    products: dict[str, list[dict]] = {}
    for slot in design.slots:
        if slot.selected_products:
            products[slot.slot_id] = [
                {"name": p.name, "image_url": p.image_url}
                for p in slot.selected_products
            ]

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

    import os
    _render_quality = os.environ.get("RENDER_QUALITY", "medium")
    _render_cost = 0.10 if _render_quality == "medium" else 0.30
    log_event(run_id, "render_generated", {
        "render_cost": _render_cost, "cached": False,
    }, api_cost=_render_cost)

    return {"run_id": run_id, "render_url": f"/renders/{run_id}.jpg", "cached": False}


# ---------------------------------------------------------------------------
# POST /design/{run_id}/hotspots — detect product locations in the render
# ---------------------------------------------------------------------------

@router.post("/design/{run_id}/hotspots")
async def detect_hotspots(run_id: str) -> dict:
    """Use a vision model to detect product bounding boxes in the room render.

    Returns approximate hotspot coordinates (0-1 fractions) for each
    detected hero product, mapped to their buy links and prices.
    Cached per run_id alongside the render.
    """
    from services.render_service import render_exists, get_render_path
    from services.hotspot_service import detect_product_hotspots, hotspots_exist, load_hotspots

    design = _get_design(run_id)  # 404 or 503 if unavailable

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
async def track_event(req: TrackEventRequest) -> dict:
    """Log a client-side funnel event. Always returns 200 — never fails the client."""
    if req.event_type not in _ALLOWED_CLIENT_EVENTS:
        return {"ok": False, "reason": "unknown_event_type"}
    log_event(req.run_id, req.event_type, req.data)
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

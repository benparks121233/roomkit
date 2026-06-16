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
from services.composition_gate import validate_composition
from services.composition_service import plan_composition
from services.intake_service import parse_intake
from services.selection_service import select_products, pick_count_for_slot
from services.sourcing.amazon_adapter import AmazonAdapter
from services.style_service import interpret_style
from validators.budget_rules import validate_pool_spend

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory design storage (v1 — ephemeral, lives as long as uvicorn process)
# ---------------------------------------------------------------------------
_designs: dict[str, DesignResponse] = {}


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
            user_budget=req.budget,
        )

    # 5. Sourcing + selection — parallel LLM calls for non-owned slots.
    adapter = AmazonAdapter()
    slot_results: list[SlotResult] = []

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
        candidates = adapter.fetch_candidates(
            slot.slot_id,
            style_profile.keywords,
            (0.0, slot.allocated_budget * 1.5),
            spec_hints,
            interests=room_request.interests or None,
        )
        logger.info("Sourced %s: %d candidates (budget $%.2f)", slot.slot_id, len(candidates), slot.allocated_budget)

        # Mirror type filter: if user selected a mirror type (e.g. "round",
        # "full_length"), prefer candidates whose name matches that type.
        # Fall back to full pool if too few type-matches remain.
        if slot.slot_id == "mirror" and room_request.mirror_type:
            mtype = room_request.mirror_type.replace("_", " ").lower()
            typed = [c for c in candidates if mtype in c.name.lower()]
            if len(typed) >= 5:
                candidates = typed

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
        user_budget=req.budget,
    )
    _designs[response.run_id] = response

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
    if run_id not in _designs:
        raise HTTPException(status_code=404, detail=f"Design {run_id} not found")
    return _designs[run_id]


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
    if run_id not in _designs:
        raise HTTPException(status_code=404, detail=f"Design {run_id} not found")
    design = _designs[run_id]

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
# POST /design/{run_id}/render — generate AI room render
# ---------------------------------------------------------------------------

class RenderRequest(BaseModel):
    """Body for POST /design/{run_id}/render."""
    selections: dict[str, list[str]] = {}  # slot_id → [product_id, ...]


@router.post("/design/{run_id}/render")
async def generate_render(run_id: str, body: RenderRequest | None = None) -> dict:
    """Generate a photorealistic AI room render from the user's selected products.

    The request body contains the user's actual selections (slot_id → product_ids)
    so the render uses exactly what the user picked, not server defaults.
    """
    from services.render_service import render_room, render_exists, get_render_path

    if run_id not in _designs:
        raise HTTPException(status_code=404, detail=f"Design {run_id} not found")

    log_event(run_id, "render_requested")

    # Return cached render if it exists.
    if render_exists(run_id):
        log_event(run_id, "render_generated", {"render_cost": 0.0, "cached": True}, api_cost=0.0)
        return {"run_id": run_id, "render_url": f"/renders/{run_id}.jpg", "cached": True}

    design = _designs[run_id]
    user_selections = body.selections if body else {}

    # Build product lookup: all products (primary + alternatives) by (slot_id, product_id).
    product_lookup: dict[tuple[str, str], ProductResult] = {}
    for slot in design.slots:
        if slot.product:
            product_lookup[(slot.slot_id, slot.product.product_id)] = slot.product
        for alt in slot.alternatives:
            product_lookup[(slot.slot_id, alt.product_id)] = alt

    # Resolve the user's selections to actual product data.
    # For multi-select slots (wall_art, plants, etc.), include ALL selected
    # products so the render shows every item the user picked.
    products: dict[str, list[dict]] = {}
    for slot in design.slots:
        slot_id = slot.slot_id
        selected_ids = user_selections.get(slot_id, [])

        if selected_ids:
            items = []
            for pid in selected_ids:
                prod = product_lookup.get((slot_id, pid))
                if prod:
                    items.append({
                        "name": prod.name,
                        "image_url": prod.image_url,
                    })
            if items:
                products[slot_id] = items
                continue

        # Fallback to rank-1 default
        if slot.product:
            products[slot_id] = [{
                "name": slot.product.name,
                "image_url": slot.product.image_url,
            }]

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

    if run_id not in _designs:
        raise HTTPException(status_code=404, detail=f"Design {run_id} not found")

    if not render_exists(run_id):
        raise HTTPException(status_code=400, detail="Render not yet generated")

    # Return cached hotspots.
    if hotspots_exist(run_id):
        return {"run_id": run_id, "hotspots": load_hotspots(run_id), "cached": True}

    design = _designs[run_id]

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
    user_budget: float = 1500.0,
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
        user_budget=user_budget,
        total_spent=total_spent,
        is_feasible=slot_plan.is_feasible if not gate_error else False,  # type: ignore[attr-defined]
        slots=slots_results,
    )

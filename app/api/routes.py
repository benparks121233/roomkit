# app/api/routes.py
# All HTTP route handlers.
# Owns: request parsing, delegating to services, returning responses.
# Business logic never lives here — it belongs in services/ and validators/.
# Stage 1: stub endpoints that return 501 until the pipeline is wired.

from fastapi import APIRouter

router = APIRouter()


@router.post("/design")
async def create_design(request: dict) -> dict:
    # Stage 3+: parse RoomRequest, run intake → style → composition →
    # sourcing → selection → snapshot → validate → render → assemble.
    raise NotImplementedError("Stage 3: implement design pipeline")


@router.get("/design/{run_id}")
async def get_design(run_id: str) -> dict:
    # Stage 8+: load design from DB, verify snapshot freshness, return board.
    raise NotImplementedError("Stage 8: implement design retrieval")


@router.post("/click")
async def record_click(event: dict) -> dict:
    # Stage 10: log click event (run_id, slot_id, product_id, source).
    raise NotImplementedError("Stage 10: implement click logging")

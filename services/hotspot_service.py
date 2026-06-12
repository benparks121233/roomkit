# services/hotspot_service.py
# Owns: mapping product hotspots onto AI-rendered room images.
#
# Primary approach: use predetermined positions from the render prompt's
# layout specification (HOTSPOT_POSITIONS in render_service.py). Since we
# tell the render where to place each item, we already know where they are.
#
# Results are cached as JSON alongside the render image.

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_RENDERS_DIR = Path(__file__).parent.parent / "data" / "renders"


def _hotspots_path(run_id: str) -> Path:
    return _RENDERS_DIR / f"{run_id}_hotspots.json"


def hotspots_exist(run_id: str) -> bool:
    return _hotspots_path(run_id).exists()


def load_hotspots(run_id: str) -> list[dict]:
    path = _hotspots_path(run_id)
    if not path.exists():
        return []
    return json.loads(path.read_text())


def detect_product_hotspots(
    run_id: str,
    render_path: str,
    products: dict[str, dict],
    room_type: str = "bedroom",
) -> list[dict] | None:
    """Map product hotspots onto a room render using predetermined positions.

    Uses the same layout coordinates that the render prompt specified, so
    hotspots land exactly where the render was told to place items — no
    unreliable post-hoc vision detection needed.

    Args:
        run_id: Design ID for caching.
        render_path: Path to the rendered room JPEG (unused but kept for API compat).
        products: Dict of slot_id → {"name": str, "price": float, "buy_url": str}.
        room_type: "bedroom" or "living_room" — determines position layout.

    Returns:
        List of hotspot dicts, or None on failure.
    """
    # Check cache.
    cache_path = _hotspots_path(run_id)
    if cache_path.exists():
        return json.loads(cache_path.read_text())

    try:
        from services.render_service import HOTSPOT_POSITIONS

        positions = HOTSPOT_POSITIONS.get(room_type, HOTSPOT_POSITIONS.get("bedroom", {}))

        hotspots = []
        for slot_id, prod in products.items():
            pos = positions.get(slot_id)
            if not pos:
                logger.debug("No position defined for slot %s in %s", slot_id, room_type)
                continue

            hotspots.append({
                "slot_id": slot_id,
                "x": pos["x"],
                "y": pos["y"],
                "w": pos["w"],
                "h": pos["h"],
                "product_name": prod["name"],
                "price": prod["price"],
                "buy_url": prod["buy_url"],
            })

        # Cache.
        cache_path.write_text(json.dumps(hotspots, indent=2))
        logger.info("Mapped %d hotspots for %s (%s layout)", len(hotspots), run_id, room_type)
        return hotspots

    except Exception:
        logger.exception("Hotspot mapping failed for %s", run_id)
        return None

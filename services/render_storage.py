from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

BUCKET = "renders"


def upload_render(run_id: str, local_path: Path) -> str | None:
    """Upload a render JPEG to Supabase Storage.

    Returns the public URL on success, None on failure (fail-open).
    """
    from services.supabase_client import get_client

    client = get_client()
    if client is None:
        logger.warning("render_storage: Supabase not configured — render not uploaded")
        return None

    object_path = f"{run_id}.jpg"
    try:
        with open(local_path, "rb") as f:
            file_bytes = f.read()

        client.storage.from_(BUCKET).upload(
            object_path,
            file_bytes,
            {"content-type": "image/jpeg", "cache-control": "public, max-age=31536000"},
        )

        url = client.storage.from_(BUCKET).get_public_url(object_path)
        logger.info("render_storage: uploaded %s (%d KB)", object_path, len(file_bytes) // 1024)
        return url
    except Exception:
        logger.exception("render_storage: upload failed for %s", run_id)
        return None


def save_render_url(run_id: str, render_url: str) -> None:
    """Write the render_url to the design row."""
    from services.supabase_client import get_client

    client = get_client()
    if client is None:
        return

    try:
        client.table("designs").update(
            {"render_url": render_url},
        ).eq("run_id", run_id).execute()
        logger.info("render_storage: saved render_url for %s", run_id)
    except Exception:
        logger.exception("render_storage: failed to save render_url for %s", run_id)

from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

BUCKET = "renders"

_VERIFY_ATTEMPTS = 4
_VERIFY_DELAYS = [0.5, 1.0, 2.0, 3.0]


def _verify_retrievable(url: str) -> bool:
    """HEAD-check that the uploaded object is actually retrievable."""
    for i in range(_VERIFY_ATTEMPTS):
        try:
            r = httpx.head(url, timeout=5, follow_redirects=True)
            if r.status_code == 200:
                logger.info("render_storage: verified retrievable on attempt %d", i + 1)
                return True
            logger.warning("render_storage: verify attempt %d got %d", i + 1, r.status_code)
        except Exception as e:
            logger.warning("render_storage: verify attempt %d error: %s", i + 1, e)
        if i < _VERIFY_ATTEMPTS - 1:
            time.sleep(_VERIFY_DELAYS[i])
    return False


def upload_render(run_id: str, local_path: Path) -> str | None:
    """Upload a render JPEG to Supabase Storage.

    Returns the public URL on success, None on failure (fail-open).
    Verifies the object is retrievable before returning (storage propagation).
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

        if not _verify_retrievable(url):
            logger.warning("render_storage: object not retrievable after upload — returning URL anyway (frontend will retry)")

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

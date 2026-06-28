# services/concurrency.py
# Redis-based counting semaphores for capping concurrent API calls across workers.
# Two semaphores: LLM (Anthropic selection) and render (OpenAI gpt-image-1).
# Falls back to local threading.Semaphore when Redis is unavailable.

from __future__ import annotations

import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

_REDIS_KEY = "roomkit:llm_active"
_KEY_TTL = 120
_ACQUIRE_TIMEOUT = 60.0
_ACQUIRE_POLL_INTERVAL = 0.5

_local_semaphore: threading.Semaphore | None = None


def _get_concurrency_cap() -> int:
    return int(os.environ.get("LLM_CONCURRENCY_CAP", "30"))


def _get_local_semaphore() -> threading.Semaphore:
    global _local_semaphore
    if _local_semaphore is None:
        cap = _get_concurrency_cap()
        workers = int(os.environ.get("UVICORN_WORKERS", "1"))
        per_worker = cap // max(workers, 1)
        _local_semaphore = threading.Semaphore(max(per_worker, 1))
        logger.info(
            "Local LLM semaphore: %d slots (CAP=%d, WORKERS=%d)",
            max(per_worker, 1), cap, workers,
        )
    return _local_semaphore


def acquire_llm_slots(count: int, timeout: float = _ACQUIRE_TIMEOUT) -> bool:
    """Acquire `count` LLM concurrency slots.

    Returns True if acquired, False if timed out.  Caller MUST call
    release_llm_slots(count) in a finally block.

    Redis path: INCRBY roomkit:llm_active.  If over cap, DECRBY and
    retry with backoff until timeout.  Key TTL refreshed on every
    successful acquire as a crash safety net.

    Fallback: local threading.Semaphore(CAP // WORKERS) — bounded but
    uncoordinated across workers.
    """
    from services.redis_client import get_redis

    r = get_redis()
    if r is None:
        return _acquire_local(count, timeout)

    try:
        return _acquire_redis(r, count, timeout)
    except Exception:
        logger.warning("Redis semaphore acquire failed — falling back to local", exc_info=True)
        return _acquire_local(count, timeout)


def release_llm_slots(count: int) -> None:
    """Release `count` LLM concurrency slots.  Safe to call even if
    acquire returned False (no-op in that case)."""
    from services.redis_client import get_redis

    r = get_redis()
    if r is None:
        _release_local(count)
        return

    try:
        _release_redis(r, count)
    except Exception:
        logger.warning("Redis semaphore release failed — releasing local", exc_info=True)
        _release_local(count)


def _acquire_redis(r, count: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout

    while True:
        current = r.incrby(_REDIS_KEY, count)
        if current <= _get_concurrency_cap():
            r.expire(_REDIS_KEY, _KEY_TTL)
            return True

        r.decrby(_REDIS_KEY, count)

        if time.monotonic() >= deadline:
            logger.warning(
                "LLM semaphore timeout: %d slots requested, %d active, cap %d",
                count, current - count, _get_concurrency_cap(),
            )
            return False

        time.sleep(_ACQUIRE_POLL_INTERVAL)


def _release_redis(r, count: int) -> None:
    new_val = r.decrby(_REDIS_KEY, count)
    if new_val < 0:
        r.set(_REDIS_KEY, 0)
        r.expire(_REDIS_KEY, _KEY_TTL)


def _acquire_local(count: int, timeout: float) -> bool:
    sem = _get_local_semaphore()
    acquired = 0
    deadline = time.monotonic() + timeout

    for _ in range(count):
        remaining = max(0, deadline - time.monotonic())
        if not sem.acquire(timeout=remaining):
            for _ in range(acquired):
                sem.release()
            return False
        acquired += 1

    return True


def _release_local(count: int) -> None:
    sem = _get_local_semaphore()
    for _ in range(count):
        sem.release()


# ---------------------------------------------------------------------------
# Render semaphore — caps concurrent OpenAI gpt-image-1 calls.
# Cap=4 keeps steady-state throughput at ~6.9 IPM (under Tier 3's 7 IPM).
# One slot per render (not multi-slot like LLM selection).
#
# Unlike the LLM semaphore (which 503s on timeout because it's synchronous),
# renders are ASYNC — the user already has a 202, the frontend is polling.
# So the worker just waits for a slot. 600s timeout is a safety net against
# truly stuck keys, not an expected path.
# ---------------------------------------------------------------------------

_RENDER_REDIS_KEY = "roomkit:render_active"
_RENDER_KEY_TTL = 300
_RENDER_ACQUIRE_TIMEOUT = 600.0

_render_local_semaphore: threading.Semaphore | None = None


def _get_render_cap() -> int:
    return int(os.environ.get("RENDER_CONCURRENCY_CAP", "4"))


def _get_render_local_semaphore() -> threading.Semaphore:
    global _render_local_semaphore
    if _render_local_semaphore is None:
        cap = _get_render_cap()
        workers = int(os.environ.get("UVICORN_WORKERS", "1"))
        per_worker = cap // max(workers, 1)
        _render_local_semaphore = threading.Semaphore(max(per_worker, 1))
        logger.info(
            "Local render semaphore: %d slots (CAP=%d, WORKERS=%d)",
            max(per_worker, 1), cap, workers,
        )
    return _render_local_semaphore


def acquire_render_slot(timeout: float = _RENDER_ACQUIRE_TIMEOUT) -> bool:
    """Acquire one render concurrency slot.

    Returns True if acquired, False if timed out. Caller MUST call
    release_render_slot() in a finally block.
    """
    from services.redis_client import get_redis

    r = get_redis()
    if r is None:
        return _acquire_render_local(timeout)

    try:
        return _acquire_render_redis(r, timeout)
    except Exception:
        logger.warning("Redis render semaphore failed — local fallback", exc_info=True)
        return _acquire_render_local(timeout)


def release_render_slot() -> None:
    """Release one render concurrency slot."""
    from services.redis_client import get_redis

    r = get_redis()
    if r is None:
        _release_render_local()
        return

    try:
        _release_render_redis(r)
    except Exception:
        logger.warning("Redis render release failed — releasing local", exc_info=True)
        _release_render_local()


def _acquire_render_redis(r, timeout: float) -> bool:
    deadline = time.monotonic() + timeout

    while True:
        current = r.incrby(_RENDER_REDIS_KEY, 1)
        if current <= _get_render_cap():
            r.expire(_RENDER_REDIS_KEY, _RENDER_KEY_TTL)
            return True

        r.decrby(_RENDER_REDIS_KEY, 1)

        if time.monotonic() >= deadline:
            logger.warning(
                "Render semaphore timeout: %d active, cap %d",
                current - 1, _get_render_cap(),
            )
            return False

        time.sleep(_ACQUIRE_POLL_INTERVAL)


def _release_render_redis(r) -> None:
    new_val = r.decrby(_RENDER_REDIS_KEY, 1)
    if new_val < 0:
        r.set(_RENDER_REDIS_KEY, 0)
        r.expire(_RENDER_REDIS_KEY, _RENDER_KEY_TTL)


def _acquire_render_local(timeout: float) -> bool:
    return _get_render_local_semaphore().acquire(timeout=timeout)


def _release_render_local() -> None:
    _get_render_local_semaphore().release()

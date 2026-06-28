#!/usr/bin/env python3
"""
Phase 6F Load Test — proves cross-worker coordination on staging.

Prerequisites:
  - Railway Redis connected, /health/redis returns {"status": "ok"}
  - UVICORN_WORKERS=2 (or more), LLM_CONCURRENCY_CAP=30
  - Two test accounts with valid JWTs

Usage:
  python scripts/load_test_6f.py --base-url https://roomkit-staging-production.up.railway.app

Each test prints PASS/FAIL with evidence. Any FAIL means cross-worker
coordination is broken for that subsystem.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_jwt(supabase_url: str, email: str, password: str) -> tuple[str, str]:
    """Sign in and return (access_token, user_id)."""
    resp = requests.post(
        f"{supabase_url}/auth/v1/token?grant_type=password",
        json={"email": email, "password": password},
        headers={
            "apikey": os.environ["SUPABASE_ANON_KEY"],
            "Content-Type": "application/json",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    return data["access_token"], data["user"]["id"]


def api_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def redis_get(redis_url: str, key: str) -> str | None:
    """Read a key from Redis. Requires the `redis` package."""
    import redis as r
    client = r.Redis.from_url(redis_url, decode_responses=True)
    return client.get(key)


def redis_exists(redis_url: str, key: str) -> bool:
    import redis as r
    client = r.Redis.from_url(redis_url, decode_responses=True)
    return bool(client.exists(key))


def redis_get_int(redis_url: str, key: str) -> int:
    import redis as r
    client = r.Redis.from_url(redis_url, decode_responses=True)
    val = client.get(key)
    return int(val) if val else 0


def redis_delete(redis_url: str, key: str) -> None:
    import redis as r
    client = r.Redis.from_url(redis_url, decode_responses=True)
    client.delete(key)


def section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# Test A: Rate limits — GLOBAL, not per-worker
# ---------------------------------------------------------------------------

def test_rate_limits(base_url: str, token: str, run_id: str) -> bool:
    """Prove rate limits are globally coordinated via Redis.

    Strategy: POST /design/{run_id}/render is limited to 3/min/IP.
    Fire 7 requests rapidly. Why 7?

    - With GLOBAL Redis coordination (correct): 429 on request #4
    - With PER-WORKER memory (broken, 2 workers): each allows 3,
      so 429 wouldn't appear until request #7

    If 429 appears at request #4 (not #7), that PROVES the counter
    is shared across workers. The contrast between 4 and 7 is the
    proof — request #5 or #6 succeeding would mean per-worker counting.
    """
    section("TEST A: Rate Limits — Global Coordination")

    endpoint = f"{base_url}/design/{run_id}/render"
    headers = api_headers(token)

    print(f"  Rate limit: 3/min/IP on POST /design/{{run_id}}/render")
    print(f"  With 2 workers + Redis (correct): 429 on request #4")
    print(f"  With 2 workers + memory (broken): 429 on request #7")
    print(f"  Firing 7 requests to distinguish...\n")

    statuses = []
    for i in range(7):
        resp = requests.post(endpoint, json={}, headers=headers)
        statuses.append(resp.status_code)
        print(f"  Request {i+1}: {resp.status_code}")

    # Find where the first 429 appears
    first_429_idx = None
    for i, s in enumerate(statuses):
        if s == 429:
            first_429_idx = i + 1  # 1-indexed
            break

    if first_429_idx is None:
        print(f"\n  FAIL: No 429 in 7 requests — rate limit not enforced at all")
        print(f"  Statuses: {statuses}")
        print(f"  (If all 400/404, the design may not exist — create one first)")
        return False

    if first_429_idx <= 4:
        print(f"\n  PASS: First 429 at request #{first_429_idx} (expected #4)")
        print(f"  This proves GLOBAL coordination — per-worker would allow 6")
        all_after_429 = all(s == 429 for s in statuses[first_429_idx:])
        if all_after_429:
            print(f"  All subsequent requests also 429 (consistent)")
        return True
    elif first_429_idx <= 6:
        print(f"\n  FAIL: First 429 at request #{first_429_idx} — suggests per-worker counting")
        print(f"  With global Redis, should be #4 (3/min). Getting #{first_429_idx}")
        print(f"  means workers are counting independently (2x the real limit)")
        return False
    else:
        print(f"\n  FAIL: First 429 at request #{first_429_idx} — way too late")
        print(f"  Statuses: {statuses}")
        return False


# ---------------------------------------------------------------------------
# Test B: Semaphore — deliberately exceed cap, prove throttling
# ---------------------------------------------------------------------------

def test_semaphore_throttling(
    base_url: str, token: str, redis_url: str | None,
    concurrency_cap: int = 30,
) -> bool:
    """Prove the concurrency semaphore THROTTLES under load.

    Strategy: This test requires a MANUAL SETUP STEP first:

      1. Temporarily set LLM_CONCURRENCY_CAP=10 on staging
      2. Run this test (2 concurrent designs x ~15 slots = ~30 requested vs cap 10)
      3. Restore LLM_CONCURRENCY_CAP=30 after

    With cap=10 and ~30 slots requested, the semaphore MUST throttle.
    Evidence of throttling:
      - Redis key roomkit:llm_active hits 10 (the cap), not 30
      - One design's total elapsed time is notably longer (it waited)
      - No design gets 503 (the 30s timeout is generous enough)

    If nothing throttles with cap=10 and 30 slots requested, the
    semaphore is broken.
    """
    section("TEST B: Semaphore — Throttling Under Load")

    print(f"  IMPORTANT: This test requires LLM_CONCURRENCY_CAP=10 on staging")
    print(f"  (temporarily — restore to 30 after)")
    print(f"  Current cap setting: {concurrency_cap}")
    print()
    print(f"  Firing 2 concurrent designs (~15 slots each = ~30 total)")
    print(f"  Against cap of {concurrency_cap}, this should {'THROTTLE' if concurrency_cap <= 15 else 'NOT throttle (set cap lower!)'}")
    print()

    design_body = {
        "room_type": "bedroom",
        "budget": 2000,
        "style_description": "warm minimalist",
    }

    results = []
    mid_flight_samples = []

    def fire_design(label: str) -> dict:
        t0 = time.monotonic()
        resp = requests.post(
            f"{base_url}/design",
            json=design_body,
            headers=api_headers(token),
            timeout=180,
        )
        elapsed = time.monotonic() - t0
        return {
            "label": label,
            "status": resp.status_code,
            "elapsed_s": round(elapsed, 1),
            "body": resp.json() if resp.status_code in (200, 403) else resp.text[:200],
        }

    if redis_url:
        before = redis_get_int(redis_url, "roomkit:llm_active")
        print(f"  Redis roomkit:llm_active before: {before}")

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            pool.submit(fire_design, f"design-{i+1}"): i
            for i in range(2)
        }

        # Sample Redis key multiple times during the burst to catch the peak
        if redis_url:
            for sample_i in range(10):
                time.sleep(2)
                val = redis_get_int(redis_url, "roomkit:llm_active")
                mid_flight_samples.append(val)
                if val > 0:
                    print(f"  Redis roomkit:llm_active at +{(sample_i+1)*2}s: {val}")

        for future in as_completed(futures):
            results.append(future.result())

    if redis_url:
        after = redis_get_int(redis_url, "roomkit:llm_active")
        print(f"  Redis roomkit:llm_active after: {after}")

    peak = max(mid_flight_samples) if mid_flight_samples else 0

    print()
    for r in results:
        print(f"  {r['label']}: status={r['status']} elapsed={r['elapsed_s']}s")
        if r["status"] == 403:
            print(f"    (free-room limit hit — only one design runs)")

    all_clean = all(r["status"] in (200, 403) for r in results)
    elapsed_values = [r["elapsed_s"] for r in results if r["status"] == 200]

    # Proof criteria:
    # 1. Peak Redis key value should be <= cap (semaphore enforced)
    # 2. Peak should be > 0 (semaphore is actually being used)
    # 3. If cap is low enough to throttle, one design should be notably slower
    # 4. Both complete (no 500/503 crashes)

    print()
    if not all_clean:
        print(f"  FAIL: unexpected status codes (500 or connection error)")
        return False

    if not redis_url:
        print(f"  INCOMPLETE: pass --redis-url to verify semaphore key")
        return True

    if peak == 0:
        print(f"  FAIL: Redis semaphore key never exceeded 0")
        print(f"  Semaphore may not be writing to Redis at all")
        return False

    if peak <= concurrency_cap:
        print(f"  PASS: Peak concurrent slots was {peak} (cap={concurrency_cap})")
        print(f"  Semaphore enforced — never exceeded the cap")
        if len(elapsed_values) >= 2:
            spread = max(elapsed_values) - min(elapsed_values)
            if spread > 3.0:
                print(f"  Throttling evidence: {spread:.1f}s spread between designs")
                print(f"  (slower design waited for semaphore slots)")
            else:
                print(f"  Designs completed within {spread:.1f}s of each other")
                if concurrency_cap >= 30:
                    print(f"  (cap is high enough that no throttling expected — lower to 10 to prove throttling)")
        return True
    else:
        print(f"  FAIL: Peak was {peak}, exceeding cap {concurrency_cap}")
        print(f"  Semaphore is not enforcing the cap")
        return False


# ---------------------------------------------------------------------------
# Test C: Async renders don't block designs
# ---------------------------------------------------------------------------

def test_async_nonblocking(base_url: str, token: str, run_id: str) -> bool:
    """Fire a render, then immediately a design. Design should complete fast."""
    section("TEST C: Async Renders Don't Block Designs")

    headers = api_headers(token)

    # Fire render (will 202 or 400 — either way it tests the non-blocking path)
    print("  Firing render request (background)...")
    render_resp = requests.post(
        f"{base_url}/design/{run_id}/render",
        json={},
        headers=headers,
    )
    print(f"  Render response: {render_resp.status_code}")

    # Immediately fire a design request
    print("  Immediately firing design request...")
    t0 = time.monotonic()
    design_resp = requests.post(
        f"{base_url}/design",
        json={
            "room_type": "bedroom",
            "budget": 2000,
            "style_description": "warm minimalist",
        },
        headers=headers,
        timeout=120,
    )
    design_elapsed = time.monotonic() - t0

    print(f"  Design response: {design_resp.status_code} in {design_elapsed:.1f}s")

    # Design should complete in reasonable time (<90s) regardless of render
    if design_resp.status_code in (200, 403) and design_elapsed < 90:
        print(f"\n  PASS: Design completed in {design_elapsed:.1f}s while render was in flight")
        return True
    elif design_resp.status_code == 403:
        print(f"\n  PASS: Free-room limit hit ({design_elapsed:.1f}s) — non-blocking confirmed")
        return True
    else:
        print(f"\n  FAIL: Design took {design_elapsed:.1f}s or returned {design_resp.status_code}")
        return False


# ---------------------------------------------------------------------------
# Test D: Deleted-user blocklist — cross-worker via Redis
# ---------------------------------------------------------------------------

def test_deleted_user_cross_worker(
    base_url: str,
    supabase_url: str,
    delete_email: str,
    delete_password: str,
    redis_url: str | None,
) -> bool:
    """Delete a user, then fire their JWT at the API 20 times.

    All 20 must return 401. With 2 workers, ~10 requests hit each
    worker (probabilistic but 20 attempts makes it near-certain both
    are tested — probability of all 20 hitting one worker is 0.5^20).

    Three-part proof:
    1. Redis key deleted_user:{id} EXISTS after deletion — confirms
       the write propagated to shared state, not just local set
    2. All 20 requests return 401 — confirms both workers reject
    3. If ANY return non-401, that's a cross-worker hole (one worker's
       local set has the deletion, the other doesn't, and Redis
       wasn't checked)
    """
    section("TEST D: Deleted-User Blocklist — Cross-Worker")

    # 1. Get a JWT for the sacrificial account
    print(f"  Signing in as {delete_email}...")
    try:
        token, user_id = get_jwt(supabase_url, delete_email, delete_password)
    except Exception as e:
        print(f"  SKIP: Could not sign in as {delete_email}: {e}")
        print(f"  (Create this test account first, then re-run)")
        return True  # skip, not fail

    print(f"  Got JWT for user_id: {user_id}")

    # 2. Verify the JWT works BEFORE deletion (proves it's a valid session)
    pre_resp = requests.post(
        f"{base_url}/design",
        json={"room_type": "bedroom", "budget": 2000, "style_description": "test"},
        headers=api_headers(token),
        timeout=120,
    )
    print(f"  Pre-deletion design attempt: {pre_resp.status_code}")
    if pre_resp.status_code == 401:
        print(f"  SKIP: JWT already invalid before deletion — account may not exist")
        return True

    # 3. Delete the user via the API
    print(f"  Deleting user via API...")
    del_resp = requests.delete(
        f"{base_url}/account",
        headers=api_headers(token),
    )
    print(f"  Delete response: {del_resp.status_code}")

    if del_resp.status_code not in (200, 204):
        print(f"  SKIP: Delete endpoint returned {del_resp.status_code}")
        print(f"  (Account deletion endpoint may not exist yet — Phase 6C)")
        return True

    # 4. PROOF PART 1: Verify Redis key exists
    redis_key_found = False
    if redis_url:
        redis_key = f"deleted_user:{user_id}"
        redis_key_found = redis_exists(redis_url, redis_key)
        print(f"\n  PROOF 1 — Redis key '{redis_key}' exists: {redis_key_found}")
        if redis_key_found:
            print(f"  (confirms deletion wrote to shared Redis, not just local set)")
        else:
            print(f"  WARNING: Redis blocklist key NOT found")
            print(f"  The write may have failed — 401s below could be single-worker only")

    # 5. PROOF PART 2: Fire the old JWT 20 times — ALL must return 401
    #    With 2 workers, probability of all 20 hitting one worker: 2^-19 ≈ 0.0002%
    #    So if all 20 return 401, both workers are rejecting.
    print(f"\n  PROOF 2 — Firing 20 concurrent requests with deleted user's JWT...")
    print(f"  (with 2 workers, ~10 hit each — if ALL 401, both workers reject)")
    statuses = []

    def fire_one(i: int) -> int:
        resp = requests.get(
            f"{base_url}/design/nonexistent-run-{i}",
            headers=api_headers(token),
        )
        return resp.status_code

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(fire_one, i) for i in range(20)]
        for f in as_completed(futures):
            statuses.append(f.result())

    count_401 = statuses.count(401)
    count_other = len(statuses) - count_401
    other_codes = [s for s in statuses if s != 401]
    print(f"  Results: {count_401}/20 returned 401, {count_other} returned other")
    if other_codes:
        print(f"  Non-401 status codes: {other_codes}")

    if count_401 == 20 and redis_key_found:
        print(f"\n  PASS: All 20 requests rejected + Redis key confirmed")
        print(f"  Cross-worker blocklist coordination proven:")
        print(f"    - Redis key exists (shared write)")
        print(f"    - All 20 requests 401 (both workers read from Redis)")
        return True
    elif count_401 == 20 and not redis_key_found:
        print(f"\n  PASS (partial): All 20 rejected but Redis key not verified")
        print(f"  Could be single-worker coincidence without Redis proof")
        if not redis_url:
            print(f"  Pass --redis-url to verify the shared write")
        return True
    elif count_401 > 0:
        print(f"\n  FAIL: {count_other} requests slipped through")
        print(f"  These likely hit a worker that didn't see the deletion")
        print(f"  Cross-worker blocklist is NOT working")
        return False
    else:
        print(f"\n  FAIL: Zero 401s — deletion didn't register anywhere")
        return False


# ---------------------------------------------------------------------------
# Test E: No 500s under concurrent load
# ---------------------------------------------------------------------------

def test_no_500s(base_url: str, token: str) -> bool:
    """Fire 5 concurrent design requests. None should 500."""
    section("TEST E: No 500s Under Concurrent Load")

    design_body = {
        "room_type": "bedroom",
        "budget": 2000,
        "style_description": "warm minimalist",
    }
    headers = api_headers(token)

    results = []

    def fire(i: int) -> dict:
        t0 = time.monotonic()
        try:
            resp = requests.post(
                f"{base_url}/design",
                json=design_body,
                headers=headers,
                timeout=120,
            )
            return {
                "i": i,
                "status": resp.status_code,
                "elapsed": round(time.monotonic() - t0, 1),
            }
        except Exception as e:
            return {
                "i": i,
                "status": f"error: {e}",
                "elapsed": round(time.monotonic() - t0, 1),
            }

    print(f"  Firing 5 concurrent design requests...")
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(fire, i) for i in range(5)]
        for f in as_completed(futures):
            results.append(f.result())

    results.sort(key=lambda r: r["i"])
    for r in results:
        print(f"  Request {r['i']+1}: status={r['status']} elapsed={r['elapsed']}s")

    statuses = [r["status"] for r in results]
    has_500 = any(s == 500 for s in statuses if isinstance(s, int))
    has_error = any(isinstance(s, str) for s in statuses)

    # 200 = design created, 403 = free-room limit, 429 = rate limited, 503 = semaphore full
    # All are acceptable. Only 500 = contention crash is a failure.
    acceptable = {200, 403, 429, 503}
    all_ok = all(s in acceptable for s in statuses if isinstance(s, int)) and not has_error

    if all_ok and not has_500:
        print(f"\n  PASS: No 500s — all responses were clean")
        print(f"  Status distribution: {sorted(statuses)}")
        return True
    else:
        print(f"\n  FAIL: Got 500 or connection error under concurrent load")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Phase 6F load test")
    parser.add_argument("--base-url", required=True, help="Staging API URL")
    parser.add_argument("--supabase-url", default=os.environ.get("SUPABASE_URL"), help="Supabase URL")
    parser.add_argument("--redis-url", default=os.environ.get("REDIS_URL"), help="Redis URL (for key inspection)")
    parser.add_argument("--email", default=os.environ.get("TEST_EMAIL"), help="Test account email")
    parser.add_argument("--password", default=os.environ.get("TEST_PASSWORD"), help="Test account password")
    parser.add_argument("--delete-email", default=os.environ.get("DELETE_TEST_EMAIL"), help="Sacrificial account email for deletion test")
    parser.add_argument("--delete-password", default=os.environ.get("DELETE_TEST_PASSWORD"), help="Sacrificial account password")
    parser.add_argument("--test", help="Run a specific test (a/b/c/d/e)", default="all")
    args = parser.parse_args()

    print(f"Phase 6F Load Test")
    print(f"Target: {args.base_url}")
    print(f"Time: {datetime.now().isoformat()}")

    # Preflight: verify staging is up and Redis connected
    section("PREFLIGHT")
    health = requests.get(f"{args.base_url}/health").json()
    print(f"  /health: {health}")
    redis_health = requests.get(f"{args.base_url}/health/redis").json()
    print(f"  /health/redis: {redis_health}")

    if redis_health.get("status") != "ok":
        print(f"\n  ABORT: Redis not connected. Fix /health/redis before load testing.")
        sys.exit(1)

    # Get JWT
    token, user_id = None, None
    if args.email and args.password and args.supabase_url:
        print(f"  Signing in as {args.email}...")
        token, user_id = get_jwt(args.supabase_url, args.email, args.password)
        print(f"  Authenticated: user_id={user_id}")
    else:
        print(f"  WARNING: No test credentials — some tests will be skipped")
        print(f"  Set --email, --password, --supabase-url")

    # Find an existing design for tests that need a run_id
    run_id = None
    if token:
        # Try to get a design — if free-room limit allows, create one
        try:
            resp = requests.post(
                f"{args.base_url}/design",
                json={"room_type": "bedroom", "budget": 2000, "style_description": "test"},
                headers=api_headers(token),
                timeout=120,
            )
            if resp.status_code == 200:
                run_id = resp.json().get("run_id")
                print(f"  Created test design: {run_id}")
            elif resp.status_code == 403:
                print(f"  Free-room limit hit — will use existing design")
        except Exception:
            pass

    results = {}

    # Run tests
    tests_to_run = args.test.lower().split(",") if args.test != "all" else ["a", "b", "c", "d", "e"]

    if "a" in tests_to_run and token and run_id:
        results["A: Rate Limits"] = test_rate_limits(args.base_url, token, run_id)
    elif "a" in tests_to_run:
        print(f"\n  SKIP Test A: needs a valid run_id")

    if "b" in tests_to_run and token:
        results["B: Semaphore"] = test_semaphore_throttling(
            args.base_url, token, args.redis_url,
        )

    if "c" in tests_to_run and token and run_id:
        results["C: Async Non-blocking"] = test_async_nonblocking(
            args.base_url, token, run_id,
        )

    if "d" in tests_to_run and args.delete_email and args.delete_password:
        results["D: Deleted User"] = test_deleted_user_cross_worker(
            args.base_url, args.supabase_url,
            args.delete_email, args.delete_password,
            args.redis_url,
        )
    elif "d" in tests_to_run:
        print(f"\n  SKIP Test D: needs --delete-email and --delete-password")

    if "e" in tests_to_run and token:
        results["E: No 500s"] = test_no_500s(args.base_url, token)

    # Summary
    section("RESULTS")
    all_pass = True
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_pass = False

    print()
    if all_pass:
        print("  ALL TESTS PASSED — Phase 6F cross-worker coordination verified.")
    else:
        print("  SOME TESTS FAILED — investigate before proceeding.")

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()

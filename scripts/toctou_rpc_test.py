#!/usr/bin/env python3
"""
Phase 6E TOCTOU RPC Test — proves advisory lock serializes concurrent claims
at the REAL Postgres level, without running the full LLM pipeline.

Fires 5 genuinely-concurrent RPC calls to claim_and_save_free_design against
a single free-tier account (0 existing designs, 1-room limit).
Expected: exactly 1 returns True, exactly 4 return False.

This directly tests the advisory lock (pg_advisory_xact_lock) — the same
code path that POST /design → save_free_design() calls, but without the
~$1.85 in LLM costs.

Prerequisites:
  - Migration 003_tier_enforcement.sql applied (staging schema)
  - Target account has 0 free designs
  - .env has SUPABASE_URL, SUPABASE_SERVICE_KEY

Usage:
  python scripts/toctou_rpc_test.py
"""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv

load_dotenv()


def fire_claim(client, user_id: str, idx: int) -> tuple[int, bool | None, str]:
    """Call claim_and_save_free_design RPC and return (idx, result, detail)."""
    run_id = str(uuid.uuid4())
    t0 = time.monotonic()
    try:
        result = client.rpc("claim_and_save_free_design", {
            "p_run_id": run_id,
            "p_user_id": user_id,
            "p_room_type": "bedroom",
            "p_target_budget": 2000.0,
            "p_total_spent": 1500.0,
            "p_is_feasible": True,
            "p_style": {"name": "test", "description": "toctou test"},
            "p_slots": [],
            "p_finalized_at": None,
            "p_free_limit": 1,
        }).execute()
        elapsed = time.monotonic() - t0
        return (idx, result.data, f"{elapsed:.3f}s — claimed={result.data}")
    except Exception as e:
        elapsed = time.monotonic() - t0
        return (idx, None, f"{elapsed:.3f}s — ERROR: {e}")


def main():
    from services.supabase_client import get_client
    client = get_client()
    if client is None:
        print("  ERROR: Supabase not configured. Check .env")
        return

    user_id = "597ced63-98ff-427e-8606-931e9af7b751"

    print("=" * 60)
    print("  Phase 6E TOCTOU RPC Test")
    print("  5 concurrent claim_and_save_free_design RPCs")
    print("  Expected: 1×True + 4×False")
    print("=" * 60)

    # 1. Verify 0 free designs
    resp = client.table("designs").select(
        "run_id", count="exact",
    ).eq("user_id", user_id).eq("is_paid", False).execute()
    existing = resp.count or 0
    print(f"\n  Existing free designs: {existing}")
    if existing > 0:
        print("  Clearing existing designs first...")
        client.table("designs").delete().eq("user_id", user_id).execute()
        print("  Cleared.")

    # 2. Fire 5 concurrent RPC calls
    print(f"\n  Firing 5 concurrent RPC calls...\n")
    t_start = time.monotonic()

    results = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(fire_claim, client, user_id, i): i
            for i in range(5)
        }
        for future in as_completed(futures):
            idx, claimed, detail = future.result()
            results.append((idx, claimed, detail))
            print(f"  RPC {idx}: {detail}")

    t_total = time.monotonic() - t_start
    print(f"\n  Total wall time: {t_total:.3f}s")

    # 3. Analyze
    claims = [c for _, c, _ in results]
    n_true = sum(1 for c in claims if c is True)
    n_false = sum(1 for c in claims if c is False)
    n_error = sum(1 for c in claims if c is None)

    print(f"\n  Results: {n_true}×True, {n_false}×False, {n_error}×error")

    # 4. Verify DB state
    resp = client.table("designs").select(
        "run_id", count="exact",
    ).eq("user_id", user_id).eq("is_paid", False).execute()
    final_count = resp.count or 0
    print(f"  Designs in DB: {final_count}")

    # 5. Verdict
    print()
    if n_true == 1 and n_false == 4 and final_count == 1:
        print("  PASS — Advisory lock serialized correctly.")
        print("     Exactly 1 claim succeeded, 4 rejected at DB level.")
    elif n_true == 1 and final_count == 1:
        print(f"  PARTIAL — 1 succeeded but got {n_false}×False + "
              f"{n_error}×error (expected 4×False).")
        print("     Advisory lock works but some RPCs hit errors.")
    elif n_true > 1:
        print(f"  FAIL — {n_true} RPCs returned True (expected 1).")
        print("     Advisory lock is NOT serializing concurrent claims.")
        print(f"     DB has {final_count} designs (expected 1).")
    elif n_true == 0:
        print(f"  FAIL — 0 RPCs returned True (expected 1).")
        print(f"     {n_error}×error, {n_false}×False")
    else:
        print(f"  FAIL — unexpected: {n_true}×True, "
              f"{n_false}×False, {n_error}×error")

    # 6. Cleanup
    print(f"\n  Cleaning up test designs...")
    resp = client.table("designs").delete().eq(
        "user_id", user_id,
    ).execute()
    print(f"  Deleted {len(resp.data)} designs.")
    print()


if __name__ == "__main__":
    main()

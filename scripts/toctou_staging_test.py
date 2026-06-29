#!/usr/bin/env python3
"""
Phase 6E TOCTOU Staging Test — proves advisory lock serializes real concurrent requests.

Fires 5 genuinely-concurrent POST /design requests against a single free-tier
account (0 existing designs, 1-room limit). Expected: exactly 1 succeeds (200),
exactly 4 rejected (403). If 2+ succeed, the advisory lock isn't serializing.

Prerequisites:
  - Migration 003_tier_enforcement.sql applied (staging schema)
  - Target account has 0 free designs
  - .env has SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY

Usage:
  python scripts/toctou_staging_test.py \\
    --base-url https://roomkit-staging-production.up.railway.app \\
    --email ben14parks@gmail.com \\
    --password <password>
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from dotenv import load_dotenv

load_dotenv()


def get_jwt(email: str, password: str) -> tuple[str, str]:
    """Sign in and return (access_token, user_id)."""
    supabase_url = os.environ["SUPABASE_URL"]
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


def fire_design_request(
    base_url: str, token: str, idx: int,
) -> tuple[int, int, str]:
    """POST /design and return (idx, status_code, detail)."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = {
        "room_type": "bedroom",
        "budget": 2000,
        "style_description": "warm minimalist",
    }
    t0 = time.monotonic()
    try:
        resp = requests.post(
            f"{base_url}/design", json=body, headers=headers,
            timeout=120,
        )
        elapsed = time.monotonic() - t0
        detail = ""
        try:
            detail = resp.json().get("detail", resp.json().get("run_id", ""))
        except Exception:
            pass
        return (idx, resp.status_code, f"{elapsed:.1f}s — {detail}")
    except Exception as e:
        elapsed = time.monotonic() - t0
        return (idx, 0, f"{elapsed:.1f}s — ERROR: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="TOCTOU staging test: 5 concurrent free-tier requests",
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    print("=" * 60)
    print("  Phase 6E TOCTOU Staging Test")
    print("  5 concurrent POST /design → expect 1×200 + 4×403")
    print("=" * 60)

    # 1. Authenticate
    print(f"\n  Authenticating as {args.email}...")
    token, user_id = get_jwt(args.email, args.password)
    print(f"  User ID: {user_id}")

    # 2. Verify 0 designs
    from services.supabase_client import get_client
    client = get_client()
    resp = client.table("designs").select(
        "run_id", count="exact",
    ).eq("user_id", user_id).eq("is_paid", False).execute()
    existing = resp.count or 0
    print(f"  Existing free designs: {existing}")
    if existing > 0:
        print("  ERROR: Account has existing free designs. Clear first.")
        sys.exit(1)

    # 3. Fire 5 concurrent requests
    print(f"\n  Firing 5 concurrent POST /design...\n")
    t_start = time.monotonic()

    results = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(fire_design_request, args.base_url, token, i): i
            for i in range(5)
        }
        for future in as_completed(futures):
            idx, status, detail = future.result()
            results.append((idx, status, detail))
            print(f"  Request {idx}: {status}  ({detail})")

    t_total = time.monotonic() - t_start
    print(f"\n  Total wall time: {t_total:.1f}s")

    # 4. Analyze
    statuses = [s for _, s, _ in results]
    n_200 = statuses.count(200)
    n_403 = statuses.count(403)
    n_other = len(statuses) - n_200 - n_403

    print(f"\n  Results: {n_200}×200, {n_403}×403, {n_other}×other")

    # 5. Verify DB state
    resp = client.table("designs").select(
        "run_id", count="exact",
    ).eq("user_id", user_id).eq("is_paid", False).execute()
    final_count = resp.count or 0
    print(f"  Designs in DB: {final_count}")

    # 6. Verdict
    print()
    if n_200 == 1 and n_403 == 4 and final_count == 1:
        print("  ✅ PASS — Advisory lock serialized correctly.")
        print("     Exactly 1 design claimed, 4 rejected at DB level.")
    elif n_200 == 1 and final_count == 1:
        print(f"  ⚠️  PARTIAL — 1 succeeded but got {n_403}×403 + "
              f"{n_other}×other (expected 4×403).")
        print("     Advisory lock works but some requests hit other errors.")
    elif n_200 > 1:
        print(f"  ❌ FAIL — {n_200} requests succeeded (expected 1).")
        print("     Advisory lock is NOT serializing concurrent claims.")
        print(f"     DB has {final_count} designs (expected 1).")
    else:
        print(f"  ❌ FAIL — unexpected result: {n_200}×200, "
              f"{n_403}×403, {n_other}×other.")

    # 7. Cleanup
    print(f"\n  Cleaning up test designs...")
    resp = client.table("designs").delete().eq(
        "user_id", user_id,
    ).execute()
    print(f"  Deleted {len(resp.data)} designs.")

    print()
    sys.exit(0 if n_200 == 1 and final_count == 1 else 1)


if __name__ == "__main__":
    main()

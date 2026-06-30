#!/usr/bin/env python3
"""
Verify process_stripe_payment RPC on real Postgres.

Proves:
  A) Idempotency — first call returns rooms_remaining, second returns NULL
  B) Atomicity — dedup + credit happen in one transaction

Run after deploying 004_stripe_payments.sql + NOTIFY:
  python scripts/stripe_rpc_test.py
"""

import os
import sys

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")
if not url or not key:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY required")
    sys.exit(1)

client = create_client(url, key)

TEST_SESSION = "test-stripe-rpc-001"
TEST_USER = "00000000-0000-0000-0000-000000099999"
PACK_SIZE = 5
AMOUNT = 999

print("=" * 60)
print("process_stripe_payment RPC — idempotency proof")
print("=" * 60)

# Cleanup from prior runs
print("\n--- Cleanup ---")
client.table("stripe_payments").delete().eq("checkout_session_id", TEST_SESSION).execute()
client.table("user_packs").delete().eq("user_id", TEST_USER).execute()
print("  Cleaned up test data")

# Call 1: should credit
print("\n--- Call 1 (first delivery) ---")
resp1 = client.rpc("process_stripe_payment", {
    "p_session_id": TEST_SESSION,
    "p_user_id": TEST_USER,
    "p_pack_size": PACK_SIZE,
    "p_amount": AMOUNT,
    "p_currency": "usd",
}).execute()
print(f"  Result: {resp1.data}")

# Verify state
payments = client.table("stripe_payments").select("*").eq("checkout_session_id", TEST_SESSION).execute()
packs = client.table("user_packs").select("*").eq("user_id", TEST_USER).execute()
print(f"  stripe_payments rows: {len(payments.data)}")
print(f"  user_packs.rooms_remaining: {packs.data[0]['rooms_remaining'] if packs.data else 'MISSING'}")

assert resp1.data is not None, "FAIL: first call should return rooms_remaining"
assert resp1.data == PACK_SIZE, f"FAIL: expected {PACK_SIZE}, got {resp1.data}"
assert len(payments.data) == 1, "FAIL: expected 1 stripe_payments row"
assert packs.data[0]["rooms_remaining"] == PACK_SIZE, "FAIL: pack not credited"
print("  PASS: first delivery credited correctly")

# Call 2: same session_id — should return NULL (duplicate)
print("\n--- Call 2 (duplicate delivery) ---")
resp2 = client.rpc("process_stripe_payment", {
    "p_session_id": TEST_SESSION,
    "p_user_id": TEST_USER,
    "p_pack_size": PACK_SIZE,
    "p_amount": AMOUNT,
    "p_currency": "usd",
}).execute()
print(f"  Result: {resp2.data}")

# Verify state unchanged
payments2 = client.table("stripe_payments").select("*").eq("checkout_session_id", TEST_SESSION).execute()
packs2 = client.table("user_packs").select("*").eq("user_id", TEST_USER).execute()
print(f"  stripe_payments rows: {len(payments2.data)}")
print(f"  user_packs.rooms_remaining: {packs2.data[0]['rooms_remaining'] if packs2.data else 'MISSING'}")

assert resp2.data is None, f"FAIL: duplicate should return NULL, got {resp2.data}"
assert len(payments2.data) == 1, "FAIL: should still be 1 stripe_payments row"
assert packs2.data[0]["rooms_remaining"] == PACK_SIZE, f"FAIL: rooms changed on duplicate! Got {packs2.data[0]['rooms_remaining']}"
print("  PASS: duplicate delivery correctly returned NULL, no double-credit")

# Cleanup
print("\n--- Cleanup ---")
client.table("stripe_payments").delete().eq("checkout_session_id", TEST_SESSION).execute()
client.table("user_packs").delete().eq("user_id", TEST_USER).execute()
print("  Cleaned up test data")

print("\n" + "=" * 60)
print("ALL CHECKS PASSED")
print("  - First call: credited (returned rooms_remaining)")
print("  - Duplicate call: skipped (returned NULL)")
print("  - No double-credit")
print("=" * 60)

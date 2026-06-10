#!/usr/bin/env python3
"""
Before/after comparison of the price-utilization prompt fix.
Runs sports_den ($1500) and quiet_luxury ($2500) designs, shows per-slot
allocation vs. spend and overall budget utilization.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def run_design(label: str, req: dict) -> None:
    print(f"  {'─' * 90}")
    print(f"  {label}")
    print(f"  {'─' * 90}")

    t0 = time.monotonic()
    resp = client.post("/design", json=req)
    wall = time.monotonic() - t0
    data = resp.json()

    style = data["style"]
    print(f"  Style: {style['style_name']}, keywords: {style['keywords'][:5]}")
    print(f"  Budget: ${data['target_budget']:.2f}, wall time: {wall:.1f}s")
    print()

    total_alloc = 0.0
    total_spent = 0.0
    under_40_pct = 0
    over_70_pct = 0

    print(f"  {'Slot':<20} {'Alloc':>7} {'Picked':>8} {'%':>5}  Product")
    print(f"  {'─' * 85}")

    for s in sorted(data["slots"], key=lambda x: x["slot_id"]):
        alloc = s["allocated_budget"]
        total_alloc += alloc

        if s.get("owned"):
            print(f"  {s['slot_id']:<20} ${alloc:>6.0f}   {'owned':>7}")
            continue

        if s["product"]:
            p = s["product"]
            price = p["normalized_price"]
            total_spent += price
            pct = (price / alloc * 100) if alloc > 0 else 0
            if pct < 40:
                under_40_pct += 1
            if pct >= 70:
                over_70_pct += 1
            marker = " ←LOW" if pct < 40 else ""
            print(f"  {s['slot_id']:<20} ${alloc:>6.0f} ${price:>7.0f} {pct:>4.0f}%  "
                  f"{p['name'][:50]}{marker}")
        else:
            print(f"  {s['slot_id']:<20} ${alloc:>6.0f}   {'—':>7}       {s['null_reason']}")

    util = (total_spent / data["target_budget"] * 100) if data["target_budget"] > 0 else 0
    print()
    print(f"  TOTAL: ${total_spent:.0f} / ${data['target_budget']:.0f} = {util:.0f}% utilization")
    print(f"  Slots under 40% of allocation: {under_40_pct}")
    print(f"  Slots at 70%+ of allocation: {over_70_pct}")
    print()


# ── Designs ──

SPORTS_DEN = {
    "room_type": "bedroom", "budget": 1500.0,
    "style_description": (
        "I want a sports den bedroom — moody and atmospheric, with rich depth, "
        "in dark tones with charcoal, dark wood, and warm amber. "
        "I'm drawn to walnut and leather."
    ),
    "bed_size": "queen", "density": "balanced",
    "interests": ["music", "sports"],
    "full_room": True, "wants": [],
}

QUIET_LUXURY = {
    "room_type": "bedroom", "budget": 2500.0,
    "style_description": (
        "I want a quiet luxury bedroom — understated elegance with cashmere, "
        "marble, and brushed gold accents. Creamy neutral palette."
    ),
    "bed_size": "queen", "density": "balanced",
    "interests": [], "full_room": True, "wants": [],
}

print("=" * 95)
print("  AFTER PROMPT FIX — price-utilization signal added")
print("=" * 95)
print()

run_design("SPORTS DEN — $1500, music+sports interests", SPORTS_DEN)
run_design("QUIET LUXURY — $2500, no interests", QUIET_LUXURY)

# Reference: before numbers from diagnose_underspend.py
print("=" * 95)
print("  COMPARISON (before numbers from diagnostic run)")
print("=" * 95)
print()
print("  sports_den  ($1500):  BEFORE 66% → AFTER see above")
print("  quiet_luxury ($2500): BEFORE 57% → AFTER see above")
print()

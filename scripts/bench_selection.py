#!/usr/bin/env python3
"""Benchmark: serial vs parallel selection for a whole-room bedroom design.

Runs the full pipeline twice — once with the old serial loop (patched in),
once with the current parallel implementation — and prints wall-clock times.

Usage:
    python scripts/bench_selection.py
"""

from __future__ import annotations

import os
import sys
import time

# Load .env so ANTHROPIC_API_KEY is available.
from pathlib import Path
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

# Ensure project root is on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.schemas import DesignRequest
from services.intake_service import parse_intake
from services.style_service import interpret_style
from services.composition_service import plan_composition
from services.composition_gate import validate_composition
from services.selection_service import select_product
from services.sourcing.amazon_adapter import AmazonAdapter
from app.api.schemas import SlotResult, ProductResult


def _source_and_select_serial(slot_plan, style_profile, room_request):
    """Old serial loop — one slot at a time."""
    adapter = AmazonAdapter()
    results = []
    for slot in sorted(slot_plan.slots, key=lambda s: s.slot_id):
        if slot.owned:
            results.append((slot, None, "owned"))
            continue
        spec_hints = {}
        if "bed_size" in slot.required_specs and room_request.bed_size:
            spec_hints["bed_size"] = room_request.bed_size
        candidates = adapter.fetch_candidates(
            slot.slot_id, style_profile.keywords,
            (0.0, slot.allocated_budget), spec_hints,
        )
        product, reason = select_product(slot, style_profile, candidates)
        results.append((slot, product, reason))
    return results


def _source_and_select_parallel(slot_plan, style_profile, room_request):
    """New parallel implementation — mirrors routes.py."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    adapter = AmazonAdapter()
    owned = []
    sourceable = []

    for slot in slot_plan.slots:
        if slot.owned:
            owned.append((slot, None, "owned"))
            continue
        spec_hints = {}
        if "bed_size" in slot.required_specs and room_request.bed_size:
            spec_hints["bed_size"] = room_request.bed_size
        candidates = adapter.fetch_candidates(
            slot.slot_id, style_profile.keywords,
            (0.0, slot.allocated_budget), spec_hints,
        )
        sourceable.append((slot, candidates))

    selection_results = {}
    with ThreadPoolExecutor(max_workers=len(sourceable) or 1) as pool:
        futures = {
            pool.submit(select_product, slot, style_profile, cands): slot.slot_id
            for slot, cands in sourceable
        }
        for future in as_completed(futures):
            sid = futures[future]
            selection_results[sid] = future.result()

    results = list(owned)
    for slot, _cands in sourceable:
        product, reason = selection_results[slot.slot_id]
        results.append((slot, product, reason))

    return sorted(results, key=lambda r: r[0].slot_id)


def main():
    req = DesignRequest(room_type="bedroom", budget=1500.0)
    room_request = parse_intake(req.model_dump())

    # Shared upstream — style + composition (timed separately).
    print("Running upstream pipeline (style + composition)...")
    t0 = time.monotonic()
    style_profile = interpret_style(room_request)
    t_style = time.monotonic() - t0

    t0 = time.monotonic()
    slot_plan = plan_composition(room_request, style_profile)
    slot_plan, _ = validate_composition(slot_plan)
    t_comp = time.monotonic() - t0

    non_owned = sum(1 for s in slot_plan.slots if not s.owned)
    print(f"  Style:       {t_style:.1f}s")
    print(f"  Composition: {t_comp:.1f}s")
    print(f"  Slots to source: {non_owned}")
    print()

    # --- Serial ---
    print(f"SERIAL selection ({non_owned} slots, one at a time)...")
    t0 = time.monotonic()
    serial_results = _source_and_select_serial(slot_plan, style_profile, room_request)
    t_serial = time.monotonic() - t0
    serial_filled = sum(1 for _, p, _ in serial_results if p is not None)
    print(f"  Time:    {t_serial:.1f}s")
    print(f"  Filled:  {serial_filled}/{non_owned} slots")
    print()

    # --- Parallel ---
    print(f"PARALLEL selection ({non_owned} slots, concurrent)...")
    t0 = time.monotonic()
    parallel_results = _source_and_select_parallel(slot_plan, style_profile, room_request)
    t_parallel = time.monotonic() - t0
    parallel_filled = sum(1 for _, p, _ in parallel_results if p is not None)
    print(f"  Time:    {t_parallel:.1f}s")
    print(f"  Filled:  {parallel_filled}/{non_owned} slots")
    print()

    # --- Summary ---
    speedup = t_serial / t_parallel if t_parallel > 0 else float("inf")
    print("=" * 50)
    print(f"SERIAL:    {t_serial:.1f}s")
    print(f"PARALLEL:  {t_parallel:.1f}s")
    print(f"SPEEDUP:   {speedup:.1f}x")
    print(f"SAVED:     {t_serial - t_parallel:.1f}s")
    print()
    print(f"Full pipeline (style + comp + selection):")
    print(f"  Before:  {t_style + t_comp + t_serial:.1f}s")
    print(f"  After:   {t_style + t_comp + t_parallel:.1f}s")


if __name__ == "__main__":
    main()

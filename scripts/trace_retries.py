#!/usr/bin/env python3
"""
Stress-test: run multiple designs back-to-back through POST /design,
counting every Anthropic API call AND every 429 rejection/retry.
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------

PRICING = {
    "claude-sonnet-4-6":         {"input": 3.00,  "output": 15.00},
    "claude-haiku-4-5-20251001": {"input": 0.80,  "output":  4.00},
}

def cost_usd(model: str, input_tok: int, output_tok: int) -> float:
    rates = PRICING.get(model, {"input": 3.00, "output": 15.00})
    return (input_tok * rates["input"] + output_tok * rates["output"]) / 1_000_000

# ---------------------------------------------------------------------------
# Thread-safe counters
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_calls: list[dict] = []
_retries: list[dict] = []       # every 429 rejection
_call_counter = 0
_retry_counter = 0
_cumulative_cost = 0.0

# ---------------------------------------------------------------------------
# Monkey-patch: capture successes AND 429 rejections
# ---------------------------------------------------------------------------

import anthropic                          # noqa: E402
import anthropic.resources.messages       # noqa: E402

_original_create = anthropic.resources.messages.Messages.create

def _infer_call_name(system_prompt: str) -> str:
    s = system_prompt[:500].lower()
    if "product selector" in s:
        return "selection"
    if "composition planner" in s or "distribute" in s and "weight" in s:
        return "composition"
    if "style interpreter" in s or "style profile" in s:
        return "style"
    return "unknown"

def _instrumented_create(self, **kwargs):
    global _call_counter, _retry_counter, _cumulative_cost

    model = kwargs.get("model", "unknown")
    system = kwargs.get("system", "")
    call_name = _infer_call_name(system)
    model_short = "haiku" if "haiku" in model else "sonnet" if "sonnet" in model else model

    t0 = time.monotonic()
    try:
        result = _original_create(self, **kwargs)
    except anthropic.RateLimitError as exc:
        elapsed = time.monotonic() - t0
        with _lock:
            _retry_counter += 1
            seq = _retry_counter
            _retries.append({
                "seq": seq, "name": call_name, "model": model,
                "elapsed": elapsed,
            })
        print(
            f"  *** 429 #{seq:<3} {call_name:<14} {model_short:<7}  "
            f"({elapsed:.1f}s)  — will retry",
            flush=True,
        )
        raise  # re-raise so the caller's retry loop handles it

    elapsed = time.monotonic() - t0
    usage = result.usage
    inp = usage.input_tokens
    out = usage.output_tokens
    c = cost_usd(model, inp, out)

    with _lock:
        _call_counter += 1
        seq = _call_counter
        _cumulative_cost += c
        _calls.append({
            "seq": seq, "name": call_name, "model": model,
            "input_tokens": inp, "output_tokens": out,
            "cost": c, "elapsed": elapsed,
        })
        cum_cost = _cumulative_cost

    print(
        f"  [{seq:>3}] {call_name:<14} {model_short:<7} "
        f"in={inp:>6,}  out={out:>4}  "
        f"${c:.5f}  cum=${cum_cost:.5f}  ({elapsed:.1f}s)",
        flush=True,
    )

    return result

anthropic.resources.messages.Messages.create = _instrumented_create

# ---------------------------------------------------------------------------
# Run N designs back-to-back through the real endpoint
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app                   # noqa: E402

client = TestClient(app)

DESIGNS = [
    {
        "label": "Sports Den",
        "payload": {
            "room_type": "bedroom", "budget": 1500.0,
            "style_description": (
                "I want a sports den bedroom — moody and atmospheric, with rich depth, "
                "in dark tones with charcoal, dark wood, and warm amber. "
                "I'm drawn to walnut and leather."
            ),
            "bed_size": "queen", "density": "balanced",
            "interests": ["sports"], "full_room": True, "wants": [],
        },
    },
    {
        "label": "Japandi",
        "payload": {
            "room_type": "bedroom", "budget": 1500.0,
            "style_description": (
                "I want a japandi bedroom — serene and minimal, with natural textures. "
                "Pale wood, clean lines, matte finishes."
            ),
            "bed_size": "queen", "density": "minimal",
            "interests": [], "full_room": True, "wants": [],
        },
    },
    {
        "label": "Cottagecore",
        "payload": {
            "room_type": "bedroom", "budget": 1200.0,
            "style_description": (
                "I want a cottagecore bedroom — soft, floral, vintage. "
                "Distressed wood, linen, warm whites, dusty rose accents."
            ),
            "bed_size": "queen", "density": "layered",
            "interests": ["books"], "full_room": True, "wants": [],
        },
    },
]

print("=" * 100)
print("  RETRY STRESS TEST — 3 designs back-to-back through POST /design")
print("=" * 100)

per_design_stats = []

for i, design in enumerate(DESIGNS):
    calls_before = len(_calls)
    retries_before = len(_retries)
    cost_before = _cumulative_cost

    print(f"\n{'─' * 100}")
    print(f"  Design {i+1}/3: {design['label']}")
    print(f"{'─' * 100}")

    t0 = time.monotonic()
    resp = client.post("/design", json=design["payload"])
    wall = time.monotonic() - t0

    calls_this = len(_calls) - calls_before
    retries_this = len(_retries) - retries_before
    cost_this = _cumulative_cost - cost_before

    status = "OK" if resp.status_code == 200 else f"ERR {resp.status_code}"
    print(f"\n  → {status}  |  {calls_this} billed calls  |  "
          f"{retries_this} retries (429s)  |  ${cost_this:.5f}  |  {wall:.1f}s")

    per_design_stats.append({
        "label": design["label"],
        "billed": calls_this,
        "retries": retries_this,
        "cost": cost_this,
        "wall": wall,
    })

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print()
print("=" * 100)
print("  SUMMARY")
print("=" * 100)
print()
print(f"  {'Design':<16} {'Billed':>7} {'429s':>6} {'Total Attempts':>15} {'Cost':>10} {'Wall':>7}")
print(f"  {'─' * 65}")

total_billed = 0
total_retries = 0
total_cost = 0.0

for s in per_design_stats:
    attempts = s["billed"] + s["retries"]
    print(f"  {s['label']:<16} {s['billed']:>7} {s['retries']:>6} {attempts:>15} "
          f"${s['cost']:>9.5f} {s['wall']:>6.1f}s")
    total_billed += s["billed"]
    total_retries += s["retries"]
    total_cost += s["cost"]

print(f"  {'─' * 65}")
total_attempts = total_billed + total_retries
print(f"  {'TOTAL':<16} {total_billed:>7} {total_retries:>6} {total_attempts:>15} "
      f"${total_cost:>9.5f}")

print()
expected = 18 * len(DESIGNS)
print(f"  Expected billed calls (18 × {len(DESIGNS)}): {expected}")
print(f"  Actual billed calls:                  {total_billed}")
print(f"  429 rejections (retries):             {total_retries}")
print(f"  Retry overhead:                       {total_retries}/{total_billed} "
      f"= {total_retries/max(total_billed,1)*100:.1f}%")
print()

if total_retries > 0:
    print("  ⚠ RETRIES DETECTED — concurrency cap recommended.")
    retry_cost_est = total_retries * 0.003  # rough per-retry cost for wasted attempts
    print(f"  Estimated wasted cost from 429 churn: ~${retry_cost_est:.4f}")
else:
    print("  ✓ No retries detected across 3 back-to-back designs.")
    print("    16-way parallelism is within rate limits at current load.")
print()

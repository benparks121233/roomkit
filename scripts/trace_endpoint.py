#!/usr/bin/env python3
"""
Trace the FULL POST /design endpoint — the exact path a browser hits.
Uses FastAPI's TestClient so it runs in-process (captures all LLM calls
via the same monkey-patch, including any middleware or background tasks).
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
# Thread-safe call log
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_calls: list[dict] = []
_cumulative_input = 0
_cumulative_output = 0
_cumulative_cost = 0.0
_call_counter = 0

def _infer_call_name(model: str, system_prompt: str) -> str:
    s = system_prompt[:500].lower()
    if "product selector" in s:
        return "selection"
    if "composition planner" in s or "distribute" in s and "weight" in s:
        return "composition"
    if "style interpreter" in s or "style profile" in s:
        return "style"
    # Catch anything else — this is the point of the exercise
    for hint, label in [
        ("blurb", "blurb"), ("personali", "personalize"),
        ("summar", "summary"), ("render", "render"),
        ("describe", "describe"), ("room design", "room-describe"),
    ]:
        if hint in s:
            return label
    return f"UNKNOWN({model})"

# ---------------------------------------------------------------------------
# Monkey-patch anthropic.Messages.create
# ---------------------------------------------------------------------------

import anthropic.resources.messages  # noqa: E402

_original_create = anthropic.resources.messages.Messages.create

def _instrumented_create(self, **kwargs):
    global _cumulative_input, _cumulative_output, _cumulative_cost, _call_counter

    model = kwargs.get("model", "unknown")
    system = kwargs.get("system", "")
    call_name = _infer_call_name(model, system)

    t0 = time.monotonic()
    result = _original_create(self, **kwargs)
    elapsed = time.monotonic() - t0

    usage = result.usage
    inp = usage.input_tokens
    out = usage.output_tokens
    c = cost_usd(model, inp, out)

    with _lock:
        _call_counter += 1
        seq = _call_counter
        _cumulative_input += inp
        _cumulative_output += out
        _cumulative_cost += c
        cum_in = _cumulative_input
        cum_out = _cumulative_output
        cum_cost = _cumulative_cost

        _calls.append({
            "seq": seq, "name": call_name, "model": model,
            "input_tokens": inp, "output_tokens": out,
            "cost": c, "elapsed": elapsed,
            "cum_input": cum_in, "cum_output": cum_out, "cum_cost": cum_cost,
        })

    model_short = "haiku" if "haiku" in model else "sonnet" if "sonnet" in model else model
    print(
        f"  [{seq:>2}] {call_name:<14} {model_short:<7} "
        f"in={inp:>6,}  out={out:>4}  "
        f"${c:.5f}  "
        f"│ cum: {cum_in:>7,} in  {cum_out:>5,} out  ${cum_cost:.5f}  "
        f"({elapsed:.1f}s)",
        flush=True,
    )

    return result

anthropic.resources.messages.Messages.create = _instrumented_create

# ---------------------------------------------------------------------------
# Hit the REAL endpoint via TestClient
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)

payload = {
    "room_type": "bedroom",
    "budget": 1500.0,
    "style_description": (
        "I want a sports den bedroom — moody and atmospheric, with rich depth, "
        "in dark tones with charcoal, dark wood, and warm amber. "
        "I'm drawn to walnut and leather. "
        "I lean toward clean, straight lines. "
        "I want a full room, but not cluttered."
    ),
    "bed_size": "queen",
    "density": "balanced",
    "interests": ["sports"],
    "full_room": True,
    "wants": [],
}

print("=" * 100)
print("  LIVE COST TRACE — POST /design (full endpoint, same path as browser)")
print("=" * 100)
print()
print(f"  {'#':>4} {'Call':<14} {'Model':<7} {'Input':>8}  {'Output':>5}  "
      f"{'Cost':>9}  │ {'Cum In':>9}  {'Cum Out':>7}  {'Cum Cost':>9}  {'Time':>6}")
print("  " + "─" * 95)

t_start = time.monotonic()
resp = client.post("/design", json=payload)
t_total = time.monotonic() - t_start

print()
print(f"  HTTP {resp.status_code}  ({t_total:.1f}s wall time)")

if resp.status_code != 200:
    print(f"  ERROR: {resp.text[:500]}")
else:
    data = resp.json()
    filled = sum(1 for s in data["slots"] if s["product"] is not None)
    print(f"  run_id: {data['run_id']}")
    print(f"  style:  {data['style']['style_name']}")
    print(f"  slots:  {filled} filled / {len(data['slots'])} total")
    print(f"  spent:  ${data['total_spent']:.2f} / ${data['target_budget']:.2f}")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print()
print("=" * 100)
print("  PER-CALL BREAKDOWN")
print("=" * 100)
print(f"  {'#':>4}  {'Call':<14} {'Model':<7} {'Input':>8}  {'Output':>5}  {'Cost':>9}  {'Time':>6}")
print("  " + "─" * 60)

for c in _calls:
    model_short = "haiku" if "haiku" in c["model"] else "sonnet"
    print(
        f"  {c['seq']:>4}  {c['name']:<14} {model_short:<7} "
        f"{c['input_tokens']:>8,}  {c['output_tokens']:>5}  "
        f"${c['cost']:.5f}  {c['elapsed']:>5.1f}s"
    )

print("  " + "─" * 60)

sonnet_calls = [c for c in _calls if "sonnet" in c["model"]]
haiku_calls = [c for c in _calls if "haiku" in c["model"]]
other_calls = [c for c in _calls if "sonnet" not in c["model"] and "haiku" not in c["model"]]

s_in = sum(c["input_tokens"] for c in sonnet_calls)
s_out = sum(c["output_tokens"] for c in sonnet_calls)
s_cost = sum(c["cost"] for c in sonnet_calls)
h_in = sum(c["input_tokens"] for c in haiku_calls)
h_out = sum(c["output_tokens"] for c in haiku_calls)
h_cost = sum(c["cost"] for c in haiku_calls)

print()
print(f"  Sonnet ({len(sonnet_calls)} calls): {s_in:>8,} in + {s_out:>5,} out = ${s_cost:.5f}")
print(f"  Haiku  ({len(haiku_calls)} calls): {h_in:>8,} in + {h_out:>5,} out = ${h_cost:.5f}")
if other_calls:
    o_cost = sum(c["cost"] for c in other_calls)
    print(f"  Other  ({len(other_calls)} calls): cost = ${o_cost:.5f}")
print(f"  {'─' * 50}")
print(f"  TOTAL  ({len(_calls)} calls): {_cumulative_input:>8,} in + {_cumulative_output:>5,} out = ${_cumulative_cost:.5f}")
print(f"  Wall time: {t_total:.1f}s")
print()

# Compare
print("  Comparison to direct pipeline trace:")
print(f"    Direct pipeline:   18 calls,  $0.058")
print(f"    POST /design:      {len(_calls)} calls,  ${_cumulative_cost:.3f}")
if len(_calls) == 18:
    print(f"    SAME — no hidden calls. The endpoint IS the pipeline.")
else:
    diff = len(_calls) - 18
    extra_cost = _cumulative_cost - 0.058
    print(f"    DIFFERENCE: {diff:+d} calls, ${extra_cost:+.4f} extra cost")
    print(f"    Extra calls:")
    for c in _calls:
        if c["name"] not in ("style", "composition", "selection"):
            model_short = "haiku" if "haiku" in c["model"] else "sonnet"
            print(f"      [{c['seq']}] {c['name']} ({model_short}, {c['input_tokens']:,} in)")
print()

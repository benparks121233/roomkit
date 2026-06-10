#!/usr/bin/env python3
"""
Live-trace a real design run — prints every Anthropic API call as it
completes, with model, input/output tokens, cost, and running totals.
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
# Pricing (per 1M tokens)
# ---------------------------------------------------------------------------

PRICING = {
    "claude-sonnet-4-6":         {"input": 3.00,  "output": 15.00},
    "claude-haiku-4-5-20251001": {"input": 0.80,  "output":  4.00},
}

def cost_usd(model: str, input_tok: int, output_tok: int) -> float:
    rates = PRICING.get(model, {"input": 3.00, "output": 15.00})
    return (input_tok * rates["input"] + output_tok * rates["output"]) / 1_000_000

# ---------------------------------------------------------------------------
# Call log — thread-safe accumulator
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_calls: list[dict] = []
_cumulative_input = 0
_cumulative_output = 0
_cumulative_cost = 0.0
_call_counter = 0

# Track which call is which by inspecting the system prompt / model.
# The pipeline creates calls in order: style (Sonnet), composition (Sonnet),
# then selection-{slot_id} (Haiku) in parallel.

def _infer_call_name(model: str, system_prompt: str) -> str:
    """Guess a human-readable call name from the model + prompt content."""
    s = system_prompt[:500].lower()
    if "product selector" in s:
        return "selection"
    if "composition planner" in s or "budget weight" in s or "distribute" in s and "weight" in s:
        return "composition"
    if "style interpreter" in s or "style profile" in s:
        return "style"
    return "unknown"

# ---------------------------------------------------------------------------
# Monkey-patch: wrap Messages.create to log every call
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
            "seq": seq,
            "name": call_name,
            "model": model,
            "input_tokens": inp,
            "output_tokens": out,
            "cost": c,
            "elapsed": elapsed,
            "cum_input": cum_in,
            "cum_output": cum_out,
            "cum_cost": cum_cost,
        })

    # Live print
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

# Apply the patch
anthropic.resources.messages.Messages.create = _instrumented_create

# ---------------------------------------------------------------------------
# Run a real Sports Den design through the full pipeline
# ---------------------------------------------------------------------------

from services.intake_service import parse_intake      # noqa: E402
from services.style_service import interpret_style     # noqa: E402
from services.composition_service import plan_composition  # noqa: E402
from services.sourcing.amazon_adapter import AmazonAdapter  # noqa: E402
from services.selection_service import select_product  # noqa: E402
from concurrent.futures import ThreadPoolExecutor, as_completed  # noqa: E402

STYLE_DESC = (
    "I want a sports den bedroom — moody and atmospheric, with rich depth, "
    "in dark tones with charcoal, dark wood, and warm amber. "
    "I'm drawn to walnut and leather. "
    "I lean toward clean, straight lines. "
    "I want a full room, but not cluttered."
)

req_payload = {
    "room_type": "bedroom",
    "budget": 1500.0,
    "style_description": STYLE_DESC,
    "bed_size": "queen",
    "density": "balanced",
    "interests": ["sports"],
    "full_room": True,
    "wants": [],
}

print("=" * 100)
print("  LIVE COST TRACE — Sports Den design")
print("=" * 100)
print()
print(f"  {'#':>4} {'Call':<14} {'Model':<7} {'Input':>8}  {'Output':>5}  "
      f"{'Cost':>9}  │ {'Cum In':>9}  {'Cum Out':>7}  {'Cum Cost':>9}  {'Time':>6}")
print("  " + "─" * 95)

t_start = time.monotonic()

# 1. Intake (no LLM)
room_request = parse_intake(req_payload)

# 2. Style interpretation (Sonnet)
style_profile = interpret_style(room_request)

# 3. Composition (Sonnet)
slot_plan = plan_composition(room_request, style_profile)

# 4. Sourcing + Selection (Haiku, parallel)
adapter = AmazonAdapter()
interests = room_request.interests

sourceable = []
for slot in slot_plan.slots:
    if slot.owned:
        continue
    spec_hints = {}
    if "bed_size" in slot.required_specs and room_request.bed_size:
        spec_hints["bed_size"] = room_request.bed_size
    candidates = adapter.fetch_candidates(
        slot.slot_id, style_profile.keywords,
        (0.0, slot.allocated_budget), spec_hints,
    )
    sourceable.append((slot, candidates))

# Parallel selection — each call prints live as it completes
selection_results = {}

with ThreadPoolExecutor(max_workers=len(sourceable) or 1) as pool:
    futures = {
        pool.submit(select_product, slot, style_profile, cands, interests): slot.slot_id
        for slot, cands in sourceable
    }
    for future in as_completed(futures):
        sid = futures[future]
        selection_results[sid] = future.result()

t_total = time.monotonic() - t_start

# ---------------------------------------------------------------------------
# Summary table
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

# Totals by model
sonnet_calls = [c for c in _calls if "sonnet" in c["model"]]
haiku_calls = [c for c in _calls if "haiku" in c["model"]]

s_in = sum(c["input_tokens"] for c in sonnet_calls)
s_out = sum(c["output_tokens"] for c in sonnet_calls)
s_cost = sum(c["cost"] for c in sonnet_calls)
h_in = sum(c["input_tokens"] for c in haiku_calls)
h_out = sum(c["output_tokens"] for c in haiku_calls)
h_cost = sum(c["cost"] for c in haiku_calls)

print()
print(f"  Sonnet ({len(sonnet_calls)} calls): {s_in:>8,} in + {s_out:>5,} out = ${s_cost:.5f}")
print(f"  Haiku  ({len(haiku_calls)} calls): {h_in:>8,} in + {h_out:>5,} out = ${h_cost:.5f}")
print(f"  {'─' * 50}")
print(f"  TOTAL  ({len(_calls)} calls): {_cumulative_input:>8,} in + {_cumulative_output:>5,} out = ${_cumulative_cost:.5f}")
print(f"  Wall time: {t_total:.1f}s")
print()

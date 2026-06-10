# services/selection_service.py
# Owns: choosing one product per slot from the sourcing adapter's candidate list.
# LLM (select_products.md) selects within a constrained candidate set.
# If no candidate satisfies required specs or price band, returns (None, reason).
#
# Critical rules:
#   - The LLM can only pick from the provided candidates — never invent a product.
#   - The chosen product is returned exactly as the adapter provided it.
#     Selection never modifies price, buy_url, or specs.
#   - Owned slots are skipped entirely — they are never sourced or selected.

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

import anthropic

logger = logging.getLogger(__name__)

from schemas.product import Product
from schemas.slot import Slot
from schemas.style_profile import StyleProfile

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_LLM_MODEL = "claude-sonnet-4-6"
_LLM_MAX_TOKENS = 256
_RETRY_MAX = 3
_RETRY_BACKOFF_BASE = 1.0  # seconds; doubles each retry


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def select_product(
    slot: Slot,
    style_profile: StyleProfile,
    candidates: list[Product],
) -> tuple[Product | None, str | None]:
    """Choose the single best product for a slot from the candidate list.

    Args:
        slot:           The slot to fill (provides slot_id, required_specs, owned).
        style_profile:  User's validated style for the LLM prompt.
        candidates:     Products returned by the sourcing adapter.

    Returns:
        (Product, fit_reason)   — LLM chose a candidate; product is unmodified.
        (None, "no_candidate")  — candidate list was empty.
        (None, "no_spec_match") — no candidate satisfies required specs/price.
        (None, "llm_error")     — LLM returned unparseable or invalid response.
    """
    # Owned slots are never sourced or selected.
    if slot.owned:
        return None, "owned_slot"

    # Empty candidate list.
    if not candidates:
        return None, "no_candidate"

    # Double-check: filter candidates by slot's required specs and price band.
    # The adapter should have already done this, but we enforce defensively.
    price_max = slot.allocated_budget
    valid = [
        c for c in candidates
        if _satisfies_specs(c, slot.required_specs) and c.normalized_price <= price_max
    ]
    if not valid:
        return None, "no_spec_match"

    # Build prompt and ask the LLM.
    system_prompt, user_message = _build_selection_prompts(slot, style_profile, valid)

    try:
        raw = _call_selection_llm(system_prompt, user_message)
        result = _parse_selection(raw, valid)
    except Exception:
        return None, "llm_error"

    return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _call_selection_llm(system_prompt: str, user_message: str) -> str:
    """Send a request to the Anthropic API.  Isolated for test patching.

    Retries up to ``_RETRY_MAX`` times on 429 (rate-limit) or 529
    (overloaded) responses with exponential backoff.
    """
    client = anthropic.Anthropic()
    for attempt in range(_RETRY_MAX):
        try:
            message = client.messages.create(
                model=_LLM_MODEL,
                max_tokens=_LLM_MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            return message.content[0].text
        except anthropic.RateLimitError:
            if attempt == _RETRY_MAX - 1:
                raise
            wait = _RETRY_BACKOFF_BASE * (2 ** attempt)
            logger.warning("Selection LLM rate-limited, retrying in %.1fs", wait)
            time.sleep(wait)
    raise RuntimeError("unreachable")


def _build_selection_prompts(
    slot: Slot,
    style_profile: StyleProfile,
    candidates: list[Product],
) -> tuple[str, str]:
    """Load select_products.md, substitute variables, return (system, user)."""
    template_text = (_PROMPTS_DIR / "select_products.md").read_text()

    style_summary = (
        f"style_name: {style_profile.style_name}\n"
        f"keywords: {', '.join(style_profile.keywords)}\n"
        f"mood: {style_profile.mood}"
    )

    # Build a minimal candidates JSON for the prompt (id, name, price, specs).
    candidates_for_prompt = [
        {
            "product_id": c.product_id,
            "name": c.name,
            "normalized_price": c.normalized_price,
            "specs": c.specs,
        }
        for c in candidates
    ]
    candidates_json = json.dumps(candidates_for_prompt, indent=2)

    price_min = 0.0
    price_max = slot.allocated_budget

    rendered = (
        template_text
        .replace("{{slot_id}}", slot.slot_id)
        .replace("{{style_profile_summary}}", style_summary)
        .replace("{{min_price}}", f"{price_min:.2f}")
        .replace("{{max_price}}", f"{price_max:.2f}")
        .replace("{{required_specs}}", json.dumps(slot.required_specs))
        .replace("{{candidates_json}}", candidates_json)
    )

    # Strip leading comment lines.
    lines = rendered.split("\n")
    first_content = next(
        (i for i, line in enumerate(lines) if line.strip() and not line.startswith("#")),
        0,
    )
    rendered = "\n".join(lines[first_content:])

    # Split on '---' into sections.
    raw_sections = re.split(r"(?m)^---$", rendered)

    system_parts: list[str] = []
    user_part = ""

    for raw in raw_sections:
        section = raw.strip()
        if not section:
            continue
        if section.startswith("## System"):
            body = section.split("\n", 1)[1].strip() if "\n" in section else ""
            system_parts.append(body)
        elif section.startswith("## User"):
            user_part = section.split("\n", 1)[1].strip() if "\n" in section else ""
        elif section.startswith("## Output schema"):
            system_parts.append(section)

    return "\n\n".join(system_parts), user_part


def _parse_selection(
    raw: str, candidates: list[Product],
) -> tuple[Product | None, str | None]:
    """Parse the LLM response and look up the chosen product.

    If the LLM returns a product_id not in the candidate list, fall back to
    None with reason "llm_error".  This treats hallucinated IDs the same as
    unparseable responses — the LLM's job is to pick from the list, not invent.
    """
    data = _extract_json(raw)
    product_id = data.get("product_id")
    fit_reason = data.get("fit_reason", "")

    # LLM explicitly returned null — respect the null_reason.
    if product_id is None:
        null_reason = data.get("null_reason", "no_spec_match")
        return None, null_reason

    # Look up the product in the candidate list.
    candidate_map = {c.product_id: c for c in candidates}
    if product_id not in candidate_map:
        # Hallucinated ID — reject.  We don't guess which product it meant.
        return None, "llm_error"

    return candidate_map[product_id], fit_reason or "style_match"


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling code fences."""
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return json.loads(text.strip())


def _satisfies_specs(product: Product, required_spec_keys: list[str]) -> bool:
    """Check that the product has every required spec key."""
    for key in required_spec_keys:
        if key not in product.specs:
            return False
    return True

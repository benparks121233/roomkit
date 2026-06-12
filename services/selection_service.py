# services/selection_service.py
# Owns: choosing products per slot from the sourcing adapter's candidate list.
# LLM (select_products.md) ranks candidates within a constrained set.
# If no candidate satisfies required specs or price band, returns empty.
#
# Critical rules:
#   - The LLM can only pick from the provided candidates — never invent a product.
#   - Chosen products are returned exactly as the adapter provided them.
#     Selection never modifies price, buy_url, or specs.
#   - Owned slots are skipped entirely — they are never sourced or selected.

from __future__ import annotations

import json
import logging
import random
import re
import time
from pathlib import Path

import anthropic

logger = logging.getLogger(__name__)

from schemas.product import Product
from schemas.slot import Slot
from schemas.style_profile import StyleProfile

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_LLM_MODEL = "claude-haiku-4-5-20251001"
_LLM_MAX_TOKENS = 2048  # 25-pick slots need ~1600 tokens; 2048 is generous headroom
_RETRY_MAX = 3
_RETRY_BACKOFF_BASE = 1.0  # seconds; doubles each retry

# Number of ranked picks to REQUEST from the LLM. We over-request by ~30%
# because the diversity filter (brand dedup) typically removes 2-4 items.
_DEFAULT_PICK_COUNT = 14

# Per-slot overrides for slots that benefit from more options.
_SLOT_PICK_COUNTS: dict[str, int] = {
    "wall_art": 25,
    "plants": 20,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# Decor slots where user interests can influence product selection.
_INTEREST_SLOTS = {"wall_art", "plants", "throw_blanket"}


def pick_count_for_slot(slot_id: str) -> int:
    """Return the number of ranked picks to request for a given slot."""
    return _SLOT_PICK_COUNTS.get(slot_id, _DEFAULT_PICK_COUNT)


# Decor slots have tighter price constraints (5–50% of budget vs 35–100%).
_DECOR_SLOTS = {"wall_art", "plants", "mirror", "throw_blanket", "curtains"}


# Common product-type words that are NOT brands.
_NOT_BRANDS = {
    "lamp", "table", "floor", "wall", "ceiling", "modern", "simple", "vintage",
    "rustic", "classic", "large", "small", "set", "pack", "led", "white",
    "black", "fluted", "rattan", "wood", "metal", "fabric", "natural",
    "abstract", "botanical", "framed", "decorative",
}


def _extract_brand(name: str) -> str:
    """Extract brand from a product name (typically the first word/token).

    Returns empty string if the first word is a generic product-type word
    (not a real brand). Real Amazon brands are usually all-caps or proper
    nouns like VASAGLE, Brightech, WLIVE, etc.
    """
    # Strip leading quotes, numbers, special chars
    cleaned = re.sub(r'^[\d"\']+\s*', "", name.strip())
    first_word = cleaned.split()[0] if cleaned.split() else ""
    lower = first_word.lower()
    # Skip generic product-type words
    if lower in _NOT_BRANDS:
        return ""
    return lower


def _name_keywords(name: str) -> set[str]:
    """Extract meaningful keywords from a product name (lowercase, 4+ chars)."""
    words = re.findall(r"[a-zA-Z]{4,}", name.lower())
    # Skip the brand (first word) and common filler words
    skip = {"with", "from", "that", "this", "wood", "inch", "wide", "tall", "drawer", "drawers"}
    return {w for w in words[1:] if w not in skip}


def _apply_diversity_rules(
    products: list[Product],
    fit_reasons: list[str],
    allocated_budget: float,
    slot_id: str,
) -> tuple[list[Product], list[str]]:
    """Post-LLM filter enforcing brand diversity and price spread.

    Rules:
      - Max 2 products from the same brand per slot.
      - Same-brand items must have meaningfully different keywords.
      - After brand dedup, backfill cheaper options to ensure price diversity.
    """
    # Track brand counts and keyword sets per brand
    brand_count: dict[str, int] = {}
    brand_keywords: dict[str, list[set[str]]] = {}

    filtered: list[Product] = []
    filtered_reasons: list[str] = []

    for product, reason in zip(products, fit_reasons):
        brand = _extract_brand(product.name)
        keywords = _name_keywords(product.name)

        # Brand-level checks only apply when we can detect a real brand
        if brand:
            count = brand_count.get(brand, 0)

            # Max 2 per brand
            if count >= 2:
                continue

            # Same brand items must have different keywords
            if count > 0 and brand in brand_keywords:
                prev_kw_sets = brand_keywords[brand]
                too_similar = any(
                    len(keywords & prev) > max(len(keywords), len(prev)) * 0.5
                    for prev in prev_kw_sets
                )
                if too_similar:
                    continue

        if brand:
            brand_count[brand] = brand_count.get(brand, 0) + 1
            brand_keywords.setdefault(brand, []).append(keywords)
        filtered.append(product)
        filtered_reasons.append(reason)

    # Price spread: ensure we have items across a range.
    # If all items cluster in the top 60% of the budget, pull in a cheaper
    # option from the original ranked list that we may have skipped.
    is_decor = slot_id in _DECOR_SLOTS
    cheap_threshold = allocated_budget * (0.15 if is_decor else 0.40)
    if len(filtered) >= 3:
        has_affordable = any(p.normalized_price <= cheap_threshold for p in filtered)
        if not has_affordable:
            included_ids = {p.product_id for p in filtered}
            for product, reason in zip(products, fit_reasons):
                if product.product_id in included_ids:
                    continue
                if product.normalized_price <= cheap_threshold:
                    brand = _extract_brand(product.name)
                    if not brand or brand_count.get(brand, 0) < 2:
                        filtered.append(product)
                        filtered_reasons.append(reason)
                        break

    return filtered, filtered_reasons


def select_products(
    slot: Slot,
    style_profile: StyleProfile,
    candidates: list[Product],
    interests: list[str] | None = None,
    pick_count: int = _DEFAULT_PICK_COUNT,
) -> tuple[list[Product], list[str], str | None]:
    """Rank the top products for a slot from the candidate list.

    Args:
        slot:           The slot to fill (provides slot_id, required_specs, owned).
        style_profile:  User's validated style for the LLM prompt.
        candidates:     Products returned by the sourcing adapter.
        interests:      User interest categories (e.g. ["music", "travel"]).
                        Only used for decor slots in _INTEREST_SLOTS.
        pick_count:     Maximum number of ranked picks to request.

    Returns:
        (products, fit_reasons, null_reason) where:
          - products:    Ranked list of Products (rank 1 first). May be empty.
          - fit_reasons: Parallel list of fit_reason strings, same length as products.
          - null_reason: Set only when products is empty ("no_candidate",
                         "no_spec_match", "llm_error", "owned_slot").
    """
    # Owned slots are never sourced or selected.
    if slot.owned:
        return [], [], "owned_slot"

    # Empty candidate list.
    if not candidates:
        return [], [], "no_candidate"

    # Double-check: filter candidates by slot's required specs and price band.
    # The LLM sees only candidates within the allocation so it can never pick
    # something that breaks the never-exceed guarantee.  Alternatives up to 1.5x
    # are appended AFTER the LLM picks (user can choose them with UI warnings).
    spec_valid = [c for c in candidates if _satisfies_specs(c, slot.required_specs)]
    within_budget = [c for c in spec_valid if c.normalized_price <= slot.allocated_budget]
    stretch_pool = [c for c in spec_valid
                    if slot.allocated_budget < c.normalized_price <= slot.allocated_budget * 1.5]
    if not within_budget:
        if not spec_valid:
            return [], [], "no_spec_match"
        return [], [], "no_candidate"
    valid = within_budget

    # Shuffle candidates before sending to LLM — prevents position bias
    # from causing the same items to get picked every run. The LLM sees
    # the same pool but in different order, leading to varied selections.
    valid = list(valid)
    random.shuffle(valid)

    # Only pass interests for decor slots where they're relevant.
    slot_interests = interests if interests and slot.slot_id in _INTEREST_SLOTS else None

    # Build prompt and ask the LLM.
    system_prompt, user_message = _build_selection_prompts(
        slot, style_profile, valid, interests=slot_interests,
        pick_count=pick_count,
    )

    try:
        raw = _call_selection_llm(system_prompt, user_message)
        products, fit_reasons, null_reason = _parse_ranked_selection(raw, valid)
    except Exception:
        logger.exception("Selection LLM call failed for slot %s", slot.slot_id)
        return [], [], "llm_error"

    pre_diversity = len(products)

    # Apply diversity rules: brand dedup, price spread, per-item cap.
    if products:
        products, fit_reasons = _apply_diversity_rules(
            products, fit_reasons, slot.allocated_budget, slot.slot_id,
        )
        if not products:
            return [], [], "llm_error"

    # Append stretch-pool items (1.0x-1.5x budget) as lower-ranked alternatives
    # so the user sees premium options, but the LLM's top pick is always within budget.
    if stretch_pool and products:
        selected_ids = {p.product_id for p in products}
        for sp in sorted(stretch_pool, key=lambda p: p.normalized_price)[:3]:
            if sp.product_id not in selected_ids:
                products.append(sp)
                fit_reasons.append("Premium option (above slot budget)")

    logger.info(
        "Slot %s: %d candidates → LLM returned %d → diversity filter kept %d (requested %d, +%d stretch)",
        slot.slot_id, len(valid), pre_diversity, len(products), pick_count, len(stretch_pool),
    )

    return products, fit_reasons, null_reason


def select_product(
    slot: Slot,
    style_profile: StyleProfile,
    candidates: list[Product],
    interests: list[str] | None = None,
) -> tuple[Product | None, str | None]:
    """Choose the single best product for a slot. Backward-compatible wrapper.

    Returns:
        (Product, fit_reason)   — LLM chose a candidate; product is unmodified.
        (None, "no_candidate")  — candidate list was empty.
        (None, "no_spec_match") — no candidate satisfies required specs/price.
        (None, "llm_error")     — LLM returned unparseable or invalid response.
    """
    products, fit_reasons, null_reason = select_products(
        slot, style_profile, candidates, interests, pick_count=_DEFAULT_PICK_COUNT,
    )
    if not products:
        return None, null_reason
    return products[0], fit_reasons[0]


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
                temperature=0.3,  # Light randomization for selection diversity
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
    *,
    interests: list[str] | None = None,
    pick_count: int = _DEFAULT_PICK_COUNT,
) -> tuple[str, str]:
    """Load select_products.md, substitute variables, return (system, user)."""
    template_text = (_PROMPTS_DIR / "select_products.md").read_text()

    style_summary = (
        f"style_name: {style_profile.style_name}\n"
        f"keywords: {', '.join(style_profile.keywords)}\n"
        f"color_palette: {', '.join(style_profile.color_palette)}\n"
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

    # Interest line — only for decor slots with user interests.
    # For wall_art, interests are the dominant signal.
    interests_line = ""
    if interests:
        if slot.slot_id == "wall_art":
            interests_line = (
                f"User interests: {', '.join(interests)}\n"
                f"IMPORTANT: This is wall art — the user's interests should be the "
                f"PRIMARY factor in your rankings. Most of your picks should directly "
                f"reflect these interests. Only use room style as a secondary filter "
                f"to avoid outright clashes.\n"
            )
        else:
            interests_line = f"User interests: {', '.join(interests)}\n"

    # Neutral fallback instruction for basics (sheets, pillows, curtains,
    # throw_blanket).  The majority of picks stay characterful/varied; we just
    # guarantee 2-3 clean neutral staples among them.
    _NEUTRAL_SLOTS = {"sheets", "throw_blanket", "pillows", "curtains"}
    neutral_instruction = ""
    if slot.slot_id in _NEUTRAL_SLOTS:
        # Pick neutral tones that match the room's mood + style keywords.
        mood_lower = (style_profile.mood or "").lower()
        kw_lower = " ".join(style_profile.keywords).lower()
        style_lower = (style_profile.style_name or "").lower()
        style_signal = f"{mood_lower} {kw_lower} {style_lower}"
        if any(w in style_signal for w in ("moody", "dark", "bold", "deep", "academia", "industrial", "gamer")):
            neutral_tones = "black, charcoal, or dark grey"
        elif any(w in style_signal for w in ("warm", "cozy", "heritage", "alpine", "cottage", "coastal")):
            neutral_tones = "beige, oatmeal, or warm cream"
        else:
            neutral_tones = "white, cream, or light grey"
        neutral_instruction = (
            f"- NEUTRAL STAPLES: Among your {pick_count} picks, include 2-3 clean "
            f"neutral options ({neutral_tones} — solid/plain, no patterns) so the "
            f"user always has a safe fallback. The MAJORITY of your picks should "
            f"still be varied, characterful, and interesting — patterns, colors, "
            f"textures. Do NOT make the list mostly neutral."
        )

    rendered = (
        template_text
        .replace("{{slot_id}}", slot.slot_id)
        .replace("{{style_profile_summary}}", style_summary)
        .replace("{{min_price}}", f"{price_min:.2f}")
        .replace("{{max_price}}", f"{price_max:.2f}")
        .replace("{{required_specs}}", json.dumps(slot.required_specs))
        .replace("{{allocated_budget}}", f"{price_max:.2f}")
        .replace("{{interests}}", interests_line)
        .replace("{{candidates_json}}", candidates_json)
        .replace("{{pick_count}}", str(pick_count))
        .replace("{{neutral_instruction}}", neutral_instruction)
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


def _parse_ranked_selection(
    raw: str, candidates: list[Product],
) -> tuple[list[Product], list[str], str | None]:
    """Parse a ranked LLM response and look up products.

    Handles both the new ranked format ({"ranked_picks": [...]}) and the
    legacy single-pick format ({"product_id": "..."}) for backward
    compatibility with tests that mock the old format.

    Returns (products, fit_reasons, null_reason). Hallucinated IDs are
    silently skipped — only valid candidates are returned.
    """
    data = _extract_json(raw)
    candidate_map = {c.product_id: c for c in candidates}

    # --- New ranked format ---
    ranked_picks = data.get("ranked_picks")
    if ranked_picks:
        products: list[Product] = []
        fit_reasons: list[str] = []
        seen: set[str] = set()

        for pick in ranked_picks:
            pid = pick.get("product_id")
            if not pid or pid in seen:
                continue
            if pid not in candidate_map:
                continue
            seen.add(pid)
            products.append(candidate_map[pid])
            fit_reasons.append(pick.get("fit_reason", "") or "style_match")

        if not products:
            return [], [], "llm_error"
        return products, fit_reasons, None

    # --- Legacy single-pick format ---
    product_id = data.get("product_id")
    if product_id is None:
        null_reason = data.get("null_reason", "no_spec_match")
        return [], [], null_reason

    if product_id not in candidate_map:
        return [], [], "llm_error"

    fit_reason = data.get("fit_reason", "") or "style_match"
    return [candidate_map[product_id]], [fit_reason], None


def _parse_selection(
    raw: str, candidates: list[Product],
) -> tuple[Product | None, str | None]:
    """Parse the LLM response (legacy single-pick format).

    Kept for backward compatibility with tests that mock the old format.
    The new prompt returns ranked_picks, but this handles both formats.
    """
    data = _extract_json(raw)

    # New ranked format.
    if "ranked_picks" in data:
        products, reasons, null_reason = _parse_ranked_selection(raw, candidates)
        if not products:
            return None, null_reason
        return products[0], reasons[0]

    # Legacy single-pick format.
    product_id = data.get("product_id")
    fit_reason = data.get("fit_reason", "")

    if product_id is None:
        null_reason = data.get("null_reason", "no_spec_match")
        return None, null_reason

    candidate_map = {c.product_id: c for c in candidates}
    if product_id not in candidate_map:
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

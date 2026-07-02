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

_anthropic_client: anthropic.Anthropic | None = None

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
        logger.warning("Slot %s: 0 candidates from sourcing", slot.slot_id)
        return [], [], "no_candidate"

    # Filter candidates by slot's required specs and price band.
    # The LLM sees candidates up to 1.15x allocation (per-slot stretch — a budget
    # is a target, not a hard ceiling; a great $115 product for a $100 slot is fine).
    # Alternatives up to 1.5x are appended AFTER the LLM picks as premium options.
    _LLM_STRETCH = 1.15
    spec_valid = [c for c in candidates if _satisfies_specs(c, slot.required_specs)]
    within_budget = [c for c in spec_valid if c.normalized_price <= slot.allocated_budget * _LLM_STRETCH]
    stretch_pool = [c for c in spec_valid
                    if slot.allocated_budget * _LLM_STRETCH < c.normalized_price <= slot.allocated_budget * 1.5]
    logger.info(
        "Slot %s: %d raw candidates → %d spec_valid → %d within_budget ($%.2f) → %d stretch",
        slot.slot_id, len(candidates), len(spec_valid), len(within_budget),
        slot.allocated_budget, len(stretch_pool),
    )
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

def _get_anthropic_client() -> anthropic.Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic()
    return _anthropic_client


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, anthropic.RateLimitError):
        return True
    if isinstance(exc, anthropic.APITimeoutError):
        return True
    if isinstance(exc, anthropic.InternalServerError) and getattr(exc, "status_code", 0) >= 500:
        return True
    return False


def _call_selection_llm(system_prompt: str, user_message: str) -> str:
    """Send a request to the Anthropic API.  Isolated for test patching.

    Retries up to ``_RETRY_MAX`` times on 429 (rate-limit), 529
    (overloaded), and timeout with exponential backoff.
    """
    client = _get_anthropic_client()
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
        except Exception as exc:
            if not _is_retryable(exc) or attempt == _RETRY_MAX - 1:
                raise
            wait = _RETRY_BACKOFF_BASE * (2 ** attempt)
            logger.warning("Selection LLM transient error (%s), retrying in %.1fs", type(exc).__name__, wait)
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
    if style_profile.selection_feel:
        style_summary += f"\nselection_feel: {style_profile.selection_feel}"

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

    # Per-aesthetic soft goods color profiles.
    # For sheets, comforter, duvet_cover, curtains, pillows, throw_blanket,
    # and throw_pillows — inject an instruction telling the LLM what colors
    # and textures match THIS aesthetic.  White/neutral is always valid as a
    # lower-ranked option, but it must NOT dominate the top picks unless the
    # aesthetic is genuinely light (japandi, coastal, warm_minimalist).
    _SOFT_GOODS_SLOTS = {
        "sheets", "comforter", "duvet_cover", "curtains", "pillows",
        "throw_blanket", "throw_pillows",
    }
    _SOFT_GOODS_PALETTES: dict[str, str] = {
        "dark_academia": (
            "deep burgundy, forest green, charcoal, espresso, oxblood, "
            "dark plaid/tartan, rich jewel tones, dark walnut brown. "
            "Think: a scholarly library with moody velvet and aged leather tones"
        ),
        "cottagecore": (
            "soft sage, dusty rose, cream, floral prints, gingham, "
            "lavender, warm white, patchwork, vintage linen. "
            "Think: a sun-dappled cottage bedroom with garden-inspired textiles"
        ),
        "coastal": (
            "soft blue, sandy beige, white, seafoam, navy stripe, "
            "natural linen, light chambray. "
            "Think: breezy beach house with ocean-inspired tones"
        ),
        "japandi": (
            "warm grey, oatmeal, off-white, muted natural linen, "
            "pale beige, stone. Light tones are CORRECT for this aesthetic. "
            "Think: serene and minimal with organic textures"
        ),
        "industrial": (
            "charcoal, dark grey, black, raw linen, muted olive, "
            "dark denim, slate. "
            "Think: converted loft with utilitarian textiles"
        ),
        "quiet_luxury": (
            "white, off-white, ivory, cream, warm white — these MUST dominate "
            "ranks 1-3 for sheets, duvet_cover, and comforter. Champagne and blush "
            "acceptable at rank 4+. Grey is WRONG for this aesthetic — skip grey "
            "entirely. Premium fabric is the star — sateen, silk, high-thread-count "
            "cotton. Think: five-star hotel suite with crisp white bedding"
        ),
        "sports_den": (
            "deep navy, charcoal, dark grey, brown, team colors welcome (red, "
            "green, orange as accents). Casual and comfortable — microfiber, "
            "jersey knit, fleece, sherpa. Bold solids and simple stripes OK. "
            "Think: man cave game-day vibes, team-color throw pillows, "
            "nothing formal or delicate"
        ),
        "city_modern": (
            "black, white, cool grey, high-contrast monochrome, "
            "one bold accent color (cobalt, red). "
            "Think: sleek high-rise apartment"
        ),
        "ski_lodge": (
            "deep red, forest green, cream, warm brown, burnt orange. "
            "PATTERNS: buffalo check, plaid, tartan — these are your anchors. "
            "TEXTURES: chunky knit, sherpa, faux fur, fleece, flannel. "
            "Every textile should scream 'mountain cabin' — nothing plain, "
            "nothing modern, nothing that could belong in a city apartment. "
            "Think: ski chalet after a powder day"
        ),
        "jungle_oasis": (
            "deep green, terracotta, warm cream, botanical prints, "
            "earthy tan, olive, tropical leaf patterns. "
            "Think: lush tropical retreat"
        ),
        "gamer_den": (
            "black, dark charcoal, deep purple, dark grey, "
            "matte dark tones. Keep it sleek and minimal. "
            "Think: moody immersive tech space"
        ),
        "poster_maximalist": (
            "warm amber, dusty pink, mustard yellow, mixed brights, "
            "bold patterns, eclectic prints, retro patterns. "
            "Think: expressive dorm-meets-gallery layered maximalism"
        ),
        "warm_minimalist": (
            "cream, warm white, oatmeal, light oak tones, soft beige, "
            "natural linen, cotton. Light and airy is CORRECT here. "
            "Think: calm Scandinavian simplicity"
        ),
    }

    # ── Per-aesthetic FURNITURE material/color palettes ──────────────
    # Same mechanism as soft goods: inject per-aesthetic guidance so the
    # LLM picks furniture that matches the room's aesthetic AND coordinates
    # across slots (sofa, armchair, tables all draw from the same anchor).
    _FURNITURE_SLOTS = {
        "sofa", "armchair", "coffee_table", "side_table", "tv_stand",
        "bed_frame", "dresser", "nightstand", "desk", "desk_chair",
    }
    _FURNITURE_PALETTES: dict[str, str] = {
        "dark_academia": (
            "RANK 1-2 ANCHOR: dark brown leather OR espresso/walnut wood with brass hardware. "
            "Both sofa and armchair defaults MUST land on the same material family. "
            "Materials: aged leather, tufted velvet, dark walnut, mahogany, brass pulls/legs. "
            "Colors: dark brown, espresso, oxblood, deep forest green. "
            "Think: antique library — every piece looks like it's been in a professor's study for decades. "
            "Bedroom: walnut dresser/nightstand with brass hardware, dark wood or upholstered bed frame."
        ),
        "cottagecore": (
            "RANK 1-2 ANCHOR: cream/soft white linen upholstery OR light natural/painted wood. "
            "Both sofa and armchair defaults MUST land on the same material family. "
            "Materials: linen/cotton slipcover, painted wood, turned legs, whitewash, distressed light wood. "
            "Colors: cream, soft white, light natural wood, sage green accents. "
            "Think: farmhouse vintage — soft, inviting, looks handmade or inherited. "
            "Bedroom: white/cream painted dresser, light wood nightstand, soft upholstered bed."
        ),
        "coastal": (
            "RANK 1-2 ANCHOR: white/sandy beige linen upholstery OR light natural wood with clean lines. "
            "Both sofa and armchair defaults MUST land on the same material family. "
            "Materials: light wood, rattan accents, linen upholstery, whitewash finish, woven details. "
            "Colors: white, sandy beige, light natural wood, soft blue accents. "
            "Think: breezy beach house — light, airy, nothing heavy or dark. "
            "Bedroom: light wood dresser, white/natural nightstand, clean-line bed frame."
        ),
        "japandi": (
            "RANK 1-2 ANCHOR: light oak with clean minimal lines, no ornament. "
            "Both sofa and armchair defaults MUST land on the same material family. "
            "Materials: light oak, natural ash, clean-line upholstery in neutral tones, minimal/hidden hardware. "
            "Colors: light oak, warm grey, oatmeal, muted beige. "
            "Think: serene simplicity — every piece is quiet, functional, beautiful in its restraint. "
            "Bedroom: light oak dresser, minimal floating-style nightstand, platform bed frame."
        ),
        "industrial": (
            "RANK 1-2 ANCHOR: black metal frame + dark wood top/shelf, OR dark leather with metal legs. "
            "Both sofa and armchair defaults MUST land on the same material family. "
            "Materials: black metal, iron pipe, reclaimed/dark wood, distressed leather, raw steel. "
            "Colors: black, dark brown, raw wood tones, matte metal. "
            "Think: converted factory loft — exposed structure is the design. "
            "Bedroom: metal frame bed, dark wood dresser with metal pulls, industrial nightstand."
        ),
        "quiet_luxury": (
            "RANK 1-2 ANCHOR: cream/ivory bouclé upholstery OR solid walnut with brass/gold hardware. "
            "Both sofa and armchair defaults MUST land on the same material family. "
            "Materials: marble tops, brass/gold hardware, bouclé, solid walnut, fluted wood panels, cream leather. "
            "Colors: ivory, warm white, champagne, walnut brown, gold accents. "
            "Think: five-star hotel lobby — understated wealth, nothing cheap, nothing loud. "
            "Bedroom: upholstered bed in cream, walnut dresser with brass pulls, marble-top nightstand."
        ),
        "sports_den": (
            "RANK 1-2 ANCHOR (sofa): oversized deep-seated plush sectional OR overstuffed recliner-sofa "
            "in charcoal/navy microfiber or soft fabric — wide, sink-in, man-cave comfort. "
            "NO leather or sleek/structured pieces at rank 1-2 (leather OK at rank 3+). "
            "Both sofa and armchair defaults MUST land on the same material family. "
            "Materials: soft microfiber, plush fabric, chenille, heavy cushion, reclining mechanism, dark wood. "
            "Colors: charcoal, navy, dark brown, black. "
            "Think: man cave — oversized sink-in comfort, nothing firm or precious, built for game-day lounging. "
            "Bedroom: dark wood dresser, casual dark nightstand, sturdy simple bed frame."
        ),
        "city_modern": (
            "RANK 1-2 ANCHOR: black or white upholstery with chrome/steel legs, clean geometric lines. "
            "Both sofa and armchair defaults MUST land on the same material family. "
            "Materials: chrome legs, glass/metal, clean leather or structured fabric, lacquer, high-gloss. "
            "Colors: black, white, cool grey, chrome silver. "
            "Think: sleek high-rise apartment — sharp, minimal, contemporary. "
            "Bedroom: platform bed with clean lines, glossy white/black dresser, glass-top nightstand."
        ),
        "ski_lodge": (
            "RANK 1-2 ANCHOR: warm brown rustic wood OR cabin-style dark leather with wood frame. "
            "Both sofa and armchair defaults MUST land on the same material family. "
            "Materials: knotty pine, reclaimed wood, heavy timber, dark leather, wrought iron accents. "
            "Colors: warm brown, honey wood, dark wood, cream/natural accents. "
            "Think: mountain cabin — heavy, substantial, handcrafted feel. "
            "Bedroom: rustic wood bed frame, knotty pine dresser, log/timber nightstand."
        ),
        "jungle_oasis": (
            "RANK 1-2 ANCHOR: natural rattan/cane OR dark tropical wood (teak, mango). "
            "Both sofa and armchair defaults MUST land on the same material family. "
            "Materials: rattan, cane weave, bamboo, dark tropical wood, woven natural fiber, live-edge. "
            "Colors: natural rattan tan, dark wood, warm brown, terracotta accents. "
            "Think: tropical retreat — organic textures, every piece looks like it grew. "
            "Bedroom: rattan or cane bed frame, dark wood dresser, woven-front nightstand."
        ),
        "gamer_den": (
            "RANK 1-2 ANCHOR (sofa): oversized deep-seated plush sectional OR overstuffed cloud sofa "
            "in dark charcoal/black soft microfiber or fabric — wide, sink-in, immersive comfort. "
            "NO leather or sleek/structured pieces at rank 1-2 (leather OK at rank 3+). "
            "Both sofa and armchair defaults MUST land on the same material family. "
            "Materials: soft microfiber, plush fabric, matte black finish, dark metal accents, black glass. "
            "Colors: black, dark charcoal, matte dark grey. "
            "Think: immersive gaming den — sink-in comfort for marathon sessions, stealth dark aesthetic, "
            "the gear is the focal point not the furniture. No RGB or 'GAMER' branding. "
            "Bedroom: black platform bed, dark modern dresser, minimal black nightstand."
        ),
        "poster_maximalist": (
            "RANK 1-2 ANCHOR: warm-toned mid-century wood OR velvet upholstery in a warm color "
            "(mustard, dusty pink, warm amber). "
            "Both sofa and armchair defaults MUST land on the same material family. "
            "Materials: mid-century wood, velvet upholstery, mixed warm tones, retro shapes, tapered legs. "
            "Colors: warm wood, mustard, dusty pink, amber, warm teal. "
            "Think: eclectic collector's apartment — personality in every piece, curated not chaotic. "
            "Bedroom: mid-century wood dresser, colorful upholstered bed, retro nightstand."
        ),
        "warm_minimalist": (
            "RANK 1-2 ANCHOR: light oak or natural wood with Scandinavian clean lines. "
            "Both sofa and armchair defaults MUST land on the same material family. "
            "Materials: light oak, natural ash, linen upholstery, minimal hardware, soft curves. "
            "Colors: light oak, warm white, soft beige, natural linen. "
            "Think: calm Scandinavian home — warm wood, soft light, nothing extra. "
            "Bedroom: light oak bed frame, natural wood dresser, floating-shelf nightstand."
        ),
    }

    neutral_instruction = ""
    if slot.slot_id in _SOFT_GOODS_SLOTS:
        style_name = (style_profile.style_name or "").lower()
        palette = _SOFT_GOODS_PALETTES.get(
            style_name,
            _SOFT_GOODS_PALETTES.get("warm_minimalist", ""),
        )
        neutral_instruction = (
            f"- **SOFT GOODS — MATCH THE AESTHETIC:**\n"
            f"  This slot carries the room's color story. Prioritize products\n"
            f"  that reflect the {style_name} palette: {palette}.\n"
            f"  Rank products that match these colors and textures highest.\n"
            f"  Show the full range of the palette across your picks.\n"
            f"  When characterful options cost less than plain basics,\n"
            f"  PREFER the characterful option — a $45 burgundy velvet curtain\n"
            f"  that nails dark_academia beats a $90 plain white linen panel."
        )
    elif slot.slot_id in _FURNITURE_SLOTS:
        style_name = (style_profile.style_name or "").lower()
        furn_palette = _FURNITURE_PALETTES.get(
            style_name,
            _FURNITURE_PALETTES.get("warm_minimalist", ""),
        )
        neutral_instruction = (
            f"- **FURNITURE — MATCH THE AESTHETIC AND COORDINATE:**\n"
            f"  Furniture sets the room's material foundation. All furniture in\n"
            f"  this room draws from the SAME palette so pieces coordinate.\n"
            f"  {style_name} furniture: {furn_palette}\n"
            f"  Rank 1-2 MUST follow the anchor above — these are auto-generate\n"
            f"  defaults that go in unchecked, so they must match other furniture\n"
            f"  in the room. Rank 3+ can explore the broader palette."
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

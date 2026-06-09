# services/composition_service.py
# Owns: planning which slots to fill and how to split the budget across them.
#
# Three public functions, three pieces:
#   allocate_budget()      — Piece 1.  Pure math, no LLM.
#   fit_slots_to_budget()  — Piece 2.  Pure math (optional-dropping + feasibility).
#   plan_composition()     — Piece 3.  LLM proposes weights → fit_slots_to_budget().
#
# The deterministic/LLM split is structural: business-rule math lives in
# allocate_budget() and fit_slots_to_budget(); LLM creativity lives in the
# prompt.  Budget enforcement is never delegated to the prompt.

from __future__ import annotations

import json
import re
from pathlib import Path

import anthropic

from schemas.room_request import RoomRequest
from schemas.room_taxonomy import RoomTaxonomy, SlotDefinition
from schemas.slot import Slot
from schemas.slot_plan import SlotPlan
from schemas.style_profile import StyleProfile
from services.config_loader import BudgetPolicies, load_budget_policies, load_room_taxonomy

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_LLM_MODEL = "claude-sonnet-4-6"
_LLM_MAX_TOKENS = 512


def allocate_budget(
    slot_weights: dict[str, float],
    target_budget: float,
    room_preset: str,
    taxonomy: RoomTaxonomy,
    run_id: str = "",
) -> SlotPlan:
    """Allocate target_budget across slots according to weights.  Pure, no LLM.

    Algorithm:
      1. Validate room_preset against the taxonomy.
      2. Inject any required slots missing from slot_weights using their
         taxonomy default_budget_weight.
      3. If sum(weights) > 1.0, re-normalize proportionally so the weights
         sum to exactly 1.0.  If sum ≤ 1.0, use weights as-is — under-budget
         is always safe.
      4. Multiply each weight by target_budget to get allocated_budget.
      5. Apply a floating-point clamp: if rounding drift has pushed
         sum(allocated_budgets) above target_budget, scale the whole set
         down uniformly so the invariant is restored.
      6. Build Slot objects from taxonomy data + computed budgets.

    Args:
        slot_weights:  Proposed weight per slot id (0 < weight ≤ 1.0 each).
                       Need not be normalized.  Need not include all required
                       slots — missing required ones are injected.
        target_budget: Budget ceiling in USD.  Must be > 0.
        room_preset:   Key from taxonomy.room_presets (e.g. "bedroom").
        taxonomy:      Loaded RoomTaxonomy — authoritative slot definitions.
        run_id:        Optional; threaded from RoomRequest when called by
                       plan_composition().  Defaults to "" for standalone use.

    Returns:
        SlotPlan where total_allocated <= target_budget always.

    Raises:
        ValueError: if room_preset is not in the taxonomy.
        ValueError: if all effective weights are zero or negative.
        KeyError:   if a required slot id is not found in the taxonomy.
    """
    if room_preset not in taxonomy.room_presets:
        raise ValueError(
            f"Unknown room_preset '{room_preset}'. "
            f"Valid presets: {sorted(taxonomy.room_presets)}"
        )
    if target_budget <= 0:
        raise ValueError(f"target_budget must be > 0, got {target_budget}")

    required_slot_ids = taxonomy.room_presets[room_preset].required_slots

    # --- Step 1: Build effective weight dict ---------------------------------
    # Start with the caller's proposals and inject any missing required slots.
    weights: dict[str, float] = dict(slot_weights)
    for slot_id in required_slot_ids:
        if slot_id not in weights:
            slot_def = taxonomy.slot_by_id(slot_id)   # raises KeyError if unknown
            weights[slot_id] = slot_def.default_budget_weight

    # --- Step 2: Re-normalize if sum > 1.0 -----------------------------------
    total_weight = sum(weights.values())
    if total_weight <= 0.0:
        raise ValueError(
            "All effective slot weights are zero or negative — "
            "cannot allocate a budget."
        )
    if total_weight > 1.0:
        # Proportional re-normalization: preserves relative slot priorities.
        weights = {slot_id: w / total_weight for slot_id, w in weights.items()}

    # --- Step 3: Multiply weights by target_budget ---------------------------
    allocated: dict[str, float] = {
        slot_id: w * target_budget for slot_id, w in weights.items()
    }

    # --- Step 4: Floating-point clamp ----------------------------------------
    # After normalization the sum should equal target_budget, but IEEE 754
    # rounding can push it a few ULPs above.  Scale uniformly rather than
    # adjusting a single slot (which would distort relative proportions).
    raw_total = sum(allocated.values())
    if raw_total > target_budget:
        scale = target_budget / raw_total
        allocated = {slot_id: v * scale for slot_id, v in allocated.items()}

    # --- Step 5: Build Slot objects ------------------------------------------
    slots: list[Slot] = []
    for slot_id, budget in allocated.items():
        slot_def = taxonomy.slot_by_id(slot_id)
        slots.append(Slot(
            slot_id=slot_id,
            allocated_budget=budget,
            required_specs=list(slot_def.required_specs),
            optional=slot_def.optional,
        ))

    return SlotPlan(
        run_id=run_id,
        room_preset=room_preset,
        target_budget=target_budget,
        slots=slots,
    )


def fit_slots_to_budget(
    slot_weights: dict[str, float],
    target_budget: float,
    room_preset: str,
    taxonomy: RoomTaxonomy,
    budget_policies: BudgetPolicies,
    run_id: str = "",
) -> SlotPlan:
    """Return a feasible SlotPlan, dropping optional slots if needed.

    Algorithm:
      1. Build the full set of active slots (required + any optionals in
         slot_weights), sorted optionals by default_budget_weight ascending.
      2. Compute the feasibility floor for the current active set:
           floor = max(sum_active_weights, 1.0) × minimum_room_multiplier
         If target_budget >= floor, the set is feasible → delegate to
         allocate_budget() and return.
      3. Otherwise, drop the lowest-weight optional slot and repeat step 2.
      4. If all optionals have been dropped and required-only is still
         infeasible, return SlotPlan(is_feasible=False, ...) with:
           - slots set to the required slots at allocated_budget=0.0
           - minimum_viable_budget = max(sum_req_weights, 1.0) × multiplier

    The returned plan always satisfies:
      - total_allocated <= target_budget  (when is_feasible=True)
      - is_feasible=False with an honest minimum_viable_budget  (otherwise)

    Args:
        slot_weights:    Proposed weight per slot id.  Optional slots are
                         identified via taxonomy.slot_by_id().optional.
        target_budget:   Budget ceiling in USD.  Must be > 0.
        room_preset:     Key from taxonomy.room_presets.
        taxonomy:        Loaded RoomTaxonomy.
        budget_policies: Loaded BudgetPolicies (provides minimum_room_multiplier).
        run_id:          Optional; threaded from RoomRequest.

    Returns:
        SlotPlan — is_feasible=True and total<=budget, or is_feasible=False.

    Raises:
        ValueError: if room_preset is not in the taxonomy or budget <= 0.
    """
    if room_preset not in taxonomy.room_presets:
        raise ValueError(
            f"Unknown room_preset '{room_preset}'. "
            f"Valid presets: {sorted(taxonomy.room_presets)}"
        )
    if target_budget <= 0:
        raise ValueError(f"target_budget must be > 0, got {target_budget}")

    multiplier = budget_policies.minimum_room_multiplier
    required_ids = set(taxonomy.room_presets[room_preset].required_slots)

    # Build full weight dict: required slots (injected if absent) + optionals.
    weights: dict[str, float] = {}
    for slot_id in required_ids:
        weights[slot_id] = slot_weights.get(slot_id, taxonomy.slot_by_id(slot_id).default_budget_weight)
    for slot_id, w in slot_weights.items():
        if slot_id not in required_ids:
            weights[slot_id] = w  # optional extra slots from caller

    # Collect optional slot definitions sorted ascending by default_budget_weight
    # (lowest-weight optionals dropped first).
    def _optional_defs_ascending(active: dict[str, float]) -> list[SlotDefinition]:
        optional_slots = [
            taxonomy.slot_by_id(sid)
            for sid in active
            if sid not in required_ids
        ]
        return sorted(optional_slots, key=lambda s: s.default_budget_weight)

    # Drop optionals until feasible or none left.
    active = dict(weights)
    while True:
        total_w = sum(active.values())
        floor = max(total_w, 1.0) * multiplier
        if target_budget >= floor:
            # Feasible — delegate all budget math to allocate_budget().
            return allocate_budget(active, target_budget, room_preset, taxonomy, run_id=run_id)

        optionals = _optional_defs_ascending(active)
        if not optionals:
            break  # Nothing left to drop — infeasible.

        # Drop the cheapest optional and retry.
        active.pop(optionals[0].id)

    # Required-only is still infeasible.
    req_weight_sum = sum(
        taxonomy.slot_by_id(sid).default_budget_weight for sid in required_ids
    )
    mvb = max(req_weight_sum, 1.0) * multiplier

    required_slots = [
        Slot(
            slot_id=sid,
            allocated_budget=0.0,
            required_specs=list(taxonomy.slot_by_id(sid).required_specs),
            optional=False,
        )
        for sid in sorted(required_ids)
    ]
    return SlotPlan(
        run_id=run_id,
        room_preset=room_preset,
        target_budget=target_budget,
        slots=required_slots,
        is_feasible=False,
        minimum_viable_budget=mvb,
    )


def plan_composition(
    room_request: RoomRequest,
    style_profile: StyleProfile,
) -> SlotPlan:
    """Map a RoomRequest + StyleProfile to a SlotPlan via LLM.

    The LLM proposes slot budget *weights* only.  All dollar math, feasibility
    checks, optional-dropping, and budget clamping live in fit_slots_to_budget().

    Recovery on bad LLM output:
      - Unparseable JSON → fall back to taxonomy default weights.
      - Hallucinated slot ids → silently dropped.
      - Missing required slots → injected by fit_slots_to_budget().
      - Weights summing to anything → normalization handles it.
      - Any exception → taxonomy defaults, never raise.

    Args:
        room_request:  Validated intake; provides run_id, budget, room_type.
        style_profile: Validated style; used in the prompt for style-guided weights.

    Returns:
        SlotPlan (always).  is_feasible may be False if budget is too low.
    """
    taxonomy = load_room_taxonomy()
    budget_policies = load_budget_policies()

    room_preset = room_request.room_type or "bedroom"
    target_budget = room_request.budget or 1000.0
    run_id = room_request.run_id

    system_prompt, user_message = _build_composition_prompts(
        room_preset, target_budget, style_profile, taxonomy,
    )

    try:
        raw = _call_composition_llm(system_prompt, user_message)
        weights = _parse_weight_proposal(raw, room_preset, taxonomy)
    except Exception:
        weights = _taxonomy_default_weights(room_preset, taxonomy)

    return fit_slots_to_budget(
        weights, target_budget, room_preset, taxonomy, budget_policies,
        run_id=run_id,
    )


# ---------------------------------------------------------------------------
# Private helpers — LLM isolation + prompt building
# ---------------------------------------------------------------------------

def _call_composition_llm(system_prompt: str, user_message: str) -> str:
    """Send a request to the Anthropic API and return the raw text.

    Isolated here so tests can patch
    services.composition_service._call_composition_llm without importing
    or instantiating the Anthropic client.
    """
    client = anthropic.Anthropic()
    message = client.messages.create(
        model=_LLM_MODEL,
        max_tokens=_LLM_MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text


def _build_composition_prompts(
    room_preset: str,
    target_budget: float,
    style_profile: StyleProfile,
    taxonomy: RoomTaxonomy,
) -> tuple[str, str]:
    """Load plan_composition.md, substitute variables, return (system, user)."""
    template_text = (_PROMPTS_DIR / "plan_composition.md").read_text()

    required_ids = taxonomy.room_presets[room_preset].required_slots
    all_ids = taxonomy.slot_ids()

    # Build a human-readable slot catalogue.
    slot_lines = []
    for slot_def in taxonomy.slots:
        slot_lines.append(
            f"- id: {slot_def.id}  "
            f"default_weight: {slot_def.default_budget_weight}  "
            f"required_specs: {slot_def.required_specs}"
        )
    slot_definitions = "\n".join(slot_lines)

    # Style profile summary for the prompt.
    style_summary = (
        f"style_name: {style_profile.style_name}\n"
        f"keywords: {', '.join(style_profile.keywords)}\n"
        f"color_palette: {', '.join(style_profile.color_palette)}\n"
        f"mood: {style_profile.mood}"
    )

    optional_ids = sorted(all_ids - set(required_ids))

    rendered = (
        template_text
        .replace("{{slot_definitions}}", slot_definitions)
        .replace("{{style_profile}}", style_summary)
        .replace("{{room_preset}}", room_preset)
        .replace("{{target_budget}}", f"{target_budget:.2f}")
        .replace("{{required_slots}}", ", ".join(required_ids))
        .replace("{{optional_slots}}", ", ".join(optional_ids) if optional_ids else "(none)")
        .replace("{{style_name}}", style_profile.style_name)
    )

    # Strip leading comment lines (file header).
    lines = rendered.split("\n")
    first_content = next(
        (i for i, line in enumerate(lines) if line.strip() and not line.startswith("#")),
        0,
    )
    rendered = "\n".join(lines[first_content:])

    # Split into sections on lines that are exactly '---'.
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


def _parse_weight_proposal(
    raw: str,
    room_preset: str,
    taxonomy: RoomTaxonomy,
) -> dict[str, float]:
    """Parse the LLM JSON response into a clean {slot_id: weight} dict.

    Recovery rules:
      - Slot ids not in the taxonomy are silently dropped.
      - Non-numeric or non-positive weights are dropped.
      - If nothing usable remains, returns taxonomy defaults.
    """
    data = _extract_composition_json(raw)
    raw_weights = data.get("slot_weights", {})
    if not isinstance(raw_weights, dict):
        return _taxonomy_default_weights(room_preset, taxonomy)

    valid_ids = taxonomy.slot_ids()
    cleaned: dict[str, float] = {}
    for slot_id, weight in raw_weights.items():
        if slot_id not in valid_ids:
            continue  # hallucinated slot — drop
        try:
            w = float(weight)
        except (TypeError, ValueError):
            continue
        if w > 0:
            cleaned[slot_id] = w

    if not cleaned:
        return _taxonomy_default_weights(room_preset, taxonomy)

    # Pre-normalize if sum > 1.0.  The LLM's absolute weight scale is
    # arbitrary; only the relative proportions matter.  Without this,
    # inflated weights (e.g. sum=3.0) would inflate the feasibility floor
    # in fit_slots_to_budget(), causing a plan to appear infeasible when
    # normalization would have handled it fine.
    total = sum(cleaned.values())
    if total > 1.0:
        cleaned = {sid: w / total for sid, w in cleaned.items()}

    return cleaned


def _extract_composition_json(text: str) -> dict:
    """Extract a JSON object from the LLM response, handling code fences."""
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return json.loads(text.strip())


def _taxonomy_default_weights(
    room_preset: str, taxonomy: RoomTaxonomy,
) -> dict[str, float]:
    """Return the taxonomy default_budget_weight for every required slot."""
    required_ids = taxonomy.room_presets[room_preset].required_slots
    return {
        sid: taxonomy.slot_by_id(sid).default_budget_weight
        for sid in required_ids
    }

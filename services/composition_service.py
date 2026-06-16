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
#
# v2 taxonomy: groups sit between room-budget and individual items.
# flatten_weights() bridges groups → flat {item_id: weight} dict.
# allocate_budget() and fit_slots_to_budget() remain unchanged in logic —
# they receive flat weight dicts and don't know about groups.

from __future__ import annotations

import json
import re
from pathlib import Path

import anthropic

from schemas.room_request import RoomRequest
from schemas.room_taxonomy import RoomTaxonomy
from schemas.slot import Slot
from schemas.slot_plan import SlotPlan
from schemas.style_profile import StyleProfile
from services.config_loader import BudgetPolicies, load_budget_policies, load_room_taxonomy

# Per-category minimum price floors — derived from the cheapest real product in
# each category's catalog.  Used by allocate_budget() to ensure every slot gets
# enough budget to buy at least one item.  Fallback for unknown slots: $15.
_CATEGORY_PRICE_FLOORS: dict[str, float] = {
    "armchair": 109.99,
    "bed_frame": 31.99,
    "bookshelf": 39.99,
    "ceiling_light": 9.35,
    "coffee_table": 59.99,
    "comforter": 18.99,
    "curtains": 6.99,
    "desk": 49.99,
    "desk_chair": 39.99,
    "duvet_cover": 14.99,
    "duvet_insert": 19.99,
    "dresser": 19.96,
    "floor_lamp": 19.99,
    "mattress": 80.00,
    "mirror": 14.80,
    "nightstand": 11.99,
    "ottoman": 34.99,
    "pillows": 5.59,
    "plants": 4.89,
    "rug": 17.99,
    "sconce": 14.99,
    "sheets": 9.97,
    "side_table": 29.99,
    "sofa": 199.99,
    "sound_bar": 49.99,
    "table_lamp": 9.89,
    "throw_blanket": 8.54,
    "throw_pillows": 10.99,
    "tv": 149.99,
    "tv_stand": 49.99,
    "wall_art": 2.34,
}
_DEFAULT_PRICE_FLOOR = 15.0

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_LLM_MODEL = "claude-sonnet-4-6"
_LLM_MAX_TOKENS = 512


def allocate_budget(
    slot_weights: dict[str, float],
    target_budget: float,
    room_preset: str,
    taxonomy: RoomTaxonomy,
    run_id: str = "",
    required_override: list[str] | None = None,
) -> SlotPlan:
    """Allocate target_budget across slots according to weights.  Pure, no LLM.

    Algorithm:
      1. Validate room_preset against the taxonomy.
      2. Inject any required slots missing from slot_weights using their
         default weight from the preset's group structure.
      3. If sum(weights) > 1.0, re-normalize proportionally so the weights
         sum to exactly 1.0.  If sum ≤ 1.0, use weights as-is — under-budget
         is always safe.
      4. Multiply each weight by target_budget to get allocated_budget.
      5. Apply a floating-point clamp: if rounding drift has pushed
         sum(allocated_budgets) above target_budget, scale the whole set
         down uniformly so the invariant is restored.
      6. Build Slot objects from taxonomy data + computed budgets.

    Args:
        slot_weights:      Proposed weight per slot id (0 < weight ≤ 1.0 each).
                           Need not be normalized.  Need not include all required
                           slots — missing required ones are injected.
        target_budget:     Budget ceiling in USD.  Must be > 0.
        room_preset:       Key from taxonomy.room_presets (e.g. "bedroom").
        taxonomy:          Loaded RoomTaxonomy — authoritative slot definitions.
        run_id:            Optional; threaded from RoomRequest when called by
                           plan_composition().  Defaults to "" for standalone use.
        required_override: If provided, use this list of slot ids as the required
                           set instead of the preset's required_items().
                           Used by fit_slots_to_budget for have/need logic.

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

    preset = taxonomy.room_presets[room_preset]
    default_weights = preset.flatten_weights()

    required_slot_ids = (
        required_override if required_override is not None
        else preset.required_items()
    )

    # --- Step 1: Build effective weight dict ---------------------------------
    # Start with the caller's proposals and inject any missing required slots.
    weights: dict[str, float] = dict(slot_weights)
    for slot_id in required_slot_ids:
        if slot_id not in weights:
            if slot_id in default_weights:
                weights[slot_id] = default_weights[slot_id]
            else:
                raise KeyError(
                    f"Required slot '{slot_id}' not found in preset '{room_preset}' groups"
                )

    # --- Step 2: Always normalize to 1.0 ----------------------------------------
    # When excluded/owned slots are removed, the remaining weights sum to < 1.0.
    # Without normalization, that gap becomes un-allocated budget (utilization leak).
    # Always normalize so active slots split the FULL budget proportionally.
    total_weight = sum(weights.values())
    if total_weight <= 0.0:
        raise ValueError(
            "All effective slot weights are zero or negative — "
            "cannot allocate a budget."
        )
    if abs(total_weight - 1.0) > 1e-9:
        weights = {slot_id: w / total_weight for slot_id, w in weights.items()}

    # --- Step 3: Multiply weights by target_budget ---------------------------
    allocated: dict[str, float] = {
        slot_id: w * target_budget for slot_id, w in weights.items()
    }

    # --- Step 3b: Per-category price floors + optional drop --------------------
    # Each slot is floored to the cheapest real product in its catalog so it
    # can always buy *something*.  If scaling to fit the budget pushes an
    # optional slot back below its floor, drop it (budget goes to others).
    # Required slots are never dropped — they keep their scaled share.
    required_set = set(required_slot_ids)

    def _apply_floors(alloc: dict[str, float]) -> dict[str, float]:
        out = dict(alloc)
        for sid in out:
            floor = _CATEGORY_PRICE_FLOORS.get(sid, _DEFAULT_PRICE_FLOOR)
            if out[sid] < floor:
                out[sid] = floor
        total = sum(out.values())
        if total > target_budget:
            # Scale only the headroom above each slot's floor so that
            # every slot stays at or above its floor after scaling.
            floor_total = sum(
                _CATEGORY_PRICE_FLOORS.get(sid, _DEFAULT_PRICE_FLOOR)
                for sid in out
            )
            headroom_budget = target_budget - floor_total
            headroom_total = total - floor_total
            if headroom_total > 0 and headroom_budget > 0:
                scale = headroom_budget / headroom_total
                for sid in out:
                    floor = _CATEGORY_PRICE_FLOORS.get(sid, _DEFAULT_PRICE_FLOOR)
                    out[sid] = floor + (out[sid] - floor) * scale
            else:
                # Budget can't cover all floors — uniform scale as fallback.
                scale = target_budget / total
                out = {sid: v * scale for sid, v in out.items()}
        return out

    allocated = _apply_floors(allocated)

    # Drop optional slots that fell below their floor after scaling.
    # Re-apply floors with the freed budget.  Iterate until stable.
    for _ in range(len(allocated)):
        to_drop = [
            sid for sid in allocated
            if sid not in required_set
            and allocated[sid] < _CATEGORY_PRICE_FLOORS.get(sid, _DEFAULT_PRICE_FLOOR)
        ]
        if not to_drop:
            break
        for sid in to_drop:
            del allocated[sid]
        if not allocated:
            break
        # Re-normalize weights for remaining slots and re-allocate.
        remaining_weights = {sid: weights[sid] for sid in allocated}
        tw = sum(remaining_weights.values())
        if tw > 0:
            allocated = {sid: (w / tw) * target_budget for sid, w in remaining_weights.items()}
            allocated = _apply_floors(allocated)

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
        item_def = taxonomy.item_by_id(slot_id)
        slots.append(Slot(
            slot_id=slot_id,
            allocated_budget=budget,
            required_specs=list(item_def.required_specs),
            optional=slot_id not in required_set,
            max_quantity=item_def.max_quantity,
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
    already_have: set[str] | None = None,
    must_have: set[str] | None = None,
) -> SlotPlan:
    """Return a feasible SlotPlan, dropping optional slots if needed.

    Supports per-request customization via already_have / must_have:
      - already_have: slots the user owns.  Never sourced, never counted
        toward feasibility/budget.  Recorded on the plan with owned=True
        and allocated_budget=0 for render/coherence.
      - must_have: slots promoted to required.  Never dropped during the
        optional-dropping loop.

    Algorithm:
      1. Compute effective_required = (preset_required - already_have) | must_have.
      2. Build weight dict for sourced slots only (excluding already_have).
      3. Feasibility floor is computed against sourced active weights.
      4. Drop non-required, non-must_have optionals (lowest weight first)
         until feasible.
      5. If still infeasible after dropping all droppable optionals, return
         is_feasible=False with MVB based on effective_required.
      6. On feasibility, delegate to allocate_budget(), then append owned
         slots at $0.

    Args:
        slot_weights:    Proposed weight per slot id.
        target_budget:   Budget ceiling in USD.  Must be > 0.
        room_preset:     Key from taxonomy.room_presets.
        taxonomy:        Loaded RoomTaxonomy.
        budget_policies: Loaded BudgetPolicies (provides minimum_room_multiplier).
        run_id:          Optional; threaded from RoomRequest.
        already_have:    Slot ids the user already owns (excluded from sourcing).
        must_have:       Slot ids forced into the effective required set.

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

    already_have = already_have or set()
    must_have = must_have or set()

    multiplier = budget_policies.minimum_room_multiplier
    preset = taxonomy.room_presets[room_preset]
    preset_required = set(preset.required_items())
    default_weights = preset.flatten_weights()

    # Effective required: preset required minus owned, plus must-have.
    effective_required = (preset_required - already_have) | must_have

    # Build weight dict for SOURCED slots only (exclude already_have entirely).
    weights: dict[str, float] = {}
    for slot_id in effective_required:
        if slot_id not in already_have:
            weights[slot_id] = slot_weights.get(
                slot_id, default_weights.get(slot_id, 0.05)
            )
    for slot_id, w in slot_weights.items():
        if slot_id not in effective_required and slot_id not in already_have:
            weights[slot_id] = w  # optional extra slots from caller

    # Droppable optionals: sourced slots that are NOT in effective_required.
    # Sort by their default weight (ascending) so cheapest drops first.
    def _droppable_ids_ascending(active: dict[str, float]) -> list[str]:
        droppable = [
            sid for sid in active
            if sid not in effective_required
        ]
        return sorted(droppable, key=lambda sid: default_weights.get(sid, 0.0))

    # Drop optionals until feasible or none left.
    active = dict(weights)
    while True:
        total_w = sum(active.values())
        floor = max(total_w, 1.0) * multiplier
        if target_budget >= floor:
            # Feasible — delegate budget math to allocate_budget().
            plan = allocate_budget(
                active, target_budget, room_preset, taxonomy,
                run_id=run_id,
                required_override=list(effective_required),
            )
            # Append owned slots at $0 for render/coherence.
            owned_slots = _build_owned_slots(already_have, taxonomy)
            if owned_slots:
                plan = plan.model_copy(update={"slots": plan.slots + owned_slots})
            return plan

        droppable = _droppable_ids_ascending(active)
        if not droppable:
            break  # Nothing left to drop — infeasible.

        # Drop the cheapest droppable optional and retry.
        active.pop(droppable[0])

    # Effective-required-only is still infeasible.
    req_weight_sum = sum(
        default_weights.get(sid, 0.05)
        for sid in effective_required
    )
    mvb = max(req_weight_sum, 1.0) * multiplier

    infeasible_slots = [
        Slot(
            slot_id=sid,
            allocated_budget=0.0,
            required_specs=list(taxonomy.item_by_id(sid).required_specs),
            optional=sid not in effective_required,
            max_quantity=taxonomy.item_by_id(sid).max_quantity,
        )
        for sid in sorted(effective_required)
    ]
    # Include owned slots on infeasible plans too (for display).
    infeasible_slots.extend(_build_owned_slots(already_have, taxonomy))

    return SlotPlan(
        run_id=run_id,
        room_preset=room_preset,
        target_budget=target_budget,
        slots=infeasible_slots,
        is_feasible=False,
        minimum_viable_budget=mvb,
    )


def _build_owned_slots(already_have: set[str], taxonomy: RoomTaxonomy) -> list[Slot]:
    """Build Slot objects for user-owned items: $0 budget, owned=True."""
    slots = []
    for sid in sorted(already_have):
        item_def = taxonomy.item_by_id(sid)
        slots.append(Slot(
            slot_id=sid,
            allocated_budget=0.0,
            required_specs=list(item_def.required_specs),
            optional=True,  # owned slots are not sourced
            owned=True,
            max_quantity=item_def.max_quantity,
        ))
    return slots


# Slots dropped per density level.  Only optional slots may appear here.
# "minimal" drops extra decor/accent items; "balanced"/"layered" keep all.
# Slots dropped per density level.  Only non-preference-addressed optional
# items appear here.  Survey-gated items (desk, lighting types,
# mirror, bedding type) are controlled by the preference survey on the
# full-room path, or by the wants picker on the partial-room path — never
# by density.
_DENSITY_DROP: dict[str, set[str]] = {
    "minimal": {"plants", "curtains", "throw_blanket"},
    "balanced": set(),
    "layered": set(),
}


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

    # Density: treat density-dropped slots as "already owned" so they get
    # $0 budget and are excluded from sourcing.  Density only controls
    # ambient items (plants, curtains, throw) — survey-gated items are
    # controlled by preferences (full-room) or the wants picker (partial).
    density = getattr(room_request, "density", "balanced")
    density_drops = set(_DENSITY_DROP.get(density, set()))

    already_have = set(room_request.already_have) | density_drops

    # Bedding: comforter and duvet are mutually exclusive.
    # - If user chose duvet (comforter excluded but duvet slots NOT excluded),
    #   promote duvet_insert + duvet_cover to must_have so they get real budget.
    # - If comforter is NOT excluded, promote it so the bed isn't bare.
    # - On partial-room paths where comforter is in already_have because the
    #   user simply didn't want it (and also didn't want duvet), do NOT
    #   auto-promote duvet slots — they'll also be in already_have.
    must_have = set(room_request.must_have)
    if room_preset == "bedroom":
        if "comforter" in already_have:
            # Only promote duvet if the duvet slots are NOT also excluded.
            # If they're excluded too, user wants neither (partial-room path).
            if "duvet_insert" not in already_have and "duvet_cover" not in already_have:
                must_have.add("duvet_insert")
                must_have.add("duvet_cover")
        else:
            must_have.add("comforter")

    return fit_slots_to_budget(
        weights, target_budget, room_preset, taxonomy, budget_policies,
        run_id=run_id,
        already_have=already_have,
        must_have=must_have,
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

    preset = taxonomy.room_presets[room_preset]
    required_ids = preset.required_items()
    all_ids = preset.all_items()

    # Build a human-readable item catalogue from the grouped structure.
    slot_lines = []
    for group_name, group_def in preset.groups.items():
        for item_id, gi in group_def.items.items():
            effective_weight = group_def.budget_weight * gi.sub_weight
            slot_lines.append(
                f"- id: {item_id}  group: {group_name}  "
                f"weight: {effective_weight:.3f}  "
                f"required_specs: {list(taxonomy.item_by_id(item_id).required_specs)}"
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

    valid_ids = taxonomy.item_ids()
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
    """Return the flattened default weights for every item in the preset."""
    preset = taxonomy.room_presets[room_preset]
    return preset.flatten_weights()

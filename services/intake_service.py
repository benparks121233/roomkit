# services/intake_service.py
# Owns: parsing raw user input into a validated RoomRequest.
#
# Rules (from AGENTS.md / build packet):
#   - Missing or ambiguous fields → None, never guessed.
#   - room_type must be a key in slot_taxonomy.yaml room_presets.
#     If the caller supplies a room_type that is not in the taxonomy,
#     raise ValueError — do not silently null it.
#   - budget must be > 0 if supplied; raise ValueError otherwise.
#   - No LLM calls here.  Style interpretation is Stage 4 (style_service).
#   - Every call gets a fresh run_id (UUID4).

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from schemas.room_request import RoomRequest
from services.config_loader import load_room_taxonomy


def parse_intake(raw_input: dict) -> RoomRequest:
    """Parse raw user input into a validated RoomRequest.

    Args:
        raw_input: dict with any subset of the following keys:
            room_type (str)         — must match a taxonomy preset if present
            dimensions (str)        — e.g. "12x14"
            photo_url (str)         — storage URL / path
            budget (float | int)    — must be > 0 if present
            bed_size (str)          — e.g. "queen"
            style_description (str) — free-form style cue
            qa_answers (dict)       — structured Q&A answers

    Returns:
        RoomRequest with a fresh run_id and created_at; missing fields are None.

    Raises:
        ValueError: if budget is present and ≤ 0.
        ValueError: if room_type is present and not in the taxonomy presets.
    """
    taxonomy = load_room_taxonomy()

    # --- Validate room_type -------------------------------------------
    # Missing → None (we can log a partial request and still proceed).
    # Present but unknown → hard rejection; we don't guess an alternative.
    room_type = raw_input.get("room_type") or None
    if room_type is not None:
        valid_presets = set(taxonomy.room_presets.keys())
        if room_type not in valid_presets:
            raise ValueError(
                f"Unknown room_type '{room_type}'. "
                f"Valid values: {sorted(valid_presets)}"
            )

    # --- Validate budget -----------------------------------------------
    # Missing → None (partial request; downstream stages will gate on this).
    # Present and ≤ 0 → hard rejection; a non-positive budget is nonsensical.
    raw_budget = raw_input.get("budget")
    if raw_budget is None:
        budget: float | None = None
    else:
        budget = float(raw_budget)
        if budget <= 0:
            raise ValueError(
                f"budget must be > 0, got {budget}"
            )

    # --- Pass-through optional fields (null if absent) -----------------
    dimensions: str | None = raw_input.get("dimensions") or None
    photo_url: str | None = raw_input.get("photo_url") or None
    bed_size: str | None = raw_input.get("bed_size") or None
    style_description: str | None = raw_input.get("style_description") or None
    qa_answers: dict[str, str] = dict(raw_input.get("qa_answers") or {})

    # --- Validate already_have / must_have -----------------------------
    # Both are optional lists of slot ids.  Every id must exist in the
    # taxonomy.  A slot id appearing in both lists is a contradiction.
    valid_slot_ids = taxonomy.slot_ids()
    already_have: list[str] = list(raw_input.get("already_have") or [])
    must_have: list[str] = list(raw_input.get("must_have") or [])

    for sid in already_have:
        if sid not in valid_slot_ids:
            raise ValueError(
                f"Unknown slot id '{sid}' in already_have. "
                f"Valid slot ids: {sorted(valid_slot_ids)}"
            )
    for sid in must_have:
        if sid not in valid_slot_ids:
            raise ValueError(
                f"Unknown slot id '{sid}' in must_have. "
                f"Valid slot ids: {sorted(valid_slot_ids)}"
            )

    overlap = set(already_have) & set(must_have)
    if overlap:
        raise ValueError(
            f"Slot ids appear in both already_have and must_have: "
            f"{sorted(overlap)}. A slot cannot be both owned and requested."
        )

    return RoomRequest(
        run_id=str(uuid.uuid4()),
        room_type=room_type,
        dimensions=dimensions,
        photo_url=photo_url,
        budget=budget,
        bed_size=bed_size,
        style_description=style_description,
        qa_answers=qa_answers,
        already_have=already_have,
        must_have=must_have,
        created_at=datetime.now(tz=timezone.utc),
    )

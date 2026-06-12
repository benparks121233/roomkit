# schemas/room_request.py
# Owns: the validated intake output — the contract between intake_service
# and everything downstream in the pipeline.
#
# Design rules:
#   - Missing fields are None, never guessed. parse_intake() enforces this.
#   - No business validation lives here (budget > 0, room_type membership).
#     That belongs in services/intake_service.py so errors are explicit and testable.
#   - Downstream services read room_type and budget from this object;
#     they must not re-validate or re-parse raw input.

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RoomRequest(BaseModel):
    # Identity — assigned by intake_service, unique per call.
    run_id: str

    # Room — None if the user did not supply or the value was unrecognisable.
    # room_type is validated against taxonomy presets in intake_service; if
    # supplied and unknown it is rejected before this object is created.
    room_type: Optional[str] = None

    # Spatial input — exactly one of these is expected, but neither is required
    # by the schema so a partial intake can still be logged.
    dimensions: Optional[str] = None       # e.g. "12x14", "10 x 12 ft"
    photo_url: Optional[str] = None        # storage URL / path of uploaded photo

    # Budget — None if not supplied.  Values ≤ 0 are rejected by intake_service
    # before this object is created, so any non-None value here is positive.
    budget: Optional[float] = None

    # Spec hints surfaced by Q&A — None if not mentioned.
    bed_size: Optional[str] = None         # e.g. "queen", "king" (bedroom only)

    # Style — free-form text from Q&A; interpreted by style_service in Stage 4.
    style_description: Optional[str] = None

    # Direct core aesthetic from the quiz (e.g. "quiet_luxury", "dark_academia").
    # When set, style_service uses this as the deterministic style_name instead
    # of letting the LLM reinterpret from style_description.
    core_aesthetic: Optional[str] = None

    # Structured Q&A answers keyed by question id.  Empty dict if no Q&A.
    qa_answers: dict[str, str] = {}

    # Density preference — controls how many optional slots are included.
    # "minimal" drops extra decor, "balanced" is default, "layered" keeps all.
    density: str = "balanced"

    # User interest categories (e.g. "music", "sports", "travel").
    # Used to personalize decor slot selection prompts.
    interests: list[str] = []

    # Slot ids the user already owns — composition will mark these as present
    # but not source them.  Validated against the taxonomy in intake_service.
    already_have: list[str] = []

    # Slot ids the user explicitly wants included, even if normally optional
    # for the room preset.  Validated against the taxonomy in intake_service.
    must_have: list[str] = []

    # Timestamp set by intake_service at parse time (UTC).
    created_at: datetime

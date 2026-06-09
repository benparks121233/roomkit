# schemas/style_profile.py
# Owns: the LLM style interpretation output — the contract between
# style_service and composition_service (and anything else that needs the style).
#
# Design rules:
#   - LLM output is always validated against this schema before leaving
#     style_service; free prose never reaches downstream services.
#   - style_name membership against the catalogue is NOT validated here;
#     the schema does not know the YAML.  style_service enforces that.
#   - confidence is clamped to [0.0, 1.0] — LLM outputs are not always
#     perfectly ranged and we prefer clamping to raising.
#   - fallback=True signals that the LLM could not make a confident match
#     and the profile was chosen as the best-available default.

from __future__ import annotations

from pydantic import BaseModel, field_validator


class StyleProfile(BaseModel):
    # Profile id — must be a key from context/style_profiles.yaml.
    # Validated against the catalogue by style_service, not here.
    style_name: str

    # Style cues forwarded to composition_service and select_products.md.
    keywords: list[str]
    color_palette: list[str]

    # One-phrase mood description (e.g. "calm, grounded, uncluttered").
    mood: str

    # How well the user's input matched this profile (0.0 = no signal,
    # 1.0 = perfect match).  Values from the LLM are clamped, not rejected.
    confidence: float

    # True when confidence < LOW_CONFIDENCE_THRESHOLD or when the LLM
    # response was unparseable / named an unknown profile.  Downstream
    # services may use this to surface a "we picked a default" notice.
    fallback: bool

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        """Clamp to [0.0, 1.0] — never raise on out-of-range LLM output."""
        return max(0.0, min(1.0, float(v)))

# schemas/style_profile.py
# Owns: LLM style interpretation output — named style + keywords + mood cues.
# Schema-constrained; LLM never returns free prose. Stage 4: add fields.

from pydantic import BaseModel


class StyleProfile(BaseModel):
    # Stage 4: style_name, keywords, color_palette, mood, confidence
    pass

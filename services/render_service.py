# services/render_service.py
# Owns: generating the styled room image from the slot plan + style profile.
# Presentation layer only — the render is NEVER a source of product or price truth.
# Backend is swappable (Anthropic, OpenAI, Stability). Runs in the async worker.
# Stage 9: implement.


def render_room(style_profile, slot_plan, run_id: str) -> str:
    # Returns a URL or storage path for the generated room image.
    # Render failures should not block the board from being assembled.
    raise NotImplementedError("Stage 9")

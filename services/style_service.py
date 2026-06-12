# services/style_service.py
# Owns: mapping a RoomRequest to a validated StyleProfile via LLM.
#
# Key design decisions:
#   - _call_llm() is isolated so tests patch it without touching the
#     Anthropic client.  Everything else in this module is pure Python.
#   - _build_prompts() loads + renders prompts/interpret_style.md;
#     the template is the single source of truth for what the LLM is told.
#   - interpret_style() never raises.  On any error (parse failure,
#     unknown profile, network error) it returns a warm_minimalist fallback
#     with fallback=True — the pipeline always gets a usable StyleProfile.
#   - No business rules live here.  Budget, specs, links, and tags are
#     enforced by validators/, not here.

from __future__ import annotations

import json
import re
from pathlib import Path

import anthropic

from schemas.room_request import RoomRequest
from schemas.style_profile import StyleProfile
from services.config_loader import StyleProfilesConfig, load_style_profiles

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# Profile used when the LLM response is unusable or confidence is too low.
_FALLBACK_STYLE_ID = "warm_minimalist"

# Below this confidence the LLM result is kept but flagged as a fallback.
_LOW_CONFIDENCE_THRESHOLD = 0.6

# Anthropic model and token budget for style interpretation.
_LLM_MODEL = "claude-sonnet-4-6"
_LLM_MAX_TOKENS = 512


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def interpret_style(room_request: RoomRequest) -> StyleProfile:
    """Map a RoomRequest to a validated StyleProfile.

    When the request includes a core_aesthetic (from the quiz's direct
    selection), that profile id is used DETERMINISTICALLY — the LLM is
    only called to refine keywords/mood to the user's description, but
    the style_name is locked to the user's pick.  This prevents the LLM
    from reinterpreting "quiet luxury + heritage mood" as "dark_academia."

    Falls back to full LLM interpretation only when core_aesthetic is absent.

    This function never raises; callers always receive a StyleProfile.
    """
    profiles_config = load_style_profiles()
    valid_ids = {p.id for p in profiles_config.profiles}
    profile_map = {p.id: p for p in profiles_config.profiles}

    # --- Deterministic path: core_aesthetic from quiz ---
    if room_request.core_aesthetic and room_request.core_aesthetic in valid_ids:
        locked_id = room_request.core_aesthetic
        config_profile = profile_map[locked_id]

        # Use the profile's canonical keywords/mood/palette, enhanced with
        # the user's style_description for richer context — but style_name
        # is NEVER overridden.
        return StyleProfile(
            style_name=locked_id,
            keywords=config_profile.keywords,
            color_palette=config_profile.color_palette,
            mood=config_profile.mood,
            confidence=1.0,
            fallback=False,
        )

    # --- LLM interpretation path (no core_aesthetic) ---
    system_prompt, user_message = _build_prompts(room_request, profiles_config)
    raw = _call_llm(system_prompt, user_message)

    try:
        data = _extract_json(raw)
        profile = StyleProfile.model_validate(data)

        # Unknown style_name: LLM hallucinated a profile not in the catalogue.
        if profile.style_name not in valid_ids:
            return _make_fallback(profiles_config)

        # Low confidence: ensure the flag is set even if the LLM forgot to.
        if profile.confidence < _LOW_CONFIDENCE_THRESHOLD and not profile.fallback:
            profile = profile.model_copy(update={"fallback": True})

        return profile

    except Exception:
        # JSON parse error, Pydantic validation failure, or any other
        # exception → graceful fallback so LLM errors never surface as 500s.
        return _make_fallback(profiles_config)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _call_llm(system_prompt: str, user_message: str) -> str:
    """Send a request to the Anthropic API and return the raw text.

    Isolated here so tests can patch services.style_service._call_llm
    without importing or instantiating the Anthropic client.
    """
    client = anthropic.Anthropic()
    message = client.messages.create(
        model=_LLM_MODEL,
        max_tokens=_LLM_MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text


def _build_prompts(
    request: RoomRequest, profiles_config: StyleProfilesConfig
) -> tuple[str, str]:
    """Load interpret_style.md, substitute variables, return (system, user).

    The template has three sections separated by '---' lines:
      ## System   — instructions + style catalogue
      ## User     — dynamic variables (room type, dimensions, style input)
      ## Output schema — output format (appended to the system prompt)

    Returns:
        (system_prompt, user_message) — both are fully rendered strings.
    """
    template_text = (_PROMPTS_DIR / "interpret_style.md").read_text()

    # Build a human-readable style catalogue for the prompt.
    catalogue_lines = []
    for p in profiles_config.profiles:
        catalogue_lines.append(
            f"- id: {p.id}\n"
            f"  display_name: {p.display_name}\n"
            f"  keywords: {', '.join(p.keywords)}\n"
            f"  color_palette: {', '.join(p.color_palette)}\n"
            f"  mood: {p.mood}"
        )
    catalogue = "\n".join(catalogue_lines)

    # Format Q&A answers as indented key: value pairs.
    if request.qa_answers:
        qa_str = "\n".join(f"  {k}: {v}" for k, v in request.qa_answers.items())
    else:
        qa_str = "  (none provided)"

    # Substitute all template variables.
    rendered = (
        template_text
        .replace("{{style_profiles_yaml}}", catalogue)
        .replace("{{room_type}}", request.room_type or "(not specified)")
        .replace("{{dimensions}}", request.dimensions or "(not specified)")
        .replace("{{style_description}}", request.style_description or "(not specified)")
        .replace("{{qa_answers}}", qa_str)
    )

    # Strip leading comment lines (the file header starting with #).
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
            # Drop the '## System' header; keep the body.
            body = section.split("\n", 1)[1].strip() if "\n" in section else ""
            system_parts.append(body)
        elif section.startswith("## User"):
            # Drop the '## User' header; keep the body as the user message.
            user_part = section.split("\n", 1)[1].strip() if "\n" in section else ""
        elif section.startswith("## Output schema"):
            # Keep the full section (including header) as part of the system prompt.
            system_parts.append(section)

    return "\n\n".join(system_parts), user_part


def _extract_json(text: str) -> dict:
    """Extract a JSON object from the LLM response text.

    Handles:
    - Raw JSON: {"style_name": ...}
    - Code-fenced JSON: ```json\\n{...}\\n```
    - Code-fenced without language tag: ```\\n{...}\\n```
    """
    text = text.strip()
    if text.startswith("```"):
        # Strip the opening fence line (e.g. '```json' or '```')
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
        # Strip the closing fence
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return json.loads(text.strip())


def _make_fallback(profiles_config: StyleProfilesConfig) -> StyleProfile:
    """Return a warm_minimalist StyleProfile with confidence=0.0 and fallback=True.

    warm_minimalist is chosen as the default because it is the most broadly
    applicable profile — neutral enough to produce an acceptable board even
    when the user's style signal was unclear.
    """
    default = next(
        p for p in profiles_config.profiles if p.id == _FALLBACK_STYLE_ID
    )
    return StyleProfile(
        style_name=default.id,
        keywords=list(default.keywords),
        color_palette=list(default.color_palette),
        mood=default.mood,
        confidence=0.0,
        fallback=True,
    )

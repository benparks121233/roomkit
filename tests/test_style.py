# tests/test_style.py
# Tests for services/style_service.py (Stage 4).
#
# Per AGENTS.md: no live LLM calls in tests.
# All tests patch services.style_service._call_llm with pre-built JSON strings.
#
# Coverage:
#   - Clean high-confidence match → correct StyleProfile, fallback=False.
#   - Low-confidence response → fallback=True regardless of what LLM set.
#   - Malformed JSON → graceful warm_minimalist fallback, fallback=True.
#   - Unknown style_name (hallucinated profile) → warm_minimalist fallback.
#   - LLM wraps response in ```json fence → still parsed correctly.
#   - confidence clamped when LLM returns a value > 1.0.
#   - Result is always a valid StyleProfile instance (schema enforced).
#   - All five named profiles are individually accepted when returned by LLM.

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from schemas.room_request import RoomRequest
from schemas.style_profile import StyleProfile
from services.style_service import interpret_style

# ---------------------------------------------------------------------------
# Test fixture helpers
# ---------------------------------------------------------------------------

def _make_request(
    room_type: str = "bedroom",
    style_description: str | None = "cozy and warm",
    qa_answers: dict | None = None,
) -> RoomRequest:
    """Build a minimal RoomRequest for use in style tests."""
    return RoomRequest(
        run_id="test-run-001",
        room_type=room_type,
        budget=1000.0,
        style_description=style_description,
        qa_answers=qa_answers or {},
        created_at=datetime.now(tz=timezone.utc),
    )


def _llm_json(
    style_name: str = "warm_minimalist",
    keywords: list[str] | None = None,
    color_palette: list[str] | None = None,
    mood: str = "calm, grounded",
    confidence: float = 0.9,
    fallback: bool = False,
) -> str:
    """Return a JSON string that simulates a valid LLM response."""
    return json.dumps({
        "style_name": style_name,
        "keywords": keywords or ["natural wood", "linen"],
        "color_palette": color_palette or ["cream", "warm white"],
        "mood": mood,
        "confidence": confidence,
        "fallback": fallback,
    })


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

def test_clean_high_confidence_match_returns_correct_profile():
    with patch("services.style_service._call_llm", return_value=_llm_json(
        style_name="warm_minimalist",
        confidence=0.92,
        fallback=False,
    )):
        result = interpret_style(_make_request(style_description="light wood and linen"))

    assert isinstance(result, StyleProfile)
    assert result.style_name == "warm_minimalist"
    assert result.confidence == 0.92
    assert result.fallback is False


def test_result_carries_llm_keywords_and_palette():
    with patch("services.style_service._call_llm", return_value=_llm_json(
        style_name="city_modern",
        keywords=["sleek", "glass", "monochrome"],
        color_palette=["black", "white", "cool grey"],
        mood="sharp, metropolitan",
        confidence=0.85,
    )):
        result = interpret_style(_make_request())

    assert result.style_name == "city_modern"
    assert "sleek" in result.keywords
    assert "black" in result.color_palette
    assert result.mood == "sharp, metropolitan"


def test_living_room_request_accepted():
    with patch("services.style_service._call_llm", return_value=_llm_json(
        style_name="coastal",
        confidence=0.88,
    )):
        result = interpret_style(_make_request(room_type="living_room"))

    assert result.style_name == "coastal"
    assert result.fallback is False


def test_qa_answers_do_not_break_prompt_rendering():
    """Verify Q&A answers flow through without errors (prompt rendering)."""
    with patch("services.style_service._call_llm", return_value=_llm_json(
        style_name="dark_academia",
        confidence=0.78,
    )):
        result = interpret_style(_make_request(
            qa_answers={"vibe": "rich and layered", "priority": "textiles"},
        ))

    assert result.style_name == "dark_academia"


# ---------------------------------------------------------------------------
# Fallback / low-confidence tests
# ---------------------------------------------------------------------------

def test_low_confidence_sets_fallback_flag():
    """LLM returns confidence < 0.6 → fallback=True even if LLM said False."""
    with patch("services.style_service._call_llm", return_value=_llm_json(
        style_name="industrial",
        confidence=0.42,
        fallback=False,  # LLM forgot; service must enforce
    )):
        result = interpret_style(_make_request())

    assert result.fallback is True
    assert result.confidence == pytest.approx(0.42)
    assert result.style_name == "industrial"  # kept; only flag is forced


def test_low_confidence_already_flagged_by_llm_is_preserved():
    """LLM sets both low confidence and fallback=True → accepted as-is."""
    with patch("services.style_service._call_llm", return_value=_llm_json(
        style_name="warm_minimalist",
        confidence=0.35,
        fallback=True,
    )):
        result = interpret_style(_make_request())

    assert result.fallback is True
    assert result.confidence == pytest.approx(0.35)


def test_malformed_json_returns_warm_minimalist_fallback():
    """LLM returns prose / invalid JSON → warm_minimalist fallback, fallback=True."""
    with patch("services.style_service._call_llm", return_value="Sorry, I cannot help."):
        result = interpret_style(_make_request())

    assert isinstance(result, StyleProfile)
    assert result.style_name == "warm_minimalist"
    assert result.fallback is True
    assert result.confidence == 0.0


def test_unknown_style_name_returns_warm_minimalist_fallback():
    """LLM hallucinates a profile not in the catalogue → warm_minimalist fallback."""
    with patch("services.style_service._call_llm", return_value=_llm_json(
        style_name="gothic_dungeon",  # not in style_profiles.yaml
        confidence=0.95,
        fallback=False,
    )):
        result = interpret_style(_make_request())

    assert result.style_name == "warm_minimalist"
    assert result.fallback is True


def test_empty_json_object_returns_fallback():
    with patch("services.style_service._call_llm", return_value="{}"):
        result = interpret_style(_make_request())

    assert result.fallback is True
    assert result.style_name == "warm_minimalist"


# ---------------------------------------------------------------------------
# Schema / validation tests
# ---------------------------------------------------------------------------

def test_result_is_always_a_style_profile_instance():
    with patch("services.style_service._call_llm", return_value=_llm_json()):
        result = interpret_style(_make_request())

    assert isinstance(result, StyleProfile)
    assert isinstance(result.keywords, list)
    assert isinstance(result.color_palette, list)
    assert isinstance(result.mood, str)
    assert isinstance(result.fallback, bool)


def test_confidence_clamped_above_one():
    """LLM returns confidence > 1.0 → clamped to 1.0 by validator."""
    with patch("services.style_service._call_llm", return_value=_llm_json(
        confidence=1.8,
    )):
        result = interpret_style(_make_request())

    assert result.confidence == pytest.approx(1.0)


def test_confidence_clamped_below_zero():
    """LLM returns confidence < 0.0 → clamped to 0.0 by validator."""
    with patch("services.style_service._call_llm", return_value=_llm_json(
        style_name="warm_minimalist",
        confidence=-0.5,
        fallback=True,
    )):
        result = interpret_style(_make_request())

    assert result.confidence == pytest.approx(0.0)


def test_json_in_code_fence_is_parsed_correctly():
    """LLM wraps JSON in ```json ... ``` fence → still produces a valid profile."""
    fenced = "```json\n" + _llm_json(style_name="coastal", confidence=0.80) + "\n```"
    with patch("services.style_service._call_llm", return_value=fenced):
        result = interpret_style(_make_request(room_type="living_room"))

    assert result.style_name == "coastal"
    assert result.fallback is False


# ---------------------------------------------------------------------------
# All catalogue profiles are accepted
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("profile_id", [
    "cottagecore",
    "dark_academia",
    "japandi",
    "coastal",
    "industrial",
    "quiet_luxury",
    "sports_den",
    "city_modern",
    "ski_lodge",
    "warm_minimalist",
])
def test_all_catalogue_profiles_accepted(profile_id: str):
    with patch("services.style_service._call_llm", return_value=_llm_json(
        style_name=profile_id,
        confidence=0.80,
        fallback=False,
    )):
        result = interpret_style(_make_request())

    assert result.style_name == profile_id
    assert result.fallback is False

# tests/test_intake.py
# Tests for services/intake_service.py (Stage 3).
#
# Coverage:
#   - Valid full input produces a well-formed RoomRequest.
#   - Valid minimal input (only required-to-be-meaningful fields).
#   - Missing optional fields are None, never guessed.
#   - Missing room_type → None (not rejected).
#   - Unknown room_type → ValueError.
#   - budget = 0 → ValueError.
#   - budget < 0 → ValueError.
#   - budget missing → None (partial request allowed).
#   - Each call produces a unique run_id.
#   - created_at is a UTC datetime.

import pytest

from schemas.room_request import RoomRequest
from services.intake_service import parse_intake

# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

def test_valid_full_input_returns_room_request():
    result = parse_intake({
        "room_type": "bedroom",
        "dimensions": "12x14",
        "budget": 1500.0,
        "bed_size": "queen",
        "style_description": "warm and minimal",
        "qa_answers": {"vibe": "cozy", "priority": "comfort"},
    })
    assert isinstance(result, RoomRequest)
    assert result.room_type == "bedroom"
    assert result.dimensions == "12x14"
    assert result.budget == 1500.0
    assert result.bed_size == "queen"
    assert result.style_description == "warm and minimal"
    assert result.qa_answers == {"vibe": "cozy", "priority": "comfort"}


def test_living_room_preset_accepted():
    result = parse_intake({"room_type": "living_room", "budget": 2000.0})
    assert result.room_type == "living_room"


def test_run_id_is_a_non_empty_string():
    result = parse_intake({"room_type": "bedroom", "budget": 800.0})
    assert isinstance(result.run_id, str)
    assert len(result.run_id) > 0


def test_each_call_produces_a_unique_run_id():
    r1 = parse_intake({"budget": 500.0})
    r2 = parse_intake({"budget": 500.0})
    assert r1.run_id != r2.run_id


def test_created_at_is_utc_datetime():
    from datetime import datetime, timezone
    result = parse_intake({"budget": 1000.0})
    assert isinstance(result.created_at, datetime)
    assert result.created_at.tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# Null / missing-field tests — missing fields must be None, never guessed
# ---------------------------------------------------------------------------

def test_missing_optional_fields_are_none():
    """Supplying only room_type + budget leaves all other fields None."""
    result = parse_intake({"room_type": "bedroom", "budget": 800.0})
    assert result.dimensions is None
    assert result.photo_url is None
    assert result.bed_size is None
    assert result.style_description is None
    assert result.qa_answers == {}


def test_missing_room_type_is_none_not_guessed():
    """Omitting room_type is allowed — partial request."""
    result = parse_intake({"budget": 800.0})
    assert result.room_type is None


def test_missing_budget_is_none():
    """Omitting budget is allowed — partial request."""
    result = parse_intake({"room_type": "bedroom"})
    assert result.budget is None


def test_empty_string_fields_coerced_to_none():
    """Empty strings for optional fields must be stored as None, not ''."""
    result = parse_intake({
        "room_type": "bedroom",
        "budget": 500.0,
        "dimensions": "",
        "bed_size": "",
        "style_description": "",
    })
    assert result.dimensions is None
    assert result.bed_size is None
    assert result.style_description is None


# ---------------------------------------------------------------------------
# Rejection tests — invalid values must raise ValueError
# ---------------------------------------------------------------------------

def test_budget_zero_raises_value_error():
    with pytest.raises(ValueError, match="budget"):
        parse_intake({"room_type": "bedroom", "budget": 0})


def test_budget_negative_raises_value_error():
    with pytest.raises(ValueError, match="budget"):
        parse_intake({"room_type": "bedroom", "budget": -50.0})


def test_unknown_room_type_raises_value_error():
    with pytest.raises(ValueError, match="room_type"):
        parse_intake({"room_type": "kitchen", "budget": 800.0})


def test_unknown_room_type_partial_match_raises():
    """'bed' is not a valid preset even though 'bedroom' is."""
    with pytest.raises(ValueError, match="room_type"):
        parse_intake({"room_type": "bed", "budget": 800.0})


# ---------------------------------------------------------------------------
# already_have / must_have tests
# ---------------------------------------------------------------------------

def test_already_have_parsed_correctly():
    result = parse_intake({
        "room_type": "bedroom",
        "budget": 1500.0,
        "already_have": ["bed_frame", "rug"],
    })
    assert result.already_have == ["bed_frame", "rug"]


def test_must_have_parsed_correctly():
    result = parse_intake({
        "room_type": "bedroom",
        "budget": 1500.0,
        "must_have": ["tv"],
    })
    assert result.must_have == ["tv"]


def test_both_have_and_need_parsed():
    result = parse_intake({
        "room_type": "bedroom",
        "budget": 1500.0,
        "already_have": ["bed_frame"],
        "must_have": ["tv"],
    })
    assert result.already_have == ["bed_frame"]
    assert result.must_have == ["tv"]


def test_already_have_defaults_to_empty_list():
    result = parse_intake({"room_type": "bedroom", "budget": 800.0})
    assert result.already_have == []


def test_must_have_defaults_to_empty_list():
    result = parse_intake({"room_type": "bedroom", "budget": 800.0})
    assert result.must_have == []


def test_unknown_slot_id_in_already_have_raises():
    with pytest.raises(ValueError, match="already_have"):
        parse_intake({
            "room_type": "bedroom",
            "budget": 1000.0,
            "already_have": ["magic_chair"],
        })


def test_unknown_slot_id_in_must_have_raises():
    with pytest.raises(ValueError, match="must_have"):
        parse_intake({
            "room_type": "bedroom",
            "budget": 1000.0,
            "must_have": ["magic_chair"],
        })


def test_same_id_in_both_lists_raises():
    with pytest.raises(ValueError, match="both"):
        parse_intake({
            "room_type": "bedroom",
            "budget": 1000.0,
            "already_have": ["bed_frame"],
            "must_have": ["bed_frame"],
        })

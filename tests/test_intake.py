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
#   - full_room / wants → already_have / must_have translation.

import pytest

from schemas.room_request import RoomRequest
from services.intake_service import parse_intake
from services.config_loader import load_room_taxonomy

TAXONOMY = load_room_taxonomy()
BEDROOM_ALL_SLOTS = TAXONOMY.room_presets["bedroom"].all_items()

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
# full_room / wants → already_have / must_have translation
# ---------------------------------------------------------------------------

def test_full_room_true_sources_all_slots():
    """full_room=True (default) → already_have=[], must_have=[]."""
    result = parse_intake({
        "room_type": "bedroom",
        "budget": 1500.0,
        "full_room": True,
    })
    assert result.already_have == []
    assert result.must_have == []


def test_full_room_defaults_to_true():
    """Omitting full_room defaults to True → source everything."""
    result = parse_intake({
        "room_type": "bedroom",
        "budget": 1500.0,
    })
    assert result.already_have == []
    assert result.must_have == []


def test_full_room_false_with_wants():
    """full_room=False with wants → already_have = all - wants, must_have = wants."""
    result = parse_intake({
        "room_type": "bedroom",
        "budget": 1500.0,
        "full_room": False,
        "wants": ["nightstand", "rug"],
    })
    # Wanted slots are in must_have
    assert set(result.must_have) == {"nightstand", "rug"}
    # Everything else is in already_have
    assert set(result.already_have) == BEDROOM_ALL_SLOTS - {"nightstand", "rug"}
    # No overlap
    assert set(result.already_have) & set(result.must_have) == set()


def test_full_room_false_empty_wants():
    """full_room=False with empty wants → all slots owned, nothing sourced."""
    result = parse_intake({
        "room_type": "bedroom",
        "budget": 1500.0,
        "full_room": False,
        "wants": [],
    })
    assert set(result.already_have) == BEDROOM_ALL_SLOTS
    assert result.must_have == []


def test_unknown_slot_in_wants_raises():
    """Invalid slot id in wants raises ValueError."""
    with pytest.raises(ValueError, match="wants"):
        parse_intake({
            "room_type": "bedroom",
            "budget": 1000.0,
            "full_room": False,
            "wants": ["magic_chair"],
        })


def test_wants_ignored_when_full_room_true():
    """When full_room=True, wants list is ignored."""
    result = parse_intake({
        "room_type": "bedroom",
        "budget": 1500.0,
        "full_room": True,
        "wants": ["nightstand"],
    })
    assert result.already_have == []
    assert result.must_have == []


# ---------------------------------------------------------------------------
# bed_size survives full_room/wants translation
# ---------------------------------------------------------------------------

def test_bed_size_survives_full_room_true():
    """bed_size must not be dropped by the full_room/wants path."""
    result = parse_intake({
        "room_type": "bedroom",
        "budget": 1500.0,
        "bed_size": "queen",
        "full_room": True,
    })
    assert result.bed_size == "queen"


def test_bed_size_survives_full_room_false():
    """bed_size must not be dropped when full_room=False with wants."""
    result = parse_intake({
        "room_type": "bedroom",
        "budget": 1500.0,
        "bed_size": "king",
        "full_room": False,
        "wants": ["bed_frame", "mattress"],
    })
    assert result.bed_size == "king"

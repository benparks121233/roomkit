# tests/test_api.py
# Integration tests for the /design API endpoints.
# All LLM calls are mocked — no live API calls.

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.routes import _designs
from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Mocked LLM responses
# ---------------------------------------------------------------------------

MOCK_STYLE_RESPONSE = json.dumps({
    "style_name": "warm_minimalist",
    "keywords": ["natural wood", "linen", "warm tones"],
    "color_palette": ["#FAF3E0", "#D4C5A9"],
    "mood": "calm, grounded",
    "confidence": 0.90,
    "fallback": False,
})

MOCK_COMPOSITION_RESPONSE = json.dumps({
    "slot_weights": {
        "bed_frame": 0.18,
        "mattress": 0.14,
        "sheets": 0.032,
        "comforter": 0.032,
        "pillows": 0.016,
        "nightstand": 0.075,
        "dresser": 0.075,
        "ceiling_light": 0.048,
        "table_lamp": 0.042,
        "floor_lamp": 0.030,
        "wall_art": 0.040,
        "plants": 0.030,
        "mirror": 0.030,
        "rug": 0.104,
        "curtains": 0.069,
        "throw_blanket": 0.058,
    },
    "rationale": "Mock composition for tests.",
})


def _mock_selection_llm(_system: str, user_message: str) -> str:
    """Parse the candidates JSON from the prompt and pick the first one."""
    marker = "Candidates:\n"
    try:
        idx = user_message.index(marker)
        candidates_text = user_message[idx + len(marker):]
        candidates = json.loads(candidates_text.strip())
        if candidates:
            return json.dumps({
                "product_id": candidates[0]["product_id"],
                "fit_reason": "Best style match",
                "confidence": 0.88,
                "null_reason": None,
            })
    except (ValueError, json.JSONDecodeError, KeyError, IndexError):
        pass
    return json.dumps({
        "product_id": None,
        "fit_reason": "",
        "confidence": 0.0,
        "null_reason": "no_candidate",
    })


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_designs():
    """Clear in-memory design store between tests."""
    _designs.clear()
    yield
    _designs.clear()


# ---------------------------------------------------------------------------
# Shared patch decorator — all three LLM seams mocked
# ---------------------------------------------------------------------------

def _patch_llms(fn):
    """Decorator that patches all three LLM call points."""
    fn = patch(
        "services.selection_service._call_selection_llm",
        side_effect=_mock_selection_llm,
    )(fn)
    fn = patch(
        "services.composition_service._call_composition_llm",
        return_value=MOCK_COMPOSITION_RESPONSE,
    )(fn)
    fn = patch(
        "services.style_service._call_llm",
        return_value=MOCK_STYLE_RESPONSE,
    )(fn)
    return fn


# ---------------------------------------------------------------------------
# POST /design — happy path
# ---------------------------------------------------------------------------

class TestCreateDesign:

    @_patch_llms
    def test_returns_200_with_run_id(self, _s, _c, _sel):
        resp = client.post("/design", json={"room_type": "bedroom", "budget": 1500})
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data
        assert data["room_type"] == "bedroom"

    @_patch_llms
    def test_style_fields_present(self, _s, _c, _sel):
        resp = client.post("/design", json={"room_type": "bedroom", "budget": 1500})
        style = resp.json()["style"]
        assert style["style_name"] == "warm_minimalist"
        assert isinstance(style["keywords"], list)
        assert style["confidence"] > 0
        assert style["fallback"] is False

    @_patch_llms
    def test_budget_not_exceeded(self, _s, _c, _sel):
        resp = client.post("/design", json={"room_type": "bedroom", "budget": 1500})
        data = resp.json()
        assert data["target_budget"] == 1500.0
        assert data["total_spent"] <= data["target_budget"]

    @_patch_llms
    def test_total_spent_matches_slot_sum(self, _s, _c, _sel):
        resp = client.post("/design", json={"room_type": "bedroom", "budget": 1500})
        data = resp.json()
        slot_sum = sum(
            s["product"]["normalized_price"]
            for s in data["slots"]
            if s["product"] is not None
        )
        assert abs(data["total_spent"] - slot_sum) < 0.01

    @_patch_llms
    def test_slots_present(self, _s, _c, _sel):
        resp = client.post("/design", json={"room_type": "bedroom", "budget": 1500})
        slots = resp.json()["slots"]
        assert len(slots) > 0
        slot_ids = [s["slot_id"] for s in slots]
        # At minimum, required bedroom slots should be present.
        assert "bed_frame" in slot_ids
        assert "rug" in slot_ids

    @_patch_llms
    def test_every_slot_has_product_or_null_reason(self, _s, _c, _sel):
        resp = client.post("/design", json={"room_type": "bedroom", "budget": 1500})
        for slot in resp.json()["slots"]:
            if slot["product"] is None:
                assert slot["null_reason"] is not None, (
                    f"Slot {slot['slot_id']} has no product and no null_reason"
                )

    @_patch_llms
    def test_product_slots_have_affiliate_tag(self, _s, _c, _sel):
        resp = client.post("/design", json={"room_type": "bedroom", "budget": 1500})
        for slot in resp.json()["slots"]:
            if slot["product"] is not None:
                assert "tag=roomkitai-20" in slot["product"]["buy_url"], (
                    f"Slot {slot['slot_id']} missing affiliate tag"
                )

    @_patch_llms
    def test_product_slots_have_fit_reason(self, _s, _c, _sel):
        resp = client.post("/design", json={"room_type": "bedroom", "budget": 1500})
        for slot in resp.json()["slots"]:
            if slot["product"] is not None:
                assert slot["product"]["fit_reason"], (
                    f"Slot {slot['slot_id']} has empty fit_reason"
                )


# ---------------------------------------------------------------------------
# bed_size spec matching — bed-group slots require bed_size
# ---------------------------------------------------------------------------

class TestBedSizeSpecFlow:
    """Verify bed_size flows from DesignRequest → spec_hints → candidate
    filtering for every valid size.  Fixtures must have products for all
    four sizes or these tests will catch the gap."""

    BED_SLOT_IDS = {"bed_frame", "mattress", "sheets", "comforter"}

    @_patch_llms
    @pytest.mark.parametrize("size", ["twin", "full", "queen", "king"])
    def test_bed_slots_filled_for_every_size(self, _s, _c, _sel, size):
        resp = client.post("/design", json={
            "room_type": "bedroom",
            "budget": 1500,
            "bed_size": size,
        })
        data = resp.json()
        for slot in data["slots"]:
            if slot["slot_id"] in self.BED_SLOT_IDS:
                assert slot["product"] is not None, (
                    f"Slot {slot['slot_id']} has no product when bed_size='{size}'"
                )

    @_patch_llms
    def test_bed_size_with_full_room_true(self, _s, _c, _sel):
        """bed_size must survive the full_room=True path."""
        resp = client.post("/design", json={
            "room_type": "bedroom",
            "budget": 1500,
            "bed_size": "queen",
            "full_room": True,
        })
        data = resp.json()
        bed_slot = next(s for s in data["slots"] if s["slot_id"] == "bed_frame")
        assert bed_slot["product"] is not None, "bed_frame empty with full_room + bed_size"

    @_patch_llms
    def test_bed_size_with_partial_room_wants_bed(self, _s, _c, _sel):
        """bed_size must survive the full_room=False path for wanted bed slots."""
        resp = client.post("/design", json={
            "room_type": "bedroom",
            "budget": 1500,
            "bed_size": "queen",
            "full_room": False,
            "wants": ["bed_frame", "rug"],
        })
        data = resp.json()
        bed_slot = next(s for s in data["slots"] if s["slot_id"] == "bed_frame")
        assert bed_slot["product"] is not None, "bed_frame empty with wants + bed_size"
        assert bed_slot["owned"] is False


# ---------------------------------------------------------------------------
# Owned slots
# ---------------------------------------------------------------------------

class TestOwnedSlots:

    @_patch_llms
    def test_partial_room_owned_slot_has_null_reason(self, _s, _c, _sel):
        resp = client.post("/design", json={
            "room_type": "bedroom",
            "budget": 1500,
            "full_room": False,
            "wants": ["nightstand", "rug"],
        })
        data = resp.json()
        # bed_frame is NOT in wants → treated as owned
        bed_slot = next(s for s in data["slots"] if s["slot_id"] == "bed_frame")
        assert bed_slot["owned"] is True
        assert bed_slot["product"] is None
        assert bed_slot["null_reason"] == "owned"

    @_patch_llms
    def test_partial_room_owned_slot_gets_zero_budget(self, _s, _c, _sel):
        resp = client.post("/design", json={
            "room_type": "bedroom",
            "budget": 1500,
            "full_room": False,
            "wants": ["nightstand", "rug"],
        })
        data = resp.json()
        bed_slot = next(s for s in data["slots"] if s["slot_id"] == "bed_frame")
        assert bed_slot["allocated_budget"] == 0.0


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

class TestDesignErrors:

    @_patch_llms
    def test_invalid_room_type_returns_422(self, _s, _c, _sel):
        resp = client.post("/design", json={
            "room_type": "garage",
            "budget": 1500,
        })
        assert resp.status_code == 422

    @_patch_llms
    def test_tiny_budget_not_feasible(self, _s, _c, _sel):
        resp = client.post("/design", json={
            "room_type": "bedroom",
            "budget": 10.0,
        })
        data = resp.json()
        # With $10 total, the composition gate should flag infeasible.
        assert data["is_feasible"] is False


# ---------------------------------------------------------------------------
# GET /design/{run_id}
# ---------------------------------------------------------------------------

class TestGetDesign:

    @_patch_llms
    def test_get_retrieves_saved_design(self, _s, _c, _sel):
        post_resp = client.post("/design", json={
            "room_type": "bedroom",
            "budget": 1500,
        })
        run_id = post_resp.json()["run_id"]
        get_resp = client.get(f"/design/{run_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["run_id"] == run_id
        assert get_resp.json() == post_resp.json()

    def test_get_unknown_returns_404(self):
        resp = client.get("/design/nonexistent-id")
        assert resp.status_code == 404

"""Phase 6E: Tier enforcement tests.

Tests free-room limit (claim-at-save), pack ledger (decrement/re-credit),
room-type gating, watermark toggle, and TOCTOU concurrent safety.
"""

from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("TESTING", "1")

from fastapi.testclient import TestClient

from app.api.routes import _designs
from app.auth import get_current_user
from app.main import app

# ---------------------------------------------------------------------------
# Mocked LLM responses (same as test_api.py)
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
        "bed_frame": 0.18, "mattress": 0.14, "sheets": 0.032,
        "comforter": 0.032, "pillows": 0.016, "nightstand": 0.075,
        "dresser": 0.075, "ceiling_light": 0.048, "table_lamp": 0.042,
        "floor_lamp": 0.030, "wall_art": 0.040, "plants": 0.030,
        "mirror": 0.030, "rug": 0.104, "curtains": 0.069,
        "throw_blanket": 0.058,
    },
    "rationale": "Mock composition for tests.",
})


_MOCK_USAGE = {"input_tokens": 0, "output_tokens": 0}


def _mock_selection_llm(_system: str, user_message: str) -> tuple[str, dict]:
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
            }), _MOCK_USAGE
    except (ValueError, json.JSONDecodeError, KeyError, IndexError):
        pass
    return json.dumps({
        "product_id": None, "fit_reason": "", "confidence": 0.0,
        "null_reason": "no_candidate",
    }), _MOCK_USAGE


def _patch_llms(fn):
    fn = patch(
        "services.selection_service._call_selection_llm",
        side_effect=_mock_selection_llm,
    )(fn)
    fn = patch(
        "services.composition_service._call_composition_llm",
        return_value=(MOCK_COMPOSITION_RESPONSE, _MOCK_USAGE),
    )(fn)
    fn = patch(
        "services.style_service._call_llm",
        return_value=(MOCK_STYLE_RESPONSE, _MOCK_USAGE),
    )(fn)
    return fn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FREE_USER = {"user_id": "tier-free-001", "email": "free@test.com", "token": "tok"}
_PAID_USER = {"user_id": "tier-paid-001", "email": "paid@test.com", "token": "tok"}

_DESIGN_REQ = {"room_type": "bedroom", "budget": 2000, "style_description": "warm minimalist"}


def _mock_svc_client(
    *,
    pack_remaining: int | None = None,
    free_count: int = 0,
    claim_result: bool = True,
):
    """Build a mock Supabase service client for tier tests.

    pack_remaining: return value from decrement_pack RPC (None = no pack).
    free_count: count of existing free designs for count check.
    claim_result: return value from claim_and_save_free_design RPC.
    """
    mock = MagicMock()

    def _rpc(name, params):
        execute_result = MagicMock()
        if name == "decrement_pack":
            execute_result.data = pack_remaining
        elif name == "claim_and_save_free_design":
            execute_result.data = claim_result
        elif name == "re_credit_pack":
            execute_result.data = None
        rpc_callable = MagicMock()
        rpc_callable.execute.return_value = execute_result
        return rpc_callable

    mock.rpc.side_effect = _rpc

    # Count query chain: .table("designs").select(...).eq(...).eq(...).execute()
    count_resp = MagicMock()
    count_resp.count = free_count

    eq_chain = MagicMock()
    eq_chain.eq.return_value = eq_chain
    eq_chain.execute.return_value = count_resp

    select_mock = MagicMock()
    select_mock.eq.return_value = eq_chain

    table_mock = MagicMock()
    table_mock.select.return_value = select_mock

    # Also support .upsert() for paid-path save_design
    table_mock.upsert.return_value.execute.return_value = None

    # deleted_emails: always return empty (no cooldown) in tests
    deleted_emails_mock = MagicMock()
    deleted_emails_resp = MagicMock()
    deleted_emails_resp.data = []
    deleted_emails_chain = MagicMock()
    deleted_emails_chain.gte.return_value = deleted_emails_chain
    deleted_emails_chain.eq.return_value = deleted_emails_chain
    deleted_emails_chain.execute.return_value = deleted_emails_resp
    deleted_emails_mock.select.return_value = deleted_emails_chain

    _orig_table_rv = table_mock

    def _table(name):
        if name == "deleted_emails":
            return deleted_emails_mock
        return _orig_table_rv

    mock.table.side_effect = _table
    mock.table.return_value = _orig_table_rv

    return mock


@pytest.fixture(autouse=True)
def _clear():
    _designs.clear()
    prev = app.dependency_overrides.get(get_current_user)
    yield
    _designs.clear()
    if prev is not None:
        app.dependency_overrides[get_current_user] = prev
    else:
        app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Free tier tests
# ---------------------------------------------------------------------------

class TestFreeTier:

    @_patch_llms
    def test_free_user_bedroom_succeeds(self, _s, _c, _sel):
        """Free user creates a bedroom — 200, is_paid=False."""
        app.dependency_overrides[get_current_user] = lambda: _FREE_USER
        mock_client = _mock_svc_client(pack_remaining=None, free_count=0, claim_result=True)

        with patch("services.supabase_client.get_client", return_value=mock_client):
            client = TestClient(app)
            resp = client.post("/design", json=_DESIGN_REQ)

        assert resp.status_code == 200
        assert resp.json()["is_paid"] is False

    def test_free_user_living_room_rejected(self):
        """Free user tries living_room — 403."""
        app.dependency_overrides[get_current_user] = lambda: _FREE_USER
        mock_client = _mock_svc_client(pack_remaining=None, free_count=0)

        with patch("services.supabase_client.get_client", return_value=mock_client):
            client = TestClient(app)
            resp = client.post("/design", json={**_DESIGN_REQ, "room_type": "living_room"})

        assert resp.status_code == 403
        assert "bedroom only" in resp.json()["detail"]["message"].lower()

    def test_free_user_at_limit_rejected(self):
        """Free user already has 1 free design — 403."""
        app.dependency_overrides[get_current_user] = lambda: _FREE_USER
        mock_client = _mock_svc_client(pack_remaining=None, free_count=1)

        with patch("services.supabase_client.get_client", return_value=mock_client):
            client = TestClient(app)
            resp = client.post("/design", json=_DESIGN_REQ)

        assert resp.status_code == 403
        assert "1 room limit" in resp.json()["detail"]["message"].lower()

    @_patch_llms
    def test_free_limit_ignores_paid_designs(self, _s, _c, _sel):
        """Count check filters is_paid=False — paid designs don't consume free slot."""
        app.dependency_overrides[get_current_user] = lambda: _FREE_USER
        mock_client = _mock_svc_client(pack_remaining=None, free_count=0, claim_result=True)

        with patch("services.supabase_client.get_client", return_value=mock_client):
            client = TestClient(app)
            resp = client.post("/design", json=_DESIGN_REQ)

        assert resp.status_code == 200
        # Verify the .eq("is_paid", False) call was made in the count query chain
        table_call = mock_client.table
        table_call.assert_called_with("designs")
        select_call = table_call.return_value.select
        first_eq = select_call.return_value.eq
        first_eq.assert_called_with("user_id", _FREE_USER["user_id"])
        second_eq = first_eq.return_value.eq
        second_eq.assert_called_with("is_paid", False)


# ---------------------------------------------------------------------------
# Paid tier tests
# ---------------------------------------------------------------------------

class TestPaidTier:

    @_patch_llms
    def test_paid_user_any_room_type(self, _s, _c, _sel):
        """Paid user creates living_room — 200, is_paid=True, decrement called."""
        app.dependency_overrides[get_current_user] = lambda: _PAID_USER
        mock_client = _mock_svc_client(pack_remaining=4)

        with patch("services.supabase_client.get_client", return_value=mock_client):
            client = TestClient(app)
            resp = client.post("/design", json={**_DESIGN_REQ, "room_type": "living_room"})

        assert resp.status_code == 200
        assert resp.json()["is_paid"] is True

        # Verify decrement_pack was called
        rpc_calls = [c for c in mock_client.rpc.call_args_list if c[0][0] == "decrement_pack"]
        assert len(rpc_calls) == 1
        assert rpc_calls[0][0][1]["p_user_id"] == _PAID_USER["user_id"]

    @_patch_llms
    def test_paid_user_exhausted_falls_to_free(self, _s, _c, _sel):
        """Pack empty (decrement returns null) — falls to free path, bedroom OK."""
        app.dependency_overrides[get_current_user] = lambda: _PAID_USER
        mock_client = _mock_svc_client(pack_remaining=None, free_count=0, claim_result=True)

        with patch("services.supabase_client.get_client", return_value=mock_client):
            client = TestClient(app)
            resp = client.post("/design", json=_DESIGN_REQ)

        assert resp.status_code == 200
        assert resp.json()["is_paid"] is False

    @_patch_llms
    def test_paid_design_saved_with_is_paid_true(self, _s, _c, _sel):
        """Paid path sets is_paid=True on the saved design row."""
        app.dependency_overrides[get_current_user] = lambda: _PAID_USER
        mock_client = _mock_svc_client(pack_remaining=4)

        with patch("services.supabase_client.get_client", return_value=mock_client):
            client = TestClient(app)
            resp = client.post("/design", json=_DESIGN_REQ)

        assert resp.status_code == 200

        # Verify the upsert row has is_paid=True
        upsert_call = mock_client.table.return_value.upsert
        assert upsert_call.called
        row = upsert_call.call_args[0][0]
        assert row["is_paid"] is True


# ---------------------------------------------------------------------------
# Re-credit on pipeline failure
# ---------------------------------------------------------------------------

class TestReCredit:

    def test_pipeline_crash_re_credits_pack(self):
        """If pipeline raises after pack decrement, re_credit_pack is called."""
        app.dependency_overrides[get_current_user] = lambda: _PAID_USER
        mock_client = _mock_svc_client(pack_remaining=4)

        with patch("services.supabase_client.get_client", return_value=mock_client), \
             patch("services.style_service._call_llm", side_effect=RuntimeError("LLM down")):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post("/design", json=_DESIGN_REQ)

        assert resp.status_code == 500

        # Verify re_credit_pack was called
        rpc_calls = [c for c in mock_client.rpc.call_args_list if c[0][0] == "re_credit_pack"]
        assert len(rpc_calls) == 1
        assert rpc_calls[0][0][1]["p_user_id"] == _PAID_USER["user_id"]


# ---------------------------------------------------------------------------
# Watermark toggle
# ---------------------------------------------------------------------------

def _make_render_design(run_id: str, is_paid: bool, user_id: str | None = None):
    """Build a minimal finalized design for render tests."""
    from app.api.schemas import (
        DesignResponse,
        ProductResult,
        SlotResult,
        StyleResult,
    )
    prod = ProductResult(
        product_id="p1", name="Bed", normalized_price=400,
        image_url="http://img", buy_url="http://buy",
        fit_reason="good",
    )
    return DesignResponse(
        run_id=run_id, room_type="bedroom",
        style=StyleResult(
            style_name="warm_minimalist", keywords=["wood"],
            mood="calm", confidence=0.9, fallback=False,
        ),
        target_budget=2000, total_spent=1500, is_feasible=True,
        slots=[SlotResult(
            slot_id="bed_frame", allocated_budget=500,
            owned=False, max_quantity=1, product=prod,
            alternatives=[], selected_products=[prod],
            null_reason=None,
        )],
        finalized_at="2026-01-01T00:00:00Z",
        is_paid=is_paid,
        user_id=user_id,
    )


_RENDER_PATCHES = {
    "services.render_service.render_exists": False,
    "services.redis_client.get_redis": None,
}


class TestWatermark:

    def test_free_design_render_watermarked(self):
        """Free design → watermark=True passed to render_room."""
        app.dependency_overrides[get_current_user] = lambda: _FREE_USER
        _designs["wm-free-001"] = _make_render_design(
            "wm-free-001", is_paid=False, user_id=_FREE_USER["user_id"],
        )

        render_patch = patch(
            "services.render_service.render_room",
            return_value=("/tmp/render.jpg", None),
        )
        with render_patch as mock_render, \
             patch("services.render_service.render_exists", return_value=False), \
             patch("services.redis_client.get_redis", return_value=None):
            client = TestClient(app)
            resp = client.post("/design/wm-free-001/render", json={})

        assert resp.status_code == 200
        mock_render.assert_called_once()
        assert mock_render.call_args.kwargs.get("watermark") is True
        assert mock_render.call_args.kwargs.get("is_paid") is False

    def test_paid_design_render_no_watermark(self):
        """Paid design → watermark=False, is_paid=True passed to render_room."""
        app.dependency_overrides[get_current_user] = lambda: _PAID_USER
        _designs["wm-paid-001"] = _make_render_design(
            "wm-paid-001", is_paid=True, user_id=_PAID_USER["user_id"],
        )

        render_patch = patch(
            "services.render_service.render_room",
            return_value=("/tmp/render.jpg", None),
        )
        with render_patch as mock_render, \
             patch("services.render_service.render_exists", return_value=False), \
             patch("services.redis_client.get_redis", return_value=None):
            client = TestClient(app)
            resp = client.post("/design/wm-paid-001/render", json={})

        assert resp.status_code == 200
        mock_render.assert_called_once()
        assert mock_render.call_args.kwargs.get("watermark") is False
        assert mock_render.call_args.kwargs.get("is_paid") is True


# ---------------------------------------------------------------------------
# TOCTOU concurrent test
# ---------------------------------------------------------------------------

class TestTOCTOU:

    @_patch_llms
    def test_concurrent_free_claims_one_wins(self, _s, _c, _sel):
        """5 concurrent requests for same free user — exactly 1 succeeds."""
        app.dependency_overrides[get_current_user] = lambda: _FREE_USER

        # Simulate atomic claim: first call succeeds, rest fail.
        # Use a lock to serialize claim_and_save_free_design calls,
        # mirroring the advisory lock behavior.
        _claim_lock = threading.Lock()
        _claimed = {"count": 0}

        def _rpc(name, params):
            execute_result = MagicMock()
            if name == "decrement_pack":
                execute_result.data = None  # no pack
            elif name == "claim_and_save_free_design":
                with _claim_lock:
                    if _claimed["count"] < 1:
                        _claimed["count"] += 1
                        execute_result.data = True
                    else:
                        execute_result.data = False
            elif name == "re_credit_pack":
                execute_result.data = None
            rpc_callable = MagicMock()
            rpc_callable.execute.return_value = execute_result
            return rpc_callable

        mock_client = MagicMock()
        mock_client.rpc.side_effect = _rpc

        # Count query — return 0 for fast-path (let all through to the atomic claim)
        count_resp = MagicMock()
        count_resp.count = 0
        eq_chain = MagicMock()
        eq_chain.eq.return_value = eq_chain
        eq_chain.execute.return_value = count_resp
        select_mock = MagicMock()
        select_mock.eq.return_value = eq_chain
        table_mock = MagicMock()
        table_mock.select.return_value = select_mock
        table_mock.upsert.return_value.execute.return_value = None

        # deleted_emails cooldown check must return empty data
        de_resp = MagicMock()
        de_resp.data = []
        de_chain = MagicMock()
        de_chain.gte.return_value = de_chain
        de_chain.eq.return_value = de_chain
        de_chain.execute.return_value = de_resp
        de_select = MagicMock()
        de_select.eq.return_value = de_chain
        de_table = MagicMock()
        de_table.select.return_value = de_select

        def _table(name):
            if name == "deleted_emails":
                return de_table
            return table_mock

        mock_client.table.side_effect = _table
        mock_client.table.return_value = table_mock

        results = []

        def make_request(i):
            c = TestClient(app, raise_server_exceptions=False)
            resp = c.post("/design", json=_DESIGN_REQ)
            results.append(resp.status_code)

        with patch("services.supabase_client.get_client", return_value=mock_client):
            with ThreadPoolExecutor(max_workers=5) as pool:
                futures = [pool.submit(make_request, i) for i in range(5)]
                for f in futures:
                    f.result()

        assert results.count(200) == 1, f"Expected exactly 1 success, got {results}"
        assert results.count(403) == 4, f"Expected exactly 4 rejections, got {results}"

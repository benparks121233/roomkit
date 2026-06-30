"""Tests for Phase 7A: Stripe Checkout + webhook + pack credit."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("TESTING", "1")

from app.auth import get_current_user
from app.main import app
from fastapi.testclient import TestClient

import services.stripe_service  # ensure module is in sys.modules for patch targets

_USER = {"user_id": "00000000-0000-0000-0000-000000000010", "email": "stripe@test.com", "token": "tok"}


@pytest.fixture(autouse=True)
def _auth_override():
    prev = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: _USER
    yield
    if prev is not None:
        app.dependency_overrides[get_current_user] = prev
    else:
        app.dependency_overrides.pop(get_current_user, None)


client = TestClient(app)


def _checkout_completed_event(session_id="cs_test_1", user_id=None, pack_size="5",
                               amount=999, currency="usd"):
    return {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "client_reference_id": user_id or _USER["user_id"],
                "metadata": {"pack_size": pack_size},
                "amount_total": amount,
                "currency": currency,
            },
        },
    }


def _post_webhook(content=b'{}', sig="t=1,v1=ok"):
    return client.post(
        "/stripe/webhook",
        content=content,
        headers={"content-type": "application/json", "stripe-signature": sig},
    )


# ---------------------------------------------------------------------------
# POST /checkout
# ---------------------------------------------------------------------------

class TestCheckout:
    """POST /checkout — create Stripe Checkout Session."""

    @patch("services.stripe_service._STRIPE_SECRET_KEY", "sk_test_xxx")
    @patch("services.stripe_service.stripe")
    def test_returns_url(self, mock_stripe):
        mock_price = MagicMock()
        mock_price.metadata = {"pack_size": "5"}
        mock_price.product = MagicMock()
        mock_price.product.metadata = {"pack_size": "5"}
        mock_stripe.Price.retrieve.return_value = mock_price

        mock_session = MagicMock()
        mock_session.id = "cs_test_123"
        mock_session.url = "https://checkout.stripe.com/pay/cs_test_123"
        mock_stripe.checkout.Session.create.return_value = mock_session

        resp = client.post("/checkout", json={"price_id": "price_test_abc"})
        assert resp.status_code == 200
        assert resp.json()["url"] == "https://checkout.stripe.com/pay/cs_test_123"

        create_call = mock_stripe.checkout.Session.create.call_args
        assert create_call.kwargs["client_reference_id"] == _USER["user_id"]
        assert create_call.kwargs["customer_email"] == _USER["email"]
        assert create_call.kwargs["metadata"]["pack_size"] == "5"

    def test_no_price_id_returns_400(self):
        with patch.dict(os.environ, {"STRIPE_PRICE_ID": ""}, clear=False):
            resp = client.post("/checkout", json={})
        assert resp.status_code == 400
        assert "price_id" in resp.json()["detail"].lower()

    @patch("services.stripe_service._STRIPE_SECRET_KEY", "")
    def test_stripe_not_configured_returns_503(self):
        resp = client.post("/checkout", json={"price_id": "price_xxx"})
        assert resp.status_code == 503
        assert "not configured" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# POST /stripe/webhook — signature verification
# ---------------------------------------------------------------------------

class TestWebhookSignature:
    """Webhook endpoint rejects bad signatures, accepts good ones."""

    def test_missing_signature_returns_400(self):
        resp = client.post(
            "/stripe/webhook",
            content=b'{"type": "checkout.session.completed"}',
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 400
        assert "signature" in resp.json()["detail"].lower()

    @patch("services.stripe_service._STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("services.stripe_service.stripe.Webhook.construct_event")
    def test_bad_signature_returns_400(self, mock_construct):
        from stripe import SignatureVerificationError
        mock_construct.side_effect = SignatureVerificationError("bad sig", "sig_header")

        resp = _post_webhook(sig="t=123,v1=bad")
        assert resp.status_code == 400

    @patch("services.stripe_service._STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("services.stripe_service.stripe.Webhook.construct_event")
    @patch("services.supabase_client.get_client")
    def test_valid_signature_processes(self, mock_supabase, mock_construct):
        mock_construct.return_value = _checkout_completed_event("cs_test_sig")

        mock_client = MagicMock()
        mock_rpc_resp = MagicMock()
        mock_rpc_resp.data = 5
        mock_client.rpc.return_value.execute.return_value = mock_rpc_resp
        mock_supabase.return_value = mock_client

        resp = _post_webhook()
        assert resp.status_code == 200
        assert resp.json()["status"] == "credited"


# ---------------------------------------------------------------------------
# POST /stripe/webhook — idempotency
# ---------------------------------------------------------------------------

class TestWebhookIdempotency:
    """Duplicate webhook deliveries don't double-credit."""

    @patch("services.stripe_service._STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("services.stripe_service.stripe.Webhook.construct_event")
    @patch("services.supabase_client.get_client")
    def test_first_delivery_credits(self, mock_supabase, mock_construct):
        mock_construct.return_value = _checkout_completed_event("cs_test_idem")

        mock_client = MagicMock()
        mock_rpc_resp = MagicMock()
        mock_rpc_resp.data = 5
        mock_client.rpc.return_value.execute.return_value = mock_rpc_resp
        mock_supabase.return_value = mock_client

        resp = _post_webhook()
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "credited"
        assert body["pack_size"] == 5
        assert body["rooms_remaining"] == 5

        mock_client.rpc.assert_called_once_with("process_stripe_payment", {
            "p_session_id": "cs_test_idem",
            "p_user_id": _USER["user_id"],
            "p_pack_size": 5,
            "p_amount": 999,
            "p_currency": "usd",
        })

    @patch("services.stripe_service._STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("services.stripe_service.stripe.Webhook.construct_event")
    @patch("services.supabase_client.get_client")
    def test_duplicate_delivery_skips(self, mock_supabase, mock_construct):
        """RPC returns null on duplicate -> 200 with status=duplicate."""
        mock_construct.return_value = _checkout_completed_event("cs_test_idem")

        mock_client = MagicMock()
        mock_rpc_resp = MagicMock()
        mock_rpc_resp.data = None
        mock_client.rpc.return_value.execute.return_value = mock_rpc_resp
        mock_supabase.return_value = mock_client

        resp = _post_webhook()
        assert resp.status_code == 200
        assert resp.json()["status"] == "duplicate"


# ---------------------------------------------------------------------------
# POST /stripe/webhook — failure modes
# ---------------------------------------------------------------------------

class TestWebhookFailures:
    """Edge cases and failure modes."""

    @patch("services.stripe_service._STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("services.stripe_service.stripe.Webhook.construct_event")
    def test_ignored_event_type(self, mock_construct):
        mock_construct.return_value = {
            "type": "payment_intent.created",
            "data": {"object": {}},
        }

        resp = _post_webhook()
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    @patch("services.stripe_service._STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("services.stripe_service.stripe.Webhook.construct_event")
    def test_missing_client_reference_id(self, mock_construct):
        event = _checkout_completed_event("cs_test_nouser")
        event["data"]["object"]["client_reference_id"] = None
        mock_construct.return_value = event

        resp = _post_webhook()
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"

    @patch("services.stripe_service._STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("services.stripe_service.stripe.Webhook.construct_event")
    @patch("services.supabase_client.get_client", return_value=None)
    def test_supabase_unavailable_returns_500(self, _mock_sb, mock_construct):
        """Supabase down -> 500 so Stripe retries (no orphan state)."""
        mock_construct.return_value = _checkout_completed_event("cs_test_nodb")

        resp = _post_webhook()
        assert resp.status_code == 500

    @patch("services.stripe_service._STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("services.stripe_service.stripe.Webhook.construct_event")
    @patch("services.supabase_client.get_client")
    def test_rpc_failure_returns_500(self, mock_supabase, mock_construct):
        """RPC raises -> 500, Stripe retries. Transaction rolled back, no orphan dedup row."""
        mock_construct.return_value = _checkout_completed_event("cs_test_rpcfail")

        mock_client = MagicMock()
        mock_client.rpc.return_value.execute.side_effect = Exception("connection lost")
        mock_supabase.return_value = mock_client

        resp = _post_webhook()
        assert resp.status_code == 500

    @patch("services.stripe_service._STRIPE_WEBHOOK_SECRET", "")
    def test_webhook_secret_not_configured_returns_500(self):
        resp = _post_webhook()
        assert resp.status_code == 500

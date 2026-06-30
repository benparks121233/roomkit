from __future__ import annotations

import logging
import os

import stripe
from stripe import SignatureVerificationError

logger = logging.getLogger(__name__)

_STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
_STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")


def create_checkout_session(
    user_id: str,
    user_email: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
) -> str:
    if not _STRIPE_SECRET_KEY:
        raise RuntimeError("Stripe not configured")

    stripe.api_key = _STRIPE_SECRET_KEY

    price = stripe.Price.retrieve(price_id, expand=["product"])
    product = price.product

    product_meta = dict(product.metadata) if product and hasattr(product, "metadata") else {}
    price_meta = dict(price.metadata) if hasattr(price, "metadata") else {}
    pack_size = product_meta.get("pack_size") or price_meta.get("pack_size")
    if not pack_size:
        raise RuntimeError(
            f"pack_size not found in product or price metadata for {price_id}"
        )

    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{"price": price_id, "quantity": 1}],
        client_reference_id=user_id,
        customer_email=user_email,
        metadata={"pack_size": str(pack_size)},
        success_url=success_url,
        cancel_url=cancel_url,
    )

    logger.info("stripe: created checkout session %s for user %s", session.id, user_id)
    return session.url


def handle_webhook_event(payload: bytes, sig_header: str) -> dict:
    if not _STRIPE_WEBHOOK_SECRET:
        raise RuntimeError("Stripe webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, _STRIPE_WEBHOOK_SECRET,
        )
    except SignatureVerificationError:
        logger.warning("stripe webhook: invalid signature")
        return {"status": "bad_signature"}
    except Exception:
        logger.exception("stripe webhook: signature verification failed")
        return {"status": "bad_signature"}

    if event["type"] != "checkout.session.completed":
        logger.info("stripe webhook: ignoring event type %s", event["type"])
        return {"status": "ignored", "event_type": event["type"]}

    session = event["data"]["object"]
    session_id = session["id"]
    user_id = session.get("client_reference_id")
    pack_size_str = (session.get("metadata") or {}).get("pack_size")
    amount_total = session.get("amount_total", 0)
    currency = session.get("currency", "usd")

    if not user_id:
        logger.error("stripe webhook: session %s missing client_reference_id", session_id)
        return {"status": "error", "detail": "missing client_reference_id"}

    if not pack_size_str:
        logger.error("stripe webhook: session %s missing pack_size metadata", session_id)
        return {"status": "error", "detail": "missing pack_size"}

    pack_size = int(pack_size_str)

    from services.supabase_client import get_client
    client = get_client()
    if client is None:
        raise RuntimeError("Supabase not available — cannot process payment")

    resp = client.rpc("process_stripe_payment", {
        "p_session_id": session_id,
        "p_user_id": user_id,
        "p_pack_size": pack_size,
        "p_amount": amount_total,
        "p_currency": currency,
    }).execute()

    if resp.data is None:
        logger.info("stripe webhook: duplicate session %s — already processed", session_id)
        return {"status": "duplicate", "session_id": session_id}

    rooms_remaining = resp.data
    logger.info(
        "stripe webhook: credited %d rooms to user %s (session %s, remaining=%s)",
        pack_size, user_id, session_id, rooms_remaining,
    )

    try:
        from services.tracking import log_event
        log_event(session_id, "pack_purchased", {
            "user_id": user_id,
            "pack_size": pack_size,
            "amount_cents": amount_total,
            "currency": currency,
            "rooms_remaining": rooms_remaining,
        }, user_id=user_id)
    except Exception:
        logger.warning("stripe webhook: event logging failed (non-fatal)", exc_info=True)

    return {
        "status": "credited",
        "session_id": session_id,
        "user_id": user_id,
        "pack_size": pack_size,
        "rooms_remaining": rooms_remaining,
    }

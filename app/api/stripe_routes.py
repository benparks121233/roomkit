from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.auth import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stripe"])


class CheckoutRequest(BaseModel):
    price_id: str | None = None
    success_url: str | None = None
    cancel_url: str | None = None


class CheckoutResponse(BaseModel):
    url: str


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(req: CheckoutRequest, user: CurrentUser) -> CheckoutResponse:
    price_id = req.price_id or os.environ.get("STRIPE_PRICE_ID", "")
    if not price_id:
        raise HTTPException(400, "No price_id provided and STRIPE_PRICE_ID not configured")

    site_url = os.environ.get("NEXT_PUBLIC_SITE_URL", "http://localhost:3000")
    success_url = f"{site_url}/purchase/success"
    cancel_url = f"{site_url}/purchase/cancel"

    try:
        from services.stripe_service import create_checkout_session
        url = create_checkout_session(
            user_id=user["user_id"],
            user_email=user["email"],
            price_id=price_id,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except RuntimeError as exc:
        if "not configured" in str(exc):
            raise HTTPException(503, "Payments not configured")
        raise HTTPException(500, "Failed to create checkout session")
    except Exception:
        logger.exception("checkout: failed to create session")
        raise HTTPException(500, "Failed to create checkout session")

    return CheckoutResponse(url=url)


@router.get("/pack/balance")
async def pack_balance(user: CurrentUser) -> dict:
    """Return the user's remaining room pack balance."""
    from services.supabase_client import get_client
    client = get_client()
    if client is None:
        return {"rooms_remaining": 0, "has_pack": False}

    try:
        resp = client.table("user_packs").select("rooms_remaining").eq(
            "user_id", user["user_id"]
        ).maybe_single().execute()
        if resp and resp.data:
            return {"rooms_remaining": resp.data["rooms_remaining"], "has_pack": True}
        return {"rooms_remaining": 0, "has_pack": False}
    except Exception:
        logger.exception("pack_balance: failed for %s", user["user_id"])
        return {"rooms_remaining": 0, "has_pack": False}


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    raw_body = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not sig_header:
        raise HTTPException(400, "Missing stripe-signature header")

    try:
        from services.stripe_service import handle_webhook_event
        result = handle_webhook_event(raw_body, sig_header)
    except RuntimeError as exc:
        if "not configured" in str(exc) or "not available" in str(exc):
            logger.error("stripe webhook: %s", exc)
            raise HTTPException(500, str(exc))
        raise
    except Exception:
        logger.exception("stripe webhook: unhandled error")
        raise HTTPException(500, "Webhook processing failed")

    if result["status"] == "bad_signature":
        raise HTTPException(400, "Invalid signature")

    return result

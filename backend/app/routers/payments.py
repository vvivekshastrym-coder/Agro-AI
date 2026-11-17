"""Agro AI Payments & Checkout Processing Router
Enforces server-determined pricing from immutable published plan versions.
Supports Razorpay integration with idempotent webhook processing and cryptographic signature verification.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import datetime
import uuid
import hmac
import hashlib
import os
import logging
import httpx

from ..database.connection import get_db
from ..database.models import (
    User, SubscriptionPlan, SubscriptionPlanVersion,
    PaymentOrder, PaymentTransaction, PaymentWebhookEvent, UserSubscription,
    BroadcastItem, BroadcastStatus
)
from ..auth.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

def get_razorpay_key_id() -> str:
    return os.getenv("RAZORPAY_KEY_ID", "").strip()

def get_razorpay_key_secret() -> str:
    return os.getenv("RAZORPAY_KEY_SECRET", "").strip()

def get_razorpay_webhook_secret() -> str:
    return os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()


async def create_razorpay_order(amount_minor: int, currency: str, receipt: str) -> dict:
    key_id, key_secret = get_razorpay_key_id(), get_razorpay_key_secret()
    if not key_id or not key_secret:
        raise HTTPException(status_code=503, detail={"error": {"code": "PAYMENT_PROVIDER_NOT_CONFIGURED", "message": "Payment checkout is temporarily unavailable."}})
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.razorpay.com/v1/orders",
                auth=(key_id, key_secret),
                json={"amount": amount_minor, "currency": currency, "receipt": receipt},
            )
        response.raise_for_status()
        provider_order = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.error("Razorpay order creation failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail={"error": {"code": "PAYMENT_PROVIDER_UNAVAILABLE", "message": "Payment checkout is temporarily unavailable."}})
    if (
        not provider_order.get("id")
        or provider_order.get("status") != "created"
        or provider_order.get("amount") != amount_minor
        or provider_order.get("currency") != currency
    ):
        raise HTTPException(status_code=502, detail={"error": {"code": "INVALID_PROVIDER_ORDER", "message": "The payment provider returned an invalid order."}})
    return provider_order


async def get_razorpay_payment(payment_id: str) -> dict:
    key_id, key_secret = get_razorpay_key_id(), get_razorpay_key_secret()
    if not key_id or not key_secret:
        raise HTTPException(status_code=503, detail={"error": {"code": "PAYMENT_PROVIDER_NOT_CONFIGURED", "message": "Payment verification is temporarily unavailable."}})
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"https://api.razorpay.com/v1/payments/{payment_id}",
                auth=(key_id, key_secret),
            )
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.error("Razorpay payment lookup failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail={"error": {"code": "PAYMENT_PROVIDER_UNAVAILABLE", "message": "Payment verification is temporarily unavailable."}})



class CreateOrderRequest(BaseModel):
    plan_version_id: str
    coupon_code: Optional[str] = None


class VerifyPaymentRequest(BaseModel):
    order_id: str = Field(..., min_length=1, max_length=100)
    provider_payment_id: str = Field(..., min_length=8, max_length=100, pattern=r"^pay_[A-Za-z0-9]+$")
    provider_signature: str = Field(..., min_length=64, max_length=64, pattern=r"^[a-fA-F0-9]{64}$")


def compute_interval_end(start: datetime.datetime, interval: str) -> datetime.datetime:
    """Calculates subscription expiry date based on interval."""
    if interval == "monthly":
        return start + datetime.timedelta(days=30)
    elif interval == "quarterly":
        return start + datetime.timedelta(days=90)
    elif interval == "yearly":
        return start + datetime.timedelta(days=365)
    elif interval == "lifetime":
        return start + datetime.timedelta(days=3650)
    return start + datetime.timedelta(days=30)


@router.post("/create-order")
async def create_payment_order(
    req: CreateOrderRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    POST /api/payments/create-order
    Creates a payment order for the specified published plan version.
    The order price is ALWAYS read from the database, never from the caller.
    Supports Super Admin approved promotional discount coupons.
    """
    version = db.query(SubscriptionPlanVersion).filter(
        SubscriptionPlanVersion.id == req.plan_version_id,
        SubscriptionPlanVersion.is_published == True
    ).first()

    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "PLAN_NOT_FOUND", "message": "Published plan version not found."}}
        )

    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.id == version.plan_id,
        SubscriptionPlan.status == "published"
    ).first()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "PLAN_UNAVAILABLE", "message": "This plan is currently not available for purchase."}}
        )

    amount_minor = version.price_minor
    discount_minor = 0
    coupon_applied = None

    if req.coupon_code:
        code_clean = req.coupon_code.strip().upper()
        now = datetime.datetime.now(datetime.timezone.utc)
        offer = db.query(BroadcastItem).filter(
            BroadcastItem.status == BroadcastStatus.approved,
            BroadcastItem.discount_code == code_clean
        ).first()

        if offer and offer.discount_percent:
            if not offer.valid_until or offer.valid_until >= now:
                if not offer.target_plan_slug or offer.target_plan_slug == plan.slug:
                    discount_fraction = min(max(offer.discount_percent, 0.0), 100.0) / 100.0
                    discount_minor = int(version.price_minor * discount_fraction)
                    amount_minor = max(0, version.price_minor - discount_minor)
                    coupon_applied = code_clean

    # Create the provider order server-side; never invent a provider reference.
    order_uuid = str(uuid.uuid4())
    key_id = get_razorpay_key_id()
    provider_order = await create_razorpay_order(amount_minor, version.currency, order_uuid[:40])
    provider_order_id = provider_order["id"]

    order_notes = {}
    if coupon_applied:
        order_notes["coupon_code"] = coupon_applied
        order_notes["discount_minor"] = discount_minor
        order_notes["original_amount_minor"] = version.price_minor

    order = PaymentOrder(
        id=order_uuid,
        user_id=user.id,
        plan_version_id=version.id,
        amount_minor=amount_minor,
        currency=version.currency,
        provider="razorpay",
        provider_order_id=provider_order_id,
        receipt=provider_order.get("receipt"),
        status="created",
        notes=order_notes
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    return {
        "order_id": order.id,
        "provider_order_id": order.provider_order_id,
        "amount_minor": order.amount_minor,
        "amount_formatted": f"₹{order.amount_minor / 100:.2f}",
        "original_amount_minor": version.price_minor,
        "original_amount_formatted": f"₹{version.price_minor / 100:.2f}",
        "discount_minor": discount_minor,
        "discount_formatted": f"₹{discount_minor / 100:.2f}" if discount_minor else None,
        "coupon_applied": coupon_applied,
        "currency": order.currency,
        "provider": "razorpay",
        "key_id": key_id,
        "provider_configured": True,
        "plan_name": version.name,
        "billing_interval": version.billing_interval
    }


@router.post("/verify-payment")
async def verify_payment(
    req: VerifyPaymentRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    POST /api/payments/verify-payment
    Cryptographically verifies the provider's signature and activates the subscription.
    """
    order = db.query(PaymentOrder).filter(
        PaymentOrder.id == req.order_id,
        PaymentOrder.user_id == user.id
    ).with_for_update().first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "ORDER_NOT_FOUND", "message": "Payment order not found."}}
        )

    # A checkout signature is mandatory in every environment, and the payment
    # must also be confirmed as captured against the provider's authenticated API.
    key_secret = get_razorpay_key_secret()
    if not key_secret or not get_razorpay_key_id():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "PAYMENT_VERIFICATION_NOT_CONFIGURED", "message": "Payment verification is temporarily unavailable."}}
        )
    if not order.provider_order_id:
        raise HTTPException(status_code=409, detail={"error": {"code": "PROVIDER_ORDER_MISSING", "message": "This order is not linked to a provider order."}})
    msg = f"{order.provider_order_id}|{req.provider_payment_id}"
    expected_sig = hmac.new(key_secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, req.provider_signature):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_SIGNATURE", "message": "Cryptographic payment verification failed."}}
        )

    provider_payment = await get_razorpay_payment(req.provider_payment_id)
    if (
        provider_payment.get("status") != "captured"
        or provider_payment.get("order_id") != order.provider_order_id
        or provider_payment.get("amount") != order.amount_minor
        or provider_payment.get("currency") != order.currency
    ):
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "PAYMENT_NOT_RECONCILED", "message": "The provider has not confirmed a captured payment matching this order."}},
        )

    existing_tx = db.query(PaymentTransaction).filter(
        PaymentTransaction.provider_payment_id == req.provider_payment_id
    ).first()
    if existing_tx and (existing_tx.order_id != order.id or existing_tx.user_id != user.id):
        raise HTTPException(status_code=409, detail={"error": {"code": "PAYMENT_ALREADY_LINKED", "message": "This payment is already linked to another order."}})
    if order.status == "paid" and existing_tx:
        existing_subscription = db.query(UserSubscription).filter(
            UserSubscription.user_id == user.id,
            UserSubscription.plan_version_id == order.plan_version_id,
            UserSubscription.status == "active",
        ).order_by(UserSubscription.created_at.desc()).first()
        if existing_subscription:
            db.refresh(existing_subscription)
            return {
                "success": True,
                "subscription_id": existing_subscription.id,
                "status": "active",
                "current_period_end": existing_subscription.current_period_end.isoformat(),
                "plan_name": existing_subscription.plan_version.name if existing_subscription.plan_version else "Premium Plan",
            }
    if order.status not in {"created", "attempted"}:
        raise HTTPException(status_code=409, detail={"error": {"code": "ORDER_NOT_PAYABLE", "message": "This order is not awaiting payment verification."}})

    # 1. Update order status
    order.status = "paid"

    # 2. Record transaction idempotently
    tx = existing_tx
    if not tx:
        tx = PaymentTransaction(
            id=str(uuid.uuid4()),
            order_id=order.id,
            user_id=user.id,
            provider="razorpay",
            provider_payment_id=req.provider_payment_id,
            provider_signature=req.provider_signature,
            amount_minor=order.amount_minor,
            currency=order.currency,
            status="success"
        )
        db.add(tx)

    # 3. Activate subscription
    version = db.query(SubscriptionPlanVersion).filter(SubscriptionPlanVersion.id == order.plan_version_id).first()
    now = datetime.datetime.now(datetime.timezone.utc)
    interval = version.billing_interval if version else "monthly"
    period_end = compute_interval_end(now, interval)

    # Deactivate existing active subscriptions
    active_subs = db.query(UserSubscription).filter(
        UserSubscription.user_id == user.id,
        UserSubscription.status == "active"
    ).all()
    for s in active_subs:
        s.status = "superseded"

    new_sub = UserSubscription(
        id=str(uuid.uuid4()),
        user_id=user.id,
        plan_version_id=order.plan_version_id,
        status="active",
        current_period_start=now,
        current_period_end=period_end,
        cancel_at_period_end=False
    )
    db.add(new_sub)

    db.commit()

    return {
        "success": True,
        "subscription_id": new_sub.id,
        "status": "active",
        "current_period_end": period_end.isoformat(),
        "plan_name": version.name if version else "Premium Plan"
    }


@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_razorpay_signature: Optional[str] = Header(None),
    x_razorpay_event_id: Optional[str] = Header(None),
):
    """
    POST /api/payments/webhook
    Idempotent webhook handler with duplicate event detection.
    """
    raw_body = await request.body()
    webhook_secret = get_razorpay_webhook_secret()
    if not webhook_secret:
        raise HTTPException(status_code=503, detail={"error": {"code": "WEBHOOK_NOT_CONFIGURED", "message": "Payment event processing is temporarily unavailable."}})
    if not x_razorpay_signature:
        raise HTTPException(status_code=400, detail={"error": {"code": "WEBHOOK_SIGNATURE_REQUIRED", "message": "A valid provider signature is required."}})
    expected_sig = hmac.new(webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, x_razorpay_signature):
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_WEBHOOK_SIGNATURE", "message": "Invalid webhook signature."}})

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_id = (x_razorpay_event_id or "").strip()
    if not event_id or len(event_id) > 100:
        raise HTTPException(status_code=400, detail={"error": {"code": "WEBHOOK_EVENT_ID_REQUIRED", "message": "The provider event ID header is required."}})
    event_type = payload.get("event", "unknown")

    # Idempotency check: unique (provider, provider_event_id)
    existing_event = db.query(PaymentWebhookEvent).filter(
        PaymentWebhookEvent.provider == "razorpay",
        PaymentWebhookEvent.provider_event_id == event_id
    ).first()

    if existing_event:
        logger.info(f"Duplicate webhook event ignored: {event_id}")
        return {"status": "already_processed", "event_id": event_id}

    # Record only the minimum provider identifiers; webhook entities may contain PII.
    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {}) if isinstance(payload.get("payload"), dict) else {}
    provider_order_id = payment_entity.get("order_id") if isinstance(payment_entity, dict) else None
    provider_payment_id = payment_entity.get("id") if isinstance(payment_entity, dict) else None
    event_metadata = {"provider_order_id": provider_order_id, "provider_payment_id": provider_payment_id}
    event_record = PaymentWebhookEvent(
        id=str(uuid.uuid4()),
        provider="razorpay",
        provider_event_id=event_id,
        event_type=event_type,
        payload=event_metadata,
        processed=True,
        processed_at=datetime.datetime.now(datetime.timezone.utc)
    )
    db.add(event_record)

    # Process payment capture or order paid
    if event_type in ("order.paid", "payment.captured"):
        if not provider_order_id or not provider_payment_id or payment_entity.get("status") != "captured":
            db.rollback()
            raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_CAPTURE_EVENT", "message": "A captured payment with provider order and payment IDs is required."}})
        order = db.query(PaymentOrder).filter(PaymentOrder.provider_order_id == provider_order_id).with_for_update().first()
        if not order:
            db.rollback()
            raise HTTPException(status_code=404, detail={"error": {"code": "ORDER_NOT_FOUND", "message": "Provider order not found."}})
        if payment_entity.get("amount") != order.amount_minor or payment_entity.get("currency") != order.currency:
            db.rollback()
            raise HTTPException(status_code=409, detail={"error": {"code": "PAYMENT_AMOUNT_MISMATCH", "message": "Captured payment does not match the order amount and currency."}})
        tx = db.query(PaymentTransaction).filter(PaymentTransaction.provider_payment_id == provider_payment_id).first()
        if tx and (tx.order_id != order.id or tx.user_id != order.user_id):
            db.rollback()
            raise HTTPException(status_code=409, detail={"error": {"code": "PAYMENT_ALREADY_LINKED", "message": "Payment is already linked to another order."}})
        if order.status != "paid":
            if order.status not in {"created", "attempted", "issue_reported"}:
                db.rollback()
                raise HTTPException(status_code=409, detail={"error": {"code": "ORDER_NOT_PAYABLE", "message": "This order cannot accept payment."}})
            order.status = "paid"
            if not tx:
                db.add(PaymentTransaction(
                    id=str(uuid.uuid4()), order_id=order.id, user_id=order.user_id,
                    provider="razorpay", provider_payment_id=provider_payment_id,
                    amount_minor=order.amount_minor, currency=order.currency, status="success"
                ))
            version = db.query(SubscriptionPlanVersion).filter(SubscriptionPlanVersion.id == order.plan_version_id).first()
            if not version:
                db.rollback()
                raise HTTPException(status_code=409, detail={"error": {"code": "PLAN_VERSION_NOT_FOUND", "message": "The purchased plan version is unavailable."}})
            now = datetime.datetime.now(datetime.timezone.utc)
            period_end = compute_interval_end(now, version.billing_interval)
            active_subs = db.query(UserSubscription).filter(
                UserSubscription.user_id == order.user_id,
                UserSubscription.status == "active"
            ).all()
            for subscription in active_subs:
                subscription.status = "superseded"
            db.add(UserSubscription(
                id=str(uuid.uuid4()), user_id=order.user_id,
                plan_version_id=order.plan_version_id, status="active",
                current_period_start=now, current_period_end=period_end,
                cancel_at_period_end=False
            ))

    db.commit()
    return {"status": "processed", "event_id": event_id}


# ── FARMER PAYMENT ASSISTANCE & ISSUE REPORTING ───────────────────

class ReportPaymentIssueRequest(BaseModel):
    issue_type: str = Field("payment_deducted_not_activated") # payment_failed, payment_deducted_not_activated, other
    description: str = Field(..., min_length=3)
    upi_ref_or_utr: Optional[str] = None
    contact_phone: Optional[str] = None


class FailOrderRequest(BaseModel):
    error_code: Optional[str] = None
    error_description: Optional[str] = None


@router.post("/orders/{order_id}/report-issue")
async def report_payment_issue(
    order_id: str,
    req: ReportPaymentIssueRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Allows a farmer to report a payment difficulty or money deducted via UPI so staff can assist."""
    order = db.query(PaymentOrder).filter(PaymentOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail={"error": {"code": "ORDER_NOT_FOUND", "message": "Order not found."}})
    if order.user_id != user.id:
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Not authorized to report issue for this order."}})

    order.status = "issue_reported"
    notes = order.notes.copy() if order.notes else {}
    issues_list = notes.get("reported_issues", [])
    issues_list.append({
        "reported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "issue_type": req.issue_type,
        "description": req.description,
        "upi_ref_or_utr": req.upi_ref_or_utr,
        "contact_phone": req.contact_phone or user.phone
    })
    notes["reported_issues"] = issues_list
    notes["has_open_issue"] = True
    order.notes = notes
    db.commit()

    return {
        "success": True,
        "order_id": order.id,
        "status": order.status,
        "message": "Payment issue reported to Agro AI support staff. Our team will review and assist you promptly."
    }


@router.post("/orders/{order_id}/fail")
async def record_payment_failure(
    order_id: str,
    req: FailOrderRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Records client-side checkout failures (e.g. UPI bank server down, user canceled modal) so staff can track issues."""
    order = db.query(PaymentOrder).filter(PaymentOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail={"error": {"code": "ORDER_NOT_FOUND", "message": "Order not found."}})
    if order.user_id != user.id:
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Not authorized for this order."}})

    if order.status != "paid":
        order.status = "failed"
        notes = order.notes.copy() if order.notes else {}
        notes["failure_details"] = {
            "failed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "error_code": req.error_code,
            "error_description": req.error_description
        }
        order.notes = notes
        db.commit()

    return {"status": order.status, "order_id": order.id}


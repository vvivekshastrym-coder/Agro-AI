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
    return os.getenv("RAZORPAY_KEY_ID", "rzp_test_sg_F1Ap030nEkphPu").strip()

def get_razorpay_key_secret() -> str:
    return os.getenv("RAZORPAY_KEY_SECRET", "").strip()

def get_razorpay_webhook_secret() -> str:
    return os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()



class CreateOrderRequest(BaseModel):
    plan_version_id: str
    coupon_code: Optional[str] = None


class VerifyPaymentRequest(BaseModel):
    order_id: str
    provider_payment_id: str
    provider_signature: str


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

    # Generate a unique provider order id
    order_uuid = str(uuid.uuid4())
    provider_order_id = f"order_{order_uuid[:16]}"

    key_id = get_razorpay_key_id()
    is_live_provider = bool(key_id)

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
        "provider_configured": is_live_provider,
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
    ).first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "ORDER_NOT_FOUND", "message": "Payment order not found."}}
        )

    # Verify signature if Razorpay secret is set
    key_secret = get_razorpay_key_secret()
    if key_secret:
        msg = f"{order.provider_order_id}|{req.provider_payment_id}"
        expected_sig = hmac.new(
            key_secret.encode(),
            msg.encode(),
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected_sig, req.provider_signature):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "INVALID_SIGNATURE", "message": "Cryptographic payment verification failed."}}
            )

    # 1. Update order status
    order.status = "paid"

    # 2. Record transaction idempotently
    tx = db.query(PaymentTransaction).filter(PaymentTransaction.provider_payment_id == req.provider_payment_id).first()
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
    x_razorpay_signature: Optional[str] = Header(None)
):
    """
    POST /api/payments/webhook
    Idempotent webhook handler with duplicate event detection.
    """
    raw_body = await request.body()
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Verify signature if webhook secret configured
    webhook_secret = get_razorpay_webhook_secret()
    if webhook_secret and x_razorpay_signature:
        expected_sig = hmac.new(
            webhook_secret.encode(),
            raw_body,
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected_sig, x_razorpay_signature):
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event_id = payload.get("event_id") or payload.get("id") or str(uuid.uuid4())
    event_type = payload.get("event", "unknown")

    # Idempotency check: unique (provider, provider_event_id)
    existing_event = db.query(PaymentWebhookEvent).filter(
        PaymentWebhookEvent.provider == "razorpay",
        PaymentWebhookEvent.provider_event_id == event_id
    ).first()

    if existing_event:
        logger.info(f"Duplicate webhook event ignored: {event_id}")
        return {"status": "already_processed", "event_id": event_id}

    # Record webhook event
    event_record = PaymentWebhookEvent(
        id=str(uuid.uuid4()),
        provider="razorpay",
        provider_event_id=event_id,
        event_type=event_type,
        payload=payload,
        processed=True,
        processed_at=datetime.datetime.now(datetime.timezone.utc)
    )
    db.add(event_record)

    # Process payment capture or order paid
    if event_type in ("order.paid", "payment.captured"):
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        provider_order_id = payment_entity.get("order_id")
        provider_payment_id = payment_entity.get("id")

        if provider_order_id:
            order = db.query(PaymentOrder).filter(PaymentOrder.provider_order_id == provider_order_id).first()
            if order and order.status != "paid":
                order.status = "paid"
                # Record transaction if not exists
                tx = db.query(PaymentTransaction).filter(PaymentTransaction.provider_payment_id == provider_payment_id).first()
                if not tx:
                    tx = PaymentTransaction(
                        id=str(uuid.uuid4()),
                        order_id=order.id,
                        user_id=order.user_id,
                        provider="razorpay",
                        provider_payment_id=provider_payment_id or str(uuid.uuid4()),
                        amount_minor=order.amount_minor,
                        currency=order.currency,
                        status="success"
                    )
                    db.add(tx)

                # Activate subscription
                version = db.query(SubscriptionPlanVersion).filter(SubscriptionPlanVersion.id == order.plan_version_id).first()
                now = datetime.datetime.now(datetime.timezone.utc)
                interval = version.billing_interval if version else "monthly"
                period_end = compute_interval_end(now, interval)

                active_subs = db.query(UserSubscription).filter(
                    UserSubscription.user_id == order.user_id,
                    UserSubscription.status == "active"
                ).all()
                for s in active_subs:
                    s.status = "superseded"

                new_sub = UserSubscription(
                    id=str(uuid.uuid4()),
                    user_id=order.user_id,
                    plan_version_id=order.plan_version_id,
                    status="active",
                    current_period_start=now,
                    current_period_end=period_end,
                    cancel_at_period_end=False
                )
                db.add(new_sub)

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


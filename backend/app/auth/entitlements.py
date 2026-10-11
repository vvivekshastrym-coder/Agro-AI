"""Agro AI Entitlements & Usage Enforcement Engine
Enforces subscription plan limits on server-side capabilities:
- kisan_chat (Kisan GPT)
- diagnose_leaf (Leaf Diagnosis)
- mandi_price (Mandi Price Live Ingestion)
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import datetime
import uuid

from ..database.models import UserSubscription, SubscriptionPlanVersion, PlanEntitlement, SubscriptionUsage

# Baseline monthly allowances for free tier accounts
FREE_TIER_LIMITS: Dict[str, Optional[int]] = {
    "kisan_chat": 15,     # 15 messages / month
    "diagnose_leaf": 5,    # 5 leaf scans / month
    "mandi_price": 50,     # 50 price lookups / month
}


def get_current_period_start(sub: Optional[UserSubscription] = None) -> datetime.datetime:
    """Computes UTC period start for usage accounting."""
    now = datetime.datetime.now(datetime.timezone.utc)
    if sub and sub.current_period_start:
        return sub.current_period_start
    # Fallback to 1st of current calendar month at 00:00:00 UTC
    return datetime.datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)


def check_and_consume_entitlement(
    db: Session,
    user_id: str,
    feature_key: str,
    consume: bool = True
) -> Dict[str, Any]:
    """
    Checks if a user is entitled to execute feature_key and optionally consumes 1 unit.
    Raises HTTPException 402/403 if disallowed or limit exceeded.
    """
    now = datetime.datetime.now(datetime.timezone.utc)

    # 1. Look up active subscription
    sub = db.query(UserSubscription).filter(
        UserSubscription.user_id == user_id,
        UserSubscription.status == "active"
    ).first()

    # Check expiration
    if sub and sub.current_period_end:
        sub_end = sub.current_period_end.replace(tzinfo=datetime.timezone.utc) if sub.current_period_end.tzinfo is None else sub.current_period_end
        if sub_end < now:
            sub.status = "expired"
            db.commit()
            sub = None

    limit: Optional[int] = None
    plan_name: str = "Free Tier"

    if sub:
        # User has an active subscription
        version = db.query(SubscriptionPlanVersion).filter(
            SubscriptionPlanVersion.id == sub.plan_version_id
        ).first()
        if version:
            plan_name = version.name

        entitlement = db.query(PlanEntitlement).filter(
            PlanEntitlement.plan_version_id == sub.plan_version_id,
            PlanEntitlement.feature_key == feature_key
        ).first()

        if entitlement:
            if not entitlement.enabled:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": {
                            "code": "FEATURE_DISABLED",
                            "message": f"Feature '{feature_key}' is not included in your active plan ({plan_name}).",
                            "feature": feature_key,
                            "plan": plan_name
                        }
                    }
                )
            limit = entitlement.usage_limit  # None means unlimited
        else:
            # Default to unlimited if not specifically constrained in paid version
            limit = None
    else:
        # Free Tier baseline: if payment options / plans are not yet published, grant unlimited free access
        from ..database.models import SubscriptionPlan
        published_plans_count = db.query(SubscriptionPlan).filter(SubscriptionPlan.status == "published").count()
        if published_plans_count == 0:
            limit = None
            plan_name = "Free Farmer Access"
        else:
            limit = FREE_TIER_LIMITS.get(feature_key, 5)

    # 2. Check and consume usage if limit is enforced
    period_start = get_current_period_start(sub)

    usage = db.query(SubscriptionUsage).filter(
        SubscriptionUsage.user_id == user_id,
        SubscriptionUsage.feature_key == feature_key,
        SubscriptionUsage.period_start == period_start
    ).first()

    current_used = usage.used if usage else 0

    if limit is not None and current_used >= limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": {
                    "code": "USAGE_LIMIT_EXCEEDED",
                    "message": f"Monthly limit of {limit} for {feature_key.replace('_', ' ').title()} has been reached. Please upgrade your plan.",
                    "feature": feature_key,
                    "plan": plan_name,
                    "limit": limit,
                    "used": current_used
                }
            }
        )

    if consume:
        if not usage:
            usage = SubscriptionUsage(
                id=str(uuid.uuid4()),
                user_id=user_id,
                feature_key=feature_key,
                period_start=period_start,
                used=1
            )
            db.add(usage)
        else:
            usage.used += 1
        db.commit()
        current_used += 1

    return {
        "allowed": True,
        "feature": feature_key,
        "plan": plan_name,
        "limit": limit,
        "used": current_used,
        "unlimited": (limit is None)
    }

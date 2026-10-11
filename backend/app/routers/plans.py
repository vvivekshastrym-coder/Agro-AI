"""Farmer-facing Subscription Plans & Entitlements API
Allows farmers to inspect published membership plans, active subscriptions, and feature quotas.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
import datetime

from ..database.connection import get_db
from ..database.models import (
    SubscriptionPlan, SubscriptionPlanVersion, PlanEntitlement,
    UserSubscription, SubscriptionUsage, User
)
from ..auth.deps import get_current_user
from ..auth.entitlements import FREE_TIER_LIMITS, get_current_period_start

router = APIRouter()


@router.get("")
async def get_published_plans(db: Session = Depends(get_db)):
    """
    GET /api/plans
    Returns all publicly available, published subscription plans and their published versions.
    Does not expose draft, paused, or archived plans.
    """
    plans = db.query(SubscriptionPlan).filter(SubscriptionPlan.status == "published").all()
    out = []
    for p in plans:
        # Find published versions
        versions = db.query(SubscriptionPlanVersion).filter(
            SubscriptionPlanVersion.plan_id == p.id,
            SubscriptionPlanVersion.is_published == True
        ).order_by(SubscriptionPlanVersion.version.desc()).all()

        if not versions:
            continue

        ver_list = []
        for v in versions:
            entitlements = {
                e.feature_key: {
                    "enabled": e.enabled,
                    "usage_limit": e.usage_limit,
                    "limit_period": e.limit_period
                } for e in v.entitlements
            }
            ver_list.append({
                "id": v.id,
                "version": v.version,
                "name": v.name,
                "description": v.description,
                "price_minor": v.price_minor,
                "price_formatted": f"₹{v.price_minor / 100:.2f}",
                "currency": v.currency,
                "billing_interval": v.billing_interval,
                "trial_days": v.trial_days,
                "benefits": v.benefits,
                "entitlements": entitlements
            })

        out.append({
            "id": p.id,
            "slug": p.slug,
            "status": p.status,
            "versions": ver_list
        })
    return out


@router.get("/me")
async def get_my_subscription_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    GET /api/plans/me
    Returns current caller's active plan, expiry date, and real-time usage for gated features.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    sub = db.query(UserSubscription).filter(
        UserSubscription.user_id == user.id,
        UserSubscription.status == "active"
    ).first()

    if sub and sub.current_period_end:
        sub_end = sub.current_period_end.replace(tzinfo=datetime.timezone.utc) if sub.current_period_end.tzinfo is None else sub.current_period_end
        if sub_end < now:
            sub.status = "expired"
            db.commit()
            sub = None

    period_start = get_current_period_start(sub)

    # Calculate usages for gated features
    usage_map = {}
    features = ["kisan_chat", "diagnose_leaf", "mandi_price"]

    for feat in features:
        u_rec = db.query(SubscriptionUsage).filter(
            SubscriptionUsage.user_id == user.id,
            SubscriptionUsage.feature_key == feat,
            SubscriptionUsage.period_start == period_start
        ).first()
        used = u_rec.used if u_rec else 0

        # Determine limit
        limit = None
        enabled = True
        if sub:
            ent = db.query(PlanEntitlement).filter(
                PlanEntitlement.plan_version_id == sub.plan_version_id,
                PlanEntitlement.feature_key == feat
            ).first()
            if ent:
                enabled = ent.enabled
                limit = ent.usage_limit
        else:
            published_plans_count = db.query(SubscriptionPlan).filter(SubscriptionPlan.status == "published").count()
            if published_plans_count == 0:
                limit = None
            else:
                limit = FREE_TIER_LIMITS.get(feat, 5)

        usage_map[feat] = {
            "used": used,
            "limit": limit,
            "unlimited": (limit is None),
            "enabled": enabled
        }

    plan_info = None
    if sub:
        v = db.query(SubscriptionPlanVersion).filter(SubscriptionPlanVersion.id == sub.plan_version_id).first()
        plan_info = {
            "subscription_id": sub.id,
            "plan_name": v.name if v else "Premium Plan",
            "billing_interval": v.billing_interval if v else "monthly",
            "current_period_start": sub.current_period_start.isoformat() if sub.current_period_start else None,
            "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
            "cancel_at_period_end": sub.cancel_at_period_end,
            "status": sub.status
        }

    return {
        "has_active_subscription": bool(sub),
        "plan": plan_info or {"plan_name": "Free Farmer Access", "status": "active"},
        "period_start": period_start.isoformat(),
        "usages": usage_map
    }

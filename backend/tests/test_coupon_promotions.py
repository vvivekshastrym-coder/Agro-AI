"""Tests for promotional offer discount coupons verified against Super Admin approved broadcasts."""
import os, sys, uuid, time
import pytest
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric import ec
import jwt

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.auth import deps
from app.database.connection import SessionLocal
from app.database.models import (
    User, AdminUser, AdminUserRole, SubscriptionPlan, SubscriptionPlanVersion,
    BroadcastItem, BroadcastType, BroadcastStatus, PaymentOrder
)

_KEY = ec.generate_private_key(ec.SECP256R1())

class _FakeJWKS:
    def get_signing_key_from_jwt(self, token):
        class K: key = _KEY.public_key()
        return K()

@pytest.fixture(autouse=True)
def _patch_jwks(monkeypatch):
    monkeypatch.setattr(deps, "_get_jwks_client", lambda: _FakeJWKS())

client = TestClient(app)

def token(sub, key=_KEY, alg="ES256", aud="authenticated", exp_delta=3600, **extra):
    claims = {"sub": sub, "aud": aud, "exp": int(time.time()) + exp_delta, "email": f"{sub}@farm.test", **extra}
    return jwt.encode(claims, key, algorithm=alg)

def auth(sub):
    return {"Authorization": f"Bearer {token(sub)}"}

def test_coupon_discount_applied_on_checkout():
    db = SessionLocal()
    # 1. Setup Super Admin
    admin_sub = "test_sa_admin"
    sa_user = db.query(User).filter(User.id == admin_sub).first()
    if not sa_user:
        sa_user = User(id=admin_sub, phone="+919876500099", role="admin")
        db.add(sa_user)
    sa_role = db.query(AdminUser).filter(AdminUser.user_id == admin_sub).first()
    if not sa_role:
        sa_role = AdminUser(id=str(uuid.uuid4()), user_id=admin_sub, role=AdminUserRole.super_admin, is_active=True)
        db.add(sa_role)
    db.commit()

    admin_headers = auth(admin_sub)
    plan_slug = f"test_plan_{uuid.uuid4().hex[:6]}"

    # Create plan container
    p_res = client.post("/api/admin/plans", headers=admin_headers, json={"slug": plan_slug})
    assert p_res.status_code == 200
    plan_id = p_res.json()["id"]

    # Create version (₹200 = 20000 minor)
    v_res = client.post(f"/api/admin/plans/{plan_id}/versions", headers=admin_headers, json={
        "name": "Test Membership",
        "price_minor": 20000,
        "currency": "INR",
        "billing_interval": "monthly"
    })
    assert v_res.status_code == 200
    vid = v_res.json()["id"]

    # Publish version & plan
    client.post(f"/api/admin/plans/{plan_id}/versions/{vid}/publish", headers=admin_headers)
    client.patch(f"/api/admin/plans/{plan_id}/status", headers=admin_headers, json={"status": "published"})

    # 2. Create approved coupon offer (25% off)
    test_code = f"TEST{uuid.uuid4().hex[:4].upper()}"
    offer = BroadcastItem(
        id=str(uuid.uuid4()),
        item_type=BroadcastType.offer,
        title="Test Promotion 25%",
        content="25% off for test",
        discount_percent=25.0,
        discount_code=test_code,
        target_plan_slug=plan_slug,
        status=BroadcastStatus.approved
    )
    db.add(offer)
    db.commit()
    offer_id = offer.id
    db.close()

    try:
        # Checkout WITH coupon
        buyer = f"farmer_{uuid.uuid4().hex[:6]}"
        res = client.post("/api/payments/create-order", headers=auth(buyer), json={
            "plan_version_id": vid,
            "coupon_code": test_code
        })
        assert res.status_code == 200
        data = res.json()
        assert data["amount_minor"] == 15000  # 20000 - 25% (5000) = 15000 (₹150.00)
        assert data["discount_minor"] == 5000
        assert data["coupon_applied"] == test_code
        assert data["amount_formatted"] == "₹150.00"

        # Checkout WITHOUT coupon should be full price (₹200.00)
        res_full = client.post("/api/payments/create-order", headers=auth(buyer), json={
            "plan_version_id": vid
        })
        assert res_full.status_code == 200
        data_full = res_full.json()
        assert data_full["amount_minor"] == 20000
        assert data_full["coupon_applied"] is None
        assert data_full["discount_minor"] == 0

        # Cleanup created orders
        db = SessionLocal()
        orders = db.query(PaymentOrder).filter(PaymentOrder.plan_version_id == vid).all()
        for o in orders:
            db.delete(o)
        db.commit()
        db.close()
    finally:
        # Teardown test offer, version, and plan
        db = SessionLocal()
        del_offer = db.query(BroadcastItem).filter(BroadcastItem.id == offer_id).first()
        if del_offer:
            db.delete(del_offer)
        del_ver = db.query(SubscriptionPlanVersion).filter(SubscriptionPlanVersion.id == vid).first()
        if del_ver:
            db.delete(del_ver)
        del_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
        if del_plan:
            db.delete(del_plan)
        db.commit()
        db.close()

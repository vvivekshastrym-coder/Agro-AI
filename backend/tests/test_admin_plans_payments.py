"""Automated verification tests for:
- Phase 1 & 2: Admin users, roles, RBAC enforcement
- Phase 3: Subscription plan draft / versioning / publishing
- Phase 4: Entitlements and usage quota enforcement (kisan_chat, diagnose_leaf)
- Phase 5: Payment order creation, verification, and idempotent webhooks
- Phase 7: Tamper-evident admin audit logs & data requests
"""
import os, sys, tempfile, time, datetime, uuid
import pytest
import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

# Ensure test DB isolation
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.auth import deps
from app.database.connection import SessionLocal
from app.database.models import (
    User, AdminUser, AdminUserRole, SubscriptionPlan, SubscriptionPlanVersion,
    PlanEntitlement, UserSubscription, SubscriptionUsage, PaymentOrder,
    PaymentTransaction, PaymentWebhookEvent, AdminAuditLog, DataRequest
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


def test_non_admin_blocked_from_admin_console():
    """Regular farmer accounts cannot view or modify administrative plans."""
    res = client.get("/api/admin/plans", headers=auth("farmer_rajesh"))
    # If no admins exist yet, first caller bootstraps as super_admin, subsequent callers are rejected.
    # We verify that a second non-admin is strictly forbidden.
    res2 = client.get("/api/admin/plans", headers=auth("farmer_suresh"))
    assert res2.status_code == 403
    assert res2.json()["detail"]["error"]["code"] == "ADMIN_FORBIDDEN"


def test_plan_lifecycle_and_publishing():
    """Draft plans cannot be purchased; once published, they are visible and purchaseable."""
    # First admin bootstrap
    admin_auth = auth("farmer_rajesh")

    # 1. Create a draft plan
    slug = f"plan_{uuid.uuid4().hex[:8]}"
    p_res = client.post("/api/admin/plans", headers=admin_auth, json={"slug": slug})
    assert p_res.status_code == 200
    plan_id = p_res.json()["id"]

    # 2. Add version 1 with entitlements
    v_res = client.post(f"/api/admin/plans/{plan_id}/versions", headers=admin_auth, json={
        "name": "Kisan Plus Monthly",
        "description": "Premium diagnosis and expert advisory",
        "price_minor": 49900,  # ₹499.00
        "currency": "INR",
        "billing_interval": "monthly",
        "trial_days": 7,
        "benefits": ["Unlimited Kisan GPT", "100 Leaf Scans/mo", "Live Mandi Ingestion"],
        "entitlements": {
            "kisan_chat": {"enabled": True, "usage_limit": None},
            "diagnose_leaf": {"enabled": True, "usage_limit": 100},
            "mandi_price": {"enabled": True, "usage_limit": None}
        }
    })
    assert v_res.status_code == 200
    version_id = v_res.json()["id"]

    # 3. Verify draft plan is NOT visible to public farmers
    pub_plans = client.get("/api/plans").json()
    assert not any(p["id"] == plan_id for p in pub_plans)

    # 4. Attempting to purchase a draft version fails
    order_fail = client.post("/api/payments/create-order", headers=auth("farmer_suresh"), json={
        "plan_version_id": version_id
    })
    assert order_fail.status_code == 404

    # 5. Publish version
    pub_res = client.post(f"/api/admin/plans/{plan_id}/versions/{version_id}/publish", headers=admin_auth)
    assert pub_res.status_code == 200
    assert pub_res.json()["is_published"] is True

    # 6. Now published plan version is visible in public plans
    pub_plans_after = client.get("/api/plans").json()
    matching_plan = next((p for p in pub_plans_after if p["id"] == plan_id), None)
    assert matching_plan is not None
    assert matching_plan["versions"][0]["price_minor"] == 49900


def test_payment_order_and_subscription_activation():
    """Checkout correctly charges server-side price and activates user subscription."""
    admin_auth = auth("farmer_rajesh")
    buyer_auth = auth("farmer_suresh")

    # Fetch published plans
    plans = client.get("/api/plans").json()
    assert len(plans) > 0
    version = plans[0]["versions"][0]
    version_id = version["id"]
    expected_price = version["price_minor"]

    # Create payment order
    order_res = client.post("/api/payments/create-order", headers=buyer_auth, json={
        "plan_version_id": version_id
    })
    assert order_res.status_code == 200
    order_data = order_res.json()
    assert order_data["amount_minor"] == expected_price
    order_id = order_data["order_id"]

    # Verify payment
    tx_id = f"pay_{uuid.uuid4().hex[:8]}"
    verify_res = client.post("/api/payments/verify-payment", headers=buyer_auth, json={
        "order_id": order_id,
        "provider_payment_id": tx_id,
        "provider_signature": "valid_sandbox_sig"
    })
    assert verify_res.status_code == 200
    assert verify_res.json()["success"] is True
    assert verify_res.json()["status"] == "active"

    # Farmer's subscription profile shows active plan
    my_plan = client.get("/api/plans/me", headers=buyer_auth).json()
    assert my_plan["has_active_subscription"] is True
    assert my_plan["plan"]["plan_name"] == version["name"]


def test_entitlement_usage_quota_enforcement():
    """Exceeding feature limit raises 402 with structured USAGE_LIMIT_EXCEEDED error."""
    farmer_id = "farmer_quota_test"
    farmer_auth = auth(farmer_id)

    # Free tier limit for leaf diagnosis is 5. We consume all 5 and check 6th is rejected.
    db = SessionLocal()
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        period_start = datetime.datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
        usage = SubscriptionUsage(
            id=str(uuid.uuid4()),
            user_id=farmer_id,
            feature_key="diagnose_leaf",
            period_start=period_start,
            used=5
        )
        db.add(usage)
        db.commit()
    finally:
        db.close()

    # Attempting diagnosis when usage >= limit
    fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    res = client.post(
        "/api/diagnosis/analyze",
        headers=farmer_auth,
        files={"image": ("test.png", fake_png, "image/png")}
    )
    assert res.status_code == 402
    assert res.json()["detail"]["error"]["code"] == "USAGE_LIMIT_EXCEEDED"
    assert res.json()["detail"]["error"]["feature"] == "diagnose_leaf"


def test_webhook_idempotency():
    """Duplicate provider event IDs are safely ignored without duplicate processing."""
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    payload = {
        "event_id": event_id,
        "event": "order.paid",
        "payload": {
            "payment": {
                "entity": {
                    "id": f"pay_{uuid.uuid4().hex[:8]}",
                    "order_id": "non_existent_order",
                    "method": "upi"
                }
            }
        }
    }

    # First delivery
    res1 = client.post("/api/payments/webhook", json=payload)
    assert res1.status_code == 200
    assert res1.json()["status"] == "processed"

    # Second duplicate delivery
    res2 = client.post("/api/payments/webhook", json=payload)
    assert res2.status_code == 200
    assert res2.json()["status"] == "already_processed"


def test_admin_audit_logs_recorded():
    """Privileged actions record tamper-evident audit logs."""
    admin_auth = auth("farmer_rajesh")
    logs = client.get("/api/admin/audit-logs", headers=admin_auth).json()
    assert len(logs) > 0
    actions = [l["action"] for l in logs]
    assert "CREATE_PLAN" in actions or "PUBLISH_PLAN_VERSION" in actions


def test_data_privacy_requests_processing():
    """Admins can view and process GDPR data requests."""
    admin_auth = auth("farmer_rajesh")
    db = SessionLocal()
    req_id = str(uuid.uuid4())
    try:
        dr = DataRequest(
            id=req_id,
            user_id="farmer_suresh",
            request_type="export",
            status="pending"
        )
        db.add(dr)
        db.commit()
    finally:
        db.close()

    # List requests
    reqs = client.get("/api/admin/data-requests", headers=admin_auth).json()
    assert any(r["id"] == req_id for r in reqs)

    # Process request
    proc_res = client.post(f"/api/admin/data-requests/{req_id}/process", headers=admin_auth, json={
        "status": "completed",
        "admin_notes": "Data package generated and sent to farmer"
    })
    assert proc_res.status_code == 200
    assert proc_res.json()["status"] == "completed"


def test_super_admin_can_delete_published_plan():
    """Head Super Admin has executive authority to delete a published subscription plan."""
    admin_auth = auth("farmer_rajesh")
    plan_slug = f"test-delete-plan-{int(time.time())}"

    # 1. Create plan
    c_res = client.post("/api/admin/plans", headers=admin_auth, json={"slug": plan_slug})
    assert c_res.status_code == 200
    plan_id = c_res.json()["id"]

    # 2. Create version
    v_res = client.post(f"/api/admin/plans/{plan_id}/versions", headers=admin_auth, json={
        "name": "Kisan Test To Delete",
        "description": "Plan to be deleted",
        "price_minor": 19900,
        "currency": "INR",
        "billing_interval": "monthly",
        "trial_days": 7,
        "benefits": ["Benefit 1"],
        "entitlements": {
            "kisan_chat": {"enabled": True, "usage_limit": None, "limit_period": "monthly"},
            "diagnose_leaf": {"enabled": True, "usage_limit": 50, "limit_period": "monthly"}
        }
    })
    assert v_res.status_code == 200
    ver_id = v_res.json()["id"]

    # 3. Publish version (makes plan published)
    pub_res = client.post(f"/api/admin/plans/{plan_id}/versions/{ver_id}/publish", headers=admin_auth)
    assert pub_res.status_code == 200

    # 4. Delete the published plan as Super Admin
    del_res = client.delete(f"/api/admin/plans/{plan_id}", headers=admin_auth)
    assert del_res.status_code == 200
    assert "successfully deleted" in del_res.json()["message"]

    # 5. Verify plan is no longer returned in plans list
    plans = client.get("/api/admin/plans", headers=admin_auth).json()
    assert not any(p["id"] == plan_id for p in plans)


def test_super_admin_can_delete_published_plan_version():
    """Super Admin can delete a specific published version from a multi-version plan."""
    admin_auth = auth("farmer_rajesh")
    plan_slug = f"test-multiversion-{int(time.time())}"

    # Create plan
    p = client.post("/api/admin/plans", headers=admin_auth, json={"slug": plan_slug}).json()
    plan_id = p["id"]

    # Create v1
    v1 = client.post(f"/api/admin/plans/{plan_id}/versions", headers=admin_auth, json={
        "name": "Version 1",
        "price_minor": 19900,
        "billing_interval": "monthly",
        "entitlements": {"kisan_chat": {"enabled": True}}
    }).json()

    # Publish v1
    client.post(f"/api/admin/plans/{plan_id}/versions/{v1['id']}/publish", headers=admin_auth)

    # Delete v1
    del_v = client.delete(f"/api/admin/plans/{plan_id}/versions/{v1['id']}", headers=admin_auth)
    assert del_v.status_code == 200
    assert "successfully deleted" in del_v.json()["message"]


def test_non_super_admin_forbidden_from_deleting_plan():
    """Only Super Admin can delete plans; regular users or non-super admins are forbidden."""
    # Farmer Suresh has no super admin rights
    suresh_auth = auth("farmer_suresh")
    res = client.delete("/api/admin/plans/some-plan-id", headers=suresh_auth)
    assert res.status_code == 403


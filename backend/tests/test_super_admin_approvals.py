"""Automated verification tests for Super Admin Access Approval Architecture & Decision Hierarchy:
1. Super Admin (vvivekshastrym@gmail.com / Vivek@123) direct authentication.
2. Unapproved staff access gate (HTTP 403 APPROVAL_REQUIRED).
3. Staff access request submission and approval queue.
4. Super Admin approval & role grant workflow.
5. Decision Hierarchy: Super Admin exclusive authority over plan publishing & lifecycle transitions.
6. Revocation of staff access.
"""
import os, sys, time, uuid
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database.connection import SessionLocal
from app.database.models import User, AdminUser, AdminUserRole, AdminAccessRequest, SubscriptionPlan, SubscriptionPlanVersion

client = TestClient(app)


def test_super_admin_login_success():
    """Head Super Admin (vvivekshastrym@gmail.com) can log in with Vivek@123."""
    res = client.post("/api/admin/login", json={
        "email": "vvivekshastrym@gmail.com",
        "password": "Vivek@123"
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["role"] == "super_admin"
    assert data["user"]["email"] == "vvivekshastrym@gmail.com"


def test_super_admin_login_wrong_password_fails():
    """Incorrect password for Super Admin returns HTTP 401."""
    res = client.post("/api/admin/login", json={
        "email": "vvivekshastrym@gmail.com",
        "password": "WrongPassword123"
    })
    assert res.status_code == 401
    assert res.json()["detail"]["error"]["code"] == "INVALID_CREDENTIALS"


def test_unapproved_staff_cannot_login():
    """Unregistered or unapproved staff cannot log in to admin panel."""
    res = client.post("/api/admin/login", json={
        "email": "unapproved_worker@agroai.internal",
        "password": "WorkerPass@123"
    })
    assert res.status_code in (401, 403)


def test_staff_request_access_and_approval_workflow():
    """Full workflow: staff requests access -> Super Admin approves -> staff logs in -> role enforced."""
    # 1. Super Admin logs in to obtain super admin token
    sa_res = client.post("/api/admin/login", json={
        "email": "vvivekshastrym@gmail.com",
        "password": "Vivek@123"
    })
    sa_token = sa_res.json()["access_token"]
    sa_headers = {"Authorization": f"Bearer {sa_token}"}

    # 2. Company worker submits access request
    worker_email = f"worker_{uuid.uuid4().hex[:6]}@agroai.internal"
    worker_pwd = "SecretWorker@2026"
    req_res = client.post("/api/admin/request-access", json={
        "email": worker_email,
        "full_name": "Ramesh Kumar (Plan Analyst)",
        "password": worker_pwd,
        "requested_role": "plan_manager",
        "notes": "Joining the Pricing & Plans team"
    })
    assert req_res.status_code == 200
    assert req_res.json()["status"] == "pending"

    # 3. Worker tries to login BEFORE Super Admin approval -> rejected with HTTP 403 APPROVAL_REQUIRED
    pre_login = client.post("/api/admin/login", json={
        "email": worker_email,
        "password": worker_pwd
    })
    assert pre_login.status_code == 403
    assert pre_login.json()["detail"]["error"]["code"] == "APPROVAL_REQUIRED"

    # 4. Super Admin lists pending requests and finds worker
    reqs = client.get("/api/admin/access-requests", headers=sa_headers).json()
    worker_req = next(r for r in reqs if r["email"] == worker_email)
    assert worker_req["status"] == "pending"

    # 5. Super Admin approves worker request with role 'plan_manager'
    appr_res = client.post(
        f"/api/admin/access-requests/{worker_req['id']}/approve",
        headers=sa_headers,
        json={"role": "plan_manager"}
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "approved"

    # 6. Worker can now log in successfully and receives 'plan_manager' role
    login_res = client.post("/api/admin/login", json={
        "email": worker_email,
        "password": worker_pwd
    })
    assert login_res.status_code == 200
    worker_token = login_res.json()["access_token"]
    assert login_res.json()["role"] == "plan_manager"
    worker_headers = {"Authorization": f"Bearer {worker_token}"}

    # 7. Decision Hierarchy Enforcement:
    # A) Worker CAN create draft plan and version
    slug = f"plan_{uuid.uuid4().hex[:6]}"
    p_res = client.post("/api/admin/plans", headers=worker_headers, json={"slug": slug})
    assert p_res.status_code == 200
    plan_id = p_res.json()["id"]

    v_res = client.post(f"/api/admin/plans/{plan_id}/versions", headers=worker_headers, json={
        "name": "Kisan Pro Staff Draft",
        "price_minor": 29900,
        "billing_interval": "monthly"
    })
    assert v_res.status_code == 200
    version_id = v_res.json()["id"]

    # B) Worker CANNOT publish the version -> must be Super Admin decision
    pub_fail = client.post(f"/api/admin/plans/{plan_id}/versions/{version_id}/publish", headers=worker_headers)
    assert pub_fail.status_code == 403
    assert pub_fail.json()["detail"]["error"]["code"] == "INSUFFICIENT_ROLE"

    # C) Worker CANNOT change plan status
    status_fail = client.patch(f"/api/admin/plans/{plan_id}/status", headers=worker_headers, json={"status": "published"})
    assert status_fail.status_code == 403

    # D) Super Admin DOES have authority to publish the plan
    pub_ok = client.post(f"/api/admin/plans/{plan_id}/versions/{version_id}/publish", headers=sa_headers)
    assert pub_ok.status_code == 200
    assert pub_ok.json()["is_published"] is True

    # 8. Super Admin can revoke worker access
    db = SessionLocal()
    u = db.query(User).filter(User.email == worker_email).first()
    worker_uid = u.id
    db.close()

    revoke_res = client.post("/api/admin/users/assign-role", headers=sa_headers, json={
        "user_id": worker_uid,
        "is_active": False
    })
    assert revoke_res.status_code == 200
    assert revoke_res.json()["is_active"] is False

    # Worker can no longer log in after revocation
    post_revoke_login = client.post("/api/admin/login", json={
        "email": worker_email,
        "password": worker_pwd
    })
    assert post_revoke_login.status_code == 403

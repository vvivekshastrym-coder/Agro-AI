"""Comprehensive automated tests for the 3-Tier Role-Based Admin Console (Phases 1–15):
1. Level 1 Super Admin Head -> Level 2 Admin -> Level 3 Staff hierarchy & permissions matrix.
2. Delegation boundaries, privilege escalation prevention, and Super Admin Head protection.
3. Overview 9-module real-time metrics, system status, and audit feed.
4. Agro AI Mart & Posts/Offers workflow + strict self-approval prevention + customer draft isolation.
5. Excel Data Registry: file/dataset validation, duplicate & invalid row detection, error CSV export,
   review/approval/publication to MarketPrice, and rollback.
6. Subscription Plans: Admin draft creation vs Super Admin Head exclusive publishing.
7. Payment Orders: strict prevention of manual override of unverified payments to paid.
8. Data Requests workflow: OPEN -> ASSIGNED -> IN_PROGRESS -> RESOLVED.
9. Security Audit Logs: immutability (403 on DELETE/PATCH/PUT), secret redaction, and RBAC protection.
"""
import os
import sys
import uuid
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database.connection import SessionLocal
from app.database.models import MarketPrice, PaymentOrder
from app.routers.admin import _sanitize_audit_payload

client = TestClient(app)


def _get_super_admin_headers():
    res = client.post("/api/admin/login", json={
        "email": "vvivekshastrym@gmail.com",
        "password": "Vivek@123"
    })
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, res.json()["user"]["id"]


def _create_and_approve_worker(sa_headers, role: str, name_prefix: str):
    email = f"{name_prefix}_{uuid.uuid4().hex[:6]}@agroai.internal"
    pwd = "WorkerSecure@2026"
    req = client.post("/api/admin/request-access", json={
        "email": email,
        "full_name": f"{name_prefix.title()} User",
        "password": pwd,
        "requested_role": role,
        "notes": f"Automated test for {role}"
    })
    assert req.status_code == 200, req.text
    reqs = client.get("/api/admin/access-requests", headers=sa_headers).json()
    target = next(r for r in reqs if r["email"] == email)

    appr = client.post(
        f"/api/admin/access-requests/{target['id']}/approve",
        headers=sa_headers,
        json={"role": role}
    )
    assert appr.status_code == 200, appr.text

    login = client.post("/api/admin/login", json={"email": email, "password": pwd})
    assert login.status_code == 200, login.text
    data = login.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]["id"], email


def test_super_admin_head_identity_matrix_and_overview():
    """Verify Level 1 Super Admin Head profile, 9 authorized modules, role matrix, and live overview metrics."""
    sa_headers, sa_id = _get_super_admin_headers()

    me = client.get("/api/admin/me", headers=sa_headers)
    assert me.status_code == 200
    me_data = me.json()
    assert me_data["hierarchy_level"] == "SUPER_ADMIN_HEAD"
    assert me_data["is_super_admin"] is True
    assert len(me_data["authorized_modules"]) == 9

    matrix = client.get("/api/admin/roles/matrix", headers=sa_headers)
    assert matrix.status_code == 200
    m_data = matrix.json()
    assert "SUPER_ADMIN_HEAD" in m_data["hierarchy_levels"]
    assert "ADMIN" in m_data["hierarchy_levels"]
    assert "STAFF" in m_data["hierarchy_levels"]
    assert "excel_registry" in m_data["modules"]

    overview = client.get("/api/admin/overview/metrics", headers=sa_headers)
    assert overview.status_code == 200
    ov = overview.json()
    for key in (
        "registered_users", "total_farmers", "active_subscriptions", "total_orders",
        "published_posts_offers", "pending_posts_offers", "pending_farmer_applications",
        "pending_product_approvals", "recent_excel_imports_count", "pending_excel_imports_count",
        "published_subscription_plans_count", "verified_payments_count", "open_data_requests_count",
        "recent_audit_activity", "system_status"
    ):
        assert key in ov, f"Missing overview key: {key}"
    assert ov["system_status"]["database"] == "Connected"
    assert ov["system_status"]["super_admin_head"] == "vvivekshastrym@gmail.com"


def test_three_tier_hierarchy_and_delegation_boundaries():
    """Verify Level 1 -> Level 2 -> Level 3 role assignment, escalation blocks, and owner protection."""
    sa_headers, sa_id = _get_super_admin_headers()

    # Create a Level 2 Admin and a Level 3 Staff user
    admin_headers, admin_uid, _ = _create_and_approve_worker(sa_headers, "admin", "level2_admin")
    staff_headers, staff_uid, _ = _create_and_approve_worker(sa_headers, "staff", "level3_staff")

    # Verify /api/admin/me hierarchy levels
    admin_me = client.get("/api/admin/me", headers=admin_headers).json()
    assert admin_me["hierarchy_level"] == "ADMIN"

    staff_me = client.get("/api/admin/me", headers=staff_headers).json()
    assert staff_me["hierarchy_level"] == "STAFF"
    assert "audit_logs" not in staff_me["authorized_modules"]
    assert "subscription_plans" not in staff_me["authorized_modules"]

    # 1. Level 3 Staff CANNOT assign roles to anyone (including self)
    staff_escalate = client.post("/api/admin/users/assign-role", headers=staff_headers, json={
        "user_id": staff_uid,
        "role": "super_admin",
        "is_active": True
    })
    assert staff_escalate.status_code == 403

    # 2. Level 2 Admin CANNOT promote anyone to 'admin' or 'super_admin'
    admin_escalate = client.post("/api/admin/users/assign-role", headers=admin_headers, json={
        "user_id": staff_uid,
        "role": "super_admin",
        "is_active": True
    })
    assert admin_escalate.status_code == 403
    assert admin_escalate.json()["detail"]["error"]["code"] == "ROLE_ESCALATION_FORBIDDEN"

    admin_to_admin = client.post("/api/admin/users/assign-role", headers=admin_headers, json={
        "user_id": staff_uid,
        "role": "admin",
        "is_active": True
    })
    assert admin_to_admin.status_code == 403
    assert admin_to_admin.json()["detail"]["error"]["code"] == "ROLE_ESCALATION_FORBIDDEN"

    # 3. Level 2 Admin CANNOT modify Super Admin Head account
    admin_touch_owner = client.post("/api/admin/users/assign-role", headers=admin_headers, json={
        "user_id": sa_id,
        "role": "staff",
        "is_active": False
    })
    assert admin_touch_owner.status_code in (400, 403)
    assert admin_touch_owner.json()["detail"]["error"]["code"] in ("CANNOT_REVOKE_SUPER_ADMIN", "ROLE_ESCALATION_FORBIDDEN")

    # 4. Level 2 Admin CANNOT delegate a permission they do not possess (e.g. subscription_plans:publish)
    admin_bad_perm = client.post("/api/admin/users/assign-role", headers=admin_headers, json={
        "user_id": staff_uid,
        "role": "staff",
        "is_active": True,
        "permissions": {"subscription_plans": ["publish"]}
    })
    assert admin_bad_perm.status_code == 403
    assert admin_bad_perm.json()["detail"]["error"]["code"] == "PERMISSION_ESCALATION_FORBIDDEN"

    # 5. Level 2 Admin CAN delegate valid Staff permissions within their own scope
    admin_valid_delegate = client.post("/api/admin/users/assign-role", headers=admin_headers, json={
        "user_id": staff_uid,
        "role": "staff",
        "is_active": True,
        "permissions": {"posts_offers": ["read", "create", "submit"], "data_requests": ["read", "edit"]}
    })
    assert admin_valid_delegate.status_code == 200
    assert admin_valid_delegate.json()["hierarchy_level"] == "STAFF"


def test_posts_offers_self_approval_prevention_and_draft_isolation():
    """Verify Staff drafts do not appear in public endpoints and authors cannot self-approve."""
    sa_headers, _ = _get_super_admin_headers()
    admin_headers, _, _ = _create_and_approve_worker(sa_headers, "admin", "post_admin")
    staff_headers, _, _ = _create_and_approve_worker(sa_headers, "staff", "post_staff")

    unique_title = f"Monsoon Seed Advisory {uuid.uuid4().hex[:6]}"

    # Level 3 Staff creates and submits a post
    create_res = client.post("/api/admin/broadcasts", headers=staff_headers, json={
        "item_type": "post",
        "title": unique_title,
        "content": "Treat paddy seeds before sowing.",
        "tags": ["paddy", "monsoon"],
        "submit_for_approval": True
    })
    assert create_res.status_code == 200
    post_id = create_res.json()["id"]
    assert create_res.json()["status"] == "pending_approval"

    # Public customer endpoint MUST NOT leak unapproved post
    pub_list = client.get("/api/broadcasts").json()
    assert not any(p["id"] == post_id for p in pub_list)

    # Staff CANNOT approve their own or any post
    staff_appr = client.post(f"/api/admin/broadcasts/{post_id}/approve", headers=staff_headers)
    assert staff_appr.status_code == 403

    # Level 2 Admin submits a post and tries to self-approve -> blocked with SELF_APPROVAL_FORBIDDEN
    admin_post = client.post("/api/admin/broadcasts", headers=admin_headers, json={
        "item_type": "offer",
        "title": f"Admin Self Offer {uuid.uuid4().hex[:6]}",
        "content": "15% off soil testing",
        "discount_percent": 15,
        "discount_code": "SOIL15",
        "submit_for_approval": True
    }).json()
    self_appr = client.post(f"/api/admin/broadcasts/{admin_post['id']}/approve", headers=admin_headers)
    assert self_appr.status_code == 403
    assert self_appr.json()["detail"]["error"]["code"] == "SELF_APPROVAL_FORBIDDEN"

    # Level 2 Admin CAN approve the Staff member's post
    admin_appr_staff = client.post(f"/api/admin/broadcasts/{post_id}/approve", headers=admin_headers)
    assert admin_appr_staff.status_code == 200
    assert admin_appr_staff.json()["status"] == "approved"

    # Now public customer endpoint returns the approved post
    pub_list_after = client.get("/api/broadcasts").json()
    assert any(p["id"] == post_id for p in pub_list_after)

    # Archive the post and verify it leaves the public feed
    arch_res = client.post(f"/api/admin/broadcasts/{post_id}/archive", headers=admin_headers)
    assert arch_res.status_code == 200
    pub_list_archived = client.get("/api/broadcasts").json()
    assert not any(p["id"] == post_id for p in pub_list_archived)


def test_excel_data_registry_validation_publish_and_rollback():
    """Verify Excel Data Registry upload validation, duplicate/error reporting, approval, live publish, and rollback."""
    sa_headers, _ = _get_super_admin_headers()
    admin_headers, _, _ = _create_and_approve_worker(sa_headers, "admin", "excel_admin")
    staff_headers, _, _ = _create_and_approve_worker(sa_headers, "staff", "excel_staff")

    # 1. Reject unsupported file type (.exe)
    bad_ext = client.post(
        "/api/admin/excel-registry/upload",
        headers=staff_headers,
        json={
            "filename": "malware.exe",
            "target_dataset": "mandi_prices",
            "csv_content": "state,district,market,commodity,modal_price\nKarnataka,Mandya,Mandya,Tomato,2000"
        }
    )
    assert bad_ext.status_code == 400
    assert bad_ext.json()["detail"]["error"]["code"] == "INVALID_FILE_TYPE"

    # 2. Reject restricted dataset ('payments' cannot be imported via Excel)
    bad_ds = client.post(
        "/api/admin/excel-registry/upload",
        headers=staff_headers,
        json={
            "filename": "payments.csv",
            "target_dataset": "payments",
            "csv_content": "order_id,status\n1,paid"
        }
    )
    assert bad_ds.status_code == 400
    assert bad_ds.json()["detail"]["error"]["code"] == "RESTRICTED_IMPORT_TARGET"

    # 3. Upload a CSV with 2 valid rows, 1 duplicate row, and 1 invalid row (missing modal_price)
    unique_market = f"TestAPMC_{uuid.uuid4().hex[:6]}"
    csv_content = (
        "state,district,market,commodity,variety,modal_price,min_price,max_price\n"
        f"Karnataka,Mandya,{unique_market},Tomato,Hybrid,2400,2100,2600\n"
        f"Karnataka,Mandya,{unique_market},Onion,Red,1800,1500,2000\n"
        f"Karnataka,Mandya,{unique_market},Tomato,Hybrid,2400,2100,2600\n"
        f"Karnataka,Mandya,{unique_market},Potato,Local,,1200,1500\n"
    )

    upload_res = client.post(
        "/api/admin/excel-registry/upload",
        headers=staff_headers,
        json={
            "filename": "karnataka_mandi.csv",
            "target_dataset": "mandi_prices",
            "csv_content": csv_content
        }
    )
    assert upload_res.status_code == 200, upload_res.text
    job = upload_res.json()
    job_id = job["id"]
    assert job["status"] == "PENDING_REVIEW"
    assert job["total_rows"] == 4
    assert job["valid_rows_count"] == 2
    assert job["duplicate_rows_count"] == 1
    assert job["invalid_rows_count"] == 2  # 1 duplicate + 1 missing modal_price in error_rows

    # 4. Download CSV error report
    err_csv = client.get(f"/api/admin/excel-registry/jobs/{job_id}/errors-csv", headers=staff_headers)
    assert err_csv.status_code == 200
    assert "modal_price" in err_csv.text

    # 5. Staff CANNOT approve or publish the import job
    staff_appr = client.post(f"/api/admin/excel-registry/jobs/{job_id}/approve", headers=staff_headers, json={})
    assert staff_appr.status_code == 403

    # 6. Level 2 Admin approves and publishes the import job
    admin_appr = client.post(
        f"/api/admin/excel-registry/jobs/{job_id}/approve",
        headers=admin_headers,
        json={"review_notes": "Validated 2 Mandya APMC records"}
    )
    assert admin_appr.status_code == 200
    assert admin_appr.json()["status"] == "APPROVED"

    admin_pub = client.post(
        f"/api/admin/excel-registry/jobs/{job_id}/publish",
        headers=admin_headers,
        json={"review_notes": "Publishing to MarketPrice table"}
    )
    assert admin_pub.status_code == 200
    pub_data = admin_pub.json()
    assert pub_data["status"] == "PUBLISHED"
    assert pub_data["published_records_count"] == 2

    # Verify the 2 records exist in the database
    db = SessionLocal()
    try:
        count_live = db.query(MarketPrice).filter(MarketPrice.market_name == unique_market).count()
        assert count_live == 2
    finally:
        db.close()

    # 7. Rollback the published import job and verify the records are removed
    rb_res = client.post(
        f"/api/admin/excel-registry/jobs/{job_id}/rollback",
        headers=admin_headers,
        json={"review_notes": "Rolling back test import"}
    )
    assert rb_res.status_code == 200
    assert rb_res.json()["status"] == "ROLLED_BACK"
    assert rb_res.json()["removed_records"] == 2

    db = SessionLocal()
    try:
        count_after = db.query(MarketPrice).filter(MarketPrice.market_name == unique_market).count()
        assert count_after == 0
    finally:
        db.close()


def test_subscription_plan_publishing_restricted_to_super_admin_head():
    """Verify Level 2 Admin can create a draft plan & version, but ONLY Super Admin Head can publish it."""
    sa_headers, _ = _get_super_admin_headers()
    admin_headers, _, _ = _create_and_approve_worker(sa_headers, "admin", "plan_admin")

    slug = f"kisan_pro_{uuid.uuid4().hex[:6]}"
    create_plan = client.post("/api/admin/plans", headers=admin_headers, json={"slug": slug})
    assert create_plan.status_code == 200, create_plan.text
    plan_id = create_plan.json()["id"]

    create_ver = client.post(f"/api/admin/plans/{plan_id}/versions", headers=admin_headers, json={
        "name": "Kisan Pro Seasonal",
        "description": "Seasonal advisory & priority Mandi alerts",
        "price_minor": 19900,
        "currency": "INR",
        "billing_interval": "monthly",
        "trial_days": 7,
        "benefits": ["Unlimited Mandi Alerts", "Priority Soil Advisory"],
        "entitlements": {
            "chat_messages": {"enabled": True, "usage_limit": 50, "limit_period": "daily"}
        }
    })
    assert create_ver.status_code == 200, create_ver.text
    ver_id = create_ver.json()["id"]

    # Level 2 Admin tries to publish -> MUST fail with 403 INSUFFICIENT_ROLE
    admin_pub = client.post(f"/api/admin/plans/{plan_id}/versions/{ver_id}/publish", headers=admin_headers)
    assert admin_pub.status_code == 403

    # Level 1 Super Admin Head publishes -> succeeds
    sa_pub = client.post(f"/api/admin/plans/{plan_id}/versions/{ver_id}/publish", headers=sa_headers)
    assert sa_pub.status_code == 200
    assert sa_pub.json()["is_published"] is True


def test_payment_verification_integrity_blocks_manual_paid_override():
    """Verify nobody can manually override an unverified or failed payment order to 'paid'."""
    sa_headers, sa_id = _get_super_admin_headers()

    db = SessionLocal()
    try:
        order = PaymentOrder(
            id=str(uuid.uuid4()),
            user_id=sa_id,
            plan_version_id="test_plan_v1",
            amount_minor=29900,
            currency="INR",
            provider_order_id=f"order_{uuid.uuid4().hex[:10]}",
            status="created",
        )
        db.add(order)
        db.commit()
        order_id = order.id
    finally:
        db.close()

    override_res = client.post(
        f"/api/admin/payments/orders/{order_id}/override-status",
        headers=sa_headers,
        json={"status": "paid", "reason": "Manual override attempt"}
    )
    assert override_res.status_code == 400
    assert override_res.json()["detail"]["error"]["code"] == "PAYMENT_VERIFICATION_REQUIRED"


def test_data_requests_full_workflow_and_audit_log_immutability():
    """Verify Data Requests OPEN -> ASSIGNED -> IN_PROGRESS -> RESOLVED and Audit Log immutability & redaction."""
    sa_headers, sa_id = _get_super_admin_headers()
    staff_headers, staff_id, _ = _create_and_approve_worker(sa_headers, "staff", "support_staff")

    # 1. Create a Data Request
    req_res = client.post("/api/admin/data-requests", headers=staff_headers, json={
        "request_type": "farmer_data_correction",
        "category": "mandi_data",
        "priority": "high",
        "details": {
            "subject": "Correct APMC Mysuru Cotton Price",
            "description": "Modal price was recorded as 720 instead of 7200."
        }
    })
    assert req_res.status_code == 200, req_res.text
    req_id = req_res.json()["id"]
    assert req_res.json()["status"] == "OPEN"

    # 2. Transition OPEN -> ASSIGNED -> IN_PROGRESS -> RESOLVED
    for next_status in ("ASSIGNED", "IN_PROGRESS", "RESOLVED"):
        wf = client.patch(
            f"/api/admin/data-requests/{req_id}/workflow",
            headers=sa_headers,
            json={
                "status": next_status,
                "assigned_to": staff_id,
                "priority": "high",
                "admin_notes": f"Moved to {next_status}"
            }
        )
        assert wf.status_code == 200, wf.text
        assert wf.json()["status"] == next_status

    # 3. Verify _sanitize_audit_payload redacts secrets/tokens
    sanitized = _sanitize_audit_payload({
        "email": "test@agro.ai",
        "password": "PlaintextPassword123",
        "access_token": "jwt.secret.token",
        "nested": {"provider_signature": "sig_12345", "role": "staff"}
    })
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["access_token"] == "[REDACTED]"
    assert sanitized["nested"]["provider_signature"] == "[REDACTED]"
    assert sanitized["nested"]["role"] == "staff"

    # 4. Staff without audit_logs:read cannot view audit logs
    staff_logs = client.get("/api/admin/audit-logs", headers=staff_headers)
    assert staff_logs.status_code == 403

    # 5. Super Admin Head can view audit logs, but CANNOT delete or modify them (immutable)
    sa_logs = client.get("/api/admin/audit-logs", headers=sa_headers)
    assert sa_logs.status_code == 200
    logs_data = sa_logs.json()
    assert isinstance(logs_data, list) and len(logs_data) > 0
    first_log_id = logs_data[0]["id"]

    for method in ("DELETE", "PATCH", "PUT"):
        tamper = client.request(method, f"/api/admin/audit-logs/{first_log_id}", headers=sa_headers)
        assert tamper.status_code == 403
        assert tamper.json()["detail"]["error"]["code"] == "AUDIT_LOG_IMMUTABLE"

"""Four-Level Administrative Hierarchy & Department Scoping Test Suite:
LEVEL 1: SUPER ADMIN (Global authority)
LEVEL 2: ADMIN (Assigned department(s) only; can request feature shutdown, cannot execute globally)
LEVEL 3: SUPERVISOR (Assigned team only; cannot create departments or manage Admins)
LEVEL 4: STAFF (Assigned tasks only; cannot access Supervisor/Admin controls)
Also verifies permission expiry (403 PERMISSION_EXPIRED) and cross-department IDOR prevention.
"""
import datetime
import time
import uuid
import jwt
from fastapi.testclient import TestClient

from app.main import app
from app.auth import deps
from app.database.connection import SessionLocal
from app.database.models import User, UserRole, AdminUser, AdminUserRole

client = TestClient(app)


def _token(uid: str, email: str, role: str = "super_admin"):
    now = int(time.time())
    return jwt.encode(
        {
            "sub": uid, "email": email, "iss": "agro-ai-local", "aud": "authenticated",
            "role": role, "sv": 1, "aal": "aal2", "mfa_verified": True,
            "iat": now, "exp": now + 3600,
        },
        deps.GUEST_SESSION_SECRET,
        algorithm="HS256",
    )


def _seed(role: AdminUserRole, depts=None, expires_at=None, prefix="h4"):
    uid = f"{prefix}_{uuid.uuid4().hex[:8]}"
    email = f"{uid}@example.com"
    h_map = {
        AdminUserRole.super_admin: "SUPER_ADMIN_HEAD",
        AdminUserRole.admin: "ADMIN",
        AdminUserRole.supervisor: "SUPERVISOR",
        AdminUserRole.staff: "STAFF",
    }
    db = SessionLocal()
    db.add(User(id=uid, email=email, full_name=f"User {uid}", role=UserRole.farmer, is_active=True, is_verified=True))
    db.add(AdminUser(
        id=str(uuid.uuid4()),
        user_id=uid,
        role=role,
        hierarchy_level=h_map[role],
        departments=depts or [],
        permission_expires_at=expires_at,
        is_active=True,
        mfa_enforced=True,
        session_version=1,
    ))
    db.commit()
    db.close()
    return uid, email


def test_mandi_admin_isolated_from_finance_and_cannot_toggle_global_flags():
    sa_uid, sa_email = _seed(AdminUserRole.super_admin, prefix="l1_sa")
    mandi_uid, mandi_email = _seed(AdminUserRole.admin, depts=["mandi"], prefix="l2_mandi")
    sup_uid, sup_email = _seed(AdminUserRole.supervisor, depts=["mandi"], prefix="l3_sup")
    staff_uid, staff_email = _seed(AdminUserRole.staff, depts=["mandi"], prefix="l4_staff")

    sa_hdr = {"Authorization": f"Bearer {_token(sa_uid, sa_email, 'super_admin')}"}
    mandi_hdr = {"Authorization": f"Bearer {_token(mandi_uid, mandi_email, 'admin')}"}
    sup_hdr = {"Authorization": f"Bearer {_token(sup_uid, sup_email, 'supervisor')}"}
    staff_hdr = {"Authorization": f"Bearer {_token(staff_uid, staff_email, 'staff')}"}

    # 1. Verify /api/admin/me returns exact 4-level hierarchy
    assert client.get("/api/admin/me", headers=sa_hdr).json()["hierarchy_level"] == "SUPER_ADMIN_HEAD"
    assert client.get("/api/admin/me", headers=mandi_hdr).json()["hierarchy_level"] == "ADMIN"
    assert client.get("/api/admin/me", headers=sup_hdr).json()["hierarchy_level"] == "SUPERVISOR"
    assert client.get("/api/admin/me", headers=staff_hdr).json()["hierarchy_level"] == "STAFF"

    # 2. Mandi Admin can access Mandi workspace, blocked from Finance (403 DEPARTMENT_ACCESS_DENIED)
    assert client.get("/api/admin/departments/mandi/workspace", headers=mandi_hdr).status_code == 200
    r_cross = client.get("/api/admin/departments/finance/workspace", headers=mandi_hdr)
    assert r_cross.status_code == 403
    assert r_cross.json()["detail"]["error"]["code"] == "DEPARTMENT_ACCESS_DENIED"

    # 3. Department list is scoped: Mandi Admin sees only mandi; Super Admin sees all 9+
    mandi_depts = [d["slug"] for d in client.get("/api/admin/departments", headers=mandi_hdr).json()["departments"]]
    assert mandi_depts == ["mandi"]
    sa_depts = [d["slug"] for d in client.get("/api/admin/departments", headers=sa_hdr).json()["departments"]]
    assert len(sa_depts) >= 9

    # 4. Supervisor & Staff cannot create departments or teams or change global features
    assert client.post("/api/admin/departments", json={"slug": "xdept", "name": "X"}, headers=sup_hdr).status_code == 403
    assert client.post("/api/admin/teams", json={"name": "T1", "department_slug": "mandi"}, headers=sup_hdr).status_code == 403
    assert client.post("/api/admin/teams", json={"name": "T2", "department_slug": "mandi"}, headers=staff_hdr).status_code == 403
    assert client.get("/api/admin/teams", headers=staff_hdr).status_code == 403

    # 5. Mandi Admin can create a team in Mandi, but NOT in Finance
    assert client.post("/api/admin/teams", json={"name": "Mandi Sync Team", "department_slug": "mandi"}, headers=mandi_hdr).status_code == 201
    assert client.post("/api/admin/teams", json={"name": "Finance Hack", "department_slug": "finance"}, headers=mandi_hdr).status_code == 403

    # 6. Mandi Admin cannot change global feature directly, CAN submit a request, CANNOT approve it; Super Admin approves
    try:
        assert client.post("/api/admin/features/mandi/status", json={"status": "MAINTENANCE", "reason": "Direct attempt"}, headers=mandi_hdr).status_code == 403
        r_req = client.post("/api/admin/features/requests", json={"feature_key": "mandi", "requested_status": "MAINTENANCE", "department_slug": "mandi", "reason": "APMC feed delayed"}, headers=mandi_hdr)
        assert r_req.status_code == 201
        req_id = r_req.json()["id"]

        # Mandi Admin cannot approve own request
        assert client.post(f"/api/admin/features/requests/{req_id}/decide", json={"decision": "approved"}, headers=mandi_hdr).status_code == 403

        # Super Admin approves -> Mandi immediately enters MAINTENANCE (503)
        r_ok = client.post(f"/api/admin/features/requests/{req_id}/decide", json={"decision": "approved"}, headers=sa_hdr)
        assert r_ok.status_code == 200
        assert client.get("/api/market/states").status_code == 503
    finally:
        client.post("/api/admin/features/mandi/status", json={"status": "ENABLED", "reason": "Test cleanup restore"}, headers=sa_hdr)


def test_expired_admin_permission_immediately_revokes_access():
    past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)
    exp_uid, exp_email = _seed(AdminUserRole.admin, depts=["mandi"], expires_at=past, prefix="exp_adm")
    exp_hdr = {"Authorization": f"Bearer {_token(exp_uid, exp_email, 'admin')}"}
    r = client.get("/api/admin/me", headers=exp_hdr)
    assert r.status_code == 403
    assert r.json()["detail"]["error"]["code"] == "PERMISSION_EXPIRED"

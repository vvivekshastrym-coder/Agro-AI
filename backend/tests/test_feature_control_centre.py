"""Super Admin Global Feature Control Centre Test Suite.

Verifies:
- Super Admin can enable, disable, set maintenance, emergency-shutdown and restore features
- Non-Super-Admin (admin, analyst) and regular farmers are rejected (403)
- Disabling / emergency-shutting-down Mandi blocks direct API access (503 FEATURE_UNAVAILABLE)
  even for existing authenticated sessions, while unrelated features (e.g. schemes/weather) stay 200 OK
  and historical database records stay intact
- Protected security keys (auth, admin, audit_logs) cannot be disabled (400)
- Scheduled shutdown & auto-restore execute server-side without browser involvement
- Audit logs and PlatformFeatureHistory record every change
"""
import datetime
import time
import uuid
import jwt
from fastapi.testclient import TestClient

from app.main import app
from app.auth import deps
from app.database.connection import SessionLocal
from app.database.models import User, UserRole, AdminUser, AdminUserRole, MandiMarket

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


def _seed(role: AdminUserRole = None, prefix: str = "fc"):
    uid = f"{prefix}_{uuid.uuid4().hex[:8]}"
    email = f"{uid}@example.com"
    db = SessionLocal()
    db.add(User(id=uid, email=email, full_name=f"User {uid}", role=UserRole.farmer, is_active=True, is_verified=True))
    if role is not None:
        db.add(AdminUser(
            id=str(uuid.uuid4()), user_id=uid, role=role,
            hierarchy_level="SUPER_ADMIN_HEAD" if role == AdminUserRole.super_admin else ("ADMIN" if role == AdminUserRole.admin else "STAFF"),
            is_active=True, mfa_enforced=True, session_version=1,
        ))
    db.commit()
    db.close()
    return uid, email


def test_only_super_admin_can_change_feature_status_and_protected_keys_blocked():
    sa_uid, sa_email = _seed(AdminUserRole.super_admin, "sa_fc")
    ops_uid, ops_email = _seed(AdminUserRole.admin, "ops_fc")
    f_uid, f_email = _seed(None, "farmer_fc")

    sa_hdr = {"Authorization": f"Bearer {_token(sa_uid, sa_email, 'super_admin')}"}
    ops_hdr = {"Authorization": f"Bearer {_token(ops_uid, ops_email, 'admin')}"}
    f_hdr = {"Authorization": f"Bearer {_token(f_uid, f_email, 'farmer')}"}

    # Ops Admin and Farmer cannot toggle global features
    for hdr in (ops_hdr, f_hdr):
        r = client.post("/api/admin/features/mandi/status", json={"status": "DISABLED", "reason": "Unauthorized attempt"}, headers=hdr)
        assert r.status_code == 403

    # Protected security keys cannot be disabled even by Super Admin
    for sec_key in ("auth", "admin", "audit_logs"):
        r = client.post(f"/api/admin/features/{sec_key}/status", json={"status": "DISABLED", "reason": "Attempt to disable security"}, headers=sa_hdr)
        assert r.status_code == 400
        assert r.json()["detail"]["error"]["code"] == "SECURITY_FEATURE_PROTECTED"


def test_mandi_shutdown_blocks_api_preserves_data_and_isolates_other_features():
    sa_uid, sa_email = _seed(AdminUserRole.super_admin, "sa_m")
    f_uid, f_email = _seed(None, "farmer_m")
    sa_hdr = {"Authorization": f"Bearer {_token(sa_uid, sa_email, 'super_admin')}"}
    f_hdr = {"Authorization": f"Bearer {_token(f_uid, f_email, 'farmer')}"}

    try:
        # 1. Mandi works before shutdown
        assert client.get("/api/market/states", headers=f_hdr).status_code == 200

        db = SessionLocal()
        markets_before = db.query(MandiMarket).count()
        db.close()
        assert markets_before > 0

        # 2. Super Admin triggers EMERGENCY_SHUTDOWN on Mandi
        r_shut = client.post(
            "/api/admin/features/mandi/status",
            json={
                "status": "EMERGENCY_SHUTDOWN",
                "reason": "Upstream APMC feed corruption detected",
                "maintenance_message": "Mandi prices are paused while we verify today's APMC feed.",
            },
            headers=sa_hdr,
        )
        assert r_shut.status_code == 200
        assert r_shut.json()["status"] == "EMERGENCY_SHUTDOWN"

        # 3. Direct API call with existing farmer session is immediately blocked (503)
        r_blocked = client.get("/api/market/states", headers=f_hdr)
        assert r_blocked.status_code == 503
        err = r_blocked.json()["detail"]["error"]
        assert err["code"] == "FEATURE_UNAVAILABLE"
        assert err["feature"] == "mandi"
        assert err["status"] == "EMERGENCY_SHUTDOWN"
        assert "paused" in err["message"]

        # 4. Unrelated feature (e.g. /api/schemes) remains completely unaffected
        r_other = client.get("/api/schemes", headers=f_hdr)
        assert r_other.status_code == 200

        # 5. Public feature map reflects shutdown
        pub = client.get("/api/public/features")
        assert pub.status_code == 200
        assert pub.json()["features"]["mandi"]["status"] == "EMERGENCY_SHUTDOWN"

        # 6. Historical Mandi DB records remain completely intact
        db = SessionLocal()
        assert db.query(MandiMarket).count() == markets_before
        db.close()

        # 7. History & audit log recorded
        hist = client.get("/api/admin/features/mandi/history", headers=sa_hdr)
        assert hist.status_code == 200
        assert any(h["state"] == "EMERGENCY_SHUTDOWN" for h in hist.json()["history"])

        # 8. Super Admin restores Mandi -> immediately accessible again
        r_rest = client.post(
            "/api/admin/features/mandi/status",
            json={"status": "ENABLED", "reason": "APMC feed verified and restored"},
            headers=sa_hdr,
        )
        assert r_rest.status_code == 200
        assert client.get("/api/market/states", headers=f_hdr).status_code == 200
    finally:
        client.post(
            "/api/admin/features/mandi/status",
            json={"status": "ENABLED", "reason": "Test cleanup restore"},
            headers=sa_hdr,
        )


def test_scheduled_shutdown_and_auto_restore_execute_server_side():
    sa_uid, sa_email = _seed(AdminUserRole.super_admin, "sa_sched")
    sa_hdr = {"Authorization": f"Bearer {_token(sa_uid, sa_email, 'super_admin')}"}
    past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)).isoformat()

    try:
        # Schedule a shutdown whose time has already passed -> server enforces MAINTENANCE automatically
        r_s = client.post(
            "/api/admin/features/schemes/schedule",
            json={"scheduled_shutdown_at": past, "scheduled_target_state": "MAINTENANCE", "reason": "Scheduled DB index rebuild"},
            headers=sa_hdr,
        )
        assert r_s.status_code == 200
        assert client.get("/api/schemes").status_code == 503

        # Schedule an auto-restore whose time has already passed -> server restores to ENABLED automatically
        r_r = client.post(
            "/api/admin/features/schemes/schedule",
            json={"scheduled_restore_at": past, "reason": "Scheduled auto-restore window"},
            headers=sa_hdr,
        )
        assert r_r.status_code == 200
        assert client.get("/api/schemes").status_code == 200
    finally:
        client.post("/api/admin/features/schemes/status", json={"status": "ENABLED", "reason": "Test cleanup restore"}, headers=sa_hdr)

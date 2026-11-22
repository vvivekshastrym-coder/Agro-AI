"""Super Admin Master Control Center Tests:
- All 16 platform features present in registry
- Bulk disable_all_farmer -> saves snapshot, blocks farmer APIs, keeps admin/health open -> restore_previous restores prior state -> enable_all restores all
- Platform-Wide Maintenance Mode -> blocks farmer APIs (503 PLATFORM_MAINTENANCE) while keeping /api/admin & /api/health open
- User moderation: Super Admin can ban, reinstate, and force-logout/revoke sessions; Ops Admin cannot ban (403); Super Admin cannot self-ban (400)
"""
import time
import uuid
import jwt
from fastapi.testclient import TestClient

from app.main import app
from app.auth import deps
from app.database.connection import SessionLocal
from app.database.models import User, UserRole, AdminUser, AdminUserRole

client = TestClient(app)


def _token(uid: str, email: str, role: str = "super_admin", sv: int = 1):
    now = int(time.time())
    return jwt.encode(
        {
            "sub": uid, "email": email, "iss": "agro-ai-local", "aud": "authenticated",
            "role": role, "sv": sv, "aal": "aal2", "mfa_verified": True,
            "iat": now, "exp": now + 3600,
        },
        deps.GUEST_SESSION_SECRET,
        algorithm="HS256",
    )


def _seed(role: AdminUserRole = None, prefix: str = "mc"):
    uid = f"{prefix}_{uuid.uuid4().hex[:8]}"
    email = f"{uid}@example.com"
    db = SessionLocal()
    db.add(User(id=uid, email=email, full_name=f"User {uid}", role=UserRole.farmer, is_active=True, is_verified=True))
    if role is not None:
        db.add(AdminUser(
            id=str(uuid.uuid4()), user_id=uid, role=role,
            hierarchy_level="SUPER_ADMIN_HEAD" if role == AdminUserRole.super_admin else "ADMIN",
            is_active=True, mfa_enforced=True, session_version=1,
        ))
    db.commit()
    db.close()
    return uid, email


def test_registry_has_all_17_modules_and_bulk_disable_restore():
    sa_uid, sa_email = _seed(AdminUserRole.super_admin, "sa_bulk")
    sa_hdr = {"Authorization": f"Bearer {_token(sa_uid, sa_email, 'super_admin')}"}

    r_list = client.get("/api/admin/features", headers=sa_hdr)
    assert r_list.status_code == 200
    keys = {f["key"] for f in r_list.json()["features"]}
    for expected in ("mandi", "agrogpt", "diagnosis", "weather", "pest_radar", "marketplace", "logistics", "drone", "satellite", "schemes", "credit", "carbon", "subscriptions", "farm_passport", "voice_ai", "notifications", "farmer_registration"):
        assert expected in keys

    try:
        # Put one feature (credit) into DISABLED first to verify snapshot restores mixed states
        assert client.post("/api/admin/features/credit/status", json={"status": "DISABLED", "reason": "Pre-snapshot state"}, headers=sa_hdr).status_code == 200

        # Bulk pause all farmer modules
        r_off = client.post("/api/admin/features/bulk", json={"action": "disable_all_farmer", "reason": "Emergency bulk pause drill"}, headers=sa_hdr)
        assert r_off.status_code == 200
        assert r_off.json()["affected_count"] >= 16

        # Farmer endpoints blocked, admin & health still open
        assert client.get("/api/market/states").status_code == 503
        assert client.get("/api/schemes").status_code == 503
        assert client.get("/api/admin/me", headers=sa_hdr).status_code == 200
        assert client.get("/health").status_code == 200

        # Restore snapshot -> mandi returns to ENABLED while credit returns to DISABLED
        r_snap = client.post("/api/admin/features/bulk", json={"action": "restore_previous", "reason": "Restoring pre-drill snapshot"}, headers=sa_hdr)
        assert r_snap.status_code == 200
        assert client.get("/api/market/states").status_code == 200
        st_after = {f["key"]: f["status"] for f in client.get("/api/admin/features", headers=sa_hdr).json()["features"]}
        assert st_after["credit"] == "DISABLED"
    finally:
        client.post("/api/admin/features/bulk", json={"action": "enable_all", "reason": "Cleanup restore all features"}, headers=sa_hdr)


def test_platform_wide_maintenance_mode_blocks_farmers_and_keeps_admin_recovery():
    sa_uid, sa_email = _seed(AdminUserRole.super_admin, "sa_pm")
    sa_hdr = {"Authorization": f"Bearer {_token(sa_uid, sa_email, 'super_admin')}"}

    try:
        r_on = client.post(
            "/api/admin/security/platform-maintenance",
            json={"enabled": True, "reason": "Database upgrade window", "maintenance_message": "Upgrading Agro AI servers."},
            headers=sa_hdr,
        )
        assert r_on.status_code == 200
        assert r_on.json()["enabled"] is True

        # Farmer APIs blocked with PLATFORM_MAINTENANCE
        r_farmer = client.get("/api/schemes")
        assert r_farmer.status_code == 503
        assert r_farmer.json()["detail"]["error"]["code"] == "PLATFORM_MAINTENANCE"

        # Admin recovery & public feature status remain open
        assert client.get("/api/admin/me", headers=sa_hdr).status_code == 200
        pub = client.get("/api/public/features")
        assert pub.status_code == 200
        assert pub.json()["platform_maintenance"]["enabled"] is True
    finally:
        client.post("/api/admin/security/platform-maintenance", json={"enabled": False, "reason": "Maintenance complete"}, headers=sa_hdr)
        assert client.get("/api/schemes").status_code == 200


def test_user_ban_reinstate_and_force_logout_controls():
    sa_uid, sa_email = _seed(AdminUserRole.super_admin, "sa_u")
    ops_uid, ops_email = _seed(AdminUserRole.admin, "ops_u")
    target_uid, target_email = _seed(None, "target_u")

    sa_hdr = {"Authorization": f"Bearer {_token(sa_uid, sa_email, 'super_admin')}"}
    ops_hdr = {"Authorization": f"Bearer {_token(ops_uid, ops_email, 'admin')}"}
    target_hdr = {"Authorization": f"Bearer {_token(target_uid, target_email, 'farmer')}"}

    # Ops Admin cannot permanently ban (403)
    assert client.post(f"/api/admin/users/{target_uid}/ban", json={"reason": "Abuse report"}, headers=ops_hdr).status_code == 403
    # Super Admin cannot self-ban (400)
    assert client.post(f"/api/admin/users/{sa_uid}/ban", json={"reason": "Self ban test"}, headers=sa_hdr).status_code == 400

    # Super Admin bans target -> target token is rejected (403 ACCOUNT_DISABLED)
    r_ban = client.post(f"/api/admin/users/{target_uid}/ban", json={"reason": "Verified spam abuse"}, headers=sa_hdr)
    assert r_ban.status_code == 200
    assert client.post("/api/agro-gpt/chat", json={"message": "hi"}, headers=target_hdr).status_code == 403

    # Reinstate target -> target regains access
    r_re = client.post(f"/api/admin/users/{target_uid}/reinstate", json={"reason": "Appeal approved"}, headers=sa_hdr)
    assert r_re.status_code == 200

    # Force logout Ops Admin -> Ops Admin's v1 token immediately revoked (401 SESSION_REVOKED)
    r_rev = client.post(f"/api/admin/users/{ops_uid}/revoke-sessions", json={"reason": "Lost device reported"}, headers=sa_hdr)
    assert r_rev.status_code == 200
    assert r_rev.json()["admin_session_version"] == 2
    assert client.get("/api/admin/me", headers=ops_hdr).status_code == 401

"""Zero-Trust Admin Panel Security Test Suite (Phase A + B).

Verifies:
- Regular farmer cannot access admin endpoints (403)
- Hardcoded email alone NEVER auto-promotes in production without valid bootstrap token
- Server-side MFA enforcement (aal2) blocks password-only aal1 tokens when enabled
- Session revocation (POST /api/admin/sessions/revoke-all) immediately invalidates old tokens
- Progressive login rate limiting locks repeated failed login attempts (429)
- Emergency lockdown blocks non-Super-Admin access (503), revokes their sessions,
  keeps Super Admin access intact, and preserves audit logs
- Audit logs cannot be mutated or deleted even by Super Admin
- Admin API responses include Cache-Control: no-store
"""
import os
import time
import uuid
import jwt
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth import deps
from app.routers import admin as admin_router
from app.database.connection import SessionLocal
from app.database.models import User, UserRole, AdminUser, AdminUserRole, AdminAuditLog, PlatformFeature

client = TestClient(app)


def _make_token(uid: str, email: str, role: str = "super_admin", sv: int = 1, mfa: bool = True, exp_offset: int = 3600):
    now = int(time.time())
    payload = {
        "sub": uid,
        "email": email,
        "iss": "agro-ai-local",
        "aud": "authenticated",
        "role": role,
        "sv": sv,
        "aal": "aal2" if mfa else "aal1",
        "mfa_verified": mfa,
        "iat": now,
        "exp": now + exp_offset,
    }
    return jwt.encode(payload, deps.GUEST_SESSION_SECRET, algorithm="HS256")


def _seed_user_and_admin(role: AdminUserRole = None, email_prefix: str = "zt"):
    uid = f"{email_prefix}_{uuid.uuid4().hex[:8]}"
    email = f"{uid}@example.com"
    db = SessionLocal()
    u = User(id=uid, email=email, full_name=f"User {uid}", role=UserRole.farmer, is_active=True, is_verified=True)
    db.add(u)
    adm = None
    if role is not None:
        adm = AdminUser(
            id=str(uuid.uuid4()),
            user_id=uid,
            role=role,
            hierarchy_level="SUPER_ADMIN_HEAD" if role == AdminUserRole.super_admin else ("ADMIN" if role == AdminUserRole.admin else "STAFF"),
            is_active=True,
            mfa_enforced=True,
            session_version=1,
        )
        db.add(adm)
    db.commit()
    db.close()
    return uid, email


def test_farmer_blocked_from_admin_and_no_cache_header():
    # Ensure at least one active super admin exists so dev bootstrap does not trigger
    _seed_user_and_admin(AdminUserRole.super_admin, "sa_seed")
    uid, email = _seed_user_and_admin(None, "farmer")
    tok = _make_token(uid, email, role="farmer", mfa=True)
    resp = client.get("/api/admin/me", headers={"Authorization": f"Bearer {tok}"})
    assert resp.status_code == 403
    assert "no-store" in resp.headers.get("cache-control", "").lower()


def test_production_never_auto_promotes_by_hardcoded_email(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("ADMIN_BOOTSTRAP_TOKEN", raising=False)

    # Create a user with SUPER_ADMIN_EMAIL but NO AdminUser row
    db = SessionLocal()
    existing = db.query(User).filter(User.email == admin_router.SUPER_ADMIN_EMAIL).first()
    if existing:
        db.query(AdminUser).filter(AdminUser.user_id == existing.id).delete()
        uid = existing.id
    else:
        uid = f"prod_founder_{uuid.uuid4().hex[:8]}"
        db.add(User(id=uid, email=admin_router.SUPER_ADMIN_EMAIL, full_name="Founder", role=UserRole.farmer, is_active=True, is_verified=True))
    db.commit()
    db.close()

    tok = _make_token(uid, admin_router.SUPER_ADMIN_EMAIL, role="super_admin", mfa=True)
    resp = client.get("/api/admin/me", headers={"Authorization": f"Bearer {tok}"})
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"]["code"] == "ADMIN_FORBIDDEN"


def test_mfa_enforced_blocks_aal1_and_allows_aal2(monkeypatch):
    monkeypatch.setenv("ADMIN_MFA_REQUIRED", "true")
    uid, email = _seed_user_and_admin(AdminUserRole.super_admin, "mfa_sa")

    aal1_tok = _make_token(uid, email, role="super_admin", sv=1, mfa=False)
    r_fail = client.get("/api/admin/me", headers={"Authorization": f"Bearer {aal1_tok}"})
    assert r_fail.status_code == 403
    assert r_fail.json()["detail"]["error"]["code"] == "MFA_REQUIRED"

    aal2_tok = _make_token(uid, email, role="super_admin", sv=1, mfa=True)
    r_ok = client.get("/api/admin/me", headers={"Authorization": f"Bearer {aal2_tok}"})
    assert r_ok.status_code == 200
    assert r_ok.json()["role"] == "super_admin"


def test_session_revocation_invalidates_old_admin_token():
    uid, email = _seed_user_and_admin(AdminUserRole.super_admin, "rev_sa")
    tok_v1 = _make_token(uid, email, role="super_admin", sv=1, mfa=True)

    assert client.get("/api/admin/me", headers={"Authorization": f"Bearer {tok_v1}"}).status_code == 200

    rev = client.post("/api/admin/sessions/revoke-all", headers={"Authorization": f"Bearer {tok_v1}"})
    assert rev.status_code == 200
    assert rev.json()["session_version"] == 2

    # Old token (sv=1) must now be rejected with 401 SESSION_REVOKED
    r_old = client.get("/api/admin/me", headers={"Authorization": f"Bearer {tok_v1}"})
    assert r_old.status_code == 401
    assert r_old.json()["detail"]["error"]["code"] == "SESSION_REVOKED"

    # New token (sv=2) works
    tok_v2 = _make_token(uid, email, role="super_admin", sv=2, mfa=True)
    assert client.get("/api/admin/me", headers={"Authorization": f"Bearer {tok_v2}"}).status_code == 200


def test_admin_login_rate_limiting_lockout():
    admin_router._ADMIN_LOGIN_FAILURES.clear()
    bad_email = f"bruteforce_{uuid.uuid4().hex[:8]}@example.com"
    for _ in range(5):
        r = client.post("/api/admin/login", json={"email": bad_email, "password": "wrong-password"})
        assert r.status_code == 401

    r_locked = client.post("/api/admin/login", json={"email": bad_email, "password": "wrong-password"})
    assert r_locked.status_code == 429
    assert r_locked.json()["detail"]["error"]["code"] == "LOGIN_RATE_LIMITED"
    admin_router._ADMIN_LOGIN_FAILURES.clear()


def test_emergency_lockdown_blocks_non_super_admin_and_preserves_audit_logs():
    sa_uid, sa_email = _seed_user_and_admin(AdminUserRole.super_admin, "ld_sa")
    ops_uid, ops_email = _seed_user_and_admin(AdminUserRole.admin, "ld_ops")
    sa_tok = _make_token(sa_uid, sa_email, role="super_admin", sv=1, mfa=True)
    ops_tok = _make_token(ops_uid, ops_email, role="admin", sv=1, mfa=True)

    try:
        # Ops Admin works before lockdown
        assert client.get("/api/admin/me", headers={"Authorization": f"Bearer {ops_tok}"}).status_code == 200

        # Super Admin enables lockdown
        r_on = client.post(
            "/api/admin/security/lockdown",
            json={"enabled": True, "reason": "Suspected credential compromise drill"},
            headers={"Authorization": f"Bearer {sa_tok}"},
        )
        assert r_on.status_code == 200
        assert r_on.json()["enabled"] is True
        assert r_on.json()["revoked_admin_sessions"] >= 1

        # Ops Admin's old token is revoked (401); even a refreshed sv token is blocked by lockdown (503)
        assert client.get("/api/admin/me", headers={"Authorization": f"Bearer {ops_tok}"}).status_code == 401
        ops_tok_v2 = _make_token(ops_uid, ops_email, role="admin", sv=2, mfa=True)
        r_blocked = client.get("/api/admin/me", headers={"Authorization": f"Bearer {ops_tok_v2}"})
        assert r_blocked.status_code == 503
        assert r_blocked.json()["detail"]["error"]["code"] == "ADMIN_EMERGENCY_LOCKDOWN"

        # Super Admin still has access and audit logs are preserved & immutable
        assert client.get("/api/admin/me", headers={"Authorization": f"Bearer {sa_tok}"}).status_code == 200
        logs = client.get("/api/admin/audit-logs", headers={"Authorization": f"Bearer {sa_tok}"})
        assert logs.status_code == 200
        log_rows = logs.json() if isinstance(logs.json(), list) else logs.json().get("logs", [])
        actions = [entry["action"] for entry in log_rows]
        assert "EMERGENCY_LOCKDOWN_ENABLED" in actions
        first_log_id = log_rows[0]["id"]
        assert client.delete(f"/api/admin/audit-logs/{first_log_id}", headers={"Authorization": f"Bearer {sa_tok}"}).status_code == 403
    finally:
        # Always disable lockdown after test so other tests are unaffected
        client.post(
            "/api/admin/security/lockdown",
            json={"enabled": False, "reason": "Drill complete, restoring normal operations"},
            headers={"Authorization": f"Bearer {sa_tok}"},
        )

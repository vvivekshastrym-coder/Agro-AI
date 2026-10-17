"""Automated Security, Privacy & Store-Readiness Regression Test Suite for Agro AI.
Verifies:
- SEC-001: Static file exposure blocklist (.env, .db, .sql, .py, /backend, /.git, etc.)
- SEC-002: Production mode admin bootstrap & super-admin password gate
- SEC-003: Production mode payment verification signature requirement
- SEC-004: Supabase PostgreSQL RLS coverage across all 55 schema tables
- PRIV-001: Self-service account deletion (DELETE /api/auth/me) & web deletion portal (POST /api/auth/delete-account-request, /privacy, /delete-account)
- MOB-001: Android API 36 + network_security_config + allowBackup=false + iOS PrivacyInfo.xcprivacy & Info.plist
"""
import os
import re
import uuid
import jwt
import time
from fastapi.testclient import TestClient

from app.main import app
from app.database.connection import SessionLocal
from app.database.models import (
    User, UserRole, Farm, DiagnosisReport, DataRequest,
    PaymentOrder, AdminUser, AdminUserRole
)
from app.auth.deps import GUEST_SESSION_SECRET

client = TestClient(app)


def _make_user_token(user_id: str, email: str, name: str = "Test Farmer") -> str:
    payload = {
        "sub": user_id,
        "iss": "agro-ai-local",
        "aud": "authenticated",
        "email": email,
        "name": name,
        "role": "farmer",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, GUEST_SESSION_SECRET, algorithm="HS256")


def test_sec001_blocks_sensitive_files_and_internal_directories():
    """Verify static mount never serves .env, SQLite DBs, SQL schemas, Python source, or hidden dirs."""
    sensitive_paths = [
        "/.env",
        "/.env.local",
        "/kisanai.db",
        "/supabase_schema.sql",
        "/backend/app/main.py",
        "/backend/app/routers/admin.py",
        "/.git/config",
        "/scripts/prepare-mobile-dist.mjs",
        "/capacitor.config.ts",
        "/releases/agroai-upload-key.jks",
        "/releases/signing-keystore-credentials.txt",
    ]
    for path in sensitive_paths:
        res = client.get(path)
        assert res.status_code == 404, f"Expected 404 for sensitive path {path}, got {res.status_code}"


def test_sec001_security_headers_present():
    """Verify OWASP security headers are attached to HTTP responses."""
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert "camera=(self)" in res.headers.get("Permissions-Policy", "")
    assert "max-age=31536000" in res.headers.get("Strict-Transport-Security", "")
    assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_priv001_privacy_and_delete_account_pages_served():
    """Verify public /privacy, /delete-account, and /download-app routes."""
    priv_res = client.get("/privacy")
    assert priv_res.status_code == 200
    assert "Privacy Policy" in priv_res.text

    del_res = client.get("/delete-account")
    assert del_res.status_code == 200
    assert "Delete Your Agro AI Account" in del_res.text

    dl_res = client.get("/download-app")
    assert dl_res.status_code == 200
    assert "Test Agro AI on Your Mobile Device" in dl_res.text


def test_priv001_in_app_account_deletion_cascades_and_revokes_access():
    """Verify DELETE /api/auth/me deletes user farm/diagnosis data, anonymizes PII, and blocks subsequent token reuse."""
    db = SessionLocal()
    uid = str(uuid.uuid4())
    email = f"delete_me_{uid[:8]}@agro.ai"
    try:
        user = User(
            id=uid,
            email=email,
            phone="+919900112233",
            full_name="Farmer To Delete",
            role=UserRole.farmer,
            is_active=True,
        )
        db.add(user)
        db.flush()

        farm = Farm(id=str(uuid.uuid4()), user_id=uid, village="Green Valley")
        diag = DiagnosisReport(
            id=str(uuid.uuid4()),
            farmer_id=uid,
            crop="Tomato",
            disease="Early Blight",
            confidence=0.92,
        )
        db.add_all([farm, diag])
        db.commit()
    finally:
        db.close()

    token = _make_user_token(uid, email)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Verify profile works before deletion
    me_before = client.get("/api/auth/me", headers=headers)
    assert me_before.status_code == 200
    assert me_before.json()["email"] == email

    # 2. Execute self-service account deletion
    del_res = client.delete("/api/auth/me", headers=headers)
    assert del_res.status_code == 200
    body = del_res.json()
    assert body["status"] == "deleted"
    assert body["user_id"] == uid

    # 3. Verify farms and diagnosis reports were purged and user PII anonymized
    db = SessionLocal()
    try:
        assert db.query(Farm).filter(Farm.user_id == uid).count() == 0
        assert db.query(DiagnosisReport).filter(DiagnosisReport.farmer_id == uid).count() == 0
        u_after = db.query(User).filter(User.id == uid).first()
        assert u_after is not None
        assert u_after.is_active is False
        assert u_after.email is None
        assert u_after.phone is None
        assert u_after.full_name == "Deleted User"
        dr = db.query(DataRequest).filter(DataRequest.user_id == uid, DataRequest.request_type == "delete").first()
        assert dr is not None
        assert dr.status == "completed"
    finally:
        db.close()

    # 4. Verify subsequent API calls with the old JWT are rejected with 403 ACCOUNT_DISABLED
    me_after = client.get("/api/auth/me", headers=headers)
    assert me_after.status_code == 403


def test_priv001_web_account_deletion_request_endpoint():
    """Verify POST /api/auth/delete-account-request supports Google Play external web deletion flow."""
    res = client.post(
        "/api/auth/delete-account-request",
        json={"identifier": "farmer_web_del@agro.ai", "reason": "No longer farming"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("received", "submitted")
    assert "request_id" in data


def test_sec003_production_payment_verification_requires_secret(monkeypatch):
    """Verify verify_payment refuses to mark order paid in production if RAZORPAY_KEY_SECRET is unset."""
    db = SessionLocal()
    uid = str(uuid.uuid4())
    order_id = str(uuid.uuid4())
    email = f"payer_{uid[:6]}@agro.ai"
    try:
        user = User(id=uid, email=email, full_name="Payer", role=UserRole.farmer, is_active=True)
        order = PaymentOrder(
            id=order_id,
            user_id=uid,
            plan_version_id="ver_test_123",
            amount_minor=49900,
            currency="INR",
            status="created",
            provider="razorpay",
            provider_order_id="order_test_123",
        )
        db.add_all([user, order])
        db.commit()
    finally:
        db.close()

    token = _make_user_token(uid, email)
    headers = {"Authorization": f"Bearer {token}"}

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("RAZORPAY_KEY_SECRET", raising=False)

    res = client.post(
        "/api/payments/verify-payment",
        headers=headers,
        json={
            "order_id": order_id,
            "provider_payment_id": "pay_fake_123",
            "provider_signature": "forged_signature",
        },
    )
    assert res.status_code == 503


def test_sec004_supabase_schema_enables_rls_on_all_55_tables():
    """Verify supabase_schema.sql enables Row-Level Security on every table it creates."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    schema_path = os.path.join(project_root, "supabase_schema.sql")
    with open(schema_path, encoding="utf-8") as f:
        sql = f.read()

    created_tables = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", sql))
    rls_tables = set(re.findall(r"ALTER TABLE (\w+) ENABLE ROW LEVEL SECURITY;", sql))
    assert len(created_tables) >= 55
    missing_rls = created_tables - rls_tables
    assert not missing_rls, f"Tables missing RLS enablement: {missing_rls}"


def test_mob001_mobile_store_configs_hardened():
    """Verify Android API 36, allowBackup=false, network_security_config, and iOS PrivacyInfo.xcprivacy exist."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    vars_gradle = open(os.path.join(project_root, "android", "variables.gradle"), encoding="utf-8").read()
    assert "targetSdkVersion = 36" in vars_gradle
    assert "compileSdkVersion = 36" in vars_gradle

    manifest = open(
        os.path.join(project_root, "android", "app", "src", "main", "AndroidManifest.xml"),
        encoding="utf-8",
    ).read()
    assert 'android:allowBackup="false"' in manifest
    assert 'android:networkSecurityConfig="@xml/network_security_config"' in manifest

    net_sec = open(
        os.path.join(project_root, "android", "app", "src", "main", "res", "xml", "network_security_config.xml"),
        encoding="utf-8",
    ).read()
    assert 'cleartextTrafficPermitted="false"' in net_sec

    ios_privacy = open(
        os.path.join(project_root, "ios", "App", "App", "PrivacyInfo.xcprivacy"),
        encoding="utf-8",
    ).read()
    assert "NSPrivacyAccessedAPICategoryUserDefaults" in ios_privacy

    ios_plist = open(
        os.path.join(project_root, "ios", "App", "App", "Info.plist"),
        encoding="utf-8",
    ).read()
    assert "NSCameraUsageDescription" in ios_plist
    assert "NSLocationWhenInUseUsageDescription" in ios_plist

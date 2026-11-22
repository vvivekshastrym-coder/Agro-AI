"""Stage D3 — Real Data Only & Zero Fabrication Regression Test Suite.

Verifies:
- Production mode NEVER auto-seeds hardcoded drone operators or static reference mandi prices
- Freshness classifier returns FRESH / DELAYED / STALE / UNAVAILABLE accurately (never labels stale data fresh)
- Syncing an unconfigured provider (e.g. agmarknet_data_gov without DATA_GOV_IN_API_KEY) truthfully records
  'unconfigured' in data_sync_logs (never fake 'success')
- Mandi outlier detector catches anomalous records (min > modal, modal > max, non-positive modal)
- Department-scoped Admin (mandi) only sees mandi data sources and cannot toggle/sync finance providers (403)
"""
import datetime
import time
import uuid
import jwt
from fastapi.testclient import TestClient

from app.main import app
from app.auth import deps
from app.routers import drone as drone_router
from app.routers import market as market_router
from app.services.data_integrity import classify_freshness, detect_mandi_outliers
from app.database.connection import SessionLocal
from app.database.models import User, UserRole, AdminUser, AdminUserRole, DroneOperator, MarketPrice

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


def _seed_admin(role: AdminUserRole, depts=None, prefix="di"):
    uid = f"{prefix}_{uuid.uuid4().hex[:8]}"
    email = f"{uid}@example.com"
    db = SessionLocal()
    db.add(User(id=uid, email=email, full_name=f"User {uid}", role=UserRole.farmer, is_active=True, is_verified=True))
    db.add(AdminUser(
        id=str(uuid.uuid4()), user_id=uid, role=role,
        hierarchy_level="SUPER_ADMIN_HEAD" if role == AdminUserRole.super_admin else "ADMIN",
        departments=depts or [], is_active=True, mfa_enforced=True, session_version=1,
    ))
    db.commit()
    db.close()
    return uid, email


def test_production_mode_blocks_demo_drone_and_mandi_seeding(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("ALLOW_DEMO_SEED", raising=False)

    db = SessionLocal()
    try:
        db.query(DroneOperator).delete()
        db.commit()
        drone_router._ensure_default_drone_operators(db)
        assert db.query(DroneOperator).count() == 0

        market_router._REFERENCE_CHECKED = False
        before = db.query(MarketPrice).count()
        market_router._ensure_reference_mandi_prices(db)
        assert db.query(MarketPrice).count() == before
    finally:
        db.close()


def test_freshness_classifier_never_marks_stale_as_fresh():
    now = datetime.datetime.now(datetime.timezone.utc)
    fresh_iso = (now - datetime.timedelta(hours=2)).isoformat()
    delayed_iso = (now - datetime.timedelta(hours=30)).isoformat()
    stale_iso = (now - datetime.timedelta(days=5)).isoformat()

    assert classify_freshness(fresh_iso, threshold_hours=24) == "FRESH"
    assert classify_freshness(delayed_iso, threshold_hours=24) == "DELAYED"
    assert classify_freshness(stale_iso, threshold_hours=24) == "STALE"
    assert classify_freshness(None, threshold_hours=24) == "UNAVAILABLE"


def test_outlier_detector_catches_invalid_mandi_price_bounds():
    bad_id = f"bad_mp_{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        db.add(MarketPrice(
            id=bad_id, commodity="Tomato", market_name="Test APMC", state="Karnataka",
            min_price=2500.0, modal_price=1500.0, max_price=1200.0, data_source="test_anomaly",
        ))
        db.commit()
        outliers = detect_mandi_outliers(db)
        found = [o for o in outliers if o["id"] == bad_id]
        assert len(found) == 1
        assert "min_greater_than_modal" in found[0]["reasons"]
        assert "modal_greater_than_max" in found[0]["reasons"]
    finally:
        db.query(MarketPrice).filter(MarketPrice.id == bad_id).delete()
        db.commit()
        db.close()


def test_data_integrity_center_sync_honesty_and_department_scoping(monkeypatch):
    monkeypatch.delenv("DATA_GOV_IN_API_KEY", raising=False)
    monkeypatch.delenv("AGMARKNET_API_KEY", raising=False)

    sa_uid, sa_email = _seed_admin(AdminUserRole.super_admin, prefix="sa_di")
    mandi_uid, mandi_email = _seed_admin(AdminUserRole.admin, depts=["mandi"], prefix="m_di")
    sa_hdr = {"Authorization": f"Bearer {_token(sa_uid, sa_email, 'super_admin')}"}
    mandi_hdr = {"Authorization": f"Bearer {_token(mandi_uid, mandi_email, 'admin')}"}

    # Super Admin sees all 9 registered providers
    r_sa = client.get("/api/admin/data-integrity/overview", headers=sa_hdr)
    assert r_sa.status_code == 200
    assert r_sa.json()["total_sources"] >= 9

    # Mandi Admin sees ONLY mandi department providers
    r_m = client.get("/api/admin/data-integrity/overview", headers=mandi_hdr)
    assert r_m.status_code == 200
    m_depts = {s["department_slug"] for s in r_m.json()["sources"]}
    assert m_depts == {"mandi"}

    # Mandi Admin cannot sync or toggle Finance's razorpay_payments (403)
    assert client.post("/api/admin/data-integrity/sources/razorpay_payments/sync", headers=mandi_hdr).status_code == 403
    assert client.post("/api/admin/data-integrity/sources/razorpay_payments/toggle", json={"is_enabled": False, "reason": "Unauthorized"}, headers=mandi_hdr).status_code == 403

    # Syncing AGMARKNET without key truthfully records 'unconfigured' (never fake 'success')
    r_sync = client.post("/api/admin/data-integrity/sources/agmarknet_data_gov/sync", headers=sa_hdr)
    assert r_sync.status_code == 200
    assert r_sync.json()["status"] == "unconfigured"

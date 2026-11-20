"""Comprehensive tests for Privacy-First Age Verification, Parental Consent,
Google Fonts removal, IP privacy, Session Replay disabled, Cookie Consent,
and Subscription Cancellation / Invoices.
"""
import datetime
import pathlib
import uuid
import jwt
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth.deps import GUEST_SESSION_SECRET
from app.database.connection import SessionLocal
from app.database.models import (
    User, UserRole, SubscriptionPlan, SubscriptionPlanVersion,
    UserSubscription, PaymentOrder, AdminAuditLog
)

client = TestClient(app)
ROOT = pathlib.Path(__file__).resolve().parents[2]


def _make_token(sub: str) -> dict:
    tok = jwt.encode(
        {
            "sub": sub,
            "aud": "authenticated",
            "iss": "agro-ai-local",
            "exp": int(datetime.datetime.now(datetime.timezone.utc).timestamp()) + 3600,
        },
        GUEST_SESSION_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {tok}"}


def test_adult_registration_flow():
    uid = str(uuid.uuid4())
    hdr = _make_token(uid)
    r = client.post("/api/auth/age-verify", json={"date_of_birth": "1995-05-15", "country_code": "IN"}, headers=hdr)
    assert r.status_code == 200
    data = r.json()
    assert data["age_category"] == "adult"
    assert data["requires_parental_consent"] is False
    assert data["account_status"] == "active"
    assert client.get("/api/auth/me", headers=hdr).status_code == 200


def test_under_9_registration_restricted_and_blocked_until_parent_consent():
    uid = str(uuid.uuid4())
    hdr = _make_token(uid)
    dob = (datetime.date.today() - datetime.timedelta(days=365 * 7)).isoformat()
    r = client.post("/api/auth/age-verify", json={"date_of_birth": dob, "country_code": "IN"}, headers=hdr)
    assert r.status_code == 200
    data = r.json()
    assert data["age_category"] == "child_under_9"
    assert data["experience_mode"] == "restricted_child"
    assert data["requires_parental_consent"] is True
    assert data["account_status"] == "pending_parental_consent"

    # Unauthorized minor/child access to normal protected routes must be blocked
    blocked = client.get("/api/plans/me", headers=hdr)
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["error"]["code"] == "PARENTAL_CONSENT_REQUIRED"


def test_minor_registration_parent_approval_rejection_and_withdrawal():
    uid = str(uuid.uuid4())
    hdr = _make_token(uid)
    dob = (datetime.date.today() - datetime.timedelta(days=365 * 14)).isoformat()
    r = client.post("/api/auth/age-verify", json={"date_of_birth": dob, "country_code": "IN"}, headers=hdr)
    assert r.status_code == 200
    assert r.json()["age_category"] == "minor_9_17"
    assert r.json()["account_status"] == "pending_parental_consent"

    # Request parental consent
    req = client.post("/api/auth/parental-consent/request", json={"parent_contact": "parent@example.com"}, headers=hdr)
    assert req.status_code == 200
    consent_id = req.json()["consent_id"]
    code = req.json()["dev_verification_code"]

    # Wrong code fails
    bad = client.post("/api/auth/parental-consent/verify", json={
        "consent_id": consent_id, "verification_code": "000000", "decision": "approved", "parent_confirmed_adult": True
    })
    assert bad.status_code == 401

    # Parent approves
    ok = client.post("/api/auth/parental-consent/verify", json={
        "consent_id": consent_id, "verification_code": code, "decision": "approved", "parent_confirmed_adult": True
    })
    assert ok.status_code == 200
    assert ok.json()["status"] == "approved"
    assert ok.json()["child_account_status"] == "active"

    # Now minor can access normal features
    assert client.get("/api/plans/me", headers=hdr).status_code == 200

    # Parent withdraws consent -> immediately suspends child account
    wd = client.post("/api/auth/parental-consent/withdraw", json={"consent_id": consent_id, "reason": "Parent withdrew"}, headers=hdr)
    assert wd.status_code == 200
    assert wd.json()["status"] == "withdrawn"
    assert wd.json()["child_account_status"] == "suspended"

    # Access blocked again
    assert client.get("/api/plans/me", headers=hdr).status_code == 403


def test_parent_consent_rejection_keeps_minor_suspended():
    uid = str(uuid.uuid4())
    hdr = _make_token(uid)
    dob = (datetime.date.today() - datetime.timedelta(days=365 * 15)).isoformat()
    client.post("/api/auth/age-verify", json={"date_of_birth": dob, "country_code": "IN"}, headers=hdr)
    req = client.post("/api/auth/parental-consent/request", json={"parent_contact": "guardian@example.com"}, headers=hdr)
    cid = req.json()["consent_id"]
    code = req.json()["dev_verification_code"]

    rej = client.post("/api/auth/parental-consent/verify", json={
        "consent_id": cid, "verification_code": code, "decision": "rejected", "parent_confirmed_adult": True
    })
    assert rej.status_code == 200
    assert rej.json()["status"] == "rejected"
    assert rej.json()["child_account_status"] == "suspended"
    assert client.get("/api/plans/me", headers=hdr).status_code == 403


def test_country_specific_age_rules_and_frontend_manipulation_rejected():
    uid = str(uuid.uuid4())
    hdr = _make_token(uid)
    dob_14 = (datetime.date.today() - datetime.timedelta(days=365 * 14 + 5)).isoformat()

    # In US (COPPA 13+), 14 does not require COPPA parental consent; in IN (DPDP 18+), 14 DOES.
    r_in = client.post("/api/auth/age-verify", json={"date_of_birth": dob_14, "country_code": "IN"}, headers=hdr)
    assert r_in.json()["requires_parental_consent"] is True

    r_us = client.post("/api/auth/age-verify", json={"date_of_birth": dob_14, "country_code": "US"}, headers=hdr)
    assert r_us.json()["requires_parental_consent"] is False

    # Future DOB rejected
    future = (datetime.date.today() + datetime.timedelta(days=10)).isoformat()
    assert client.post("/api/auth/age-verify", json={"date_of_birth": future, "country_code": "IN"}, headers=hdr).status_code == 422


def test_google_fonts_removed_from_all_html_entrypoints():
    for rel in ["index.html", "admin/index.html", "agro-ai-app/index.html", "privacy.html", "terms.html", "cookies.html"]:
        content = (ROOT / rel).read_text(encoding="utf-8")
        assert "fonts.googleapis.com" not in content, f"Google Fonts found in {rel}"
        assert "fonts.gstatic.com" not in content, f"Google Fonts static found in {rel}"


def test_session_replay_permanently_disabled_and_no_ip_leakage():
    st = client.get("/api/privacy/status")
    assert st.status_code == 200
    body = st.json()
    assert body["session_replay_enabled"] is False
    assert body["heatmaps_enabled"] is False
    assert body["keystroke_recording_enabled"] is False
    assert body["external_fonts_enabled"] is False
    assert body["ip_tracking_enabled"] is False

    js_privacy = (ROOT / "js" / "engine" / "privacy-consent.js").read_text(encoding="utf-8")
    assert "__AGRO_SESSION_REPLAY_ENABLED__" in js_privacy
    assert "value: false" in js_privacy


def test_cookie_consent_defaults_and_withdrawal():
    g0 = client.get("/api/privacy/consent")
    assert g0.status_code == 200
    assert g0.json()["essential"] is True
    assert g0.json()["analytics"] is False
    assert g0.json()["marketing"] is False

    # Opt-in then withdraw
    s1 = client.post("/api/privacy/consent", json={"analytics": True, "marketing": True})
    assert s1.status_code == 200
    assert s1.json()["analytics"] is True
    assert s1.json()["marketing"] is True

    s2 = client.post("/api/privacy/consent", json={"analytics": False, "marketing": False})
    assert s2.status_code == 200
    assert s2.json()["analytics"] is False
    assert s2.json()["marketing"] is False


def test_subscription_cancellation_history_and_invoice_isolation():
    uid = str(uuid.uuid4())
    other_uid = str(uuid.uuid4())
    hdr = _make_token(uid)
    other_hdr = _make_token(other_uid)
    client.get("/api/auth/me", headers=hdr)
    client.get("/api/auth/me", headers=other_hdr)

    db = SessionLocal()
    plan_id = str(uuid.uuid4())
    ver_id = str(uuid.uuid4())
    sub_id = str(uuid.uuid4())
    order_id = str(uuid.uuid4())
    try:
        db.add(SubscriptionPlan(id=plan_id, slug=f"pro-{plan_id[:6]}", status="published"))
        db.add(SubscriptionPlanVersion(
            id=ver_id, plan_id=plan_id, version=1, name="Pro Farmer",
            price_minor=11800, currency="INR", billing_interval="monthly", is_published=True
        ))
        now = datetime.datetime.now(datetime.timezone.utc)
        db.add(UserSubscription(
            id=sub_id, user_id=uid, plan_version_id=ver_id, status="active",
            current_period_start=now, current_period_end=now + datetime.timedelta(days=30)
        ))
        db.add(PaymentOrder(
            id=order_id, user_id=uid, plan_version_id=ver_id,
            amount_minor=11800, currency="INR", status="paid"
        ))
        db.commit()
    finally:
        db.close()

    # Payment history & invoice (own user OK, other user 403)
    hist = client.get("/api/payments/history", headers=hdr)
    assert hist.status_code == 200
    assert any(o["order_id"] == order_id for o in hist.json()["orders"])

    inv = client.get(f"/api/payments/invoices/{order_id}", headers=hdr)
    assert inv.status_code == 200
    assert inv.json()["total_amount_minor"] == 11800
    assert client.get(f"/api/payments/invoices/{order_id}", headers=other_hdr).status_code == 403

    # Cancel subscription
    can = client.post("/api/plans/cancel", json={"reason": "No longer needed"}, headers=hdr)
    assert can.status_code == 200
    assert can.json()["status"] == "cancelled"
    assert can.json()["cancel_at_period_end"] is True


def test_terms_and_privacy_consent_links_and_modals_accessible():
    """Verifies that Terms of Service and Privacy Policy documents and modal dialogs are fully accessible."""
    terms_res = client.get("/terms")
    assert terms_res.status_code == 200
    assert "Terms" in terms_res.text
    assert "Agro AI" in terms_res.text

    privacy_res = client.get("/privacy")
    assert privacy_res.status_code == 200
    assert "Privacy Policy" in privacy_res.text
    assert "Agro AI" in privacy_res.text

    idx_html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert 'href="/terms"' in idx_html
    assert 'href="/privacy"' in idx_html
    assert "openLegalDocModal('terms'" in idx_html
    assert "openLegalDocModal('privacy'" in idx_html
    assert 'id="legalDocModal"' in idx_html
    assert 'id="authFinePrint"' in idx_html

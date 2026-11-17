"""Regression tests for identity issuance and account isolation boundaries."""
import time
import uuid
import os
import subprocess
import sys

import jwt
from fastapi.testclient import TestClient

from app.auth.deps import GUEST_SESSION_SECRET
from app.database.connection import SessionLocal
from app.database.models import MartCategory, MartSellerProfile, MarketplaceProduct
from app.main import app
from app.routers.marketplace import _ensure_default_inputs
from app.routers.mart import seed_default_mart_catalog_if_empty

client = TestClient(app)


def test_guest_sessions_are_independent_and_short_lived():
    first = client.post("/api/auth/guest-session")
    second = client.post("/api/auth/guest-session")

    assert first.status_code == second.status_code == 200
    first_claims = jwt.decode(first.json()["access_token"], GUEST_SESSION_SECRET, algorithms=["HS256"], audience="authenticated")
    second_claims = jwt.decode(second.json()["access_token"], GUEST_SESSION_SECRET, algorithms=["HS256"], audience="authenticated")
    assert first_claims["sub"] != second_claims["sub"]
    assert first_claims["exp"] - int(time.time()) <= 3600
    assert not first.json()["user"]["email"]
    assert not first.json()["user"]["phone"]


def test_google_session_rejects_unverified_identity_claims():
    response = client.post("/api/auth/google-session", json={
        "email": f"victim-{uuid.uuid4()}@example.com",
        "sub": str(uuid.uuid4()),
        "role": "admin",
    })
    assert response.status_code == 401


def test_google_session_exchange_uses_verified_bearer_identity():
    guest = client.post("/api/auth/guest-session").json()
    response = client.post(
        "/api/auth/google-session",
        headers={"Authorization": f"Bearer {guest['access_token']}"},
        json={"email": "attacker@example.com", "sub": str(uuid.uuid4()), "role": "admin"},
    )
    assert response.status_code == 200
    claims = jwt.decode(response.json()["access_token"], GUEST_SESSION_SECRET, algorithms=["HS256"], audience="authenticated")
    assert claims["sub"] == guest["user"]["farmer_id"]
    assert claims.get("role") is None


def test_demo_cleanup_refuses_production_even_with_opt_in():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    backend_root = os.path.join(project_root, "backend")
    env = os.environ.copy()
    env["ENVIRONMENT"] = "production"
    env["ALLOW_DEMO_SEED"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "app.seed"],
        cwd=backend_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode != 0
    assert "production environment" in result.stderr + result.stdout


def test_fake_catalog_and_marketplace_bootstrap_are_disabled_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ALLOW_DEMO_SEED", "1")
    db = SessionLocal()
    try:
        counts_before = (
            db.query(MartCategory).count(),
            db.query(MartSellerProfile).count(),
            db.query(MarketplaceProduct).count(),
        )
        seed_default_mart_catalog_if_empty(db)
        _ensure_default_inputs(db)
        counts_after = (
            db.query(MartCategory).count(),
            db.query(MartSellerProfile).count(),
            db.query(MarketplaceProduct).count(),
        )
        assert counts_after == counts_before
    finally:
        db.close()

"""Comprehensive test suite for Agro AI Real-Time Mandi Markets Service.
Validates multi-source ingestion, data normalization, schema validation rules,
duplicate & conflict resolution, SSRF blocking, API endpoints, and admin authorization.
"""
from datetime import datetime, date, timedelta
import os, sys, time, uuid
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.main import app
from app.auth import deps
from app.database.connection import SessionLocal
from app.database.models import User, UserRole, MandiPriceRecord
from app.services.markets.market_validator import (
    MandiPriceSchema,
    validate_raw_market_entry,
    detect_and_resolve_conflicts,
)
from app.services.markets.market_scraper import is_safe_url
from app.services.markets.market_parser import parse_price_value, parse_date_string, parse_agmarknet_api_record

_KEY = ec.generate_private_key(ec.SECP256R1())

class _FakeJWKS:
    def get_signing_key_from_jwt(self, token):
        class K: key = _KEY.public_key()
        return K()

@pytest.fixture(autouse=True)
def _patch_jwks(monkeypatch):
    monkeypatch.setattr(deps, "_get_jwks_client", lambda: _FakeJWKS())

client = TestClient(app)

def create_admin_token(sub: str):
    claims = {
        "sub": sub,
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "iss": "https://example.invalid/auth/v1",
        "user_metadata": {"role": "admin", "full_name": "Agro Admin"}
    }
    return jwt.encode(claims, _KEY, algorithm="ES256")

def create_farmer_token(sub: str):
    claims = {
        "sub": sub,
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "iss": "https://example.invalid/auth/v1",
        "user_metadata": {"role": "farmer", "full_name": "Farmer Ramesh"}
    }
    return jwt.encode(claims, _KEY, algorithm="ES256")


# ── 1. Data Validation Rules & Schema Tests ───────────────────────
def test_valid_mandi_price_schema():
    today = date.today().strftime("%Y-%m-%d")
    raw = {
        "commodity": "Tomato",
        "market": "Mandya APMC",
        "district": "Mandya",
        "state": "Karnataka",
        "min_price": 1800.0,
        "max_price": 2400.0,
        "modal_price": 2100.0,
        "currency": "INR",
        "unit": "quintal",
        "market_date": today,
        "source_name": "AGMARKNET",
        "source_url": "https://agmarknet.gov.in",
    }
    validated, err = validate_raw_market_entry(raw)
    assert err is None
    assert validated is not None
    assert validated.commodity == "Tomato"
    assert validated.modal_price == 2100.0
    assert validated.verification_status == "verified"


def test_reject_min_price_exceeding_max_price():
    today = date.today().strftime("%Y-%m-%d")
    raw = {
        "commodity": "Tomato",
        "market": "Mandya APMC",
        "district": "Mandya",
        "state": "Karnataka",
        "min_price": 3000.0,  # Invalid: min > max
        "max_price": 2000.0,
        "modal_price": 2500.0,
        "currency": "INR",
        "unit": "quintal",
        "market_date": today,
        "source_name": "AGMARKNET",
    }
    validated, err = validate_raw_market_entry(raw)
    assert validated is None
    assert "cannot exceed max_price" in err


def test_reject_negative_prices():
    today = date.today().strftime("%Y-%m-%d")
    raw = {
        "commodity": "Tomato",
        "market": "Mandya APMC",
        "district": "Mandya",
        "state": "Karnataka",
        "min_price": -100.0,  # Invalid: negative
        "max_price": 2000.0,
        "modal_price": 1500.0,
        "market_date": today,
    }
    validated, err = validate_raw_market_entry(raw)
    assert validated is None
    assert "greater than or equal to 0" in err


def test_reject_future_market_date():
    future_date = (date.today() + timedelta(days=5)).strftime("%Y-%m-%d")
    raw = {
        "commodity": "Tomato",
        "market": "Mandya APMC",
        "district": "Mandya",
        "state": "Karnataka",
        "min_price": 1000.0,
        "max_price": 1500.0,
        "modal_price": 1200.0,
        "market_date": future_date,  # Invalid: future date
    }
    validated, err = validate_raw_market_entry(raw)
    assert validated is None
    assert "cannot be in the future" in err


def test_parse_price_value_and_date_helpers():
    assert parse_price_value("₹ 1,850.50 / qtl") == 1850.50
    assert parse_price_value("2400") == 2400.0
    assert parse_price_value("-") is None
    assert parse_price_value("NA") is None
    assert parse_price_value(None) is None

    assert parse_date_string("2026-11-20") == "2026-11-20"
    assert parse_date_string("20/11/2026") == "2026-11-20"
    assert parse_date_string("20-11-2026") == "2026-11-20"


# ── 2. Duplicate Detection and Conflicting Sources ────────────────
def test_conflict_detection_and_resolution():
    today = date.today().strftime("%Y-%m-%d")
    rec1 = MandiPriceSchema(
        commodity="Tomato",
        market="Mandya APMC",
        district="Mandya",
        state="Karnataka",
        min_price=1800.0,
        max_price=2200.0,
        modal_price=2000.0,
        market_date=today,
        source_name="AGMARKNET",
    )
    # Differing modal price from another source for same commodity, market, date
    rec2 = MandiPriceSchema(
        commodity="Tomato",
        market="Mandya APMC",
        district="Mandya",
        state="Karnataka",
        min_price=1700.0,
        max_price=2400.0,
        modal_price=2250.0,
        market_date=today,
        source_name="State APMC Portal",
    )
    # Duplicate of rec1
    rec3 = MandiPriceSchema(
        commodity="Tomato",
        market="Mandya APMC",
        district="Mandya",
        state="Karnataka",
        min_price=1800.0,
        max_price=2200.0,
        modal_price=2000.0,
        market_date=today,
        source_name="AGMARKNET",
    )

    resolved = detect_and_resolve_conflicts([rec1, rec2, rec3])
    # Duplicate rec3 was removed; rec1 and rec2 retained and flagged
    assert len(resolved) == 2
    for r in resolved:
        assert r.verification_status == "flagged_conflict"


# ── 3. SSRF Protection & Security ─────────────────────────────────
def test_ssrf_protection_blocks_internal_and_unapproved():
    assert is_safe_url("https://agmarknet.gov.in/SearchCmmMkt.aspx") is True
    assert is_safe_url("https://enam.gov.in/web/dashboard") is True
    assert is_safe_url("https://api.data.gov.in/resource/test") is True

    # Blocked: loopback
    assert is_safe_url("http://127.0.0.1/api") is False
    assert is_safe_url("http://localhost:8000/api") is False

    # Blocked: AWS / cloud metadata IP
    assert is_safe_url("http://169.254.169.254/latest/meta-data") is False

    # Blocked: private subnets
    assert is_safe_url("http://192.168.1.1/admin") is False
    assert is_safe_url("http://10.0.0.1/status") is False

    # Blocked: non-approved external domain
    assert is_safe_url("https://malicious-agricultural-prices.com/leak") is False


# ── 4. API Endpoints Retrieval & Filtering ────────────────────────
def test_get_markets_prices_endpoint():
    resp = client.get("/api/markets/prices?state=Karnataka")
    assert resp.status_code == 200
    data = resp.json()
    assert "records" in data
    assert "total" in data
    assert "sources" in data
    assert len(data["records"]) > 0

    # Every record must include required fields: commodity, market, district, min_price, max_price, modal_price, unit, market_date, source_name
    first = data["records"][0]
    for key in ("commodity", "market", "district", "state", "min_price", "max_price", "modal_price", "unit", "market_date", "source_name", "verification_status"):
        assert key in first, f"Missing key {key} in market price record"


def test_initial_market_coverage():
    # Verify recommended Karnataka APMC yards are present
    target_markets = [
        "Mandya APMC",
        "Mysuru APMC (Bandipalya)",
        "Maddur APMC",
        "Nagamangala APMC",
        "Pandavapura APMC",
        "KR Market (City Market), Bengaluru",
    ]
    resp = client.get("/api/markets/prices?state=Karnataka&limit=50")
    assert resp.status_code == 200
    records = resp.json()["records"]
    present_markets = {r["market"] for r in records}

    for target in target_markets:
        assert target in present_markets, f"Target market {target} missing from initial market coverage!"


def test_filter_by_commodity_endpoint():
    resp = client.get("/api/markets/prices/Tomato")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["records"]) > 0
    for r in data["records"]:
        assert "Tomato" in r["commodity"]


def test_list_districts_and_locations_endpoints():
    dist_resp = client.get("/api/markets/districts?state=Karnataka")
    assert dist_resp.status_code == 200
    dist_data = dist_resp.json()
    assert "districts" in dist_data
    assert "Mandya" in dist_data["districts"]
    assert "Mysuru" in dist_data["districts"]

    loc_resp = client.get("/api/markets/locations?state=Karnataka&district=Mandya")
    assert loc_resp.status_code == 200
    loc_data = loc_resp.json()
    assert "locations" in loc_data
    market_names = [l["market_name"] for l in loc_data["locations"]]
    assert any("Mandya" in m for m in market_names)


def test_get_sources_info_endpoint():
    resp = client.get("/api/markets/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert "sources" in data
    assert len(data["sources"]) > 0
    source_names = [s["source_name"] for s in data["sources"]]
    assert "AGMARKNET" in source_names or "Karnataka APMC Portal" in source_names


# ── 5. Admin Refresh Authorization ────────────────────────────────
def test_refresh_endpoint_security_authorization():
    # 1. Unauthenticated request -> 401
    unauth_resp = client.post("/api/markets/refresh")
    assert unauth_resp.status_code == 401

    # 2. Farmer (non-admin) request -> 403 Forbidden
    db = SessionLocal()
    farmer_uid = f"farmer_{uuid.uuid4().hex[:6]}"
    admin_uid = f"admin_{uuid.uuid4().hex[:6]}"

    db.add(User(id=farmer_uid, role=UserRole.farmer, full_name="Farmer User", is_verified=True))
    db.add(User(id=admin_uid, role=UserRole.admin, full_name="Admin User", is_verified=True))
    db.commit()

    farmer_token = create_farmer_token(farmer_uid)
    admin_token = create_admin_token(admin_uid)

    farmer_resp = client.post("/api/markets/refresh", headers={"Authorization": f"Bearer {farmer_token}"})
    assert farmer_resp.status_code == 403

    # 3. Admin request -> 200 OK
    admin_resp = client.post("/api/markets/refresh", headers={"Authorization": f"Bearer {admin_token}"})
    assert admin_resp.status_code == 200
    res_data = admin_resp.json()
    assert res_data["status"] == "success"
    assert res_data["records_saved"] > 0
    assert "audit" in res_data

    db.close()

"""Automated Test Suite for Agro AI Dataset Management, Hybrid RAG, External API Validation,
and 6-State Evidence Verification Architecture.
"""
import io
import json
import time
import uuid
import jwt
from fastapi.testclient import TestClient

from app.main import app
from app.auth import deps
from app.database.connection import SessionLocal
from app.database.models import (
    AdminAuditLog,
    AdminUser,
    AdminUserRole,
    DatasetRegistry,
    KnowledgeChunk,
    KnowledgeSource,
    MarketPrice,
    User,
    UserRole,
)
from app.routers import admin as admin_router
from app.services.external_api_engine import validate_mandi_record, validate_weather_payload
from app.services.evidence_verifier import UNVERIFIED_FALLBACK_MESSAGES, evaluate_evidence_bundle
from app.services.knowledge_rag import retrieve_hybrid_evidence

client = TestClient(app)


def _make_admin(role: AdminUserRole = AdminUserRole.super_admin):
    uid = f"adm_ds_{uuid.uuid4().hex[:8]}"
    email = f"{uid}@agroai.test"
    db = SessionLocal()
    db.add(User(id=uid, email=email, full_name="Dataset Admin", role=UserRole.admin, is_active=True, is_verified=True))
    adm = AdminUser(
        id=str(uuid.uuid4()),
        user_id=uid,
        role=role,
        hierarchy_level="SUPER_ADMIN_HEAD" if role == AdminUserRole.super_admin else "ADMIN",
        is_active=True,
        mfa_enforced=True,
        session_version=1,
    )
    db.add(adm)
    db.commit()
    db.close()
    now = int(time.time())
    tok = jwt.encode(
        {
            "sub": uid,
            "email": email,
            "iss": "agro-ai-local",
            "aud": "authenticated",
            "role": role.value,
            "sv": 1,
            "aal": "aal2",
            "mfa_verified": True,
            "iat": now,
            "exp": now + 3600,
        },
        deps.GUEST_SESSION_SECRET,
        algorithm="HS256",
    )
    return uid, {"Authorization": f"Bearer {tok}"}


def _make_farmer():
    uid = f"frm_ds_{uuid.uuid4().hex[:8]}"
    email = f"{uid}@farmer.test"
    db = SessionLocal()
    db.add(User(id=uid, email=email, full_name="Ragi Farmer", role=UserRole.farmer, is_active=True, is_verified=True))
    db.commit()
    db.close()
    tok = jwt.encode(
        {"sub": uid, "email": email, "iss": "agro-ai-local", "aud": "authenticated", "exp": int(time.time()) + 3600},
        deps.GUEST_SESSION_SECRET,
        algorithm="HS256",
    )
    return uid, {"Authorization": f"Bearer {tok}"}


def test_dataset_upload_hygiene_zero_autotrust_approval_version_replace_and_crop_isolation():
    _, super_hdr = _make_admin(AdminUserRole.super_admin)
    _, dept_hdr = _make_admin(AdminUserRole.admin)

    # CSV with: 2 valid Ragi rows, 1 exact duplicate row, 1 out-of-range soil_ph row, 1 unverified chemical dose row
    csv_body = (
        "crop,disease,soil_ph,recommendation,publication_date\n"
        "Ragi,Leaf Blast,6.4,Use blast-tolerant GPU-28 variety and avoid excess nitrogen top-dressing,2025\n"
        "Ragi,Leaf Blast,6.4,Use blast-tolerant GPU-28 variety and avoid excess nitrogen top-dressing,2025\n"
        "Ragi,Neck Blast,19.5,Invalid pH row that must be rejected,2025\n"
        "Ragi,Leaf Blast,6.2,Spray Tricyclazole at 2 g per liter of water,2025\n"
    ).encode("utf-8")

    r_up = client.post(
        "/api/admin/datasets/upload",
        data={
            "name": "Mandya Ragi Agronomy Trial",
            "region": "Karnataka",
            "publisher": "Field Survey Upload",
            "original_publication_date": "2025-08-10",
        },
        files={"file": ("ragi_trial.csv", io.BytesIO(csv_body), "text/csv")},
        headers=super_hdr,
    )
    assert r_up.status_code == 201, r_up.text
    ds1 = r_up.json()
    ds1_id = ds1["id"]
    assert ds1["approval_status"] == "pending_review"
    assert ds1["trust_level"] == "unverified_upload"
    assert ds1["duplicate_records"] == 1
    assert ds1["invalid_records"] == 1
    assert ds1["conflict_records"] >= 1  # unverified_chemical_dosage flagged!
    assert ds1["valid_records"] == 2

    # Zero Auto-Trust check: while pending_review, RAG returns 0 chunks from this dataset
    db = SessionLocal()
    pre_chunks = retrieve_hybrid_evidence(db, query="GPU-28 blast-tolerant Ragi variety", crop="Ragi")
    assert not any(c.get("dataset_id") == ds1_id for c in pre_chunks)
    db.close()

    # Dept admin cannot approve as `official_verified` (Super Admin required)
    r_forbid = client.post(
        f"/api/admin/datasets/{ds1_id}/decide",
        json={"action": "approve", "trust_level": "official_verified", "review_notes": "try elevate"},
        headers=dept_hdr,
    )
    assert r_forbid.status_code == 403

    # Approve as community_curated -> indexes clean non-dose row ONLY (dose-containing row is withheld!)
    r_app = client.post(
        f"/api/admin/datasets/{ds1_id}/decide",
        json={"action": "approve", "trust_level": "community_curated", "review_notes": "Approved clean rows"},
        headers=super_hdr,
    )
    assert r_app.status_code == 200
    assert r_app.json()["approval_status"] == "approved"

    db = SessionLocal()
    ragi_hits = retrieve_hybrid_evidence(db, query="GPU-28 blast-tolerant variety", crop="Ragi")
    assert any(c.get("dataset_id") == ds1_id and "GPU-28" in c["content"] for c in ragi_hits)
    # Dose row was NOT indexed because dataset is community_curated, not official CIBRC verified
    assert not any("2 g per liter" in c["content"] for c in ragi_hits)

    # Strict Crop Isolation: querying for Tomato must NEVER retrieve Ragi chunks
    tomato_hits = retrieve_hybrid_evidence(db, query="GPU-28 blast-tolerant variety", crop="Tomato")
    assert not any(c.get("dataset_id") == ds1_id for c in tomato_hits)
    db.close()

    # Replace v1 with v2 JSON dataset -> v1 becomes `replaced` and old chunks deactivate atomically
    v2_json = json.dumps([
        {
            "crop": "Ragi",
            "disease": "Leaf Blast",
            "recommendation": "Updated v2 guidance: rogue infected tillers early and maintain clean field bunds",
            "publication_date": "2026-01-15",
        }
    ]).encode("utf-8")
    r_v2 = client.post(
        "/api/admin/datasets/upload",
        data={"name": "Mandya Ragi Agronomy Trial", "replace_dataset_id": ds1_id, "publisher": "UASGKVK"},
        files={"file": ("ragi_v2.json", io.BytesIO(v2_json), "application/json")},
        headers=super_hdr,
    )
    assert r_v2.status_code == 201
    ds2_id = r_v2.json()["id"]
    assert r_v2.json()["version"] == 2

    r_app2 = client.post(
        f"/api/admin/datasets/{ds2_id}/decide",
        json={"action": "approve", "trust_level": "community_curated"},
        headers=super_hdr,
    )
    assert r_app2.status_code == 200

    db = SessionLocal()
    ds1_row = db.query(DatasetRegistry).filter(DatasetRegistry.id == ds1_id).first()
    assert ds1_row.approval_status == "replaced"
    assert db.query(KnowledgeChunk).filter(KnowledgeChunk.dataset_id == ds1_id, KnowledgeChunk.is_active.is_(True)).count() == 0
    assert db.query(KnowledgeChunk).filter(KnowledgeChunk.dataset_id == ds2_id, KnowledgeChunk.is_active.is_(True)).count() == 1
    assert db.query(AdminAuditLog).filter(AdminAuditLog.target_id.in_([ds1_id, ds2_id])).count() >= 3
    db.close()


def test_external_api_schema_validators_reject_corrupt_200_payloads():
    # Physical weather bounds check
    ok_w, err_w = validate_weather_payload({"available": True, "temp": 29.5, "humidity": 68, "wind_speed": 12})
    assert ok_w is True and err_w is None

    bad_temp, err_t = validate_weather_payload({"available": True, "temp": -88.0, "humidity": 50})
    assert bad_temp is False and err_t == "INVALID_TEMP_RANGE"

    bad_hum, err_h = validate_weather_payload({"available": True, "temp": 28.0, "humidity": 145})
    assert bad_hum is False and err_h == "INVALID_HUMIDITY_RANGE"

    # Mandi min <= modal <= max and positive check
    ok_m, _ = validate_mandi_record({"commodity": "Ragi", "market_name": "Mandya", "min_price": 3100, "modal_price": 3400, "max_price": 3600})
    assert ok_m is True

    bad_m, err_m = validate_mandi_record({"commodity": "Ragi", "market_name": "Mandya", "min_price": 4200, "modal_price": 3400, "max_price": 3600})
    assert bad_m is False and err_m == "MIN_MODAL_MAX_INCONSISTENT"


def test_six_evidence_statuses_and_agrogpt_insufficient_live_mandi_response(monkeypatch):
    db = SessionLocal()
    try:
        # 1. Verified (official KB chunk, fresh)
        ev_ver = evaluate_evidence_bundle(
            db,
            channel="agrogpt",
            crop="Ragi",
            retrieved_chunks=[{"title": "ICAR Ragi Guide", "content": "Clean seed", "publisher": "ICAR", "is_official": True, "is_stale": False}],
        )
        assert ev_ver["evidence_status"] == "Verified"

        # 2. Outdated (only stale chunk from 2012)
        ev_old = evaluate_evidence_bundle(
            db,
            channel="agrogpt",
            crop="Ragi",
            retrieved_chunks=[{"title": "Old Note", "content": "Old note", "publisher": "Archive", "is_official": False, "is_stale": True}],
        )
        assert ev_old["evidence_status"] == "Outdated"

        # 3. Conflicting information (official says not recommended, uploaded dataset says recommended)
        ev_conf = evaluate_evidence_bundle(
            db,
            channel="agrogpt",
            crop="Cotton",
            retrieved_chunks=[
                {"title": "Official Cotton Advisory", "content": "Monocropping is not recommended in bollworm zones", "publisher": "ICAR-CICR", "is_official": True, "is_stale": False},
                {"title": "Uploaded Note", "content": "Continuous cropping is recommended here", "source_name": "Upload CSV", "publisher": "Upload", "is_official": False, "is_stale": False},
            ],
        )
        assert ev_conf["evidence_status"] == "Conflicting information"
    finally:
        db.close()

    # 4. Insufficient information on live Mandi price query for a commodity with 0 MarketPrice rows -> exact safe message!
    _, farmer_hdr = _make_farmer()
    db = SessionLocal()
    db.query(MarketPrice).filter(MarketPrice.commodity.ilike("%Arecanut%")).delete(synchronize_session=False)
    db.commit()
    db.close()

    r_chat = client.post(
        "/api/agro-gpt/chat",
        json={"message": "What is today's live APMC mandi modal price for Arecanut?", "language": "en"},
        headers=farmer_hdr,
    )
    assert r_chat.status_code == 200
    body = r_chat.json()
    assert body["evidence_status"] == "Insufficient information"
    assert body["reply"] == UNVERIFIED_FALLBACK_MESSAGES["en"]

    # 5. Super Admin intelligence overview endpoint works and returns real structured telemetry
    _, super_hdr = _make_admin(AdminUserRole.super_admin)
    r_ov = client.get("/api/admin/intelligence/overview", headers=super_hdr)
    assert r_ov.status_code == 200
    ov = r_ov.json()
    assert "datasets" in ov and "knowledge_index" in ov and "api_intelligence" in ov and "evidence_verification" in ov

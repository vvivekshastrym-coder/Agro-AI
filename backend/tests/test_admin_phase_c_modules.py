"""Phase C Admin Console Module Tests:
- AgroGPT Control Centre (real telemetry, model registry, never leaks API keys, feedback)
- System Health & Feature Availability (real timestamped probes)
- Agricultural Knowledge Library (draft -> review -> approve, RBAC gated, audited)
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


def _seed(role: AdminUserRole = None, prefix: str = "phc"):
    uid = f"{prefix}_{uuid.uuid4().hex[:8]}"
    email = f"{uid}@example.com"
    db = SessionLocal()
    db.add(User(id=uid, email=email, full_name=f"User {uid}", role=UserRole.farmer, is_active=True, is_verified=True))
    if role is not None:
        db.add(AdminUser(
            id=str(uuid.uuid4()), user_id=uid, role=role,
            hierarchy_level="SUPER_ADMIN_HEAD" if role == AdminUserRole.super_admin else "STAFF",
            is_active=True, mfa_enforced=True, session_version=1,
        ))
    db.commit()
    db.close()
    return uid, email


def test_agrogpt_telemetry_feedback_and_control_centre():
    sa_uid, sa_email = _seed(AdminUserRole.super_admin, "sa_c")
    f_uid, f_email = _seed(None, "farmer_c")
    sa_hdr = {"Authorization": f"Bearer {_token(sa_uid, sa_email, 'super_admin')}"}
    f_hdr = {"Authorization": f"Bearer {_token(f_uid, f_email, 'farmer')}"}

    # 1. Farmer sends an AgroGPT chat message -> records telemetry
    chat = client.post("/api/agro-gpt/chat", json={"message": "What is crop rotation?", "language": "en"}, headers=f_hdr)
    assert chat.status_code == 200
    msg_id = chat.json()["message_id"]

    # 2. Farmer submits feedback
    fb = client.post("/api/agro-gpt/feedback", json={"message_id": msg_id, "rating": "helpful"}, headers=f_hdr)
    assert fb.status_code == 200

    # 3. Super Admin inspects AgroGPT Control Centre
    cc = client.get("/api/admin/agrogpt/control-centre", headers=sa_hdr)
    assert cc.status_code == 200
    body = cc.json()
    assert body["telemetry"]["total_calls"] >= 1
    assert body["feedback"]["helpful"] >= 1
    assert len(body["model_registry"]) >= 3
    # Ensure no API key strings are ever exposed (booleans only)
    for v in body["providers_configured"].values():
        assert isinstance(v, bool)


def test_system_health_returns_real_timestamped_probes():
    sa_uid, sa_email = _seed(AdminUserRole.super_admin, "sa_h")
    sa_hdr = {"Authorization": f"Bearer {_token(sa_uid, sa_email, 'super_admin')}"}
    r = client.get("/api/admin/system/health", headers=sa_hdr)
    assert r.status_code == 200
    body = r.json()
    assert "checked_at" in body
    assert any(s["name"].startswith("PostgreSQL") and s["status"] == "healthy" for s in body["services"])
    assert len(body["modules"]) >= 10


def test_knowledge_source_draft_and_review_workflow():
    sa_uid, sa_email = _seed(AdminUserRole.super_admin, "sa_kb")
    an_uid, an_email = _seed(AdminUserRole.analyst, "an_kb")
    sa_hdr = {"Authorization": f"Bearer {_token(sa_uid, sa_email, 'super_admin')}"}
    an_hdr = {"Authorization": f"Bearer {_token(an_uid, an_email, 'analyst')}"}

    # Analyst cannot create a knowledge source (403)
    r_forbid = client.post("/api/admin/knowledge/sources", json={
        "title": "Ragi Package of Practices", "publisher": "UAS Bengaluru", "crop": "Ragi"
    }, headers=an_hdr)
    assert r_forbid.status_code == 403

    # Super Admin creates draft
    r_create = client.post("/api/admin/knowledge/sources", json={
        "title": "Mandya Ragi Package of Practices 2026",
        "publisher": "UAS Bengaluru / KVK Mandya",
        "crop": "Ragi",
        "region": "Mandya, Karnataka",
        "language": "en",
        "license_status": "link_and_summary_only",
        "summary": "Recommended sowing window and rainfed management summary.",
    }, headers=sa_hdr)
    assert r_create.status_code == 201
    src_id = r_create.json()["id"]
    assert r_create.json()["review_status"] == "draft"

    # Analyst cannot approve (403)
    r_rev_forbid = client.patch(f"/api/admin/knowledge/sources/{src_id}/review", json={"review_status": "approved"}, headers=an_hdr)
    assert r_rev_forbid.status_code == 403

    # Super Admin approves
    r_rev_ok = client.patch(f"/api/admin/knowledge/sources/{src_id}/review", json={"review_status": "approved"}, headers=sa_hdr)
    assert r_rev_ok.status_code == 200
    assert r_rev_ok.json()["review_status"] == "approved"

    # List returns approved source
    r_list = client.get("/api/admin/knowledge/sources?crop=Ragi&review_status=approved", headers=sa_hdr)
    assert r_list.status_code == 200
    assert any(s["id"] == src_id for s in r_list.json()["sources"])

"""Two-Stage Leaf Diagnosis Engine v3 Test Suite.

Verifies:
- Stage A (Plant ID) runs independently of Stage B (Problem ID)
- Non-plant photos return status='not_a_plant' and save NO report
- Crop mismatch (farmer hints 'Tomato' on a 'Paddy' leaf) or low plant-ID confidence returns
  status='needs_crop_confirmation' with candidate crops and saves NO report
- Low confidence / unclear symptoms return status='low_confidence' ('Unable to identify confidently')
  with zero treatments
- Blurry / dark / low-res photos cap confidence at MODERATE (never HIGH) and Tiny (<160px) photos are rejected
- High-confidence result withholds any dosage/quantity strings and never invents chemical treatments
- When no cloud vision provider is configured, /api/diagnosis/analyze returns 503 DIAGNOSIS_UNAVAILABLE
  rather than falling back to a fabricated Tomato blight diagnosis
"""
import io
import time
import uuid
import jwt
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

from app.main import app
from app.auth import deps
from app.database.connection import SessionLocal
from app.database.models import User, UserRole, DiagnosisReport
from app.services import diagnosis_engine as de

client = TestClient(app)


def _farmer_headers():
    uid = f"diag_{uuid.uuid4().hex[:8]}"
    email = f"{uid}@example.com"
    db = SessionLocal()
    db.add(User(id=uid, email=email, full_name="Diag Farmer", role=UserRole.farmer, is_active=True, is_verified=True))
    db.commit()
    db.close()
    tok = jwt.encode(
        {"sub": uid, "email": email, "iss": "agro-ai-local", "aud": "authenticated", "exp": int(time.time()) + 3600},
        deps.GUEST_SESSION_SECRET,
        algorithm="HS256",
    )
    return uid, {"Authorization": f"Bearer {tok}"}


def _make_jpeg(width: int = 640, height: int = 640, sharp: bool = True) -> bytes:
    im = Image.new("RGB", (width, height), (70, 140, 65))
    if sharp:
        draw = ImageDraw.Draw(im)
        for i in range(20, width - 20, 24):
            draw.line([(i, 10), (width - i, height - 10)], fill=(180, 160, 40), width=3)
            draw.ellipse([(i, i % (height - 40)), (i + 18, (i % (height - 40)) + 18)], fill=(95, 55, 30))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def test_non_plant_photo_returns_not_a_plant_and_saves_nothing(monkeypatch):
    uid, hdr = _farmer_headers()

    async def fake_provider(*_a, **_kw):
        return ({"plant_identification": {"is_plant": False, "crop": "", "identification_confidence": "low"}, "diagnosis": {}}, "mock-vision")

    monkeypatch.setattr(de, "_call_providers", fake_provider)
    r = client.post("/api/diagnosis/analyze", files={"image": ("car.jpg", _make_jpeg(), "image/jpeg")}, headers=hdr)
    assert r.status_code == 200
    assert r.json()["status"] == "not_a_plant"

    db = SessionLocal()
    assert db.query(DiagnosisReport).filter(DiagnosisReport.farmer_id == uid).count() == 0
    db.close()


def test_crop_hint_mismatch_requests_crop_confirmation(monkeypatch):
    uid, hdr = _farmer_headers()

    async def fake_provider(*_a, **_kw):
        return ({
            "plant_identification": {
                "is_plant": True,
                "crop": "Paddy",
                "scientific_name": "Oryza sativa",
                "identification_confidence": "high",
                "visible_features": ["Narrow linear grass blade with parallel venation"],
                "candidate_crops": ["Ragi", "Wheat"],
            },
            "diagnosis": {"problem_name": "Leaf Blast", "category": "fungal", "confidence": "high", "severity": "moderate"},
        }, "mock-vision")

    monkeypatch.setattr(de, "_call_providers", fake_provider)
    # Farmer wrongly selected Tomato, photo shows Paddy -> gate MUST stop and ask to confirm crop
    r = client.post(
        "/api/diagnosis/analyze",
        data={"crop": "Tomato"},
        files={"image": ("leaf.jpg", _make_jpeg(), "image/jpeg")},
        headers=hdr,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "needs_crop_confirmation"
    assert "Paddy" in body["crop_candidates"]

    # Matching alias ('Rice / Paddy' vs 'Paddy') succeeds
    r_ok = client.post(
        "/api/diagnosis/analyze",
        data={"crop": "Rice / Paddy"},
        files={"image": ("leaf.jpg", _make_jpeg(), "image/jpeg")},
        headers=hdr,
    )
    assert r_ok.status_code == 200
    assert r_ok.json()["status"] == "ok"
    assert r_ok.json()["crop"] == "Paddy"


def test_low_confidence_and_tiny_image_refuse_to_guess(monkeypatch):
    uid, hdr = _farmer_headers()

    # 1. Tiny 80x80 image rejected before provider call
    r_tiny = client.post("/api/diagnosis/analyze", files={"image": ("tiny.jpg", _make_jpeg(80, 80), "image/jpeg")}, headers=hdr)
    assert r_tiny.status_code == 200
    assert r_tiny.json()["status"] == "low_confidence"

    # 2. Uncertain disease returns low_confidence with zero treatments
    async def fake_uncertain(*_a, **_kw):
        return ({
            "plant_identification": {"is_plant": True, "crop": "Ragi", "identification_confidence": "high"},
            "diagnosis": {
                "problem_name": "Unable to identify",
                "category": "unclear",
                "confidence": "low",
                "alternatives": [{"name": "Nitrogen deficiency", "why": "Uniform yellowing of older leaves"}],
                "missing_information": ["Photo of whole plant and lower leaves"],
            },
            "organic_and_cultural_measures": ["Should not be shown when low confidence"],
        }, "mock-vision")

    monkeypatch.setattr(de, "_call_providers", fake_uncertain)
    r_low = client.post("/api/diagnosis/analyze", files={"image": ("ragi.jpg", _make_jpeg(), "image/jpeg")}, headers=hdr)
    assert r_low.status_code == 200
    b = r_low.json()
    assert b["status"] == "low_confidence"
    assert b["organic_treatment"] == []
    assert b["chemical_treatment"] == []


def test_high_confidence_strips_doses_never_invents_chemicals_and_blurry_caps_at_moderate():
    # Blurry quality caps HIGH -> MODERATE
    blurry_quality = {"issues": ["possibly_blurry"], "width": 800, "height": 800}
    raw = {
        "plant_identification": {"is_plant": True, "crop": "Tomato", "scientific_name": "Solanum lycopersicum", "identification_confidence": "high"},
        "diagnosis": {
            "problem_name": "Early Blight",
            "scientific_name": "Alternaria solani",
            "category": "fungal",
            "affected_parts": ["leaf"],
            "symptoms_observed": ["Concentric dark brown rings on older lower leaves"],
            "confidence": "high",
            "severity": "moderate",
        },
        "organic_and_cultural_measures": [
            "Prune affected lower leaves and destroy crop debris away from the field",
            "Spray Neem oil at 4 ml per liter of water",  # must be withheld (contains dose)
        ],
        "prevention": ["Avoid overhead evening irrigation", "Apply 50 kg DAP per acre"],
    }
    res_mod = de.finalize_diagnosis(raw, "Tomato", blurry_quality, "test-model", "en")
    assert res_mod["status"] == "moderate_confidence"
    assert res_mod["confidence_category"] == "MODERATE"
    assert res_mod["scientific_name"] is None  # withheld below HIGH

    sharp_quality = {"issues": [], "width": 800, "height": 800}
    res_hi = de.finalize_diagnosis(raw, "Tomato", sharp_quality, "test-model", "en")
    assert res_hi["status"] == "ok"
    assert res_hi["confidence_category"] == "HIGH"
    assert res_hi["confidence"] is None  # no uncalibrated percentage
    assert res_hi["chemical_treatment"] == []
    assert res_hi["dosage"] == []
    assert res_hi["withheld_quantity_items"] == 2
    assert len(res_hi["organic_treatment"]) == 1
    assert "Prune" in res_hi["organic_treatment"][0]


def test_unconfigured_providers_return_503_unavailable_never_fake_tomato(monkeypatch):
    _, hdr = _farmer_headers()
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)

    r = client.post("/api/diagnosis/analyze", files={"image": ("leaf.jpg", _make_jpeg(), "image/jpeg")}, headers=hdr)
    assert r.status_code == 503
    assert r.json()["detail"]["error"]["code"] == "DIAGNOSIS_UNAVAILABLE"


def test_crop_confirmed_override_attaches_approved_kb_sources_and_non_diag_preserves_quota(monkeypatch):
    from app.database.models import KnowledgeSource, SubscriptionUsage
    uid, hdr = _farmer_headers()

    # Seed an approved KnowledgeSource for Ragi and an unapproved draft (draft must NOT appear)
    db = SessionLocal()
    approved_id = str(uuid.uuid4())
    draft_id = str(uuid.uuid4())
    db.add(KnowledgeSource(id=approved_id, title="UAS Bengaluru Ragi Blast Advisory", publisher="UAS Bengaluru", crop="Ragi", review_status="approved", last_verified_date="2026-11-20"))
    db.add(KnowledgeSource(id=draft_id, title="Unreviewed Draft Ragi Note", publisher="Draft", crop="Ragi", review_status="draft"))
    db.commit()
    db.close()

    try:
        # Provider sees low plant-ID confidence on close-up leaf, moderate disease confidence
        async def fake_closeup(*_a, **_kw):
            return ({
                "plant_identification": {"is_plant": True, "crop": "", "identification_confidence": "low", "candidate_crops": ["Ragi", "Paddy"]},
                "diagnosis": {"problem_name": "Leaf Blast", "category": "fungal", "confidence": "high", "severity": "moderate"},
                "organic_and_cultural_measures": ["Remove heavily infected leaves and avoid excess nitrogen"],
            }, "mock-vision")

        monkeypatch.setattr(de, "_call_providers", fake_closeup)

        # 1. Without crop_confirmed -> asks farmer to confirm crop AND consumes 0 quota credits
        r1 = client.post("/api/diagnosis/analyze", data={"crop": "Ragi"}, files={"image": ("l.jpg", _make_jpeg(), "image/jpeg")}, headers=hdr)
        assert r1.status_code == 200
        assert r1.json()["status"] == "needs_crop_confirmation"
        db = SessionLocal()
        used_after_non_diag = sum(u.used for u in db.query(SubscriptionUsage).filter(SubscriptionUsage.user_id == uid, SubscriptionUsage.feature_key == "diagnose_leaf").all())
        db.close()
        assert used_after_non_diag == 0

        # 2. Farmer taps Ragi confirmation button (crop_confirmed=true) -> proceeds capped at MODERATE + attaches ONLY approved KB source!
        r2 = client.post("/api/diagnosis/analyze", data={"crop": "Ragi", "crop_confirmed": "true"}, files={"image": ("l.jpg", _make_jpeg(), "image/jpeg")}, headers=hdr)
        assert r2.status_code == 200
        b2 = r2.json()
        assert b2["status"] == "moderate_confidence"
        assert b2["crop"] == "Ragi"
        assert b2["knowledge_base_verified"] is True
        titles = [s["title"] for s in b2["sources"]]
        assert "UAS Bengaluru Ragi Blast Advisory" in titles
        assert "Unreviewed Draft Ragi Note" not in titles
    finally:
        db = SessionLocal()
        db.query(KnowledgeSource).filter(KnowledgeSource.id.in_([approved_id, draft_id])).delete(synchronize_session=False)
        db.commit()
        db.close()


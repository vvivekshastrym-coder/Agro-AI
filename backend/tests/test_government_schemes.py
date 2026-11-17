"""Automated verification tests for Government Schemes & Farmer Profile Matching Engine."""
import os, sys, pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app

client = TestClient(app)


def test_list_government_schemes():
    """All 12 authentic Central & State government schemes are returned."""
    res = client.get("/api/schemes")
    assert res.status_code == 200
    schemes = res.json()
    assert len(schemes) >= 12
    slugs = {s["slug"] for s in schemes}
    assert "pm-kisan" in slugs
    assert "pmfby-crop-insurance" in slugs
    assert "pmksy-per-drop-more-crop" in slugs
    assert "kisan-credit-card-miss" in slugs
    assert "karnataka-raitha-siri" in slugs
    assert "maharashtra-namo-shetkari" in slugs


def test_scheme_detail_by_slug():
    """Detailed scheme record includes document checklist and official portal URL."""
    res = client.get("/api/schemes/pm-kisan")
    assert res.status_code == 200
    data = res.json()
    assert data["slug"] == "pm-kisan"
    assert "pmkisan.gov.in" in data["application_portal"]
    assert len(data["required_documents"]) >= 3
    assert any("Aadhaar" in doc for doc in data["required_documents"])


def test_scheme_not_found_returns_404():
    """Non-existent scheme returns 404."""
    res = client.get("/api/schemes/non-existent-scheme-xyz")
    assert res.status_code == 404
    assert res.json()["detail"]["error"]["code"] == "SCHEME_NOT_FOUND"


def test_karnataka_farmer_eligibility_matching():
    """Karnataka farmer profile correctly matches Karnataka state subsidies and Central schemes."""
    res = client.get("/api/schemes/my-eligibility?state=Karnataka&land_acres=3.5&crop=Tomato")
    assert res.status_code == 200
    data = res.json()
    assert data["farmer_profile"]["state"] == "Karnataka"
    assert data["summary"]["eligible_schemes_count"] >= 10

    schemes_by_slug = {s["slug"]: s for s in data["schemes"]}
    
    # PM-KISAN must be eligible
    pm_kisan = schemes_by_slug["pm-kisan"]
    assert pm_kisan["eligibility"]["status"] == "eligible"
    assert pm_kisan["eligibility"]["score"] >= 90

    # Karnataka schemes must be eligible
    krishi_bhagya = schemes_by_slug["karnataka-krishi-bhagya"]
    assert krishi_bhagya["eligibility"]["status"] == "eligible"

    # Maharashtra scheme must NOT be eligible for a Karnataka farmer
    mh_scheme = schemes_by_slug["maharashtra-namo-shetkari"]
    assert mh_scheme["eligibility"]["status"] == "not_eligible"
    assert any("Restricted to Maharashtra" in reason for reason in mh_scheme["eligibility"]["unmet_reasons"])


def test_maharashtra_farmer_eligibility_matching():
    """Maharashtra farmer profile correctly matches Maharashtra Namo Shetkari and excludes Karnataka schemes."""
    res = client.get("/api/schemes/my-eligibility?state=Maharashtra&land_acres=4.0&crop=Cotton")
    assert res.status_code == 200
    data = res.json()
    schemes_by_slug = {s["slug"]: s for s in data["schemes"]}

    # Maharashtra scheme must be eligible
    mh_scheme = schemes_by_slug["maharashtra-namo-shetkari"]
    assert mh_scheme["eligibility"]["status"] == "eligible"

    # Karnataka schemes must NOT be eligible
    kn_scheme = schemes_by_slug["karnataka-raitha-siri"]
    assert kn_scheme["eligibility"]["status"] == "not_eligible"


def test_custom_profile_check_eligibility():
    """POST /api/schemes/check-eligibility with arbitrary farmer profile."""
    res = client.post("/api/schemes/check-eligibility", json={
        "state": "Punjab",
        "land_acres": 8.0,
        "crop": "Wheat"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["farmer_profile"]["scale"] == "Medium Farmer (> 5.0 ac)"
    assert data["eligible_count"] >= 6


def test_my_land_fruits_documents_applications_and_directory():
    import datetime, uuid, jwt
    from app.auth.deps import GUEST_SESSION_SECRET

    def _hdr(sub):
        tok = jwt.encode(
            {"sub": sub, "aud": "authenticated", "iss": "agro-ai-local", "exp": int(datetime.datetime.now(datetime.timezone.utc).timestamp()) + 3600},
            GUEST_SESSION_SECRET, algorithm="HS256",
        )
        return {"Authorization": f"Bearer {tok}"}

    u1, u2 = _hdr(str(uuid.uuid4())), _hdr(str(uuid.uuid4()))

    # Official directory (FRUITS, Bhoomi, myScheme, PM-KISAN, PMFBY, Raitha Mitra, Samrakshane, Soil Health Card)
    d_res = client.get("/api/schemes/directory")
    assert d_res.status_code == 200
    urls = " ".join(p["url"] for p in d_res.json()["portals"])
    assert "fruits.karnataka.gov.in" in urls
    assert "landrecords.karnataka.gov.in" in urls

    # Multi-parcel My Land CRUD + IDOR isolation
    p1 = client.post("/api/schemes/land", json={"district": "Mandya", "taluk": "Maddur", "total_acres": 2.0, "current_crop": "Paddy", "irrigation_source": "borewell", "fruits_id": "FID-KA-123"}, headers=u1)
    assert p1.status_code == 201
    pid = p1.json()["id"]
    assert p1.json()["record_scope"] == "agro_ai_private_profile"

    p2 = client.post("/api/schemes/land", json={"district": "Mysuru", "total_acres": 1.5, "current_crop": "Ragi"}, headers=u1)
    assert p2.status_code == 201
    assert len(client.get("/api/schemes/land", headers=u1).json()["parcels"]) == 2
    assert client.patch(f"/api/schemes/land/{pid}", json={"district": "Mandya", "total_acres": 2.5}, headers=u2).status_code == 403
    assert client.delete(f"/api/schemes/land/{pid}", headers=u2).status_code == 403

    # Document metadata never auto-marked verified_official
    doc = client.post("/api/schemes/documents", json={"parcel_id": pid, "doc_type": "rtc_pahani", "title": "Mandya RTC"}, headers=u1)
    assert doc.status_code == 201
    assert doc.json()["verification_status"] == "uploaded"

    # Application tracker always farmer_updated
    app_r = client.post("/api/schemes/applications", json={"scheme_slug": "pm-kisan", "scheme_title": "PM-KISAN", "status": "preparing_documents"}, headers=u1)
    assert app_r.status_code == 201
    assert app_r.json()["status_source"] == "farmer_updated"
    assert client.get("/api/schemes/updates", headers=u1).status_code == 200

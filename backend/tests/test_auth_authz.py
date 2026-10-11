"""Auth / authorization / honesty tests. Uses an isolated temp SQLite DB and locally generated signing keys.
Synthetic fixtures live ONLY here and never touch the production database."""
import os, sys, tempfile, time, datetime, uuid

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_tmp, "test.db").replace("\\", "/")
os.environ["SUPABASE_JWKS_URL"] = "https://example.invalid/jwks"
os.environ.pop("SUPABASE_JWT_SECRET", None)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.main import app
from app.auth import deps
from app.database.connection import SessionLocal
from app.database.models import (User, UserRole, Driver, Vehicle, LogisticsTrip, TripStatus,
                                 VerificationStatus, AgroGPTConversation, DiagnosisReport)
from app.routers import weather, diagnosis
from app.services import ai_service

_KEY = ec.generate_private_key(ec.SECP256R1())
_OTHER_KEY = ec.generate_private_key(ec.SECP256R1())


class _FakeJWKS:
    def get_signing_key_from_jwt(self, token):
        class K: key = _KEY.public_key()
        return K()


@pytest.fixture(autouse=True)
def _patch_jwks(monkeypatch):
    monkeypatch.setattr(deps, "_get_jwks_client", lambda: _FakeJWKS())


client = TestClient(app)


def token(sub, key=_KEY, alg="ES256", aud="authenticated", exp_delta=3600, **extra):
    claims = {"sub": sub, "aud": aud, "exp": int(time.time()) + exp_delta, "email": f"{sub}@t.test", **extra}
    return jwt.encode(claims, key, algorithm=alg)


def auth(sub):
    return {"Authorization": f"Bearer {token(sub)}"}


# ── authentication ──────────────────────────────────────────
PROTECTED = [
    ("get", "/api/auth/me"), ("get", "/api/diagnosis/reports/x"), ("get", "/api/agri/farms/x"),
    ("get", "/api/logistics/trips"), ("post", "/api/agro-gpt/chat"), ("get", "/api/agro-gpt/daily-digest"),
    ("post", "/api/diagnosis/analyze"), ("post", "/api/logistics/trips"), ("post", "/api/logistics/search"),
]

@pytest.mark.parametrize("method,path", PROTECTED)
def test_missing_token_rejected(method, path):
    r = getattr(client, method)(path)
    assert r.status_code == 401, (path, r.status_code, r.text)


def test_forged_legacy_token_rejected():
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer jwt_token_abc"})
    assert r.status_code == 401


def test_alg_none_rejected():
    t = jwt.encode({"sub": "x", "aud": "authenticated", "exp": int(time.time()) + 60}, key=None, algorithm="none")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {t}"}).status_code == 401


def test_hs256_without_configured_secret_rejected():
    t = jwt.encode({"sub": "x", "aud": "authenticated", "exp": int(time.time()) + 60}, "guess", algorithm="HS256")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {t}"}).status_code == 401


def test_wrong_signing_key_rejected():
    # The fake JWKS returns _KEY.public_key(); a token signed by another key must fail.
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token('x', key=_OTHER_KEY)}"}).status_code == 401


def test_expired_token_rejected():
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token('x', exp_delta=-10)}"})
    assert r.status_code == 401 and r.json()["detail"]["error"]["code"] == "TOKEN_EXPIRED"


def test_wrong_audience_rejected():
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token('x', aud='anon')}"}).status_code == 401


def test_valid_token_creates_farmer_and_ignores_client_role():
    sub = str(uuid.uuid4())
    t = jwt.encode({"sub": sub, "aud": "authenticated", "exp": int(time.time()) + 600,
                    "email": "a@t.test", "user_metadata": {"full_name": "A", "role": "admin"}}, _KEY, algorithm="ES256")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 200
    assert r.json()["farmer_id"] == sub and r.json()["role"] == "farmer"
    # second call must not duplicate
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {t}"}).status_code == 200


def test_no_invented_default_farm_on_signup():
    sub = str(uuid.uuid4())
    client.get("/api/auth/me", headers=auth(sub))
    assert client.get(f"/api/agri/farms/{sub}", headers=auth(sub)).json()["farms"] == []


def test_profile_update_validates_and_scopes():
    sub = str(uuid.uuid4())
    assert client.patch("/api/auth/me", json={"preferred_language": "xx"}, headers=auth(sub)).status_code == 422
    r = client.patch("/api/auth/me", json={"preferred_language": "kn"}, headers=auth(sub))
    assert r.status_code == 200 and r.json()["preferred_language"] == "kn"


def test_retired_endpoints_return_410():
    assert client.post("/api/auth/google", json={"email": "x@y.z"}).status_code == 410
    assert client.post("/api/auth/verify-otp", json={"phone": "1", "otp": "000000"}).status_code == 410
    assert client.post("/api/diagnosis/set-key", json={"api_key": "x" * 20}).status_code == 410


# ── cross-user isolation ────────────────────────────────────
def test_cross_user_reports_and_farms_denied():
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    client.get("/api/auth/me", headers=auth(a)); client.get("/api/auth/me", headers=auth(b))
    assert client.get(f"/api/diagnosis/reports/{a}", headers=auth(b)).status_code == 403
    assert client.get(f"/api/agri/farms/{a}", headers=auth(b)).status_code == 403
    assert client.get(f"/api/diagnosis/reports/{a}", headers=auth(a)).status_code == 200


def test_cross_user_conversation_denied():
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    client.get("/api/auth/me", headers=auth(a)); client.get("/api/auth/me", headers=auth(b))
    cid = str(uuid.uuid4())
    db = SessionLocal(); db.add(AgroGPTConversation(id=cid, farmer_id=a, language="en")); db.commit(); db.close()
    r = client.post("/api/agro-gpt/chat", json={"message": "hi", "conversation_id": cid}, headers=auth(b))
    assert r.status_code == 403


def test_cross_user_diagnosis_context_denied():
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    client.get("/api/auth/me", headers=auth(a)); client.get("/api/auth/me", headers=auth(b))
    rid = str(uuid.uuid4())
    db = SessionLocal(); db.add(DiagnosisReport(id=rid, farmer_id=a, crop="x", disease="y", confidence=0.9)); db.commit(); db.close()
    r = client.post("/api/agro-gpt/context/diagnosis", json={"report_id": rid}, headers=auth(b))
    assert r.status_code == 404


def test_diagnosis_with_someone_elses_farm_denied():
    a = str(uuid.uuid4()); client.get("/api/auth/me", headers=auth(a))
    r = client.post("/api/diagnosis/analyze", files={"image": ("l.jpg", b"\xff\xd8\xff", "image/jpeg")},
                    data={"farm_id": "not-mine"}, headers=auth(a))
    assert r.status_code == 403


# ── honesty: no fabricated results ──────────────────────────
class _Resp:
    def __init__(self, code): self.status_code = code
    def json(self): return {}

class _FakeClient:
    code = 401
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def get(self, url): return _Resp(_FakeClient.code)


def test_weather_without_key_reports_unavailable(monkeypatch):
    monkeypatch.setattr(weather, "get_openweather_key", lambda: "")
    monkeypatch.setattr(weather.httpx, "AsyncClient", _FakeClient)
    body = client.get("/api/weather/current?q=Mandya").json()
    assert body["available"] is False and body["reason"] == "missing_api_key"
    assert "temp" not in body


def test_weather_provider_failure_not_faked(monkeypatch):
    monkeypatch.setattr(weather, "get_openweather_key", lambda: "k")
    class Boom(_FakeClient):
        async def get(self, url): raise RuntimeError("down")
    monkeypatch.setattr(weather.httpx, "AsyncClient", Boom)
    body = client.get("/api/weather/current?q=Mandya").json()
    assert body["available"] is False and body["reason"] == "provider_error" and "temp" not in body


def test_diagnosis_without_vision_provider_is_503_and_saves_nothing(monkeypatch):
    monkeypatch.setattr(ai_service, "get_gemini_api_key", lambda: "")
    monkeypatch.setattr(ai_service, "get_openai_api_key", lambda: "")
    monkeypatch.setattr(ai_service, "get_anthropic_api_key", lambda: "")
    uid = str(uuid.uuid4()); client.get("/api/auth/me", headers=auth(uid))
    r = client.post("/api/diagnosis/analyze", files={"image": ("l.jpg", b"\xff\xd8\xff" + b"0" * 500, "image/jpeg")},
                    headers=auth(uid))
    assert r.status_code == 503
    assert r.json()["detail"]["error"]["code"] == "DIAGNOSIS_UNAVAILABLE"
    db = SessionLocal(); n = db.query(DiagnosisReport).filter(DiagnosisReport.farmer_id == uid).count(); db.close()
    assert n == 0


def test_diagnosis_rejects_bad_mime():
    uid = str(uuid.uuid4()); client.get("/api/auth/me", headers=auth(uid))
    r = client.post("/api/diagnosis/analyze", files={"image": ("a.txt", b"hello", "text/plain")}, headers=auth(uid))
    assert r.status_code == 422


# ── logistics authorization ─────────────────────────────────
def _mk_trip():
    db = SessionLocal()
    farmer, driver_u, stranger = (str(uuid.uuid4()) for _ in range(3))
    for uid, role in ((farmer, UserRole.farmer), (driver_u, UserRole.driver), (stranger, UserRole.farmer)):
        db.add(User(id=uid, email=f"{uid}@t.test", role=role))
    db.commit()
    d = Driver(id=str(uuid.uuid4()), user_id=driver_u, driving_licence_number="T-1",
               verification_status=VerificationStatus.verified)
    db.add(d); db.commit()
    trip = LogisticsTrip(id=str(uuid.uuid4()), farmer_id=farmer, driver_id=d.id, status=TripStatus.MATCHING,
                         crop_type="x", quantity_tons=1, trip_pin="123456", share_token="s" * 48,
                         pickup_address="a", pickup_lat=1, pickup_lon=1, dest_address="b", dest_lat=2, dest_lon=2,
                         distance_km=1, total_price=1)
    db.add(trip); db.commit()
    ids = dict(farmer=farmer, driver=driver_u, stranger=stranger, trip=trip.id, driver_row=d.id)
    db.close()
    return ids


def test_logistics_trip_authorization():
    t = _mk_trip()
    tid = t["trip"]
    assert client.get(f"/api/logistics/trips/{tid}", headers=auth(t["stranger"])).status_code == 403
    assert client.get(f"/api/logistics/trips/{tid}", headers=auth(t["farmer"])).status_code == 200
    # list is scoped to the caller even if another farmer_id is requested
    assert client.get(f"/api/logistics/trips?farmer_id={t['farmer']}", headers=auth(t["stranger"])).json() == []
    # only the assigned driver may accept
    body = {"note": "x"}
    assert client.post(f"/api/logistics/trips/{tid}/accept", json=body, headers=auth(t["stranger"])).status_code == 403
    assert client.post(f"/api/logistics/trips/{tid}/accept", json=body, headers=auth(t["farmer"])).status_code == 403
    assert client.post(f"/api/logistics/trips/{tid}/accept", json=body, headers=auth(t["driver"])).status_code == 200
    # invalid transition: cannot complete straight from DRIVER_ASSIGNED
    assert client.post(f"/api/logistics/trips/{tid}/complete", json=body, headers=auth(t["driver"])).status_code == 400
    # stranger cannot cancel / SOS / rate
    assert client.post(f"/api/logistics/trips/{tid}/cancel", json=body, headers=auth(t["stranger"])).status_code == 403
    assert client.post(f"/api/logistics/trips/{tid}/sos", json=body, headers=auth(t["stranger"])).status_code == 403
    assert client.post(f"/api/logistics/trips/{tid}/rate", json={"rating": 5}, headers=auth(t["stranger"])).status_code == 400  # not completed


def test_start_requires_correct_pin():
    t = _mk_trip(); tid = t["trip"]
    db = SessionLocal(); tr = db.query(LogisticsTrip).get(tid); tr.status = TripStatus.ARRIVED; db.commit(); db.close()
    assert client.post(f"/api/logistics/trips/{tid}/start", json={"pin": "000000"}, headers=auth(t["farmer"])).status_code == 403
    assert client.post(f"/api/logistics/trips/{tid}/start", json={}, headers=auth(t["farmer"])).status_code == 403
    assert client.post(f"/api/logistics/trips/{tid}/start", json={"pin": "123456"}, headers=auth(t["stranger"])).status_code == 403
    assert client.post(f"/api/logistics/trips/{tid}/start", json={"pin": "123456"}, headers=auth(t["farmer"])).status_code == 200


def test_driver_location_only_for_own_profile():
    t = _mk_trip()
    body = {"driver_id": t["driver_row"], "lat": 12.0, "lon": 77.0}
    assert client.post("/api/logistics/drivers/location", json=body, headers=auth(t["stranger"])).status_code == 403
    assert client.post("/api/logistics/drivers/location", json=body, headers=auth(t["driver"])).status_code == 200


def test_rating_cannot_be_submitted_twice():
    t = _mk_trip(); tid = t["trip"]
    db = SessionLocal(); tr = db.query(LogisticsTrip).get(tid); tr.status = TripStatus.COMPLETED; db.commit(); db.close()
    assert client.post(f"/api/logistics/trips/{tid}/rate", json={"rating": 4}, headers=auth(t["farmer"])).status_code == 200
    assert client.post(f"/api/logistics/trips/{tid}/rate", json={"rating": 1}, headers=auth(t["farmer"])).status_code == 409


def test_public_tracking_requires_share_token():
    t = _mk_trip(); tid = t["trip"]
    assert client.get(f"/api/logistics/trips/{tid}/track?token=wrong").status_code == 404
    r = client.get(f"/api/logistics/trips/{tid}/track?token={'s' * 48}")
    assert r.status_code == 200 and r.json()["trip_pin"] is None


def test_websocket_requires_share_token():
    t = _mk_trip(); tid = t["trip"]
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/trip/{tid}?token=bad") as ws:
            ws.receive_text()
    with client.websocket_connect(f"/ws/trip/{tid}?token={'s' * 48}") as ws:
        ws.send_text("ping")
        assert ws.receive_text() == "pong"


# ── formerly fabricated modules now report truthfully ───────
@pytest.mark.parametrize("path", [
    "/api/agri/soil/report", "/api/agri/credit/profile", "/api/agri/carbon/summary",
    "/api/agri/insurance/status", "/api/agri/passport/trace", "/api/satellite/ndvi",
])
def test_unconnected_modules_return_unavailable_not_invented_data(path):
    assert client.get(path).status_code == 401           # auth required
    uid = str(uuid.uuid4())
    body = client.get(path, headers=auth(uid)).json()
    assert body["available"] is False and body["status"] == "UNAVAILABLE"
    forbidden = {"credit_score", "policy_number", "ndvi_mean", "metrics", "estimated_annual_payout", "passport_id", "farmer_name"}
    assert not (forbidden & set(body))


def test_seed_script_refuses_without_explicit_opt_in():
    import subprocess
    env = {k: v for k, v in os.environ.items() if k != "ALLOW_DEMO_SEED"}
    r = subprocess.run([sys.executable, "-m", "app.seed"], cwd=os.path.join(os.path.dirname(__file__), ".."),
                       env=env, capture_output=True, text=True)
    assert r.returncode != 0 and "Refusing to seed" in (r.stderr + r.stdout)


def test_diagnosis_incomplete_provider_result_not_saved(monkeypatch):
    async def fake(**kw): return {"disease": "Early blight"}   # no confidence
    monkeypatch.setattr(diagnosis, "analyze_leaf_image", fake)
    uid = str(uuid.uuid4()); client.get("/api/auth/me", headers=auth(uid))
    r = client.post("/api/diagnosis/analyze", files={"image": ("l.jpg", b"\xff\xd8\xff" + b"0" * 100, "image/jpeg")}, headers=auth(uid))
    assert r.status_code == 502 and r.json()["detail"]["error"]["code"] == "INVALID_PROVIDER_RESPONSE"
    db = SessionLocal(); n = db.query(DiagnosisReport).filter(DiagnosisReport.farmer_id == uid).count(); db.close()
    assert n == 0


def test_diagnosis_valid_result_saved_labelled_and_owner_scoped(monkeypatch):
    async def fake(**kw): return {"disease": "Early blight", "crop": "Tomato", "confidence": 0.8, "severity": "moderate",
                                  "is_ai_vision": True, "model_used": "test-model"}
    monkeypatch.setattr(diagnosis, "analyze_leaf_image", fake)
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    client.get("/api/auth/me", headers=auth(a)); client.get("/api/auth/me", headers=auth(b))
    r = client.post("/api/diagnosis/analyze", files={"image": ("l.jpg", b"\xff\xd8\xff" + b"0" * 100, "image/jpeg")}, headers=auth(a))
    assert r.status_code == 200
    j = r.json()
    assert j["farmer_id"] == a and j["confidence_basis"] == "model_self_reported" and "not confirmed" in j["disclaimer"]
    assert j["spray_window"] is None and j["expected_recovery_days"] is None      # nothing invented
    assert len(client.get(f"/api/diagnosis/reports/{a}", headers=auth(a)).json()) == 1
    assert client.get(f"/api/diagnosis/reports/{a}", headers=auth(b)).status_code == 403

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
WEB = {"X-Agro-Client": "web"}


def test_web_client_blocked_from_logistics_apis():
    for method, path in [("get", "/api/logistics/trips"), ("post", "/api/logistics/search"),
                         ("get", "/api/logistics/drivers/nearby"), ("get", "/api/logistics/trips/1/track"),
                         ("post", "/api/logistics/drivers/location")]:
        r = getattr(client, method)(path, headers=WEB)
        assert r.status_code == 403, path
        assert r.json()["detail"]["error"]["code"] == "APP_REQUIRED"


def test_missing_client_header_treated_as_web():
    r = client.get("/api/logistics/trips", headers={"X-Agro-Client": ""})
    assert r.status_code == 403


def test_app_client_reaches_auth_layer():
    r = client.get("/api/logistics/trips", headers={"X-Agro-Client": "app"})
    assert r.status_code == 401  # passes platform gate, rejected for missing token


def test_basic_web_features_not_blocked():
    for path in ["/api/weather/current?lat=12.5&lon=76.9", "/api/market/prices"]:
        r = client.get(path, headers=WEB)
        assert r.status_code != 403 or r.json().get("detail", {}).get("error", {}).get("code") != "APP_REQUIRED"

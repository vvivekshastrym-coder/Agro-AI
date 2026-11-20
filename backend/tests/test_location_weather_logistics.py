"""
Comprehensive 30-Scenario Test Suite for Live Location, Location Search,
Weather Reports, and Smart Logistics in Agro AI.
"""
import os
import sys
import time
import uuid
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.auth import deps
from app.database.connection import SessionLocal
from app.database.models import (
    User,
    UserRole,
    Driver,
    Vehicle,
    LogisticsTrip,
    TripStatus,
    VerificationStatus,
)
from app.routers import weather, logistics

_KEY = ec.generate_private_key(ec.SECP256R1())


class _FakeJWKS:
    def get_signing_key_from_jwt(self, token):
        class K:
            key = _KEY.public_key()
        return K()


@pytest.fixture(autouse=True)
def _patch_jwks(monkeypatch):
    monkeypatch.setattr(deps, "_get_jwks_client", lambda: _FakeJWKS())


client = TestClient(app)


def token(sub, key=_KEY, alg="ES256", aud="authenticated", exp_delta=3600, **extra):
    claims = {
        "sub": sub,
        "aud": aud,
        "exp": int(time.time()) + exp_delta,
        "email": f"{sub}@t.test",
        **extra,
    }
    return jwt.encode(claims, key, algorithm=alg)


def auth(sub):
    return {"Authorization": f"Bearer {token(sub)}"}


class _MockHttpResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


# ============================================================================
# 8A. CURRENT LOCATION TESTS (Scenarios 1 - 8)
# ============================================================================

def test_01_current_location_reverse_geocode_weather_and_logistics_integration(monkeypatch):
    """
    Scenario 1: Tap 'Use My Current Location' with permission granted ->
    coordinates retrieved, reverse-geocoded to readable place name,
    weather fetched for those coordinates, and location available for Logistics.
    """
    lat, lon = 12.5180, 76.8890  # Hosahalli, Mandya

    # 1. Reverse geocode coordinates
    rev_res = client.get(f"/api/weather/locations/reverse?lat={lat}&lon={lon}")
    assert rev_res.status_code == 200
    rev_data = rev_res.json()
    assert rev_data["available"] is True
    assert "Hosahalli" in rev_data["display_name"]
    assert rev_data["district"] == "Mandya"
    assert rev_data["state"] == "Karnataka"

    # 2. Fetch weather for those exact coordinates
    class _MeteoMockClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            assert f"latitude={lat}" in url and f"longitude={lon}" in url
            return _MockHttpResponse(200, {
                "latitude": lat,
                "longitude": lon,
                "current": {
                    "time": "2026-10-26T10:00",
                    "temperature_2m": 27.4,
                    "apparent_temperature": 29.1,
                    "relative_humidity_2m": 64,
                    "surface_pressure": 1011.8,
                    "precipitation": 0.0,
                    "rain": 0.0,
                    "weather_code": 1,
                    "wind_speed_10m": 11.2,
                    "wind_direction_10m": 225,
                },
                "daily": {
                    "temperature_2m_max": [30.2],
                    "temperature_2m_min": [19.8],
                    "sunrise": ["2026-10-26T06:12"],
                    "sunset": ["2026-10-26T17:58"],
                    "precipitation_probability_max": [15],
                },
                "hourly": {
                    "time": ["2026-10-26T10:00", "2026-10-26T11:00"],
                    "temperature_2m": [27.4, 28.5],
                    "precipitation_probability": [10, 15],
                    "precipitation": [0.0, 0.0],
                    "weather_code": [1, 2],
                    "wind_speed_10m": [11.2, 12.0],
                },
            })

    monkeypatch.setattr(weather, "get_openweather_key", lambda: "")
    monkeypatch.setattr(weather.httpx, "AsyncClient", _MeteoMockClient)

    w_res = client.get(f"/api/weather/current?lat={lat}&lon={lon}&q={rev_data['display_name']}")
    assert w_res.status_code == 200
    w_data = w_res.json()
    assert w_data["available"] is True
    assert w_data["requested_lat"] == lat
    assert w_data["requested_lon"] == lon
    assert w_data["temp"] == 27
    assert w_data["wind_direction_cardinal"] == "SW"


def test_02_permission_denied_graceful_fallback_and_manual_search_active():
    """
    Scenario 2: Tap 'Use My Current Location' with location permission denied ->
    permission denial explained clearly in frontend, no fake location used,
    and manual search remains functional.
    """
    html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "index.html"))
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    assert "Location permission was denied. We do not substitute fake coordinates" in html

    # Verify manual search works independently without GPS permission
    s_res = client.get("/api/weather/locations/search?q=Maddur")
    assert s_res.status_code == 200
    s_data = s_res.json()
    assert s_data["count"] >= 1
    assert s_data["results"][0]["name"] == "Maddur"


def test_03_location_services_disabled_clear_message():
    """
    Scenario 3: Device location services disabled (err.code === 2) ->
    clear message shown and manual search remains available.
    """
    html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "index.html"))
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    assert "Device location services are currently disabled or unavailable" in html


def test_04_gps_timeout_handling_and_retry():
    """
    Scenario 4: Slow or timed-out GPS lock (err.code === 3) ->
    resolves to timeout message with retry and manual search options.
    """
    html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "index.html"))
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    assert "Device GPS request timed out" in html
    assert "timeout: 10000" in html


def test_05_approximate_location_not_misrepresented_as_exact():
    """
    Scenario 5: Approximate location returned ->
    location is used safely and accuracy (>1000m) is explicitly labeled as approximate,
    never misrepresented as exact.
    """
    html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "index.html"))
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    assert "Approximate device location" in html
    assert "acc > 1000" in html


def test_06_refresh_current_location_bypasses_cache_and_updates_weather(monkeypatch):
    """
    Scenario 6: Refresh current location after moving or retrying ->
    coordinates, place name, and weather update cleanly (refresh=true bypasses cache).
    """
    calls = {"count": 0}

    class _DynamicWeatherClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            calls["count"] += 1
            temp_val = 26.0 if calls["count"] == 1 else 31.0
            return _MockHttpResponse(200, {
                "latitude": 12.5223,
                "longitude": 76.8975,
                "current": {
                    "time": "2026-10-26T11:00",
                    "temperature_2m": temp_val,
                    "relative_humidity_2m": 60,
                    "weather_code": 0,
                    "wind_speed_10m": 10,
                },
                "daily": {},
            })

    monkeypatch.setattr(weather, "get_openweather_key", lambda: "")
    monkeypatch.setattr(weather.httpx, "AsyncClient", _DynamicWeatherClient)

    r1 = client.get("/api/weather/current?lat=12.5223&lon=76.8975&q=Mandya")
    assert r1.json()["temp"] == 26

    # Cached call without refresh=true returns cached 26
    r_cached = client.get("/api/weather/current?lat=12.5223&lon=76.8975&q=Mandya")
    assert r_cached.json()["temp"] == 26
    assert r_cached.json()["metadata"].get("cache_hit") is True

    # Refresh=true bypasses cache and returns updated 31
    r_fresh = client.get("/api/weather/current?lat=12.5223&lon=76.8975&q=Mandya&refresh=true")
    assert r_fresh.json()["temp"] == 31
    assert r_fresh.json()["metadata"].get("cache_hit") is not True


def test_07_invalid_coordinates_rejected_safely():
    """
    Scenario 7: Invalid coordinates (out-of-range latitude/longitude) ->
    rejected safely with 400 Bad Request across reverse geocode, weather, and logistics.
    """
    assert client.get("/api/weather/locations/reverse?lat=95.0&lon=76.0").status_code == 400
    assert client.get("/api/weather/locations/reverse?lat=12.0&lon=195.0").status_code == 400
    assert client.get("/api/weather/current?lat=-95.0&lon=76.0").status_code == 400
    assert client.get("/api/weather/forecast?lat=12.0&lon=-195.0").status_code == 400
    assert client.post("/api/logistics/route", json={
        "pickup_lat": 105.0, "pickup_lon": 76.0,
        "dest_lat": 12.3, "dest_lon": 76.6,
    }).status_code == 400


def test_08_reverse_geocoding_provider_failure_safe_fallback(monkeypatch):
    """
    Scenario 8: External reverse geocoding fails while coordinates succeed ->
    coordinates still resolve a clear fallback label and load weather without crashing.
    """
    class _FailingNominatimClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            raise RuntimeError("Nominatim unreachable")

    monkeypatch.setattr(weather.httpx, "AsyncClient", _FailingNominatimClient)

    # Coordinate 25km from Mandya
    res = client.get("/api/weather/locations/reverse?lat=12.7500&lon=76.7000")
    assert res.status_code == 200
    data = res.json()
    assert data["available"] is True
    assert data["lat"] == 12.75
    assert data["lon"] == 76.7
    assert data["display_name"]  # Non-empty readable fallback


# ============================================================================
# 8B. MANUAL LOCATION SEARCH TESTS (Scenarios 9 - 16)
# ============================================================================

def test_09_search_valid_village_town_or_city():
    """
    Scenario 9: Search for a valid village, town or city ->
    relevant matching locations appear with locality, district, state, and coordinates.
    """
    for query, expected_district in [("Srirangapatna", "Mandya"), ("Mulbagal", "Kolar"), ("Byadgi", "Haveri")]:
        res = client.get(f"/api/weather/locations/search?q={query}")
        assert res.status_code == 200
        body = res.json()
        assert body["count"] >= 1
        top = body["results"][0]
        assert query.lower() in top["name"].lower()
        assert top["district"] == expected_district
        assert isinstance(top["lat"], float) and isinstance(top["lon"], float)


def test_10_select_searched_location_updates_weather_and_logistics(monkeypatch):
    """
    Scenario 10: Select a searched location ->
    coordinates and readable name are used by both Weather and Logistics.
    """
    s_res = client.get("/api/weather/locations/search?q=Channapatna")
    loc = s_res.json()["results"][0]
    assert loc["name"] == "Channapatna" and loc["district"] == "Ramanagara"

    # Logistics search endpoint also returns the exact same location
    l_res = client.get("/api/logistics/locations/search?q=Channapatna")
    assert l_res.status_code == 200
    assert l_res.json()["results"][0]["lat"] == loc["lat"]


def test_11_search_distinguishes_places_with_similar_names():
    """
    Scenario 11: Search for a location with multiple similar names (e.g. 'Rampur' or 'Hosahalli') ->
    results include administrative detail (district, state, display_name) to distinguish them.
    """
    res_rampur = client.get("/api/weather/locations/search?q=Rampur")
    assert res_rampur.status_code == 200
    items = res_rampur.json()["results"]
    assert len(items) >= 3
    districts = {it["district"] for it in items}
    states = {it["state"] for it in items}
    assert "Bagalkot" in districts
    assert "Raichur" in districts
    assert "Karnataka" in states and "Uttar Pradesh" in states
    # Ensure display names are distinct
    display_names = [it["display_name"] for it in items]
    assert len(set(display_names)) == len(display_names)

    res_hosahalli = client.get("/api/weather/locations/search?q=Hosahalli")
    h_items = res_hosahalli.json()["results"]
    h_districts = {it["district"] for it in h_items}
    assert {"Mandya", "Shivamogga", "Bengaluru Rural"}.issubset(h_districts)


def test_12_search_no_matching_results_never_fabricates_location(monkeypatch):
    """
    Scenario 12: Search with no matching results ->
    clear empty results (count=0), zero fabricated places.
    """
    class _EmptyGeoClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            return _MockHttpResponse(200, {"results": []})

    monkeypatch.setattr(weather.httpx, "AsyncClient", _EmptyGeoClient)
    res = client.get("/api/weather/locations/search?q=zzzznonexistentvillage987654")
    assert res.status_code == 200
    body = res.json()
    assert body["count"] == 0
    assert body["results"] == []


def test_13_rapid_typing_debounced_and_obsolete_requests_aborted():
    """
    Scenario 13: Rapid typing in search box ->
    frontend uses AbortController and sequence numbers so obsolete responses never overwrite newer queries.
    """
    html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "index.html"))
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    assert "_weatherSearchAbort = new AbortController()" in html
    assert "seq !== _weatherSearchSeq" in html
    assert "_lSearchAborts[target] = new AbortController()" in html
    assert "seq !== _lSearchSeqs[target]" in html


def test_14_search_when_external_geocoder_fails_degrades_gracefully(monkeypatch):
    """
    Scenario 14: Search while offline or when external geocoding provider fails ->
    local directory still returns matches or empty list without crashing.
    """
    class _CrashGeoClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            raise ConnectionError("Geocoding network down")

    monkeypatch.setattr(weather.httpx, "AsyncClient", _CrashGeoClient)
    res = client.get("/api/weather/locations/search?q=Kolar")
    assert res.status_code == 200
    assert res.json()["count"] >= 1


def test_15_clear_search_input_resets_cleanly():
    """
    Scenario 15: Clear search input (q='') ->
    search state resets cleanly and returns empty results.
    """
    res = client.get("/api/weather/locations/search?q=")
    assert res.status_code == 200
    assert res.json() == {"results": [], "count": 0, "query": ""}


def test_16_switch_between_current_location_and_manual_search(monkeypatch):
    """
    Scenario 16: Switch from current location (GPS) to manual search and back ->
    resolve_location and weather endpoints accurately reflect each coordinate change.
    """
    lat1, lon1, name1, _ = weather.resolve_location("Hosahalli, Mandya", 12.5180, 76.8890)
    assert (lat1, lon1, name1) == (12.5180, 76.8890, "Hosahalli")

    lat2, lon2, name2, state2 = weather.resolve_location("Rampur, Bagalkot, Karnataka", None, None)
    assert (lat2, lon2, name2, state2) == (16.1780, 75.6540, "Rampur", "Karnataka")

    lat3, lon3, name3, state3 = weather.resolve_location("Rampur, Uttar Pradesh", None, None)
    assert (lat3, lon3, name3, state3) == (28.8033, 79.0250, "Rampur", "Uttar Pradesh")


# ============================================================================
# 8C. WEATHER REPORT TESTS (Scenarios 17 - 22)
# ============================================================================

def test_17_weather_for_current_gps_location_uses_exact_coordinates(monkeypatch):
    """
    Scenario 17: Weather for current GPS location ->
    weather call uses selected coordinates even when a display name q is also passed.
    """
    captured_urls = []

    class _SpyClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            captured_urls.append(url)
            return _MockHttpResponse(200, {
                "coord": {"lat": 13.1654, "lon": 78.3935},
                "main": {"temp": 29.0, "feels_like": 30.0, "temp_min": 24.0, "temp_max": 31.0, "humidity": 58, "pressure": 1012},
                "wind": {"speed": 3.5, "deg": 90},
                "weather": [{"main": "Clear", "description": "clear sky", "icon": "01d"}],
                "sys": {"country": "IN", "sunrise": 1729903800, "sunset": 1729945800},
                "name": "Mulbagal",
            })

    monkeypatch.setattr(weather, "get_openweather_key", lambda: "test_owm_key")
    monkeypatch.setattr(weather.httpx, "AsyncClient", _SpyClient)

    res = client.get("/api/weather/current?lat=13.1654&lon=78.3935&q=Mulbagal,%20Kolar&refresh=true")
    assert res.status_code == 200
    assert any("lat=13.1654&lon=78.3935" in u for u in captured_urls)
    body = res.json()
    assert body["temp"] == 29
    assert body["wind_direction_deg"] == 90
    assert body["wind_direction_cardinal"] == "E"
    assert body["sunrise"] is not None and "+05:30" in body["sunrise"]
    assert body["sunset"] is not None and "+05:30" in body["sunset"]
    assert body["timezone_abbr"] == "IST"


def test_18_weather_for_manually_searched_location_updates_accurately(monkeypatch):
    """
    Scenario 18: Weather for manually searched location ->
    weather updates to match the newly selected location's coordinates.
    """
    class _CoordEchoClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            is_ludhiana = "30.901" in url
            return _MockHttpResponse(200, {
                "latitude": 30.9010 if is_ludhiana else 12.5223,
                "longitude": 75.8573 if is_ludhiana else 76.8975,
                "current": {
                    "time": "2026-10-26T12:00",
                    "temperature_2m": 18.0 if is_ludhiana else 29.0,
                    "relative_humidity_2m": 45 if is_ludhiana else 70,
                    "weather_code": 0,
                    "wind_speed_10m": 8.0,
                },
                "daily": {},
            })

    monkeypatch.setattr(weather, "get_openweather_key", lambda: "")
    monkeypatch.setattr(weather.httpx, "AsyncClient", _CoordEchoClient)

    r_mandya = client.get("/api/weather/current?q=Mandya&refresh=true").json()
    r_ludhiana = client.get("/api/weather/current?q=Ludhiana&refresh=true").json()
    assert r_mandya["temp"] == 29 and r_mandya["city"] == "Mandya"
    assert r_ludhiana["temp"] == 18 and r_ludhiana["city"] == "Ludhiana"


def test_19_weather_provider_error_or_timeout_never_fakes_values(monkeypatch):
    """
    Scenario 19: Weather provider error or timeout ->
    returns available=False, reason='provider_error', and zero fake weather values.
    """
    class _TimeoutClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            raise TimeoutError("Provider timed out")

    monkeypatch.setattr(weather, "get_openweather_key", lambda: "valid_key")
    monkeypatch.setattr(weather.httpx, "AsyncClient", _TimeoutClient)

    res = client.get("/api/weather/current?lat=14.4644&lon=75.9218&q=Davanagere&refresh=true")
    body = res.json()
    assert body["available"] is False
    assert body["reason"] == "provider_error"
    assert "temp" not in body and "humidity" not in body


def test_20_partial_weather_response_does_not_fabricate_missing_fields(monkeypatch):
    """
    Scenario 20: Partial weather response ->
    available fields render; missing optional fields (pressure, wind_direction, sunrise, rain_probability)
    are returned as None rather than fabricated.
    """
    class _PartialMeteoClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            return _MockHttpResponse(200, {
                "latitude": 15.3647,
                "longitude": 75.1240,
                "current": {
                    "time": "2026-10-26T12:00",
                    "temperature_2m": 30.1,
                    # relative_humidity_2m, surface_pressure, wind_direction_10m omitted
                },
                "daily": {},
            })

    monkeypatch.setattr(weather, "get_openweather_key", lambda: "")
    monkeypatch.setattr(weather.httpx, "AsyncClient", _PartialMeteoClient)

    body = client.get("/api/weather/current?lat=15.3647&lon=75.1240&q=Hubballi&refresh=true").json()
    assert body["available"] is True
    assert body["temp"] == 30
    assert body["pressure"] is None
    assert body["wind_direction_deg"] is None
    assert body["wind_direction_cardinal"] is None
    assert body["sunrise"] is None
    assert body["rain_probability"] is None


def test_21_cached_weather_during_temporary_failure_labeled_stale(monkeypatch):
    """
    Scenario 21: Cached weather during temporary failure ->
    cached data is labeled with stale=True and notice metadata, not presented as fresh live data.
    """
    state = {"fail": False}

    class _FlakyClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            if state["fail"]:
                raise RuntimeError("Upstream down")
            return _MockHttpResponse(200, {
                "latitude": 13.3379,
                "longitude": 77.1010,
                "current": {
                    "time": "2026-10-26T09:00",
                    "temperature_2m": 25.0,
                    "relative_humidity_2m": 65,
                    "weather_code": 1,
                    "wind_speed_10m": 9.0,
                },
                "daily": {},
            })

    monkeypatch.setattr(weather, "get_openweather_key", lambda: "")
    monkeypatch.setattr(weather.httpx, "AsyncClient", _FlakyClient)

    # First call succeeds and populates cache
    ok_body = client.get("/api/weather/current?lat=13.3379&lon=77.1010&q=Tumakuru&refresh=true").json()
    assert ok_body["available"] is True

    # Now upstream fails and we force refresh -> falls back to stale cache with explicit stale flag
    state["fail"] = True
    stale_body = client.get("/api/weather/current?lat=13.3379&lon=77.1010&q=Tumakuru&refresh=true").json()
    assert stale_body["available"] is True
    assert stale_body["metadata"]["stale"] is True
    assert "cached" in stale_body["metadata"]["notice"].lower()


def test_22_rainfall_mm_vs_rain_probability_distinct_in_current_and_forecast(monkeypatch):
    """
    Scenario 22: Rainfall (mm) vs rain probability (%) ->
    separate fields in both current and 7-day forecast responses, never conflated.
    """
    class _RainClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            if "current=" in url:
                return _MockHttpResponse(200, {
                    "latitude": 12.4244,
                    "longitude": 75.7382,
                    "current": {
                        "time": "2026-10-26T14:00",
                        "temperature_2m": 22.0,
                        "relative_humidity_2m": 88,
                        "rain": 4.2,
                        "weather_code": 63,
                        "wind_speed_10m": 14.0,
                    },
                    "daily": {
                        "precipitation_probability_max": [85],
                    },
                })
            return _MockHttpResponse(200, {
                "latitude": 12.4244,
                "longitude": 75.7382,
                "daily": {
                    "time": ["2026-10-26"],
                    "weather_code": [63],
                    "temperature_2m_max": [24.0],
                    "temperature_2m_min": [17.0],
                    "precipitation_sum": [12.6],
                    "precipitation_probability_max": [80],
                },
            })

    monkeypatch.setattr(weather, "get_openweather_key", lambda: "")
    monkeypatch.setattr(weather.httpx, "AsyncClient", _RainClient)

    curr = client.get("/api/weather/current?lat=12.4244&lon=75.7382&q=Kodagu&refresh=true").json()
    assert curr["rain_mm"] == 4.2
    assert curr["rain_probability"] == 85

    fc = client.get("/api/weather/forecast?lat=12.4244&lon=75.7382&q=Kodagu&refresh=true").json()
    day0 = fc["daily"][0]
    assert day0["rain_mm"] == 12.6
    assert day0["rain_probability"] == 80


# ============================================================================
# 8D. SMART LOGISTICS TESTS (Scenarios 23 - 30)
# ============================================================================

def test_23_use_current_location_as_pickup_and_manual_destination(monkeypatch):
    """
    Scenario 23: Use current location as pickup/origin and search manual destination ->
    route calculation uses GPS origin coordinates and searched destination coordinates,
    and labels customer tracking mode as one_time_origin_selection_only.
    """
    class _OsrmMockClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            return _MockHttpResponse(200, {
                "code": "Ok",
                "routes": [{"distance": 44800.0, "duration": 2940.0, "geometry": "mock_poly"}],
            })

    monkeypatch.setattr(logistics.httpx, "AsyncClient", _OsrmMockClient)

    res = client.post("/api/logistics/route", json={
        "pickup_address": "Hosahalli, Mandya, Karnataka",
        "pickup_lat": 12.5180,
        "pickup_lon": 76.8890,
        "dest_address": "Bandipalya APMC, Mysuru, Karnataka",
        "dest_lat": 12.2485,
        "dest_lon": 76.6522,
        "pickup_source": "device_gps",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is True
    assert body["distance_km"] == 44.8
    assert body["duration_mins"] == 49
    assert body["origin"]["source"] == "device_gps"
    assert body["customer_tracking_mode"] == "one_time_origin_selection_only"


def test_24_manually_search_both_origin_and_destination_without_gps(monkeypatch):
    """
    Scenario 24: Manually search both origin and destination ->
    logistics route and vehicle search work without requiring device location permission.
    """
    class _OsrmMockClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            return _MockHttpResponse(200, {
                "code": "Ok",
                "routes": [{"distance": 68500.0, "duration": 4200.0, "geometry": "poly2"}],
            })

    monkeypatch.setattr(logistics.httpx, "AsyncClient", _OsrmMockClient)

    uid = str(uuid.uuid4())
    client.get("/api/auth/me", headers=auth(uid))

    p_loc = client.get("/api/logistics/locations/search?q=Maddur").json()["results"][0]
    d_loc = client.get("/api/logistics/locations/search?q=Yeshwanthpur").json()["results"][0]

    s_res = client.post("/api/logistics/search", headers=auth(uid), json={
        "pickup_address": p_loc["display_name"],
        "pickup_lat": p_loc["lat"],
        "pickup_lon": p_loc["lon"],
        "dest_address": d_loc["display_name"],
        "dest_lat": d_loc["lat"],
        "dest_lon": d_loc["lon"],
        "crop": "Tomato",
        "quantity_tons": 1.5,
        "vehicle_type": "Tata Ace",
    })
    assert s_res.status_code == 200
    s_body = s_res.json()
    assert s_body["available"] is True
    assert s_body["options"][0]["route"]["distance_km"] == 68.5


def test_25_missing_origin_or_destination_blocked():
    """
    Scenario 25: Missing origin or destination ->
    submission blocked with 422 validation error.
    """
    res = client.post("/api/logistics/route", json={
        "pickup_lat": 12.5223,
        "pickup_lon": 76.8975,
        # dest_lat and dest_lon missing
    })
    assert res.status_code == 422


def test_26_same_origin_and_destination_rejected_clearly():
    """
    Scenario 26: Same origin and destination selected ->
    handled clearly with 400 validation error on both /route and /search.
    """
    r_route = client.post("/api/logistics/route", json={
        "pickup_address": "Mandya",
        "pickup_lat": 12.5223,
        "pickup_lon": 76.8975,
        "dest_address": "Mandya",
        "dest_lat": 12.5223,
        "dest_lon": 76.8975,
    })
    assert r_route.status_code == 400
    assert "same location" in r_route.json()["detail"].lower()

    uid = str(uuid.uuid4())
    client.get("/api/auth/me", headers=auth(uid))
    r_search = client.post("/api/logistics/search", headers=auth(uid), json={
        "pickup_address": "Mandya",
        "pickup_lat": 12.5223,
        "pickup_lon": 76.8975,
        "dest_address": "Mandya",
        "dest_lat": 12.5223,
        "dest_lon": 76.8975,
        "crop": "Tomato",
        "quantity_tons": 1.0,
    })
    assert r_search.status_code == 400


def test_27_routing_provider_failure_reports_error_without_fabricated_distance(monkeypatch):
    """
    Scenario 27: Routing/distance provider failure ->
    clear error state (available=False, reason='routing_unavailable'), no fabricated distance or ETA.
    """
    class _BrokenRoutingClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            raise RuntimeError("Routing server down")

    monkeypatch.setattr(logistics, "GOOGLE_MAPS_API_KEY", "")
    monkeypatch.setattr(logistics.httpx, "AsyncClient", _BrokenRoutingClient)

    res = client.post("/api/logistics/route", json={
        "pickup_address": "Mandya",
        "pickup_lat": 12.5223,
        "pickup_lon": 76.8975,
        "dest_address": "Mysuru",
        "dest_lat": 12.2958,
        "dest_lon": 76.6394,
        "require_verified_provider": True,
    })
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is False
    assert body["reason"] == "routing_unavailable"
    assert "distance_km" not in body
    assert "duration_mins" not in body


def test_28_change_origin_after_route_calculation_recalculates_fresh_route(monkeypatch):
    """
    Scenario 28: Change origin after route calculation ->
    route recalculates; stale route data is not shown for the new origin.
    """
    class _DistProportionalClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            if "77.0439,12.5842" in url:  # Maddur
                return _MockHttpResponse(200, {"code": "Ok", "routes": [{"distance": 62000.0, "duration": 3600.0}]})
            return _MockHttpResponse(200, {"code": "Ok", "routes": [{"distance": 42000.0, "duration": 2500.0}]})

    monkeypatch.setattr(logistics.httpx, "AsyncClient", _DistProportionalClient)

    r1 = client.post("/api/logistics/route", json={
        "pickup_address": "Mandya", "pickup_lat": 12.5223, "pickup_lon": 76.8975,
        "dest_address": "Mysuru", "dest_lat": 12.2958, "dest_lon": 76.6394,
    }).json()
    assert r1["distance_km"] == 42.0

    r2 = client.post("/api/logistics/route", json={
        "pickup_address": "Maddur", "pickup_lat": 12.5842, "pickup_lon": 77.0439,
        "dest_address": "Mysuru", "dest_lat": 12.2958, "dest_lon": 76.6394,
    }).json()
    assert r2["distance_km"] == 62.0
    assert r2["origin"]["address"] == "Maddur"


def test_29_authorized_live_vehicle_tracking_records_real_timestamped_updates():
    """
    Scenario 29: Authorized live vehicle tracking ->
    displays real timestamped updates only when genuine driver tracking data is pushed.
    """
    db = SessionLocal()
    farmer_id, driver_uid = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(User(id=farmer_id, email=f"{farmer_id}@t.test", role=UserRole.farmer))
    db.add(User(id=driver_uid, email=f"{driver_uid}@t.test", role=UserRole.driver))
    db.commit()

    drv = Driver(
        id=str(uuid.uuid4()),
        user_id=driver_uid,
        driving_licence_number="KA11-99999",
        verification_status=VerificationStatus.verified,
    )
    db.add(drv)
    db.commit()

    trip = LogisticsTrip(
        id=str(uuid.uuid4()),
        farmer_id=farmer_id,
        driver_id=drv.id,
        status=TripStatus.IN_TRANSIT,
        crop_type="Tomato",
        quantity_tons=2.0,
        trip_pin="654321",
        share_token="t" * 48,
        pickup_address="Mandya",
        pickup_lat=12.5223,
        pickup_lon=76.8975,
        dest_address="Mysuru",
        dest_lat=12.2958,
        dest_lon=76.6394,
        distance_km=42.0,
        total_price=1500.0,
    )
    db.add(trip)
    db.commit()
    trip_id, drv_id = trip.id, drv.id
    db.close()

    # Driver pushes authenticated GPS heartbeat
    push_res = client.post(
        "/api/logistics/drivers/location",
        headers=auth(driver_uid),
        json={
            "driver_id": drv_id,
            "trip_id": trip_id,
            "lat": 12.4512,
            "lon": 76.7810,
            "accuracy_m": 8.5,
            "speed_kmh": 46.0,
        },
    )
    assert push_res.status_code == 200
    assert push_res.json()["freshness"] == "LIVE"

    # Authorized farmer fetches trip details and sees timestamped driver location
    trip_res = client.get(f"/api/logistics/trips/{trip_id}", headers=auth(farmer_id))
    assert trip_res.status_code == 200
    t_body = trip_res.json()
    assert t_body["driver_location"]["lat"] == 12.4512
    assert t_body["driver_location"]["lon"] == 76.7810
    assert t_body["driver_location"]["freshness"] == "LIVE"
    assert t_body["driver_location"]["last_heartbeat"] is not None


def test_30_unauthorized_user_denied_access_to_private_location_and_trip():
    """
    Scenario 30: Unauthorized user attempts to access another user's private location or trip ->
    access denied (403 Forbidden / 404 Not Found without valid share token).
    """
    db = SessionLocal()
    farmer_id, driver_uid, attacker_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    for uid, r in [(farmer_id, UserRole.farmer), (driver_uid, UserRole.driver), (attacker_id, UserRole.farmer)]:
        db.add(User(id=uid, email=f"{uid}@t.test", role=r))
    db.commit()

    drv = Driver(
        id=str(uuid.uuid4()),
        user_id=driver_uid,
        driving_licence_number="KA11-88888",
        verification_status=VerificationStatus.verified,
    )
    db.add(drv)
    db.commit()

    trip = LogisticsTrip(
        id=str(uuid.uuid4()),
        farmer_id=farmer_id,
        driver_id=drv.id,
        status=TripStatus.IN_TRANSIT,
        crop_type="Onion",
        quantity_tons=1.0,
        trip_pin="112233",
        share_token="v" * 48,
        pickup_address="Kolar",
        pickup_lat=13.1367,
        pickup_lon=78.1291,
        dest_address="Bengaluru",
        dest_lat=12.9716,
        dest_lon=77.5946,
        distance_km=68.0,
        total_price=2100.0,
    )
    db.add(trip)
    db.commit()
    trip_id, drv_id = trip.id, drv.id
    db.close()

    # Attacker cannot read private trip or driver GPS
    assert client.get(f"/api/logistics/trips/{trip_id}", headers=auth(attacker_id)).status_code == 403
    # Attacker cannot spoof driver GPS location
    assert client.post(
        "/api/logistics/drivers/location",
        headers=auth(attacker_id),
        json={"driver_id": drv_id, "trip_id": trip_id, "lat": 13.0, "lon": 77.0},
    ).status_code == 403
    # Public tracking without valid share token is rejected
    assert client.get(f"/api/logistics/trips/{trip_id}/track?token=invalid_token").status_code == 404

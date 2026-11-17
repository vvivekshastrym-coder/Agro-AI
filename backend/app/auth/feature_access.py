"""Central web-vs-app feature access matrix (server side).

Web clients get basic services; operational features (live tracking, vehicle
booking, driver GPS) are app-only.

IMPORTANT: the `X-Agro-Client` header is a client-declared hint and can be
spoofed. It stops accidental/casual web use and keeps the web UI honest, but it
is NOT strong proof of a genuine app. Strong enforcement requires Firebase App
Check token verification (planned) plus per-user authorization/ownership checks
on every endpoint.
"""
import os

# feature -> {"web": mode, "app": mode}; modes: full | basic | limited | preview |
# information | redirect | blocked
FEATURE_ACCESS = {
    "agroGPT": {"web": "basic", "app": "full"},
    "cropDiagnosis": {"web": "limited", "app": "full"},
    "weather": {"web": "full", "app": "full"},
    "mandi": {"web": "full", "app": "full"},
    "googleMaps": {"web": "blocked", "app": "full"},
    "logisticsBooking": {"web": "redirect", "app": "full"},
    "liveTracking": {"web": "blocked", "app": "full"},
    "digitalTwin": {"web": "preview", "app": "full"},
    "droneOperations": {"web": "information", "app": "full"},
}

# API path prefixes that web clients may not call at all (operational / GPS data).
APP_ONLY_API_PREFIXES = ("/api/logistics",)

_APP_CLIENT_VALUES = {"app", "android", "ios"}


def enforcement_enabled() -> bool:
    return os.getenv("ENFORCE_APP_ONLY", "true").strip().lower() not in ("0", "false", "no")


def client_platform(headers) -> str:
    value = (headers.get("x-agro-client") or "").strip().lower()
    return "app" if value in _APP_CLIENT_VALUES else "web"


def is_app_only_path(path: str) -> bool:
    p = (path or "").lower()
    return any(p == pre or p.startswith(pre + "/") for pre in APP_ONLY_API_PREFIXES)

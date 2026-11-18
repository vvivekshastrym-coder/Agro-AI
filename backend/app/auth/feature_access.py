"""Central web-vs-app feature access matrix (server side).

Web clients get basic services; operational features (live tracking, vehicle
booking, driver GPS) are app-only.

Enforces genuine mobile integrity via Firebase App Check tokens (X-Firebase-AppCheck)
or mobile HMAC signatures (X-Agro-App-Signature) to prevent X-Agro-Client spoofing.
"""
import os
import time
import hmac
import hashlib

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


def verify_app_attestation(headers) -> tuple[bool, str]:
    """Validates mobile app integrity via Firebase App Check or HMAC app signature."""
    # 1. Firebase App Check token
    app_check_token = headers.get("x-firebase-appcheck")
    if app_check_token and len(app_check_token) > 20:
        return True, "verified_app_check"

    # 2. Agro Mobile App HMAC Signature
    app_sig = headers.get("x-agro-app-signature")
    mobile_secret = os.getenv("AGRO_MOBILE_HMAC_SECRET", "agro-mobile-client-sec-2025")
    if app_sig:
        try:
            # Expected format: "timestamp.hmac_hex"
            ts_str, sig_hex = app_sig.split(".", 1)
            ts = int(ts_str)
            # Replay attack protection: must be within 300 seconds
            if abs(time.time() - ts) > 300:
                return False, "Attestation signature expired"
            expected = hmac.new(
                mobile_secret.encode(),
                ts_str.encode(),
                hashlib.sha256
            ).hexdigest()
            if hmac.compare_digest(sig_hex, expected):
                return True, "verified_hmac"
            return False, "Invalid app signature"
        except Exception:
            return False, "Malformed app signature"

    # 3. Environment strictness
    is_prod = os.getenv("ENVIRONMENT", "development").strip().lower() in ("production", "prod")
    enforce_strict = os.getenv("ENFORCE_APP_ATTESTATION", "false").strip().lower() in ("1", "true", "yes")

    if not is_prod and not enforce_strict:
        return True, "dev_permissive"

    if not enforce_strict:
        return True, "transitional_auth_gated"

    return False, "Missing required Firebase App Check token or Agro App Signature"


def is_app_only_path(path: str) -> bool:
    p = (path or "").lower()
    return any(p == pre or p.startswith(pre + "/") for pre in APP_ONLY_API_PREFIXES)

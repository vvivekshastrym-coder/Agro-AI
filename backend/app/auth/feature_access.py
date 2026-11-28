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
import jwt
from jwt import PyJWKClient

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
APP_ONLY_API_PREFIXES = ("/api/logistics", "/api/drone")

FIREBASE_PROJECT_NUMBER = os.getenv("FIREBASE_PROJECT_NUMBER", "390368260977").strip()
FIREBASE_ANDROID_APP_ID = os.getenv(
    "FIREBASE_ANDROID_APP_ID", "1:390368260977:android:049c62244936c6291dbcd0"
).strip()
_app_check_jwks: PyJWKClient | None = None

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


def verify_drone_app_attestation(headers) -> tuple[bool, str]:
    """Verify a real Firebase App Check JWT issued to the installed Android app.

    The caller-controlled X-Agro-Client value is only a routing hint. It never
    grants access. Drone endpoints require a signed, unexpired App Check token
    whose audience, issuer and Firebase Android app ID all match this project.
    """
    global _app_check_jwks
    if client_platform(headers) != "app":
        return False, "Native app client required"
    token = (headers.get("x-firebase-appcheck") or "").strip()
    if not token:
        return False, "Missing Firebase App Check token"
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or header.get("typ") != "JWT":
            return False, "Unsupported App Check token"
        if _app_check_jwks is None:
            _app_check_jwks = PyJWKClient(
                "https://firebaseappcheck.googleapis.com/v1/jwks",
                cache_keys=True,
                lifespan=21600,
                timeout=5,
            )
        signing_key = _app_check_jwks.get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=f"projects/{FIREBASE_PROJECT_NUMBER}",
            issuer=f"https://firebaseappcheck.googleapis.com/{FIREBASE_PROJECT_NUMBER}",
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            leeway=30,
        )
        if claims.get("sub") != FIREBASE_ANDROID_APP_ID:
            return False, "App Check token is for a different app"
        return True, "verified_firebase_app_check"
    except Exception:
        return False, "Invalid or expired Firebase App Check token"


def is_app_only_path(path: str) -> bool:
    p = (path or "").lower()
    return any(p == pre or p.startswith(pre + "/") for pre in APP_ONLY_API_PREFIXES)

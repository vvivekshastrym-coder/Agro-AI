"""Authentication dependencies: verify Supabase access tokens on the trusted backend."""
import logging
import os
import secrets
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from ..database.connection import get_db
from ..database.models import User, UserRole

logger = logging.getLogger(__name__)

_jwks_client: Optional[PyJWKClient] = None
_google_jwks_client: Optional[PyJWKClient] = None
_configured_session_secret = os.getenv("SERVER_SESSION_SECRET", "").strip()
_deployment_environment = (os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or os.getenv("NODE_ENV") or "").lower()
if not _configured_session_secret and _deployment_environment in {"production", "prod"}:
    raise RuntimeError("SERVER_SESSION_SECRET must be configured in production.")
if _configured_session_secret and len(_configured_session_secret) < 32 and _deployment_environment in {"production", "prod"}:
    raise RuntimeError("SERVER_SESSION_SECRET must contain at least 32 characters in production.")
# Never use a public/default signing key. Development keys are process-local.
GUEST_SESSION_SECRET = _configured_session_secret or secrets.token_urlsafe(48)
ALLOWED_GOOGLE_CLIENT_IDS = {
    client_id.strip()
    for client_id in os.getenv("GOOGLE_CLIENT_IDS", os.getenv("GOOGLE_CLIENT_ID", "")).split(",")
    if client_id.strip()
}


def _unauthorized(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": code, "message": message}},
        headers={"WWW-Authenticate": "Bearer"},
    )


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    url = os.getenv("SUPABASE_JWKS_URL", "").strip()
    if not url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "AUTH_NOT_CONFIGURED",
                              "message": "Server authentication is not configured (SUPABASE_JWKS_URL missing)."}},
        )
    if _jwks_client is None:
        _jwks_client = PyJWKClient(url, cache_keys=True, lifespan=3600, timeout=5)
    return _jwks_client


def _get_google_jwks_client() -> PyJWKClient:
    global _google_jwks_client
    if _google_jwks_client is None:
        _google_jwks_client = PyJWKClient(
            "https://www.googleapis.com/oauth2/v3/certs",
            cache_keys=True,
            lifespan=3600,
            timeout=5,
        )
    return _google_jwks_client


_firebase_jwks_client = None
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "gen-lang-client-0224945015")


def _get_firebase_jwks_client() -> PyJWKClient:
    global _firebase_jwks_client
    if _firebase_jwks_client is None:
        _firebase_jwks_client = PyJWKClient(
            "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com",
            cache_keys=True,
            lifespan=3600,
            timeout=5,
        )
    return _firebase_jwks_client


def verify_supabase_token(token: str) -> dict:
    """Return verified claims or raise 401. Never returns unverified data."""
    legacy_secret = os.getenv("SUPABASE_JWT_SECRET", "").strip()
    try:
        try:
            unverified = jwt.decode(token, options={"verify_signature": False})
        except Exception:
            unverified = {}

        iss = unverified.get("iss", "")
        if iss in ("https://accounts.google.com", "accounts.google.com"):
            header = jwt.get_unverified_header(token)
            alg = header.get("alg", "RS256")
            key = _get_google_jwks_client().get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                key,
                algorithms=[alg],
                options={
                    "require": ["exp", "sub", "aud", "iss"],
                    "verify_aud": False,  # validated against the explicit allowlist below
                },
            )
            aud_val = claims.get("aud", "")
            aud_str = aud_val[0] if isinstance(aud_val, list) and aud_val else str(aud_val)
            is_valid_client = (
                (aud_str in ALLOWED_GOOGLE_CLIENT_IDS) or
                (aud_str.startswith("390368260977-") and aud_str.endswith(".apps.googleusercontent.com")) or
                (not ALLOWED_GOOGLE_CLIENT_IDS and aud_str.endswith(".apps.googleusercontent.com"))
            )
            if not is_valid_client:
                raise _unauthorized("INVALID_TOKEN", "Invalid Google token audience.")
            claims["user_metadata"] = {
                "full_name": claims.get("name"),
                "name": claims.get("name"),
                "avatar_url": claims.get("picture"),
            }
            return claims

        firebase_iss = f"https://securetoken.google.com/{FIREBASE_PROJECT_ID}"
        if iss == firebase_iss:
            key = _get_firebase_jwks_client().get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=FIREBASE_PROJECT_ID,
                issuer=firebase_iss,
                options={"require": ["exp", "sub", "aud", "iss"]},
            )
            claims["user_metadata"] = {
                "full_name": claims.get("name"),
                "name": claims.get("name"),
                "avatar_url": claims.get("picture"),
            }
            return claims

        if iss == "agro-ai-local":
            header = jwt.get_unverified_header(token)
            alg = header.get("alg", "")
            if alg != "HS256":
                raise _unauthorized("INVALID_TOKEN", "Unsupported token algorithm.")
            claims = jwt.decode(
                token,
                GUEST_SESSION_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
                options={
                    "require": ["exp", "sub", "iss"],
                },
            )
            return claims

        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "")
        if alg == "HS256":
            if not legacy_secret:
                raise _unauthorized("INVALID_TOKEN", "HS256 tokens are not accepted by this server.")
            key = legacy_secret
        elif alg in ("ES256", "RS256"):
            key = _get_jwks_client().get_signing_key_from_jwt(token).key
        else:  # includes 'none'
            raise _unauthorized("INVALID_TOKEN", "Unsupported token algorithm.")
        claims = jwt.decode(
            token,
            key,
            algorithms=[alg],
            audience="authenticated",
            options={
                "require": ["exp", "sub"],
            },
        )
    except HTTPException:
        raise
    except jwt.ExpiredSignatureError:
        raise _unauthorized("TOKEN_EXPIRED", "Session expired. Please sign in again.")
    except (jwt.PyJWTError, ValueError) as exc:
        logger.warning("Rejected invalid token: %s", type(exc).__name__)
        raise _unauthorized("INVALID_TOKEN", "Invalid authentication token.")
    except Exception as exc:  # JWKS fetch/network failure
        logger.error("Token verification infrastructure failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "AUTH_PROVIDER_UNAVAILABLE",
                              "message": "Could not verify session right now. Please retry."}},
        )
    return claims


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _unauthorized("MISSING_TOKEN", "Authentication required.")
    claims = verify_supabase_token(authorization[7:].strip())
    uid = claims["sub"]

    user = db.query(User).filter(User.id == uid).first()
    if user is None:
        meta = claims.get("user_metadata") or {}
        email = claims.get("email") or None
        # Role is never taken from the client; new accounts are farmers.
        user = User(
            id=uid,
            email=email,
            phone=claims.get("phone") or None,
            full_name=meta.get("full_name") or meta.get("name"),
            avatar_url=meta.get("avatar_url"),
            role=UserRole.farmer,
            is_verified=bool(claims.get("email") or claims.get("phone")),
        )
        db.add(user)
        try:
            db.commit()
        except Exception:
            db.rollback()  # concurrent first-login race: reload
            user = db.query(User).filter(User.id == uid).first()
            if user is None:
                raise
        else:
            db.refresh(user)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "ACCOUNT_DISABLED", "message": "This account is disabled."}},
        )
    acct_status = getattr(user, "account_status", "active") or "active"
    path = (request.url.path or "").lower()
    if acct_status in ("pending_parental_consent", "pending_age_verification", "suspended"):
        if not (path.startswith("/api/auth/") or path.startswith("/api/privacy/")):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {
                    "code": "PARENTAL_CONSENT_REQUIRED",
                    "message": "Account requires age verification or verifiable parental consent before accessing this feature.",
                    "account_status": acct_status,
                }},
            )
    return user


def require_role(*roles: UserRole):
    async def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            logger.warning("Forbidden: user %s role %s needs %s", user.id, user.role, roles)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Not permitted."}},
            )
        return user
    return _dep


async def get_optional_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    try:
        claims = verify_supabase_token(authorization[7:].strip())
        uid = claims.get("sub")
        if not uid:
            return None
        return db.query(User).filter(User.id == uid).first()
    except Exception:
        return None


async def get_authenticated_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """Dependency that strictly requires an authenticated, non-guest user.
    
    Rejects missing tokens, expired tokens, guest sessions, and unverified guest accounts
    with HTTP 401 Unauthorized (code: GUEST_ACCESS_DENIED or MISSING_TOKEN).
    Used to protect AgroGPT and other member-only features.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _unauthorized("MISSING_TOKEN", "Authentication required. Please log in to access AgroGPT.")

    token = authorization[7:].strip()
    claims = verify_supabase_token(token)

    # 1. Reject guest tokens via JWT claims
    iss = claims.get("iss", "")
    meta = claims.get("user_metadata") or {}
    if iss == "agro-ai-local" or meta.get("is_guest") is True or claims.get("is_guest") is True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "GUEST_ACCESS_DENIED", "message": "AgroGPT is available only to authenticated users. Please log in to continue."}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Retrieve user model
    user = await get_current_user(request=request, authorization=authorization, db=db)

    # 3. Reject unverified guest accounts (no phone, no email, not verified)
    if not user.email and not user.phone and not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "GUEST_ACCESS_DENIED", "message": "AgroGPT is available only to authenticated users. Please log in to continue."}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


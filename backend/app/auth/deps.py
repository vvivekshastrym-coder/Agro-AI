"""Authentication dependencies: verify Supabase access tokens on the trusted backend."""
import logging
import os
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException, status
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from ..database.connection import get_db
from ..database.models import User, UserRole

logger = logging.getLogger(__name__)

_jwks_client: Optional[PyJWKClient] = None
_google_jwks_client: Optional[PyJWKClient] = None
GUEST_SESSION_SECRET = os.getenv("SERVER_SESSION_SECRET", "agro_ai_internal_guest_secret_key_2026_xyz").strip()
GOOGLE_CLIENT_ID = os.getenv(
    "GOOGLE_CLIENT_ID",
    "390368260977-87pg849eb5975glaikekhr9s4rlus4e2.apps.googleusercontent.com",
).strip()


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
                token, key, algorithms=[alg], audience=GOOGLE_CLIENT_ID,
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
                token, GUEST_SESSION_SECRET, algorithms=["HS256"], audience="authenticated",
                options={"require": ["exp", "sub", "iss"]},
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
            token, key, algorithms=[alg], audience="authenticated",
            options={"require": ["exp", "sub"]},
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

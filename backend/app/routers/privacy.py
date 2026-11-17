"""Privacy, Cookie Consent & Session-Replay Verification API."""
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth.deps import get_optional_current_user
from ..auth.privacy import CONSENT_VERSION, SESSION_REPLAY_ENABLED
from ..database.connection import get_db
from ..database.models import PrivacyAuditLog, PrivacyConsentRecord, User

router = APIRouter()


class CookieConsentRequest(BaseModel):
    analytics: bool = False
    marketing: bool = False
    subject_key: Optional[str] = None


def _is_https_prod(request: Request) -> bool:
    env = os.getenv("ENVIRONMENT", "development").strip().lower()
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "").lower()
    return env == "production" or proto == "https"


@router.get("/status")
async def get_privacy_status():
    """Machine-verifiable privacy posture endpoint."""
    return {
        "session_replay_enabled": SESSION_REPLAY_ENABLED,  # Always False
        "heatmaps_enabled": False,
        "keystroke_recording_enabled": False,
        "external_fonts_enabled": False,
        "ip_tracking_enabled": False,
        "consent_version": CONSENT_VERSION,
        "essential_cookies_only_by_default": True,
    }


@router.get("/consent")
async def get_cookie_consent(
    request: Request,
    user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    subj = user.id if user else (request.cookies.get("agro_subject_id") or "anonymous")
    rec = (
        db.query(PrivacyConsentRecord)
        .filter(
            (PrivacyConsentRecord.user_id == user.id) if user else (PrivacyConsentRecord.subject_key == subj)
        )
        .order_by(PrivacyConsentRecord.updated_at.desc())
        .first()
    )
    if not rec:
        return {
            "essential": True,
            "analytics": False,
            "marketing": False,
            "consent_version": CONSENT_VERSION,
            "recorded": False,
        }
    return {
        "essential": True,
        "analytics": bool(rec.analytics),
        "marketing": bool(rec.marketing),
        "consent_version": rec.consent_version,
        "updated_at": rec.updated_at.isoformat() if rec.updated_at else None,
        "recorded": True,
    }


@router.post("/consent")
async def save_cookie_consent(
    body: CookieConsentRequest,
    request: Request,
    response: Response,
    user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Stores granular privacy consent (Essential is always True; Analytics/Marketing are opt-in and withdrawable)."""
    subj = user.id if user else (request.cookies.get("agro_subject_id") or body.subject_key or str(uuid.uuid4()))

    rec = (
        db.query(PrivacyConsentRecord)
        .filter(
            (PrivacyConsentRecord.user_id == user.id) if user else (PrivacyConsentRecord.subject_key == subj)
        )
        .first()
    )
    if rec:
        rec.essential = True
        rec.analytics = bool(body.analytics)
        rec.marketing = bool(body.marketing)
        rec.consent_version = CONSENT_VERSION
    else:
        rec = PrivacyConsentRecord(
            id=str(uuid.uuid4()),
            user_id=user.id if user else None,
            subject_key=subj,
            essential=True,
            analytics=bool(body.analytics),
            marketing=bool(body.marketing),
            consent_version=CONSENT_VERSION,
        )
        db.add(rec)

    db.add(
        PrivacyAuditLog(
            id=str(uuid.uuid4()),
            actor_user_id=user.id if user else None,
            target_user_id=user.id if user else None,
            event_type="COOKIE_CONSENT_UPDATED",
            details={"essential": True, "analytics": bool(body.analytics), "marketing": bool(body.marketing), "version": CONSENT_VERSION},
        )
    )
    db.commit()

    is_secure = _is_https_prod(request)
    response.set_cookie(
        key="agro_subject_id",
        value=subj,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=31536000,
    )
    response.set_cookie(
        key="agro_privacy_consent",
        value=f"v={CONSENT_VERSION}&a={int(bool(body.analytics))}&m={int(bool(body.marketing))}",
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=31536000,
    )

    return {
        "essential": True,
        "analytics": bool(rec.analytics),
        "marketing": bool(rec.marketing),
        "consent_version": rec.consent_version,
        "recorded": True,
    }

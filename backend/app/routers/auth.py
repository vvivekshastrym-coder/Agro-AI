import os
import time
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional

from ..database.connection import get_db
from ..database.models import User, UserRole
from ..auth.deps import get_current_user, GUEST_SESSION_SECRET

router = APIRouter()

_RETIRED = {
    "error": {
        "code": "ENDPOINT_RETIRED",
        "message": "This sign-in method was removed because it did not verify identity. "
                   "Sign in through Supabase Auth and send the access token as 'Authorization: Bearer'.",
    }
}


def _user_payload(u: User) -> dict:
    return {
        "farmer_id": u.id,
        "email": u.email,
        "phone": u.phone,
        "full_name": u.full_name,
        "preferred_language": u.preferred_language,
        "role": u.role.value if u.role else None,
        "avatar_url": u.avatar_url,
    }


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    preferred_language: Optional[str] = Field(None, pattern=r"^(en|kn|hi|te|ta|mr|bn|gu|pa)$")


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    """Returns the verified identity behind the bearer token."""
    return _user_payload(user)


@router.patch("/me")
async def update_me(body: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Updates only the supplied fields of the caller's own profile."""
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    for k, v in changes.items():
        setattr(user, k, v)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail={"error": {"code": "DB_WRITE_FAILED", "message": "Could not save profile."}})
    db.refresh(user)
    return _user_payload(user)


@router.post("/guest-session")
async def create_guest_session(db: Session = Depends(get_db)):
    """Issues a cryptographically signed JWT session for guest farmers."""
    guest_id = "farmer_guest"
    user = db.query(User).filter(User.id == guest_id).first()
    if not user:
        user = User(
            id=guest_id,
            email="guest@agroai.in",
            phone="9876543210",
            full_name="Vivek (Guest Farmer)",
            role=UserRole.farmer,
            is_verified=True,
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
        except Exception:
            db.rollback()
            user = db.query(User).filter(User.id == guest_id).first()

    payload = {
        "sub": guest_id,
        "aud": "authenticated",
        "iss": "agro-ai-local",
        "exp": int(time.time()) + 86400 * 30,
        "email": "guest@agroai.in",
        "user_metadata": {
            "name": "Vivek (Guest Farmer)",
            "full_name": "Vivek (Guest Farmer)",
        }
    }
    guest_token = jwt.encode(payload, GUEST_SESSION_SECRET, algorithm="HS256")
    return {
        "access_token": guest_token,
        "token_type": "bearer",
        "user": _user_payload(user)
    }


from ..database.models import (
    User, UserRole, Farm, Field as FarmField, DiagnosisReport,
    AgroGPTConversation, AgroGPTMessage, MartSavedItem, MartSellerProfile,
    AdminUser, DataRequest
)
import uuid
import datetime


class WebDeleteAccountRequest(BaseModel):
    identifier: str = Field(..., min_length=4, max_length=150)
    reason: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = Field(None, max_length=500)


@router.delete("/me")
async def delete_my_account(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    DELETE /api/auth/me
    Store-compliant self-service account and personal data deletion (Google Play & Apple App Store Guideline 5.1.1(v)).
    - Permanently deletes user farms, fields, crop diagnosis reports, chat conversations, and saved items.
    - Deactivates seller/admin profiles.
    - Anonymizes personal identifiers and disables the account so existing session tokens are immediately rejected,
      while preserving anonymized financial/order ledger integrity where required by law.
    """
    uid = user.id

    # 1. Delete user-owned farms, fields, diagnosis reports, chat history, and saved items
    db.query(DiagnosisReport).filter(DiagnosisReport.farmer_id == uid).delete(synchronize_session=False)
    user_farms = db.query(Farm).filter(Farm.user_id == uid).all()
    for f in user_farms:
        db.query(FarmField).filter(FarmField.farm_id == f.id).delete(synchronize_session=False)
    db.query(Farm).filter(Farm.user_id == uid).delete(synchronize_session=False)

    convs = db.query(AgroGPTConversation).filter(AgroGPTConversation.farmer_id == uid).all()
    for c in convs:
        db.query(AgroGPTMessage).filter(AgroGPTMessage.conversation_id == c.id).delete(synchronize_session=False)
    db.query(AgroGPTConversation).filter(AgroGPTConversation.farmer_id == uid).delete(synchronize_session=False)

    db.query(MartSavedItem).filter(MartSavedItem.user_id == uid).delete(synchronize_session=False)

    # 2. Deactivate seller and admin profiles if any
    seller = db.query(MartSellerProfile).filter(MartSellerProfile.user_id == uid).first()
    if seller:
        seller.status = "SUSPENDED"
        seller.contact_phone = "REDACTED"

    admin_rec = db.query(AdminUser).filter(AdminUser.user_id == uid).first()
    if admin_rec:
        admin_rec.is_active = False

    # 3. Record deletion compliance log
    req_entry = DataRequest(
        id=str(uuid.uuid4()),
        user_id=uid,
        request_type="delete",
        status="completed",
        details={"source": "in_app_self_service"},
        admin_notes="Self-service in-app account deletion completed; PII erased and account disabled.",
        processed_at=datetime.datetime.now(datetime.timezone.utc)
    )
    db.add(req_entry)

    # 4. Anonymize PII and disable user record (immediately invalidates bearer token on subsequent calls)
    user.email = None
    user.phone = None
    user.full_name = "Deleted User"
    user.avatar_url = None
    user.password_hash = None
    user.is_active = False
    user.is_verified = False

    db.commit()

    return {
        "status": "deleted",
        "user_id": uid,
        "message": "Your account and personal data have been permanently deleted and your session has been revoked."
    }


@router.post("/delete-account-request")
async def request_web_account_deletion(
    body: WebDeleteAccountRequest,
    db: Session = Depends(get_db)
):
    """
    POST /api/auth/delete-account-request
    Public web endpoint for users who uninstalled the app to request account & data deletion
    (Google Play Data Safety external deletion resource requirement).
    """
    clean_id = body.identifier.strip().lower()
    matched_user = db.query(User).filter(
        (User.email == clean_id) | (User.phone == clean_id)
    ).first()

    note_text = body.reason or body.notes or "None"
    req_entry = DataRequest(
        id=str(uuid.uuid4()),
        user_id=matched_user.id if matched_user else "external_web_request",
        request_type="delete",
        status="pending",
        details={"identifier": clean_id, "reason": note_text, "source": "web_portal"},
        admin_notes=f"Web deletion request for identifier '{clean_id}'. Notes: {note_text}"
    )
    db.add(req_entry)
    db.commit()

    return {
        "status": "received",
        "request_id": req_entry.id,
        "message": "Your account deletion request has been recorded and queued for processing within 7 business days."
    }


# Fake OTP / Google endpoints accepted any input and issued forgeable tokens. They are retired.
@router.post("/send-otp")
@router.post("/verify-otp")
@router.post("/google")
async def retired_auth_endpoints():
    raise HTTPException(status_code=status.HTTP_410_GONE, detail=_RETIRED)


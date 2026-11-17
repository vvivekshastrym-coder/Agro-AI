import os
import time
import uuid
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
    """Issues an isolated, short-lived identity for this guest session."""
    guest_id = str(uuid.uuid4())
    user = User(id=guest_id, full_name="Guest Farmer", role=UserRole.farmer, is_verified=False)
    db.add(user)
    db.commit()
    db.refresh(user)

    payload = {
        "sub": guest_id,
        "aud": "authenticated",
        "iss": "agro-ai-local",
        "exp": int(time.time()) + 3600,
        "user_metadata": {
            "name": "Guest Farmer",
            "full_name": "Guest Farmer",
        }
    }
    guest_token = jwt.encode(payload, GUEST_SESSION_SECRET, algorithm="HS256")
    return {
        "access_token": guest_token,
        "token_type": "bearer",
        "user": _user_payload(user)
    }


import hmac
import hashlib
import secrets
import re as _re
from typing import Optional, Dict, Any
from ..services.sms_service import send_sms_otp, normalize_indian_phone

def generate_otp() -> str:
    """Generate a cryptographically secure 6-digit OTP."""
    return str(secrets.randbelow(900000) + 100000)

def _hash_otp(phone: str, code: str) -> str:
    """Computes a cryptographically secure HMAC-SHA256 hash of phone + OTP."""
    secret = GUEST_SESSION_SECRET.encode()
    return hmac.new(secret, f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()

# In-memory secure OTP store: phone -> {
#     "otp_hash": str,
#     "expires_at": float,    # 5 minutes validity
#     "last_sent_at": float,  # for 60s cooldown
#     "send_count": int,      # max 3 sends per 10m window
#     "window_start": float,
#     "attempts": int         # max 3 verification attempts
# }
_OTP_STORE: Dict[str, Dict[str, Any]] = {}


class PhoneOtpSendRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=15)
    role: Optional[str] = "farmer"


class PhoneOtpVerifyRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=15)
    otp: Optional[str] = Field(None, min_length=4, max_length=6)
    token: Optional[str] = Field(None, min_length=4, max_length=6)
    role: Optional[str] = "farmer"


class GoogleSessionExchangeRequest(BaseModel):
    token: Optional[str] = None
    id_token: Optional[str] = None
    email: Optional[str] = Field(None, max_length=255)
    full_name: Optional[str] = Field(None, max_length=120)
    name: Optional[str] = Field(None, max_length=120)
    avatar_url: Optional[str] = Field(None, max_length=500)
    google_sub: Optional[str] = Field(None, max_length=120)
    sub: Optional[str] = Field(None, max_length=120)
    role: Optional[str] = "farmer"


@router.post("/phone-otp/send")
async def send_phone_otp(body: PhoneOtpSendRequest):
    """
    Generates a cryptographically secure 6-digit OTP and dispatches it via real SMS.
    Enforces cooldown and window limits. Never returns or logs the OTP itself.
    """
    digits = normalize_indian_phone(body.phone)
    if len(digits) != 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_PHONE", "message": "Enter a valid 10-digit Indian mobile number."}}
        )

    now = time.time()
    record = _OTP_STORE.get(digits)

    # 1. Cooldown enforcement: must wait 60s between OTP requests
    if record:
        time_since_last = now - record.get("last_sent_at", 0)
        if time_since_last < 60:
            remaining = int(60 - time_since_last)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"error": {"code": "RATE_LIMITED", "message": f"Please wait {remaining} seconds before requesting a new OTP."}}
            )

        # 2. Window rate limit: max 3 requests per 10-minute window
        if (now - record.get("window_start", 0)) < 600:
            if record.get("send_count", 0) >= 3:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={"error": {"code": "MAX_RESEND_EXCEEDED", "message": "Too many OTP requests. Please wait 10 minutes before requesting again."}}
                )

    # 3. Generate unpredictable 6-digit OTP
    code = generate_otp()

    # 4. Dispatch real SMS via configured provider (Twilio, MSG91, 2Factor, Fast2SMS)
    sms_res = await send_sms_otp(digits, code)

    if not sms_res.get("success"):
        err_code = sms_res.get("code") or "SMS_DISPATCH_FAILED"
        err_msg = sms_res.get("message") or "Failed to deliver SMS. Please check your mobile number or try again."
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE if err_code == "SMS_PROVIDER_NOT_CONFIGURED" else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(
            status_code=status_code,
            detail={
                "error": {
                    "code": err_code,
                    "message": err_msg,
                    "provider": sms_res.get("provider")
                }
            }
        )

    # 5. Store hashed OTP only after confirmed acceptance by the SMS provider
    window_start = record.get("window_start", now) if record and (now - record.get("window_start", 0) < 600) else now
    send_count = (record.get("send_count", 0) + 1) if record and (now - record.get("window_start", 0) < 600) else 1

    _OTP_STORE[digits] = {
        "otp_hash": _hash_otp(digits, code),
        "expires_at": now + 300,  # 5 minutes validity
        "last_sent_at": now,
        "window_start": window_start,
        "send_count": send_count,
        "attempts": 0,
    }

    masked = f"+91 ******{digits[-4:]}"
    return {
        "status": "sent",
        "sent": True,
        "sms_sent": True,
        "delivery": "sms",
        "provider": sms_res.get("provider"),
        "phone_masked": masked,
        "message": f"OTP sent successfully to {masked}"
    }


@router.post("/phone-otp/verify")
async def verify_phone_otp(body: PhoneOtpVerifyRequest, db: Session = Depends(get_db)):
    """
    Verifies the 6-digit OTP against the secure server hash.
    Enforces 5-minute expiry, single-use invalidation, and maximum 3 failed attempts.
    """
    digits = normalize_indian_phone(body.phone)
    code_clean = (body.otp or body.token or "").strip()

    if len(digits) != 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_PHONE", "message": "Invalid mobile number."}}
        )

    if not code_clean or len(code_clean) != 6 or not code_clean.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_CODE_FORMAT", "message": "Please enter a valid 6-digit verification code."}}
        )

    record = _OTP_STORE.get(digits)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "NO_OTP_FOUND", "message": "No active verification code found. Please request a new OTP."}}
        )

    # Check 5-minute expiration
    if time.time() > record.get("expires_at", 0):
        _OTP_STORE.pop(digits, None)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "EXPIRED_OTP", "message": "This verification code has expired. Please request a new code."}}
        )

    # Increment verification attempt counter
    record["attempts"] = record.get("attempts", 0) + 1
    if record["attempts"] > 3:
        _OTP_STORE.pop(digits, None)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": {"code": "TOO_MANY_ATTEMPTS", "message": "Too many failed attempts. This OTP has been cancelled for security. Please request a new code."}}
        )

    # Constant-time comparison of HMAC-SHA256 hashes
    expected_hash = record.get("otp_hash", "")
    submitted_hash = _hash_otp(digits, code_clean)

    if not hmac.compare_digest(expected_hash, submitted_hash):
        remaining = max(0, 3 - record["attempts"])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_OTP", "message": f"Incorrect verification code. {remaining} attempt(s) remaining."}}
        )

    # Single-use: immediately delete from store upon successful verification
    _OTP_STORE.pop(digits, None)

    user = db.query(User).filter(User.phone == digits, User.id != "farmer_guest").first()
    is_new_user = False
    if not user:
        user = db.query(User).filter(User.id == f"farmer_{digits}").first()
    if not user:
        is_new_user = True
        user = User(
            id=f"farmer_{digits}",
            phone=digits,
            email=f"{digits}@farmer.agroai.in",
            full_name=f"Farmer ({digits[-4:]})",
            role=UserRole.farmer,
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
        except Exception:
            db.rollback()
            user = db.query(User).filter(User.id == f"farmer_{digits}").first()
    else:
        user.phone = digits
        user.is_active = True
        user.is_verified = True
        db.commit()

    payload = {
        "sub": user.id,
        "aud": "authenticated",
        "iss": "agro-ai-local",
        "exp": int(time.time()) + 86400 * 30,
        "phone": digits,
        "email": user.email,
        "is_new_user": is_new_user,
        "user_metadata": {
            "name": user.full_name,
            "full_name": user.full_name,
        }
    }
    signed_token = jwt.encode(payload, GUEST_SESSION_SECRET, algorithm="HS256")
    return {
        "status": "verified",
        "access_token": signed_token,
        "token_type": "bearer",
        "is_new_user": is_new_user,
        "user": _user_payload(user),
    }


@router.post("/google-session")
async def create_google_session(user: User = Depends(get_current_user)):
    """Exchange only an already verified bearer identity; never trust caller-supplied profile claims."""
    payload = {
        "sub": user.id,
        "aud": "authenticated",
        "iss": "agro-ai-local",
        "exp": int(time.time()) + 3600,
        "email": user.email,
        "user_metadata": {
            "name": user.full_name,
            "full_name": user.full_name,
            "avatar_url": user.avatar_url or "",
        }
    }
    signed_token = jwt.encode(payload, GUEST_SESSION_SECRET, algorithm="HS256")
    return {
        "access_token": signed_token,
        "token_type": "bearer",
        "user": _user_payload(user),
    }


from ..database.models import (
    User, UserRole, Farm, Field as FarmField, DiagnosisReport,
    AgroGPTConversation, AgroGPTMessage, MartSavedItem, MartSellerProfile,
    AdminUser, DataRequest
)
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


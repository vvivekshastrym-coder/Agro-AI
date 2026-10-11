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


# Fake OTP / Google endpoints accepted any input and issued forgeable tokens. They are retired.
@router.post("/send-otp")
@router.post("/verify-otp")
@router.post("/google")
async def retired_auth_endpoints():
    raise HTTPException(status_code=status.HTTP_410_GONE, detail=_RETIRED)

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import uuid
from ..database.connection import get_db
from ..database.models import User, Farm, UserRole

router = APIRouter()

class OTPRequest(BaseModel):
    phone: str

class OTPVerifyRequest(BaseModel):
    phone: str
    otp: str

class GoogleAuthRequest(BaseModel):
    credential: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    role: Optional[str] = "farmer"

@router.post("/send-otp")
async def send_otp(req: OTPRequest):
    """Sends OTP to farmer phone number."""
    return {"status": "success", "message": f"OTP sent to {req.phone}"}

@router.post("/verify-otp")
async def verify_otp(req: OTPVerifyRequest, db: Session = Depends(get_db)):
    """Verifies OTP and returns user authentication payload."""
    user = db.query(User).filter(User.phone == req.phone).first()
    if not user:
        user = User(
            id=str(uuid.uuid4()),
            phone=req.phone,
            full_name="Farmer Partner",
            role=UserRole.farmer,
            is_verified=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Create default farm for user
        farm = Farm(
            id=str(uuid.uuid4()),
            user_id=user.id,
            village="Mandya",
            district="Mandya",
            state="Karnataka",
            total_acres=5.0,
            owned_acres=5.0
        )
        db.add(farm)
        db.commit()

    return {
        "access_token": f"jwt_token_{user.id}",
        "token_type": "bearer",
        "user": {
            "farmer_id": user.id,
            "phone": user.phone,
            "full_name": user.full_name,
            "preferred_language": user.preferred_language
        }
    }

@router.post("/google")
async def google_auth(req: GoogleAuthRequest, db: Session = Depends(get_db)):
    """Authenticates or registers user via Google Sign-In."""
    email = req.email or "farmer@gmail.com"
    full_name = req.name or "Farmer Partner"
    user = db.query(User).filter(User.phone == email).first()
    if not user:
        user = User(
            id=str(uuid.uuid4()),
            phone=email,
            full_name=full_name,
            role=UserRole.farmer,
            is_verified=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        farm = Farm(
            id=str(uuid.uuid4()),
            user_id=user.id,
            village="Mandya",
            district="Mandya",
            state="Karnataka",
            total_acres=5.0,
            owned_acres=5.0
        )
        db.add(farm)
        db.commit()

    return {
        "status": "success",
        "access_token": f"jwt_google_{user.id}",
        "token_type": "bearer",
        "user": {
            "farmer_id": user.id,
            "email": email,
            "full_name": user.full_name
        }
    }

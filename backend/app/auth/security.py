from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
import os
import secrets

# ─── Configuration ───────────────────────────────────────────
SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_hex(32))
ALGORITHM = os.getenv('ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', 15))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv('REFRESH_TOKEN_EXPIRE_DAYS', 30))

# ─── Argon2 Password Hashing ─────────────────────────────────
# argon2 is the winner of the Password Hashing Competition.
# Memory cost 65536 KB (~64 MB), 3 iterations, 4 parallel lanes.
pwd_context = CryptContext(
    schemes=['argon2'],
    deprecated='auto',
    argon2__memory_cost=65536,
    argon2__time_cost=3,
    argon2__parallelism=4
)


def hash_password(password: str) -> str:
    """Return an Argon2 hash of the plaintext password."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Constant-time comparison of plaintext vs Argon2 hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ─── JWT Tokens ──────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a short-lived JWT access token (default 15 min)."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({'exp': expire, 'type': 'access', 'iat': datetime.utcnow()})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create a long-lived JWT refresh token (default 30 days)."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({'exp': expire, 'type': 'refresh', 'iat': datetime.utcnow()})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str, expected_type: str = 'access') -> Optional[dict]:
    """
    Decode and validate a JWT token.
    Returns the payload dict on success, None on any failure.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get('type') != expected_type:
            return None
        return payload
    except JWTError:
        return None


# ─── OTP ─────────────────────────────────────────────────────

def generate_otp() -> str:
    """Generate a cryptographically secure 6-digit OTP."""
    return str(secrets.randbelow(900000) + 100000)


def generate_secure_token(length: int = 32) -> str:
    """Generate a URL-safe random token (e.g. for password reset links)."""
    return secrets.token_urlsafe(length)

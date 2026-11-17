"""Privacy, Age Verification, Parental Consent & IP Minimization helpers.

Priority rules:
1. Session replay and behavioral keystroke/screen recording are ALWAYS disabled.
2. Raw visitor IP addresses are never stored in profiles/analytics or exposed via APIs.
3. Age calculation and parental consent enforcement happen strictly server-side.
"""
import datetime
import hashlib
import hmac
import os
from typing import Dict, Optional, Tuple

SESSION_REPLAY_ENABLED: bool = False
CONSENT_VERSION: str = "2026-11-17"

# Country-specific digital consent & adult age thresholds.
# India (IN) DPDP Act 2023 treats everyone under 18 as a child requiring verifiable parental consent.
# Product UX bands for India-first flow: <9 = child_under_9, 9-17 = minor_9_17, >=18 = adult.
COUNTRY_AGE_RULES: Dict[str, Tuple[int, str]] = {
    "IN": (18, "India DPDP Act (under 18 requires verifiable parental consent)"),
    "US": (13, "US COPPA (under 13 requires verifiable parental consent); 18+ full adult"),
    "GB": (13, "UK GDPR / AADC (under 13 requires parental consent); 18+ full adult"),
    "CA": (13, "Canada PIPEDA (under 13 requires parental consent)"),
    "AU": (16, "Australia Privacy / Social Media Minimum Age"),
    "DE": (16, "EU GDPR (Germany digital consent age 16)"),
    "FR": (15, "EU GDPR (France digital consent age 15)"),
    "NL": (16, "EU GDPR (Netherlands digital consent age 16)"),
    "ES": (14, "EU GDPR (Spain digital consent age 14)"),
    "SG": (13, "Singapore PDPA digital consent threshold"),
}
DEFAULT_CONSENT_AGE = 18


def redact_ip(raw_ip: Optional[str]) -> Optional[str]:
    """Never store or expose raw IP addresses. Returns a non-reversible salted prefix or None."""
    if not raw_ip:
        return None
    secret = os.getenv("SERVER_SESSION_SECRET", "agro-ai-ip-redaction-salt").encode("utf-8")
    digest = hmac.new(secret, raw_ip.strip().encode("utf-8"), hashlib.sha256).hexdigest()[:12]
    return f"redacted:{digest}"


def parse_dob(dob_str: str) -> datetime.date:
    try:
        dob = datetime.date.fromisoformat(dob_str.strip())
    except Exception:
        raise ValueError("Date of birth must be in YYYY-MM-DD format.")
    today = datetime.datetime.now(datetime.timezone.utc).date()
    if dob > today:
        raise ValueError("Date of birth cannot be in the future.")
    if (today.year - dob.year) > 120:
        raise ValueError("Date of birth is outside valid range.")
    return dob


def calculate_age(dob: datetime.date, today: Optional[datetime.date] = None) -> int:
    ref = today or datetime.datetime.now(datetime.timezone.utc).date()
    years = ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))
    return years


def classify_age(dob_str: str, country_code: str = "IN") -> dict:
    """Server-side age & consent classification. Never trust client-supplied age categories."""
    cc = (country_code or "IN").strip().upper()[:2]
    if len(cc) != 2 or not cc.isalpha():
        cc = "IN"

    dob = parse_dob(dob_str)
    age_years = calculate_age(dob)
    threshold, legal_basis = COUNTRY_AGE_RULES.get(cc, (DEFAULT_CONSENT_AGE, "Default 18+ adult consent threshold"))

    if age_years < 9:
        age_category = "child_under_9"
    elif age_years < 18:
        age_category = "minor_9_17"
    else:
        age_category = "adult"

    requires_parental_consent = age_years < threshold
    return {
        "date_of_birth": dob.isoformat(),
        "country_code": cc,
        "age_years": age_years,
        "age_category": age_category,
        "consent_threshold_age": threshold,
        "requires_parental_consent": requires_parental_consent,
        "legal_basis": legal_basis,
        "experience_mode": "restricted_child" if age_years < 9 else ("minor_supervised" if requires_parental_consent else "standard"),
    }


def hash_consent_code(consent_id: str, code: str) -> str:
    secret = os.getenv("SERVER_SESSION_SECRET", "agro-ai-parental-consent-secret").encode("utf-8")
    msg = f"{consent_id}:{code.strip()}".encode("utf-8")
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def verify_consent_code(consent_id: str, code: str, expected_hash: str) -> bool:
    if not expected_hash or not code:
        return False
    actual = hash_consent_code(consent_id, code)
    return hmac.compare_digest(actual, expected_hash)

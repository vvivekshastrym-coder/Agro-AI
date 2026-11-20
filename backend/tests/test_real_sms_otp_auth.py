import pytest
import time
import os
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.routers.auth import _OTP_STORE, _hash_otp

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_otp_store():
    _OTP_STORE.clear()
    yield
    _OTP_STORE.clear()


def test_otp_send_fails_gracefully_when_no_provider():
    """When no SMS provider credentials are configured, system must fail truthfully with 503 and NOT leak OTP."""
    with patch.dict(os.environ, {
        "TWILIO_ACCOUNT_SID": "",
        "TWILIO_AUTH_TOKEN": "",
        "TWILIO_PHONE_NUMBER": "",
        "MSG91_AUTH_KEY": "",
        "TWOFACTOR_API_KEY": "",
        "FAST2SMS_API_KEY": ""
    }):
        resp = client.post("/api/auth/phone-otp/send", json={"phone": "9876543210", "role": "farmer"})
        assert resp.status_code == 503
        data = resp.json()
        assert "otp_code" not in data
        assert data["detail"]["error"]["code"] == "SMS_PROVIDER_NOT_CONFIGURED"
        assert "9876543210" not in _OTP_STORE


def test_otp_send_success_with_provider_mock():
    """When SMS provider succeeds, OTP is hashed in store and NO otp_code is in response."""
    mock_send = AsyncMock(return_value={
        "success": True,
        "provider": "twilio",
        "message_id": "SM12345",
        "status": "delivered"
    })
    with patch("app.routers.auth.send_sms_otp", mock_send):
        resp = client.post("/api/auth/phone-otp/send", json={"phone": "+919876543210", "role": "farmer"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "sent"
        assert data["sms_sent"] is True
        assert data["provider"] == "twilio"
        assert data["phone_masked"] == "+91 ******3210"
        assert "otp_code" not in data  # CRITICAL: NEVER exposed
        assert "code" not in data

        # Verify hashed store
        record = _OTP_STORE.get("9876543210")
        assert record is not None
        assert "code" not in record  # Plain code is NEVER stored
        assert "otp_hash" in record
        assert record["attempts"] == 0


def test_otp_verification_flow():
    """Test full cycle: send OTP -> verify correct code -> single use deletion."""
    test_code = "654321"
    digits = "9876543210"

    # Pre-populate OTP store as if sent
    _OTP_STORE[digits] = {
        "otp_hash": _hash_otp(digits, test_code),
        "expires_at": time.time() + 300,
        "last_sent_at": time.time(),
        "window_start": time.time(),
        "send_count": 1,
        "attempts": 0,
    }

    # Verify with incorrect code
    resp_bad = client.post("/api/auth/phone-otp/verify", json={"phone": digits, "token": "111111"})
    assert resp_bad.status_code == 401
    assert "Incorrect verification code" in resp_bad.json()["detail"]["error"]["message"]
    assert _OTP_STORE[digits]["attempts"] == 1

    # Verify with correct code
    resp_good = client.post("/api/auth/phone-otp/verify", json={"phone": digits, "token": test_code})
    assert resp_good.status_code == 200
    good_data = resp_good.json()
    assert good_data["status"] == "verified"
    assert "access_token" in good_data
    assert good_data["user"]["phone"] == digits

    # Verify single-use: OTP is removed from store
    assert digits not in _OTP_STORE

    # Subsequent verification must fail
    resp_again = client.post("/api/auth/phone-otp/verify", json={"phone": digits, "token": test_code})
    assert resp_again.status_code == 400
    assert resp_again.json()["detail"]["error"]["code"] == "NO_OTP_FOUND"


def test_otp_expired_code():
    """Expired OTP must be rejected."""
    digits = "9876543210"
    _OTP_STORE[digits] = {
        "otp_hash": _hash_otp(digits, "123456"),
        "expires_at": time.time() - 10,  # Expired
        "last_sent_at": time.time() - 400,
        "window_start": time.time() - 400,
        "send_count": 1,
        "attempts": 0,
    }

    resp = client.post("/api/auth/phone-otp/verify", json={"phone": digits, "token": "123456"})
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"]["code"] == "EXPIRED_OTP"


def test_otp_rate_limiting_cooldown():
    """User cannot request OTP twice in under 60 seconds."""
    mock_send = AsyncMock(return_value={"success": True, "provider": "msg91"})
    with patch("app.routers.auth.send_sms_otp", mock_send):
        r1 = client.post("/api/auth/phone-otp/send", json={"phone": "9876543210"})
        assert r1.status_code == 200

        r2 = client.post("/api/auth/phone-otp/send", json={"phone": "9876543210"})
        assert r2.status_code == 429
        assert r2.json()["detail"]["error"]["code"] == "RATE_LIMITED"


def test_twilio_trial_restriction_error_21608():
    """Twilio Error 21608 (Trial unverified number) must return TWILIO_DESTINATION_UNVERIFIED without exposing secrets."""
    mock_send = AsyncMock(return_value={
        "success": False,
        "provider": "twilio",
        "code": "TWILIO_DESTINATION_UNVERIFIED",
        "message": "SMS verification is temporarily unavailable for this number. Please try again later or continue as Guest Farmer.",
        "guest_fallback_available": True
    })
    with patch("app.routers.auth.send_sms_otp", mock_send):
        resp = client.post("/api/auth/phone-otp/send", json={"phone": "+919876543210", "role": "farmer"})
        assert resp.status_code == 502
        data = resp.json()
        err = data["detail"]["error"]
        assert err["code"] == "TWILIO_DESTINATION_UNVERIFIED"
        assert "SMS verification is temporarily unavailable for this number" in err["message"]
        assert "continue as Guest Farmer" in err["message"]
        assert err["guest_fallback_available"] is True
        assert err["provider"] == "twilio"

        # Zero leakage of credentials or sensitive internals
        assert "TWILIO_AUTH_TOKEN" not in resp.text
        assert "AC7efbc452" not in resp.text
        assert "password" not in resp.text

        # Phone is NOT saved to active OTP store
        assert "9876543210" not in _OTP_STORE


def test_twilio_service_direct_error_handling():
    """Test _send_via_twilio error classifications directly with mocked HTTP responses."""
    import asyncio
    from app.services.sms_service import _send_via_twilio
    from unittest.mock import MagicMock

    async def _run():
        with patch.dict(os.environ, {
            "TWILIO_ACCOUNT_SID": "AC_TEST_SID",
            "TWILIO_AUTH_TOKEN": "TEST_AUTH_TOKEN",
            "TWILIO_PHONE_NUMBER": "+1234567890"
        }):
            # 1. Twilio 21608 Trial Unverified number
            mock_resp_21608 = MagicMock()
            mock_resp_21608.status_code = 400
            mock_resp_21608.json.return_value = {
                "code": 21608,
                "message": "The number +919876543210 is unverified. Trial accounts cannot send messages to unverified numbers"
            }

            with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_resp_21608)):
                res = await _send_via_twilio("9876543210", "Your Agro AI code is 123456")
                assert res["success"] is False
                assert res["code"] == "TWILIO_DESTINATION_UNVERIFIED"
                assert "continue as Guest Farmer" in res["message"]
                assert res["guest_fallback_available"] is True

            # 2. Twilio 21408 Region / Geo permissions disabled
            mock_resp_21408 = MagicMock()
            mock_resp_21408.status_code = 400
            mock_resp_21408.json.return_value = {
                "code": 21408,
                "message": "Permission to send an SMS has not been enabled for the region indicated by the 'To' number"
            }
            with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_resp_21408)):
                res = await _send_via_twilio("9876543210", "Your Agro AI code is 123456")
                assert res["success"] is False
                assert res["code"] == "TWILIO_REGION_RESTRICTED"
                assert "continue as Guest Farmer" in res["message"]

            # 3. Twilio 21211 Invalid mobile number
            mock_resp_21211 = MagicMock()
            mock_resp_21211.status_code = 400
            mock_resp_21211.json.return_value = {
                "code": 21211,
                "message": "The 'To' number +910000000000 is not a valid phone number."
            }
            with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_resp_21211)):
                res = await _send_via_twilio("0000000000", "Your Agro AI code is 123456")
                assert res["success"] is False
                assert res["code"] == "INVALID_MOBILE_NUMBER"
                assert "continue as Guest Farmer" in res["message"]

            # 4. Twilio 20003 Account suspended or insufficient funds
            mock_resp_20003 = MagicMock()
            mock_resp_20003.status_code = 401
            mock_resp_20003.json.return_value = {
                "code": 20003,
                "message": "Authentication Error - account suspended"
            }
            with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_resp_20003)):
                res = await _send_via_twilio("9876543210", "Your Agro AI code is 123456")
                assert res["success"] is False
                assert res["code"] == "SMS_SERVICE_UNAVAILABLE"
                assert "continue as Guest Farmer" in res["message"]

    asyncio.run(_run())


def test_window_rate_limiting_exceeded():
    """Max 3 OTP requests allowed per 10-minute window."""
    digits = "9988776655"
    now = time.time()
    _OTP_STORE[digits] = {
        "otp_hash": _hash_otp(digits, "123456"),
        "expires_at": now + 300,
        "last_sent_at": now - 80,  # Cooldown passed
        "window_start": now - 200, # In current 10-minute window
        "send_count": 3,           # Already hit 3 sends
        "attempts": 0,
    }

    # Ensure DB record doesn't override with different values
    from app.database.connection import SessionLocal
    from app.database.models import PhoneOtpRecord
    db = SessionLocal()
    try:
        db.query(PhoneOtpRecord).filter(PhoneOtpRecord.phone == digits).delete()
        db.add(PhoneOtpRecord(
            phone=digits,
            otp_hash=_hash_otp(digits, "123456"),
            expires_at=now + 300,
            last_sent_at=now - 80,
            window_start=now - 200,
            send_count=3,
            attempts=0
        ))
        db.commit()
    finally:
        db.close()

    resp = client.post("/api/auth/phone-otp/send", json={"phone": digits, "role": "farmer"})
    assert resp.status_code == 429
    assert resp.json()["detail"]["error"]["code"] == "MAX_RESEND_EXCEEDED"


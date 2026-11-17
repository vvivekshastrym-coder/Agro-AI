import pytest
import time
import os
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.routers.auth import _OTP_STORE, _hash_otp

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
    with patch("backend.app.routers.auth.send_sms_otp", mock_send):
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
    with patch("backend.app.routers.auth.send_sms_otp", mock_send):
        r1 = client.post("/api/auth/phone-otp/send", json={"phone": "9876543210"})
        assert r1.status_code == 200

        r2 = client.post("/api/auth/phone-otp/send", json={"phone": "9876543210"})
        assert r2.status_code == 429
        assert r2.json()["detail"]["error"]["code"] == "RATE_LIMITED"

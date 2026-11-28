from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.routers.drone import _validate_application_data, calculate_booking_quote
from app.auth.feature_access import is_app_only_path, verify_drone_app_attestation


def test_booking_quote_uses_provider_rate_and_minimum():
    quote = calculate_booking_quote(Decimal("2.5"), Decimal("400"), Decimal("1200"))
    assert quote == {
        "currency": "INR",
        "area_acres": 2.5,
        "rate_per_acre": 400.0,
        "base_service_amount": 1000.0,
        "minimum_booking_amount": 1200.0,
        "total": 1200.0,
    }


def test_booking_quote_rejects_missing_or_nonpositive_rate():
    with pytest.raises(ValueError):
        calculate_booking_quote(Decimal("1"), Decimal("0"), None)


def test_individual_application_requires_drone_area_and_price():
    with pytest.raises(HTTPException) as error:
        _validate_application_data("individual", {
            "full_name": "Asha Rao", "state": "Karnataka", "district": "Mysuru",
            "qualification": "Remote pilot", "certificate_number": "RP-1",
            "certificate_issuer": "DGCA", "services": ["crop_spraying"],
        })
    assert error.value.status_code == 422
    assert "drone" in error.value.detail.lower()


def test_company_application_requires_service_area_and_approved_category():
    payload = {
        "registered_name": "Field Flight Services", "representative_name": "Asha Rao",
        "state": "Karnataka", "district": "Mysuru", "services": ["crop_spraying"],
    }
    with pytest.raises(HTTPException) as error:
        _validate_application_data("company", payload)
    assert error.value.status_code == 422
    assert "service area" in error.value.detail.lower()


def test_drone_api_is_marked_app_only_and_rejects_spoofed_headers():
    assert is_app_only_path("/api/drone/providers")
    assert not is_app_only_path("/api/admin/drone/providers")
    valid, reason = verify_drone_app_attestation({
        "x-agro-client": "android", "x-firebase-appcheck": "not-a-signed-jwt-token",
    })
    assert not valid
    assert reason == "Invalid or expired Firebase App Check token"

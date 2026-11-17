"""
Agro AI Production SMS Service
Provides real SMS OTP dispatch via major Indian and global SMS providers:
1. Twilio (Global / India)
2. MSG91 (India DLT-compliant)
3. 2Factor.in (India dedicated OTP SMS)
4. Fast2SMS (India Quick SMS)

Never logs or leaks OTP values to client responses.
"""

import os
import re
import logging
from typing import Dict, Any, Optional
import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("agro_ai.sms_service")

# Standard Agro AI OTP message template
DEFAULT_OTP_TEMPLATE = "Your Agro AI verification code is {otp}. It is valid for 5 minutes. Do not share this code with anyone."


def normalize_indian_phone(phone: str) -> str:
    """Normalize phone to 10-digit Indian mobile number."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) > 10 and digits.startswith("91"):
        digits = digits[2:]
    return digits


def get_configured_provider() -> Optional[str]:
    """Detect which SMS provider has valid configuration in environment."""
    if os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN") and (os.getenv("TWILIO_PHONE_NUMBER") or os.getenv("TWILIO_MESSAGING_SERVICE_SID")):
        return "twilio"
    if os.getenv("MSG91_AUTH_KEY") and (os.getenv("MSG91_TEMPLATE_ID") or os.getenv("MSG91_FLOW_ID")):
        return "msg91"
    if os.getenv("TWOFACTOR_API_KEY"):
        return "2factor"
    if os.getenv("FAST2SMS_API_KEY"):
        return "fast2sms"
    return None


async def send_sms_otp(phone: str, otp: str) -> Dict[str, Any]:
    """
    Dispatches a real SMS OTP using the configured provider.
    Returns a dict with success status, provider name, and sanitized error messages.
    NEVER returns or logs the OTP itself in responses.
    """
    clean_digits = normalize_indian_phone(phone)
    if len(clean_digits) != 10:
        return {
            "success": False,
            "provider": "validation",
            "code": "INVALID_PHONE",
            "message": "Enter a valid 10-digit Indian mobile number."
        }

    provider = get_configured_provider()
    if not provider:
        logger.warning(
            "SMS dispatch attempted for +91 %s******%s but no SMS provider credentials are configured.",
            clean_digits[:2],
            clean_digits[-2:]
        )
        return {
            "success": False,
            "provider": "none",
            "code": "SMS_PROVIDER_NOT_CONFIGURED",
            "message": "SMS delivery service is not configured on the server. Please add Twilio, MSG91, or 2Factor API credentials to environment settings."
        }

    # Format message
    message_text = (os.getenv("SMS_OTP_TEMPLATE") or DEFAULT_OTP_TEMPLATE).replace("{otp}", otp)

    try:
        if provider == "twilio":
            return await _send_via_twilio(clean_digits, message_text)
        elif provider == "msg91":
            return await _send_via_msg91(clean_digits, otp)
        elif provider == "2factor":
            return await _send_via_2factor(clean_digits, otp)
        elif provider == "fast2sms":
            return await _send_via_fast2sms(clean_digits, message_text, otp)
        else:
            return {
                "success": False,
                "provider": provider,
                "code": "UNKNOWN_PROVIDER",
                "message": f"Unsupported provider: {provider}"
            }
    except Exception as exc:
        logger.error("Unexpected error in SMS provider dispatch: %s", str(exc), exc_info=True)
        return {
            "success": False,
            "provider": provider,
            "code": "DISPATCH_EXCEPTION",
            "message": "Failed to connect to SMS delivery provider. Please try again."
        }


async def _send_via_twilio(clean_digits: str, message_text: str) -> Dict[str, Any]:
    sid = (os.getenv("TWILIO_ACCOUNT_SID") or "").strip()
    token = (os.getenv("TWILIO_AUTH_TOKEN") or "").strip()
    from_number = (os.getenv("TWILIO_PHONE_NUMBER") or "").strip()
    messaging_service_sid = (os.getenv("TWILIO_MESSAGING_SERVICE_SID") or "").strip()

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    post_data: Dict[str, str] = {
        "To": f"+91{clean_digits}",
        "Body": message_text,
    }
    if messaging_service_sid:
        post_data["MessagingServiceSid"] = messaging_service_sid
    elif from_number:
        post_data["From"] = from_number

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, auth=(sid, token), data=post_data)

    if resp.status_code in (200, 201):
        data = resp.json()
        logger.info("SMS delivered via Twilio to +91 %s******%s (SID: %s)", clean_digits[:2], clean_digits[-2:], data.get("sid"))
        return {
            "success": True,
            "provider": "twilio",
            "message_id": data.get("sid"),
            "status": "delivered"
        }
    else:
        err_msg = "Twilio rejected SMS request"
        err_code = f"TWILIO_{resp.status_code}"
        try:
            err_json = resp.json()
            raw_code = err_json.get("code")
            if raw_code == 21608 or "unverified" in (err_json.get("message") or "").lower():
                err_code = "TWILIO_TRIAL_UNVERIFIED_NUMBER"
                err_msg = (
                    "Twilio Trial Notice: This phone number is unverified in your Twilio account. "
                    "Verify this number at twilio.com/console/phone-numbers/verified or click 'Explore as Guest Farmer' for instant access."
                )
            else:
                err_msg = err_json.get("message") or err_msg
        except Exception:
            pass
        logger.error("Twilio SMS error [%d]: %s", resp.status_code, err_msg)
        return {
            "success": False,
            "provider": "twilio",
            "code": err_code,
            "message": err_msg
        }


async def _send_via_msg91(clean_digits: str, otp: str) -> Dict[str, Any]:
    auth_key = (os.getenv("MSG91_AUTH_KEY") or "").strip()
    template_id = (os.getenv("MSG91_TEMPLATE_ID") or os.getenv("MSG91_FLOW_ID") or "").strip()
    sender_id = (os.getenv("MSG91_SENDER_ID") or "AGROAI").strip()

    url = "https://control.msg91.com/api/v5/otp"
    payload = {
        "template_id": template_id,
        "mobile": f"91{clean_digits}",
        "authkey": auth_key,
        "otp": otp,
        "sender": sender_id
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, json=payload, headers={"Content-Type": "application/json"})

    data = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
    if resp.status_code == 200 and data.get("type") == "success":
        logger.info("SMS delivered via MSG91 to +91 %s******%s", clean_digits[:2], clean_digits[-2:])
        return {
            "success": True,
            "provider": "msg91",
            "message_id": data.get("request_id"),
            "status": "delivered"
        }
    else:
        err_msg = data.get("message") or f"MSG91 status {resp.status_code}"
        logger.error("MSG91 error: %s", err_msg)
        return {
            "success": False,
            "provider": "msg91",
            "code": "MSG91_ERROR",
            "message": f"MSG91 error: {err_msg}"
        }


async def _send_via_2factor(clean_digits: str, otp: str) -> Dict[str, Any]:
    api_key = (os.getenv("TWOFACTOR_API_KEY") or "").strip()
    template_name = (os.getenv("TWOFACTOR_TEMPLATE_NAME") or "").strip()

    # 2Factor SMS URL pattern
    if template_name:
        url = f"https://2factor.in/API/V1/{api_key}/SMS/+91{clean_digits}/{otp}/{template_name}"
    else:
        url = f"https://2factor.in/API/V1/{api_key}/SMS/+91{clean_digits}/{otp}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)

    data = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
    if resp.status_code == 200 and data.get("Status") == "Success":
        logger.info("SMS delivered via 2Factor to +91 %s******%s (Session: %s)", clean_digits[:2], clean_digits[-2:], data.get("Details"))
        return {
            "success": True,
            "provider": "2factor",
            "message_id": data.get("Details"),
            "status": "delivered"
        }
    else:
        err_msg = data.get("Details") or f"2Factor status {resp.status_code}"
        logger.error("2Factor error: %s", err_msg)
        return {
            "success": False,
            "provider": "2factor",
            "code": "TWOFACTOR_ERROR",
            "message": f"2Factor error: {err_msg}"
        }


async def _send_via_fast2sms(clean_digits: str, message_text: str, otp: str) -> Dict[str, Any]:
    api_key = (os.getenv("FAST2SMS_API_KEY") or "").strip()

    url = "https://www.fast2sms.com/dev/bulkV2"
    headers = {
        "authorization": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "route": "otp",
        "variables_values": otp,
        "numbers": clean_digits
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, json=payload, headers=headers)

    data = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
    if resp.status_code == 200 and data.get("return") is True:
        logger.info("SMS delivered via Fast2SMS to +91 %s******%s", clean_digits[:2], clean_digits[-2:])
        return {
            "success": True,
            "provider": "fast2sms",
            "message_id": data.get("request_id"),
            "status": "delivered"
        }
    else:
        err_msg = (data.get("message") or [f"Fast2SMS status {resp.status_code}"])[0]
        logger.error("Fast2SMS error: %s", err_msg)
        return {
            "success": False,
            "provider": "fast2sms",
            "code": "FAST2SMS_ERROR",
            "message": f"Fast2SMS error: {err_msg}"
        }

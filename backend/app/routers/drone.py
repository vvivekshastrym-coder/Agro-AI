"""Approval-gated Drone Services API.

Farmer endpoints are protected by the global Firebase App Check middleware at
``/api/drone`` and by the signed-in user's backend session. Super Admin routes
are mounted separately below ``/api/admin/drone`` and never return document
contents from the provider directory.
"""
from __future__ import annotations

import mimetypes
import os
import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import PurePath
from typing import Any, Literal, Optional
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth.deps import get_current_user
from ..database.connection import get_db
from ..database.drone_models import (
    DroneApplication, DroneApprovalHistory, DroneBooking, DroneBookingStatusHistory,
    DroneCompany, DroneDocument, DroneFleet, DronePilot, DroneReview,
    DroneRoleAssignment, DroneServiceArea,
)
from ..database.models import AdminAuditLog, AdminUser, AdminUserRole, User
from .admin import require_admin

router = APIRouter()
admin_router = APIRouter()

SERVICE_CATEGORIES = {
    "crop_spraying", "surveying", "mapping", "crop_monitoring", "other"
}
APP_STATUSES = {
    "draft", "pending", "under_review", "more_information_required",
    "approved", "rejected", "suspended", "expired", "on_hold",
}
BOOKING_STATUSES = {
    "requested", "accepted", "rejected", "pilot_assigned", "scheduled",
    "on_the_way", "in_progress", "awaiting_farmer_confirmation", "completed", "cancelled", "disputed",
}
ACTIVE_BOOKING_STATUSES = {"accepted", "pilot_assigned", "scheduled", "on_the_way", "in_progress"}
ADMIN_REQUIRED_DOCUMENTS = {
    "individual": {"identity", "pilot_certificate", "drone_registration"},
    "company": {"identity", "business_registration"},
    "copilot": {"identity", "qualification"},
}
PRIVATE_BUCKET = "agro-drone-private"
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
ALLOWED_DOCUMENTS = {
    "application/pdf": {".pdf"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
}


class ApplicationCreate(BaseModel):
    application_type: Literal["individual", "company", "copilot"]
    data: dict[str, Any]


class ApplicationUpdate(BaseModel):
    data: dict[str, Any]


class AdminManualApplication(BaseModel):
    existing_user_id: str
    application_type: Literal["individual", "company", "copilot"]
    data: dict[str, Any]


class ApplicationReview(BaseModel):
    status: Literal["under_review", "more_information_required", "approved", "rejected", "on_hold"]
    reason: Optional[str] = Field(default=None, max_length=800)
    notes: Optional[str] = Field(default=None, max_length=3000)
    credentials_verified: bool = False
    business_documents_verified: bool = False


class ProviderStatusUpdate(BaseModel):
    status: Literal["approved", "suspended"]
    reason: str = Field(min_length=5, max_length=800)


class BookingCreate(BaseModel):
    provider_pilot_id: str
    service_category: str
    state: str = Field(min_length=2, max_length=80)
    district: str = Field(min_length=2, max_length=100)
    taluk: Optional[str] = Field(default=None, max_length=100)
    village: Optional[str] = Field(default=None, max_length=120)
    area_acres: Decimal = Field(gt=0, le=10000)
    scheduled_date: date
    farmer_notes: Optional[str] = Field(default=None, max_length=1500)

    @field_validator("service_category")
    @classmethod
    def valid_service(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in SERVICE_CATEGORIES:
            raise ValueError("Choose a supported drone service.")
        return value


class BookingStatusUpdate(BaseModel):
    status: Literal["accepted", "rejected", "pilot_assigned", "scheduled", "on_the_way", "in_progress", "completed"]
    assigned_drone_id: Optional[str] = None
    note: Optional[str] = Field(default=None, max_length=1200)


class BookingReview(BaseModel):
    rating: int = Field(ge=1, le=5)
    review: Optional[str] = Field(default=None, max_length=1500)


class RoleRequest(BaseModel):
    role: Literal["copilot", "company_manager", "company_operator"]
    company_id: Optional[str] = None


class CompanyRoleInvite(BaseModel):
    target_user_id: str
    role: Literal["copilot", "company_manager", "company_operator"]


class RoleDecision(BaseModel):
    status: Literal["approved", "rejected", "revoked"]
    reason: str = Field(min_length=5, max_length=800)


def _today() -> date:
    return datetime.now(ZoneInfo("Asia/Kolkata")).date()


def _clean(value: Any, limit: int = 180) -> str:
    return str(value or "").strip()[:limit]


def _list_of_strings(value: Any, allowed: Optional[set[str]] = None) -> list[str]:
    if not isinstance(value, list):
        return []
    values = []
    for item in value:
        item = _clean(item, 80).lower()
        if item and (allowed is None or item in allowed) and item not in values:
            values.append(item)
    return values


def _decimal(value: Any, field_name: str, *, required: bool = False) -> Optional[Decimal]:
    if value in (None, ""):
        if required:
            raise HTTPException(status_code=422, detail=f"{field_name} is required.")
        return None
    try:
        number = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=422, detail=f"{field_name} must be a valid amount.")
    if not number.is_finite() or number < 0:
        raise HTTPException(status_code=422, detail=f"{field_name} cannot be negative.")
    return number


def calculate_booking_quote(area_acres: Decimal, price_per_acre: Decimal, minimum: Optional[Decimal]) -> dict[str, Any]:
    """Use the provider's configured per-acre price and minimum; never estimate missing rates."""
    if area_acres <= 0 or price_per_acre <= 0:
        raise ValueError("A positive acreage and configured per-acre rate are required.")
    base = (area_acres * price_per_acre).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    minimum = minimum or Decimal("0.00")
    total = max(base, minimum).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {
        "currency": "INR",
        "area_acres": float(area_acres),
        "rate_per_acre": float(price_per_acre),
        "base_service_amount": float(base),
        "minimum_booking_amount": float(minimum),
        "total": float(total),
    }


def _valid_date_string(value: Any, label: str) -> Optional[date]:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{label} must use YYYY-MM-DD format.")


def _validate_application_data(kind: str, data: dict[str, Any]) -> dict[str, Any]:
    data = dict(data or {})
    if kind == "individual":
        required = ("full_name", "state", "district", "qualification", "certificate_number", "certificate_issuer")
        fleet = data.get("drones")
        areas = data.get("service_areas")
        if not isinstance(fleet, list) or not fleet:
            raise HTTPException(status_code=422, detail="Add at least one drone to the application.")
        if not isinstance(areas, list) or not areas:
            raise HTTPException(status_code=422, detail="Add at least one service area.")
        if not _list_of_strings(data.get("services"), SERVICE_CATEGORIES):
            raise HTTPException(status_code=422, detail="Choose at least one service category.")
        _decimal(data.get("price_per_acre"), "Price per acre", required=True)
        for drone in fleet:
            if not isinstance(drone, dict) or not _clean(drone.get("model")):
                raise HTTPException(status_code=422, detail="Each drone needs a model.")
            if not _list_of_strings(drone.get("capabilities"), SERVICE_CATEGORIES):
                raise HTTPException(status_code=422, detail="Each drone needs at least one service capability.")
        for area in areas:
            if not isinstance(area, dict) or not _clean(area.get("state")) or not _clean(area.get("district")):
                raise HTTPException(status_code=422, detail="Each service area needs a state and district.")
    elif kind == "company":
        required = ("registered_name", "representative_name", "state", "district")
        if not isinstance(data.get("service_areas"), list) or not data["service_areas"]:
            raise HTTPException(status_code=422, detail="Add at least one company service area.")
        if not _list_of_strings(data.get("services"), SERVICE_CATEGORIES):
            raise HTTPException(status_code=422, detail="Choose at least one company service category.")
    else:
        required = ("full_name", "state", "district", "qualification")
    for key in required:
        if not _clean(data.get(key)):
            raise HTTPException(status_code=422, detail=f"{key.replace('_', ' ').capitalize()} is required.")
    data["services"] = _list_of_strings(data.get("services"), SERVICE_CATEGORIES)
    data["full_name"] = _clean(data.get("full_name"), 150)
    data["state"] = _clean(data.get("state"), 80)
    data["district"] = _clean(data.get("district"), 100)
    return data


def _record_admin_audit(db: Session, actor: AdminUser, action: str, target: str, target_id: str, details: dict[str, Any], request: Request) -> None:
    db.add(AdminAuditLog(
        id=str(uuid.uuid4()), actor_id=actor.user_id, actor_role=actor.role.value,
        action=action, target_entity=target, target_id=target_id,
        details=details, ip_address=None,
        user_agent=(request.headers.get("user-agent") or "")[:255] or None,
    ))


def _record_application_event(db: Session, app: DroneApplication, actor_id: Optional[str], action: str,
                              previous: Optional[str], new: str, reason: Optional[str], notes: Optional[str]) -> None:
    db.add(DroneApprovalHistory(
        id=str(uuid.uuid4()), application_id=app.id, actor_user_id=actor_id,
        action=action, previous_status=previous, new_status=new,
        reason=reason, notes=notes,
    ))


def _record_booking_status(db: Session, booking: DroneBooking, actor_id: Optional[str],
                           previous: Optional[str], new: str, note: Optional[str]) -> None:
    db.add(DroneBookingStatusHistory(
        id=str(uuid.uuid4()), booking_id=booking.id, actor_user_id=actor_id,
        previous_status=previous, new_status=new, note=note,
    ))


def _service_area_match(db: Session, pilot_id: str, state: str, district: str,
                        taluk: Optional[str], village: Optional[str]) -> bool:
    areas = db.query(DroneServiceArea).filter(DroneServiceArea.pilot_id == pilot_id).all()
    norm = lambda val: (val or "").strip().casefold()
    for area in areas:
        if norm(area.state) != norm(state) or norm(area.district) != norm(district):
            continue
        if area.taluk and taluk and norm(area.taluk) != norm(taluk):
            continue
        if area.village and village and norm(area.village) != norm(village):
            continue
        if area.taluk and not taluk:
            continue
        if area.village and not village:
            continue
        return True
    return False


def _eligible_provider(db: Session, pilot: DronePilot, service: str, state: str, district: str,
                       taluk: Optional[str] = None, village: Optional[str] = None,
                       scheduled_date: Optional[date] = None) -> tuple[bool, list[DroneFleet], Optional[DroneCompany]]:
    if pilot.status != "approved" or not pilot.is_active or not pilot.credentials_verified:
        return False, [], None
    if pilot.certificate_expiry and pilot.certificate_expiry < _today():
        return False, [], None
    if not pilot.certificate_number or not pilot.certificate_issuer:
        return False, [], None
    if service not in _list_of_strings(pilot.services, SERVICE_CATEGORIES):
        return False, [], None
    if not _service_area_match(db, pilot.id, state, district, taluk, village):
        return False, [], None

    company = None
    if pilot.company_id:
        company = db.query(DroneCompany).filter(DroneCompany.id == pilot.company_id).first()
        if not company or company.status != "approved" or not company.is_active:
            return False, [], None

    availability = pilot.availability if isinstance(pilot.availability, dict) else {}
    days = availability.get("days") if isinstance(availability.get("days"), list) else []
    if not days:
        return False, [], company
    if scheduled_date and scheduled_date.weekday() not in {int(day) for day in days if str(day).isdigit()}:
        return False, [], company

    drones = db.query(DroneFleet).filter(DroneFleet.pilot_id == pilot.id, DroneFleet.status == "active").all()
    drones = [d for d in drones if service in _list_of_strings(d.capabilities, SERVICE_CATEGORIES)
              and (not d.inspection_due or d.inspection_due >= _today())]
    return bool(drones), drones, company


def _public_provider(db: Session, pilot: DronePilot, company: Optional[DroneCompany], drones: list[DroneFleet]) -> dict[str, Any]:
    avg_rating, review_count = db.query(func.avg(DroneReview.rating), func.count(DroneReview.id)).filter(
        DroneReview.pilot_id == pilot.id
    ).one()
    completed = db.query(func.count(DroneBooking.id)).filter(
        DroneBooking.provider_pilot_id == pilot.id, DroneBooking.status == "completed"
    ).scalar() or 0
    service_areas = db.query(DroneServiceArea).filter(DroneServiceArea.pilot_id == pilot.id).all()
    return {
        "pilot_id": pilot.id,
        "name": pilot.full_name,
        "photo_url": pilot.photo_url,
        "verified": True,
        "company": company.brand_name or company.registered_name if company else None,
        "services": _list_of_strings(pilot.services, SERVICE_CATEGORIES),
        "qualification": pilot.qualification,
        "experience_years": pilot.years_experience,
        "languages": _list_of_strings(pilot.languages),
        "drones": [{"manufacturer": d.manufacturer, "model": d.model,
                    "capabilities": _list_of_strings(d.capabilities, SERVICE_CATEGORIES),
                    "payload_litres": float(d.payload_litres) if d.payload_litres is not None else None}
                   for d in drones],
        "service_areas": [{"state": a.state, "district": a.district, "taluk": a.taluk, "village": a.village}
                          for a in service_areas],
        "price_per_acre": float(pilot.price_per_acre) if pilot.price_per_acre is not None else None,
        "minimum_booking_amount": float(pilot.minimum_booking_amount) if pilot.minimum_booking_amount is not None else None,
        "availability": pilot.availability if isinstance(pilot.availability, dict) else {},
        "rating": round(float(avg_rating), 1) if avg_rating is not None else None,
        "review_count": int(review_count or 0),
        "completed_services": int(completed),
    }


def _pilot_booking_owner(db: Session, pilot_id: str, actor: User) -> bool:
    pilot = db.query(DronePilot).filter(DronePilot.id == pilot_id).first()
    if not pilot:
        return False
    if pilot.owner_user_id == actor.id:
        return True
    return bool(pilot.company_id and db.query(DroneCompany).filter(
        DroneCompany.id == pilot.company_id,
        DroneCompany.owner_user_id == actor.id,
        DroneCompany.status == "approved",
        DroneCompany.is_active.is_(True),
    ).first())


def _document_signature_ok(content_type: str, payload: bytes) -> bool:
    if content_type == "application/pdf":
        return payload.startswith(b"%PDF-")
    if content_type == "image/jpeg":
        return payload.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return payload.startswith(b"\x89PNG\r\n\x1a\n")
    return False


async def _storage_headers() -> tuple[str, dict[str, str]]:
    base_url = (os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL") or "").rstrip("/")
    service_key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY") or "").strip()
    if not base_url or not service_key:
        raise HTTPException(status_code=503, detail="Private document storage is not configured.")
    return base_url, {"apikey": service_key, "Authorization": f"Bearer {service_key}"}


async def _ensure_private_bucket(client: httpx.AsyncClient, base_url: str, headers: dict[str, str]) -> None:
    endpoint = f"{base_url}/storage/v1/bucket/{PRIVATE_BUCKET}"
    response = await client.get(endpoint, headers=headers)
    if response.status_code == 200:
        return
    if response.status_code != 404:
        raise HTTPException(status_code=503, detail="Private document storage is unavailable.")
    response = await client.post(
        f"{base_url}/storage/v1/bucket",
        headers={**headers, "Content-Type": "application/json"},
        json={"id": PRIVATE_BUCKET, "name": PRIVATE_BUCKET, "public": False,
              "file_size_limit": MAX_DOCUMENT_BYTES,
              "allowed_mime_types": list(ALLOWED_DOCUMENTS.keys())},
    )
    if response.status_code not in (200, 201, 409):
        raise HTTPException(status_code=503, detail="Private document storage could not be initialized.")


async def _upload_private_document(filename: str, content_type: str, content: bytes) -> str:
    base_url, headers = await _storage_headers()
    suffix = PurePath(filename).suffix.lower()
    if content_type not in ALLOWED_DOCUMENTS or suffix not in ALLOWED_DOCUMENTS[content_type]:
        raise HTTPException(status_code=415, detail="Upload a PDF, PNG or JPEG document.")
    if not content or len(content) > MAX_DOCUMENT_BYTES:
        raise HTTPException(status_code=413, detail="Documents must be between 1 byte and 10 MB.")
    if not _document_signature_ok(content_type, content):
        raise HTTPException(status_code=415, detail="The file contents do not match the selected document type.")
    object_key = f"applications/{uuid.uuid4()}/{uuid.uuid4()}{suffix}"
    async with httpx.AsyncClient(timeout=20) as client:
        await _ensure_private_bucket(client, base_url, headers)
        response = await client.post(
            f"{base_url}/storage/v1/object/{PRIVATE_BUCKET}/{quote(object_key, safe='/')}",
            headers={**headers, "Content-Type": content_type, "x-upsert": "false"},
            content=content,
        )
    if response.status_code not in (200, 201):
        raise HTTPException(status_code=503, detail="Document upload failed. Please try again.")
    return object_key


async def _signed_document_url(object_key: str) -> str:
    base_url, headers = await _storage_headers()
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"{base_url}/storage/v1/object/sign/{PRIVATE_BUCKET}/{quote(object_key, safe='/')}",
            headers={**headers, "Content-Type": "application/json"},
            json={"expiresIn": 300},
        )
    if response.status_code != 200:
        raise HTTPException(status_code=503, detail="A temporary document link could not be created.")
    signed_path = response.json().get("signedURL") or response.json().get("signedUrl")
    if not signed_path:
        raise HTTPException(status_code=503, detail="A temporary document link could not be created.")
    if signed_path.startswith("http"):
        return signed_path
    return f"{base_url}/storage/v1{signed_path if signed_path.startswith('/') else '/' + signed_path}"


def _required_docs_present(db: Session, app: DroneApplication) -> bool:
    docs = db.query(DroneDocument.document_type).filter(DroneDocument.application_id == app.id).all()
    return ADMIN_REQUIRED_DOCUMENTS.get(app.application_type, set()).issubset({doc[0] for doc in docs})


def _materialize_approved(db: Session, app: DroneApplication, admin: AdminUser,
                          credentials_verified: bool, business_documents_verified: bool) -> None:
    data = _validate_application_data(app.application_type, app.data if isinstance(app.data, dict) else {})
    if app.application_type == "copilot":
        if not credentials_verified:
            raise HTTPException(status_code=422, detail="Confirm that the submitted qualifications were checked before approval.")
        existing = db.query(DroneRoleAssignment).filter(
            DroneRoleAssignment.user_id == app.applicant_user_id,
            DroneRoleAssignment.role == "copilot", DroneRoleAssignment.status == "approved",
        ).first()
        if not existing:
            db.add(DroneRoleAssignment(
                id=str(uuid.uuid4()), user_id=app.applicant_user_id, role="copilot",
                status="approved", requested_by=app.applicant_user_id,
                approved_by=admin.user_id, approved_at=datetime.now(timezone.utc),
            ))
        return

    if app.application_type == "company":
        if not business_documents_verified:
            raise HTTPException(status_code=422, detail="Confirm that the company documents were checked before approval.")
        company = db.query(DroneCompany).filter(DroneCompany.id == app.result_company_id).first() if app.result_company_id else None
        if not company:
            company = DroneCompany(
                id=str(uuid.uuid4()), owner_user_id=app.applicant_user_id,
                registered_name=_clean(data.get("registered_name"), 180),
                brand_name=_clean(data.get("brand_name"), 120) or None,
                representative_name=_clean(data.get("representative_name"), 120),
                contact_email=_clean(data.get("contact_email"), 255) or None,
                state=_clean(data.get("state"), 80), district=_clean(data.get("district"), 100),
                address=_clean(data.get("address"), 1000) or None,
                business_registration=_clean(data.get("business_registration"), 120) or None,
                service_categories=_list_of_strings(data.get("services"), SERVICE_CATEGORIES),
            )
            db.add(company)
            db.flush()
            app.result_company_id = company.id
        company.status = "approved"
        company.is_active = True
        company.approved_by = admin.user_id
        company.approved_at = datetime.now(timezone.utc)
        return

    if not credentials_verified:
        raise HTTPException(status_code=422, detail="Confirm that the pilot credentials were checked before approval.")
    cert_expiry = _valid_date_string(data.get("certificate_expiry"), "Certificate expiry")
    if cert_expiry and cert_expiry < _today():
        raise HTTPException(status_code=422, detail="This pilot certificate is expired and cannot be approved for bookings.")
    if not isinstance(data.get("availability"), dict) or not data["availability"].get("days"):
        raise HTTPException(status_code=422, detail="Add at least one availability day before approval.")
    days = [int(day) for day in data["availability"]["days"] if str(day).isdigit() and 0 <= int(day) <= 6]
    if not days:
        raise HTTPException(status_code=422, detail="Availability days must use 0 (Monday) through 6 (Sunday).")
    data["availability"]["days"] = sorted(set(days))
    price_per_acre = _decimal(data.get("price_per_acre"), "Price per acre", required=True)
    if price_per_acre <= 0:
        raise HTTPException(status_code=422, detail="Set a positive price per acre before approval.")
    pilot = db.query(DronePilot).filter(DronePilot.id == app.result_pilot_id).first() if app.result_pilot_id else None
    if not pilot:
        company = None
        company_id = _clean(data.get("company_id"), 36)
        if company_id:
            company = db.query(DroneCompany).filter(
                DroneCompany.id == company_id,
                DroneCompany.status == "approved",
                DroneCompany.is_active.is_(True),
            ).first()
            if not company:
                raise HTTPException(status_code=422, detail="Choose an approved company before linking this pilot.")
        pilot = DronePilot(
            id=str(uuid.uuid4()), owner_user_id=app.applicant_user_id,
            company_id=company.id if company else None,
            full_name=_clean(data.get("full_name"), 150),
            state=_clean(data.get("state"), 80), district=_clean(data.get("district"), 100),
            taluk=_clean(data.get("taluk"), 100) or None, village=_clean(data.get("village"), 120) or None,
            qualification=_clean(data.get("qualification"), 180),
            certificate_number=_clean(data.get("certificate_number"), 120),
            certificate_issuer=_clean(data.get("certificate_issuer"), 180),
            certificate_expiry=cert_expiry, credentials_verified=True,
            years_experience=max(0, int(data.get("years_experience") or 0)),
            languages=_list_of_strings(data.get("languages")),
            services=_list_of_strings(data.get("services"), SERVICE_CATEGORIES),
            availability=data["availability"], price_per_acre=price_per_acre,
            price_per_hour=_decimal(data.get("price_per_hour"), "Price per hour"),
            minimum_booking_amount=_decimal(data.get("minimum_booking_amount"), "Minimum booking amount"),
        )
        db.add(pilot)
        db.flush()
        app.result_pilot_id = pilot.id
        for area in data["service_areas"]:
            db.add(DroneServiceArea(
                id=str(uuid.uuid4()), pilot_id=pilot.id,
                state=_clean(area.get("state"), 80), district=_clean(area.get("district"), 100),
                taluk=_clean(area.get("taluk"), 100) or None, village=_clean(area.get("village"), 120) or None,
            ))
        for item in data["drones"]:
            inspection = _valid_date_string(item.get("inspection_due"), "Drone inspection due date")
            db.add(DroneFleet(
                id=str(uuid.uuid4()), pilot_id=pilot.id,
                manufacturer=_clean(item.get("manufacturer"), 120) or None,
                model=_clean(item.get("model"), 150),
                serial_number=_clean(item.get("serial_number"), 120) or None,
                registration_number=_clean(item.get("registration_number"), 120) or None,
                capabilities=_list_of_strings(item.get("capabilities"), SERVICE_CATEGORIES),
                payload_litres=_decimal(item.get("payload_litres"), "Payload capacity"),
                equipment_details=_clean(item.get("equipment_details"), 1000) or None,
                inspection_due=inspection, status="active",
            ))
    pilot.status = "approved"
    pilot.is_active = True
    pilot.credentials_verified = True
    pilot.approved_by = admin.user_id
    pilot.approved_at = datetime.now(timezone.utc)


@router.get("/providers")
@router.get("/operators", include_in_schema=False)
async def list_providers(
    service: str = Query("crop_spraying"),
    state: str = Query(..., min_length=2, max_length=80),
    district: str = Query(..., min_length=2, max_length=100),
    taluk: Optional[str] = Query(None, max_length=100),
    village: Optional[str] = Query(None, max_length=120),
    scheduled_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Only current, approved and suitably equipped providers for this location."""
    if service not in SERVICE_CATEGORIES:
        raise HTTPException(status_code=422, detail="Choose a supported drone service.")
    if scheduled_date and scheduled_date < _today():
        raise HTTPException(status_code=422, detail="Choose today or a future date.")
    pilots = db.query(DronePilot).filter(DronePilot.status == "approved", DronePilot.is_active.is_(True)).limit(500).all()
    providers = []
    for pilot in pilots:
        eligible, drones, company = _eligible_provider(db, pilot, service, state, district, taluk, village, scheduled_date)
        if eligible and pilot.price_per_acre is not None and pilot.price_per_acre > 0:
            providers.append(_public_provider(db, pilot, company, drones))
    providers.sort(key=lambda provider: (provider["rating"] is None, -(provider["rating"] or 0), provider["name"].casefold()))
    return {
        "available": bool(providers),
        "providers": providers,
        "message": None if providers else "No approved drone provider is available for this service and location yet.",
        "service": service,
        "location": {"state": state, "district": district, "taluk": taluk, "village": village},
    }


@router.get("/applications/mine")
async def my_applications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    apps = db.query(DroneApplication).filter(DroneApplication.applicant_user_id == user.id).order_by(
        DroneApplication.submitted_at.desc()
    ).limit(20).all()
    return {"applications": [{
        "id": app.id, "type": app.application_type, "status": app.status,
        "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
        "reviewed_at": app.reviewed_at.isoformat() if app.reviewed_at else None,
        "review_notes": app.review_notes,
    } for app in apps]}


@router.post("/applications", status_code=201)
async def create_application(body: ApplicationCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    existing = db.query(DroneApplication).filter(
        DroneApplication.applicant_user_id == user.id,
        DroneApplication.application_type == body.application_type,
        DroneApplication.status.in_(["draft", "pending", "under_review", "more_information_required", "on_hold"]),
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="You already have an open application of this type.")
    data = _validate_application_data(body.application_type, body.data)
    application = DroneApplication(
        id=str(uuid.uuid4()), applicant_user_id=user.id,
        application_type=body.application_type, data=data, status="draft",
    )
    db.add(application)
    db.commit()
    return {"id": application.id, "status": application.status}


@router.patch("/applications/{application_id}")
async def update_application(application_id: str, body: ApplicationUpdate,
                             db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    application = db.query(DroneApplication).filter(
        DroneApplication.id == application_id,
        DroneApplication.applicant_user_id == user.id,
    ).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found.")
    if application.status not in ("draft", "more_information_required"):
        raise HTTPException(status_code=409, detail="This application is locked while it is being reviewed.")
    application.data = _validate_application_data(application.application_type, body.data)
    application.status = "draft"
    db.commit()
    return {"id": application.id, "status": application.status}


async def _attach_document(application_id: str, document_type: str, file: UploadFile,
                           db: Session, actor: User) -> dict[str, Any]:
    if not re.fullmatch(r"[a-z_]{2,64}", document_type or ""):
        raise HTTPException(status_code=422, detail="Document type is invalid.")
    content_type = (file.content_type or "").lower()
    suffix = PurePath(PurePath(file.filename or "document").name).suffix.lower()
    if content_type not in ALLOWED_DOCUMENTS or suffix not in ALLOWED_DOCUMENTS[content_type]:
        raise HTTPException(status_code=415, detail="Upload a PDF, PNG or JPEG document.")
    content = await file.read(MAX_DOCUMENT_BYTES + 1)
    if len(content) > MAX_DOCUMENT_BYTES:
        raise HTTPException(status_code=413, detail="Documents must not exceed 10 MB.")
    object_key = await _upload_private_document(file.filename or "document", content_type, content)
    clean_filename = PurePath(file.filename or "document").name[:180]
    document = DroneDocument(
        id=str(uuid.uuid4()), application_id=application_id,
        uploaded_by=actor.id, document_type=document_type,
        object_key=object_key, original_filename=clean_filename,
        content_type=content_type, size_bytes=len(content),
    )
    db.add(document)
    try:
        db.commit()
    except Exception:
        db.rollback()
        # Best-effort cleanup; the private object remains inaccessible even if
        # cleanup is temporarily unavailable.
        base_url, headers = await _storage_headers()
        async with httpx.AsyncClient(timeout=10) as client:
            await client.delete(f"{base_url}/storage/v1/object/{PRIVATE_BUCKET}/{quote(object_key, safe='/')}", headers=headers)
        raise
    return {"id": document.id, "document_type": document.document_type,
            "filename": document.original_filename, "size_bytes": document.size_bytes,
            "verification_status": document.verification_status}


@router.post("/applications/{application_id}/documents", status_code=201)
async def upload_application_document(
    application_id: str,
    document_type: str = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    app = db.query(DroneApplication).filter(
        DroneApplication.id == application_id,
        DroneApplication.applicant_user_id == user.id,
    ).first()
    if not app or app.status not in ("draft", "more_information_required"):
        raise HTTPException(status_code=404, detail="An editable application was not found.")
    return await _attach_document(application_id, document_type, file, db, user)


@router.post("/applications/{application_id}/submit")
async def submit_application(application_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    app = db.query(DroneApplication).filter(
        DroneApplication.id == application_id,
        DroneApplication.applicant_user_id == user.id,
    ).first()
    if not app or app.status not in ("draft", "more_information_required"):
        raise HTTPException(status_code=404, detail="An editable application was not found.")
    if not _required_docs_present(db, app):
        required = sorted(ADMIN_REQUIRED_DOCUMENTS.get(app.application_type, set()))
        raise HTTPException(status_code=422, detail={"message": "Upload all required documents before submitting.", "required_documents": required})
    previous = app.status
    app.status = "pending"
    app.submitted_at = datetime.now(timezone.utc)
    _record_application_event(db, app, user.id, "submitted", previous, "pending", None, None)
    db.commit()
    return {"id": app.id, "status": app.status, "submitted_at": app.submitted_at.isoformat()}


@router.post("/bookings", status_code=201)
async def request_booking(body: BookingCreate, request: Request,
                          db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if body.scheduled_date < _today():
        raise HTTPException(status_code=422, detail="Choose today or a future booking date.")
    pilot = db.query(DronePilot).filter(DronePilot.id == body.provider_pilot_id).first()
    if not pilot:
        raise HTTPException(status_code=404, detail="The selected provider is no longer available.")
    eligible, _drones, _company = _eligible_provider(
        db, pilot, body.service_category, body.state, body.district,
        body.taluk, body.village, body.scheduled_date,
    )
    if not eligible or pilot.price_per_acre is None or pilot.price_per_acre <= 0:
        raise HTTPException(status_code=409, detail="This provider is not approved, qualified, available, or priced for the requested service.")
    quote = calculate_booking_quote(body.area_acres, pilot.price_per_acre, pilot.minimum_booking_amount)
    booking = DroneBooking(
        id=str(uuid.uuid4()), farmer_user_id=user.id, provider_pilot_id=pilot.id,
        service_category=body.service_category,
        farm_state=_clean(body.state, 80), farm_district=_clean(body.district, 100),
        farm_taluk=_clean(body.taluk, 100) or None, farm_village=_clean(body.village, 120) or None,
        area_acres=body.area_acres, scheduled_date=body.scheduled_date,
        quoted_total=Decimal(str(quote["total"])), price_snapshot=quote,
        status="requested", farmer_notes=_clean(body.farmer_notes, 1500) or None,
    )
    db.add(booking)
    db.flush()
    _record_booking_status(db, booking, user.id, None, "requested", "Farmer submitted booking request.")
    db.commit()
    return {"id": booking.id, "status": booking.status, "quote": quote,
            "message": "Booking request sent. The provider must accept before service is scheduled."}


@router.get("/bookings/mine")
async def list_my_bookings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    farmer_bookings = db.query(DroneBooking).filter(DroneBooking.farmer_user_id == user.id).order_by(
        DroneBooking.requested_at.desc()
    ).limit(100).all()
    provider_pilots = db.query(DronePilot.id).filter(DronePilot.owner_user_id == user.id).all()
    provider_ids = [row[0] for row in provider_pilots]
    company_ids = [row[0] for row in db.query(DroneCompany.id).filter(DroneCompany.owner_user_id == user.id).all()]
    if company_ids:
        provider_ids.extend(row[0] for row in db.query(DronePilot.id).filter(DronePilot.company_id.in_(company_ids)).all())
    if provider_ids:
        provider_bookings = db.query(DroneBooking).filter(
            DroneBooking.provider_pilot_id.in_(provider_ids), DroneBooking.farmer_user_id != user.id
        ).order_by(DroneBooking.requested_at.desc()).limit(100).all()
    else:
        provider_bookings = []
    bookings = {booking.id: booking for booking in [*farmer_bookings, *provider_bookings]}
    return {"bookings": [_serialize_booking(b) for b in sorted(bookings.values(), key=lambda x: x.requested_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)]}


def _serialize_booking(booking: DroneBooking) -> dict[str, Any]:
    return {
        "id": booking.id, "provider_pilot_id": booking.provider_pilot_id,
        "service_category": booking.service_category,
        "farm_location": {"state": booking.farm_state, "district": booking.farm_district,
                          "taluk": booking.farm_taluk, "village": booking.farm_village},
        "area_acres": float(booking.area_acres),
        "scheduled_date": booking.scheduled_date.isoformat(),
        "quoted_total": float(booking.quoted_total), "currency": "INR",
        "status": booking.status,
        "farmer_notes": booking.farmer_notes,
        "provider_notes": booking.provider_notes,
        "requested_at": booking.requested_at.isoformat() if booking.requested_at else None,
        "updated_at": booking.updated_at.isoformat() if booking.updated_at else None,
        "completed_at": booking.completed_at.isoformat() if booking.completed_at else None,
    }


@router.patch("/bookings/{booking_id}/provider-status")
async def update_provider_booking(booking_id: str, body: BookingStatusUpdate,
                                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    booking = db.query(DroneBooking).filter(DroneBooking.id == booking_id).first()
    if not booking or not _pilot_booking_owner(db, booking.provider_pilot_id, user):
        raise HTTPException(status_code=404, detail="Booking not found.")
    allowed_transitions = {
        "requested": {"accepted", "rejected"},
        "accepted": {"pilot_assigned", "scheduled", "rejected"},
        "pilot_assigned": {"scheduled", "rejected"},
        "scheduled": {"on_the_way", "in_progress", "cancelled"},
        "on_the_way": {"in_progress", "cancelled"},
        "in_progress": {"completed", "disputed"},
    }
    if body.status not in allowed_transitions.get(booking.status, set()):
        raise HTTPException(status_code=409, detail=f"Cannot move a {booking.status} booking to {body.status}.")
    if body.status == "pilot_assigned" or body.assigned_drone_id:
        drone = db.query(DroneFleet).filter(
            DroneFleet.id == body.assigned_drone_id,
            DroneFleet.pilot_id == booking.provider_pilot_id,
            DroneFleet.status == "active",
        ).first()
        if not drone or booking.service_category not in _list_of_strings(drone.capabilities, SERVICE_CATEGORIES):
            raise HTTPException(status_code=422, detail="Choose an active drone approved for this service.")
        if drone.inspection_due and drone.inspection_due < _today():
            raise HTTPException(status_code=409, detail="This drone's inspection is overdue.")
        booking.assigned_drone_id = drone.id
    previous = booking.status
    # Providers submit completion evidence; the farmer confirms before this
    # becomes a completed booking eligible for review and reporting.
    final_status = "awaiting_farmer_confirmation" if body.status == "completed" else body.status
    booking.status = final_status
    booking.provider_notes = _clean(body.note, 1200) or booking.provider_notes
    _record_booking_status(db, booking, user.id, previous, final_status, body.note)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This pilot or drone already has a booking on that date.")
    return _serialize_booking(booking)


@router.post("/bookings/{booking_id}/confirm-completion")
async def confirm_booking_completion(booking_id: str, db: Session = Depends(get_db),
                                     user: User = Depends(get_current_user)):
    booking = db.query(DroneBooking).filter(
        DroneBooking.id == booking_id,
        DroneBooking.farmer_user_id == user.id,
        DroneBooking.status == "awaiting_farmer_confirmation",
    ).first()
    if not booking:
        raise HTTPException(status_code=404, detail="A booking awaiting your confirmation was not found.")
    previous = booking.status
    booking.status = "completed"
    booking.completed_at = datetime.now(timezone.utc)
    _record_booking_status(db, booking, user.id, previous, "completed", "Farmer confirmed service completion.")
    db.commit()
    return _serialize_booking(booking)


@router.post("/bookings/{booking_id}/cancel")
async def cancel_booking(booking_id: str, reason: str = Query(..., min_length=5, max_length=800),
                         db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    booking = db.query(DroneBooking).filter(
        DroneBooking.id == booking_id, DroneBooking.farmer_user_id == user.id
    ).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")
    if booking.status not in ("requested", "accepted", "pilot_assigned", "scheduled"):
        raise HTTPException(status_code=409, detail="This booking can no longer be cancelled in the app.")
    previous = booking.status
    booking.status = "cancelled"
    _record_booking_status(db, booking, user.id, previous, "cancelled", reason)
    db.commit()
    return _serialize_booking(booking)


@router.post("/bookings/{booking_id}/review", status_code=201)
async def review_booking(booking_id: str, body: BookingReview,
                         db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    booking = db.query(DroneBooking).filter(
        DroneBooking.id == booking_id, DroneBooking.farmer_user_id == user.id
    ).first()
    if not booking or booking.status != "completed":
        raise HTTPException(status_code=409, detail="A review is available only after the farmer confirms the service is complete.")
    if db.query(DroneReview).filter(DroneReview.booking_id == booking.id).first():
        raise HTTPException(status_code=409, detail="This completed service already has a review.")
    review = DroneReview(
        id=str(uuid.uuid4()), booking_id=booking.id, farmer_user_id=user.id,
        pilot_id=booking.provider_pilot_id, rating=body.rating,
        review=_clean(body.review, 1500) or None,
    )
    db.add(review)
    db.commit()
    return {"id": review.id, "rating": review.rating, "created_at": review.created_at.isoformat() if review.created_at else None}


@router.post("/roles", status_code=201)
async def request_drone_role(body: RoleRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    company_id = body.company_id
    if company_id:
        company = db.query(DroneCompany).filter(
            DroneCompany.id == company_id, DroneCompany.status == "approved", DroneCompany.is_active.is_(True)
        ).first()
        if not company:
            raise HTTPException(status_code=404, detail="Approved company not found.")
        existing_role = db.query(DroneRoleAssignment).filter(
            DroneRoleAssignment.company_id == company_id,
            DroneRoleAssignment.user_id == user.id,
            DroneRoleAssignment.role == body.role,
            DroneRoleAssignment.status.in_(["pending", "awaiting_person_confirmation", "approved"]),
        ).first()
        if existing_role:
            raise HTTPException(status_code=409, detail="This role request already exists.")
        assignment = DroneRoleAssignment(
            id=str(uuid.uuid4()), user_id=user.id, company_id=company_id,
            role=body.role, status="pending", requested_by=user.id,
        )
    else:
        assignment = DroneRoleAssignment(
            id=str(uuid.uuid4()), user_id=user.id, role=body.role,
            status="pending", requested_by=user.id,
        )
    db.add(assignment)
    db.commit()
    return {"id": assignment.id, "status": assignment.status, "role": assignment.role}


@router.post("/companies/{company_id}/roles", status_code=201)
async def invite_company_role(company_id: str, body: CompanyRoleInvite,
                              db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    company = db.query(DroneCompany).filter(
        DroneCompany.id == company_id, DroneCompany.owner_user_id == user.id,
        DroneCompany.status == "approved", DroneCompany.is_active.is_(True),
    ).first()
    target = db.query(User).filter(User.id == body.target_user_id, User.is_active.is_(True)).first()
    if not company or not target:
        raise HTTPException(status_code=404, detail="Approved company or Agro AI account not found.")
    active_request = db.query(DroneRoleAssignment).filter(
        DroneRoleAssignment.company_id == company.id,
        DroneRoleAssignment.user_id == target.id,
        DroneRoleAssignment.role == body.role,
        DroneRoleAssignment.status.in_(["pending", "awaiting_person_confirmation", "approved"]),
    ).first()
    if active_request:
        raise HTTPException(status_code=409, detail="This company role request already exists.")
    assignment = DroneRoleAssignment(
        id=str(uuid.uuid4()), user_id=target.id, company_id=company.id,
        role=body.role, status="awaiting_person_confirmation", requested_by=user.id,
    )
    db.add(assignment)
    db.commit()
    return {"id": assignment.id, "status": assignment.status, "role": assignment.role}


@router.post("/roles/{assignment_id}/confirm")
async def confirm_company_role(assignment_id: str, accept: bool = Query(...),
                               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assignment = db.query(DroneRoleAssignment).filter(
        DroneRoleAssignment.id == assignment_id,
        DroneRoleAssignment.user_id == user.id,
        DroneRoleAssignment.status == "awaiting_person_confirmation",
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Role request not found.")
    assignment.status = "pending" if accept else "rejected"
    db.commit()
    return {"id": assignment.id, "status": assignment.status}


@admin_router.get("/overview")
async def admin_overview(db: Session = Depends(get_db), admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin))):
    def count(query) -> int:
        return int(query.scalar() or 0)
    return {
        "total_pilots": count(db.query(func.count(DronePilot.id))),
        "approved_pilots": count(db.query(func.count(DronePilot.id)).filter(DronePilot.status == "approved", DronePilot.is_active.is_(True))),
        "suspended_pilots": count(db.query(func.count(DronePilot.id)).filter(DronePilot.status == "suspended")),
        "total_companies": count(db.query(func.count(DroneCompany.id))),
        "approved_companies": count(db.query(func.count(DroneCompany.id)).filter(DroneCompany.status == "approved", DroneCompany.is_active.is_(True))),
        "pending_applications": count(db.query(func.count(DroneApplication.id)).filter(DroneApplication.status == "pending")),
        "under_review_applications": count(db.query(func.count(DroneApplication.id)).filter(DroneApplication.status == "under_review")),
        "active_bookings": count(db.query(func.count(DroneBooking.id)).filter(DroneBooking.status.in_(ACTIVE_BOOKING_STATUSES))),
        "completed_bookings": count(db.query(func.count(DroneBooking.id)).filter(DroneBooking.status == "completed")),
        "cancelled_bookings": count(db.query(func.count(DroneBooking.id)).filter(DroneBooking.status == "cancelled")),
        "pending_role_approvals": count(db.query(func.count(DroneRoleAssignment.id)).filter(DroneRoleAssignment.status == "pending")),
    }


@admin_router.get("/applications")
async def admin_list_applications(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin)),
):
    query = db.query(DroneApplication)
    if status_filter:
        if status_filter not in APP_STATUSES:
            raise HTTPException(status_code=422, detail="Unknown application status.")
        query = query.filter(DroneApplication.status == status_filter)
    applications = query.order_by(DroneApplication.submitted_at.desc()).limit(300).all()
    result = []
    for app in applications:
        applicant = db.query(User).filter(User.id == app.applicant_user_id).first()
        documents = db.query(DroneDocument).filter(DroneDocument.application_id == app.id).order_by(DroneDocument.created_at).all()
        history = db.query(DroneApprovalHistory).filter(DroneApprovalHistory.application_id == app.id).order_by(DroneApprovalHistory.created_at.desc()).limit(20).all()
        result.append({
            "id": app.id, "type": app.application_type, "status": app.status,
            "data": app.data, "applicant": {"user_id": applicant.id, "name": applicant.full_name,
                "email": applicant.email, "phone": applicant.phone} if applicant else None,
            "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
            "reviewed_at": app.reviewed_at.isoformat() if app.reviewed_at else None,
            "review_notes": app.review_notes,
            "documents": [{"id": d.id, "document_type": d.document_type,
                "filename": d.original_filename, "content_type": d.content_type,
                "size_bytes": d.size_bytes, "verification_status": d.verification_status}
                for d in documents],
            "required_documents_present": _required_docs_present(db, app),
            "history": [{"action": h.action, "previous_status": h.previous_status,
                "new_status": h.new_status, "reason": h.reason, "notes": h.notes,
                "created_at": h.created_at.isoformat() if h.created_at else None} for h in history],
        })
    return {"applications": result}


@admin_router.post("/applications/manual", status_code=201)
async def admin_manual_application(body: AdminManualApplication, request: Request,
                                   db: Session = Depends(get_db),
                                   admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin))):
    existing_user = db.query(User).filter(User.id == body.existing_user_id).first()
    if not existing_user:
        raise HTTPException(status_code=404, detail="Select an existing Agro AI account. This operation never creates a duplicate account.")
    data = _validate_application_data(body.application_type, body.data)
    application = DroneApplication(
        id=str(uuid.uuid4()), applicant_user_id=existing_user.id,
        application_type=body.application_type, data=data,
        status="pending", created_by_admin=admin.user_id,
    )
    db.add(application)
    _record_application_event(db, application, admin.user_id, "registered_by_super_admin", None, "pending", None, None)
    _record_admin_audit(db, admin, "DRONE_APPLICATION_MANUALLY_REGISTERED", "drone_application", application.id,
                        {"type": body.application_type, "applicant_user_id": existing_user.id}, request)
    db.commit()
    return {"id": application.id, "status": application.status}


@admin_router.post("/applications/{application_id}/documents", status_code=201)
async def admin_upload_application_document(
    application_id: str,
    document_type: str = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin)),
):
    app = db.query(DroneApplication).filter(DroneApplication.id == application_id).first()
    if not app or app.status not in ("draft", "pending", "under_review", "more_information_required"):
        raise HTTPException(status_code=404, detail="An open application was not found.")
    actor = db.query(User).filter(User.id == admin.user_id).first()
    if not actor:
        raise HTTPException(status_code=403, detail="Administrator account is unavailable.")
    return await _attach_document(application_id, document_type, file, db, actor)


@admin_router.get("/applications/{application_id}/documents/{document_id}/url")
async def admin_document_url(application_id: str, document_id: str,
                             db: Session = Depends(get_db),
                             admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin))):
    doc = db.query(DroneDocument).filter(
        DroneDocument.id == document_id, DroneDocument.application_id == application_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"signed_url": await _signed_document_url(doc.object_key), "expires_in_seconds": 300}


@admin_router.post("/applications/{application_id}/review")
async def review_application(application_id: str, body: ApplicationReview, request: Request,
                             db: Session = Depends(get_db),
                             admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin))):
    application = db.query(DroneApplication).filter(DroneApplication.id == application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found.")
    if application.status in ("approved", "rejected", "suspended", "expired"):
        raise HTTPException(status_code=409, detail="This application has a final decision.")
    if body.status in ("rejected", "on_hold", "more_information_required") and not _clean(body.reason, 800):
        raise HTTPException(status_code=422, detail="A reason is required for this decision.")
    if body.status == "approved":
        if not _required_docs_present(db, application):
            raise HTTPException(status_code=422, detail="Required documents are missing.")
        _materialize_approved(db, application, admin, body.credentials_verified, body.business_documents_verified)
    previous = application.status
    application.status = body.status
    application.reviewed_by = admin.user_id
    application.reviewed_at = datetime.now(timezone.utc)
    application.review_notes = _clean(body.notes, 3000) or _clean(body.reason, 800) or None
    if body.status in ("more_information_required", "on_hold"):
        application.reviewed_at = None
        application.reviewed_by = None
    _record_application_event(db, application, admin.user_id, body.status, previous, body.status, body.reason, body.notes)
    _record_admin_audit(db, admin, f"DRONE_APPLICATION_{body.status.upper()}", "drone_application", application.id,
                        {"previous_status": previous, "status": body.status, "reason": body.reason,
                         "credentials_verified": body.credentials_verified,
                         "business_documents_verified": body.business_documents_verified}, request)
    db.commit()
    return {"id": application.id, "status": application.status, "reviewed_at": application.reviewed_at.isoformat() if application.reviewed_at else None}


@admin_router.get("/providers")
async def admin_list_providers(status_filter: Optional[str] = Query(None, alias="status"),
                               db: Session = Depends(get_db),
                               admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin))):
    pilots_q = db.query(DronePilot)
    companies_q = db.query(DroneCompany)
    if status_filter:
        pilots_q = pilots_q.filter(DronePilot.status == status_filter)
        companies_q = companies_q.filter(DroneCompany.status == status_filter)
    pilots = pilots_q.order_by(DronePilot.created_at.desc()).limit(500).all()
    companies = companies_q.order_by(DroneCompany.created_at.desc()).limit(250).all()
    return {
        "pilots": [{"id": p.id, "owner_user_id": p.owner_user_id, "name": p.full_name,
            "company_id": p.company_id, "state": p.state, "district": p.district,
            "services": p.services, "status": p.status, "is_active": p.is_active,
            "credentials_verified": p.credentials_verified,
            "certificate_expiry": p.certificate_expiry.isoformat() if p.certificate_expiry else None,
            "price_per_acre": float(p.price_per_acre) if p.price_per_acre is not None else None,
            "created_at": p.created_at.isoformat() if p.created_at else None} for p in pilots],
        "companies": [{"id": c.id, "owner_user_id": c.owner_user_id, "name": c.registered_name,
            "brand_name": c.brand_name, "state": c.state, "district": c.district,
            "status": c.status, "is_active": c.is_active,
            "pilot_count": db.query(func.count(DronePilot.id)).filter(DronePilot.company_id == c.id).scalar() or 0,
            "created_at": c.created_at.isoformat() if c.created_at else None} for c in companies],
    }


@admin_router.patch("/providers/{provider_type}/{provider_id}/status")
async def admin_update_provider_status(provider_type: Literal["pilot", "company"], provider_id: str,
                                       body: ProviderStatusUpdate, request: Request,
                                       db: Session = Depends(get_db),
                                       admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin))):
    model = DronePilot if provider_type == "pilot" else DroneCompany
    provider = db.query(model).filter(model.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found.")
    previous = provider.status
    if body.status == "approved":
        if provider.status not in ("approved", "suspended"):
            raise HTTPException(status_code=409, detail="A provider must pass the application approval workflow before activation.")
        if provider_type == "pilot":
            if not provider.credentials_verified or (provider.certificate_expiry and provider.certificate_expiry < _today()):
                raise HTTPException(status_code=409, detail="Current, verified pilot credentials are required for reactivation.")
        provider.status = "approved"
        provider.is_active = True
    else:
        provider.status = "suspended"
        provider.is_active = False
    _record_admin_audit(db, admin, f"DRONE_{provider_type.upper()}_{body.status.upper()}",
                        f"drone_{provider_type}", provider.id,
                        {"previous_status": previous, "status": provider.status, "reason": body.reason}, request)
    db.commit()
    return {"id": provider.id, "status": provider.status, "is_active": provider.is_active}


@admin_router.get("/bookings")
async def admin_list_bookings(status_filter: Optional[str] = Query(None, alias="status"),
                              db: Session = Depends(get_db),
                              admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin))):
    query = db.query(DroneBooking)
    if status_filter:
        if status_filter not in BOOKING_STATUSES:
            raise HTTPException(status_code=422, detail="Unknown booking status.")
        query = query.filter(DroneBooking.status == status_filter)
    bookings = query.order_by(DroneBooking.requested_at.desc()).limit(500).all()
    return {"bookings": [_serialize_booking(item) | {"farmer_user_id": item.farmer_user_id,
        "provider": db.query(DronePilot.full_name).filter(DronePilot.id == item.provider_pilot_id).scalar()}
        for item in bookings]}


@admin_router.get("/roles")
async def admin_list_roles(db: Session = Depends(get_db),
                           admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin))):
    rows = db.query(DroneRoleAssignment).order_by(DroneRoleAssignment.created_at.desc()).limit(500).all()
    return {"roles": [{"id": row.id, "user_id": row.user_id, "company_id": row.company_id,
        "role": row.role, "status": row.status, "requested_by": row.requested_by,
        "created_at": row.created_at.isoformat() if row.created_at else None}
        for row in rows]}


@admin_router.patch("/roles/{assignment_id}")
async def admin_decide_role(assignment_id: str, body: RoleDecision, request: Request,
                            db: Session = Depends(get_db),
                            admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin))):
    assignment = db.query(DroneRoleAssignment).filter(DroneRoleAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Role request not found.")
    previous = assignment.status
    assignment.status = body.status
    if body.status == "approved":
        assignment.approved_by = admin.user_id
        assignment.approved_at = datetime.now(timezone.utc)
    if body.status == "revoked":
        assignment.revoked_at = datetime.now(timezone.utc)
    _record_admin_audit(db, admin, f"DRONE_ROLE_{body.status.upper()}", "drone_role_assignment", assignment.id,
                        {"role": assignment.role, "previous_status": previous, "status": body.status,
                         "reason": body.reason}, request)
    db.commit()
    return {"id": assignment.id, "status": assignment.status}


@admin_router.get("/applications/{application_id}/history")
async def admin_application_history(application_id: str, db: Session = Depends(get_db),
                                    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin))):
    rows = db.query(DroneApprovalHistory).filter(
        DroneApprovalHistory.application_id == application_id
    ).order_by(DroneApprovalHistory.created_at.desc()).all()
    return {"history": [{"actor_user_id": row.actor_user_id, "action": row.action,
        "previous_status": row.previous_status, "new_status": row.new_status,
        "reason": row.reason, "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None} for row in rows]}

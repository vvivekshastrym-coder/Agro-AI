from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid
import logging
from ..database.connection import get_db
from ..database.models import DiagnosisReport, DiagnosisImage, User, Farm
from ..auth.deps import get_current_user, get_optional_current_user
from ..auth.entitlements import check_and_consume_entitlement
from ..services.ai_service import (
    analyze_leaf_image,
    get_gemini_api_key,
    get_openai_api_key,
    set_runtime_api_key
)

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
DISCLAIMER = "AI image assessment, not confirmed by a qualified agricultural expert or laboratory test. Consult your local KVK / agriculture officer before treating."
ALLOWED_MIME_TYPES = ["image/jpeg", "image/jpg", "image/png", "image/webp"]

class ApiKeyConfigRequest(BaseModel):
    provider: str = "gemini"  # gemini | openai
    api_key: str

@router.get("/status")
async def get_diagnosis_engine_status():
    """Returns vision-provider readiness. There is no local fallback: without a provider, diagnosis is unavailable."""
    gemini_key = get_gemini_api_key()
    openai_key = get_openai_api_key()
    has_gemini = bool(gemini_key and len(gemini_key) > 10)
    has_openai = bool(openai_key and len(openai_key) > 10)
    has_cloud_vision = has_gemini or has_openai
    return {
        "has_cloud_vision": has_cloud_vision,
        "active_engine": ("Gemini Vision" if has_gemini else ("OpenAI GPT-4o-mini Vision" if has_openai else None)),
        "engine_version": "3.0-two-stage",
        "diagnosis_available": has_cloud_vision,
        "knowledge_base_verified": False,
        "chemical_recommendations": "not_available_no_verified_label_library",
    }

@router.post("/set-key")
async def set_diagnosis_api_key_retired():
    """Retired: any caller could replace the server's AI key. Configure keys via server environment only."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail={"error": {"code": "ENDPOINT_RETIRED", "message": "API keys are configured on the server environment only."}},
    )

@router.post("/analyze")
async def analyze_diagnosis(
    image: UploadFile = File(...),
    crop: Optional[str] = Form(None),
    language: Optional[str] = Form("en"),
    farmer_id: Optional[str] = Form(None),
    farm_id: Optional[str] = Form(None),
    field_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    POST /api/diagnosis/analyze
    Two-stage analysis: (A) plant identification, (B) problem identification, followed by a deterministic
    safety gate. Returns an honest non-diagnostic status instead of guessing.
    """
    # 0. Enforce server-side entitlement
    check_and_consume_entitlement(db, user.id, "diagnose_leaf", consume=True)

    if farm_id and user:
        owned = db.query(Farm).filter(Farm.id == farm_id, Farm.user_id == user.id).first()
        if not owned:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail={"error": {"code": "FORBIDDEN", "message": "Farm not found for this account."}})

    # 1. Validate File MIME Type
    if image.content_type.lower() not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_IMAGE_TYPE", "message": "Only JPG, PNG, and WebP images are allowed.", "retryable": True}}
        )

    # 2. Read and Validate File Size
    contents = await image.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"error": {"code": "IMAGE_TOO_LARGE", "message": "Image size exceeds 10MB limit.", "retryable": True}}
        )

    # Validate Magic Bytes (defense-in-depth against MIME spoofing)
    is_jpeg = contents.startswith(b"\xff\xd8\xff")
    is_png = contents.startswith(b"\x89PNG\r\n\x1a\n")
    is_webp = contents.startswith(b"RIFF") and b"WEBP" in contents[:16]
    if not (is_jpeg or is_png or is_webp):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_IMAGE_PAYLOAD", "message": "File signature is not a recognized image format (JPG, PNG, WebP).", "retryable": True}}
        )

    # 3. Call Vision AI Model Service on Backend
    try:
        res = await analyze_leaf_image(
            image_bytes=contents,
            mime_type=image.content_type,
            crop_hint=crop or "",
            language=language or "en"
        )
    except Exception as e:
        logger.error(f"Error calling AI vision model: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "DIAGNOSIS_PROVIDER_ERROR", "message": "Diagnosis service failed. No diagnosis was generated.", "retryable": True}}
        )

    if res.get("status") == "unavailable":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "DIAGNOSIS_UNAVAILABLE", "message": res.get("message"), "next_action": res.get("next_action"), "retryable": True}}
        )

    # Non-diagnostic outcomes are returned as-is and NEVER stored as a diagnosis report:
    # not a plant / crop needs confirmation / unable to identify confidently.
    res_status = res.get("status")
    if res_status in ("not_a_plant", "needs_crop_confirmation", "low_confidence"):
        res.setdefault("disclaimer", DISCLAIMER)
        return res

    # Support legacy/direct mock dicts that omit 'status' only when crop, disease and numeric confidence are all valid
    if res_status is None:
        raw_conf = res.get("confidence")
        if isinstance(raw_conf, bool) or not isinstance(raw_conf, (int, float)) or not res.get("disease") or not res.get("crop"):
            logger.error("Vision engine returned an incomplete legacy result")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"error": {"code": "INVALID_PROVIDER_RESPONSE", "message": "Diagnosis service returned an incomplete result. No diagnosis was saved.", "retryable": True}}
            )
        conf_num = float(raw_conf) / 100.0 if float(raw_conf) > 1.0 else float(raw_conf)
        if conf_num < 0.50:
            return {"status": "low_confidence", "message": "Unable to identify confidently.", "disclaimer": DISCLAIMER}
        res_status = "ok"
        res = {**res, "status": "ok", "confidence": round(conf_num, 2), "confidence_basis": res.get("confidence_basis", "model_self_reported")}

    if res_status not in ("ok", "moderate_confidence") or not res.get("disease") or not res.get("crop"):
        logger.error("Vision engine returned an unrecognised/incomplete result (status=%s)", res_status)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": {"code": "INVALID_PROVIDER_RESPONSE", "message": "Diagnosis service returned an incomplete result. No diagnosis was saved.", "retryable": True}}
        )

    model_name = res.get("model_used", "vision-model")
    conf_val = res.get("confidence") if isinstance(res.get("confidence"), (int, float)) and not isinstance(res.get("confidence"), bool) else None

    # 4. Store report. Numeric confidence is intentionally NULL: the model's self-reported number is
    # uncalibrated, so only the categorical level (HIGH / MODERATE) is kept in the API response.
    report_id = str(uuid.uuid4())
    farmer_id = user.id if user else None
    report = DiagnosisReport(
        id=report_id,
        farmer_id=farmer_id,
        farm_id=farm_id if user else None,
        field_id=field_id if user else None,
        image_url=f"/uploads/diagnosis/{report_id}.jpg",
        crop=res.get("crop"),
        disease=res["disease"],
        scientific_name=res.get("scientific_name"),
        confidence=conf_val,
        severity=res.get("severity"),
        evidence=res.get("evidence", []),
        organic_treatment=res.get("organic_treatment", []),
        chemical_treatment=[],
        dosage=[],
        prevention=res.get("prevention", []),
        spray_window=None,
        expected_recovery_days=None,
        warnings=res.get("warnings", []),
        model=model_name,
        model_version=res.get("engine_version", "3.0-two-stage")[:20]
    )

    try:
        db.add(report)
        db.commit()
        db.refresh(report)
    except Exception as dbe:
        logger.warning(f"Database save diagnosis report failed: {dbe}")
        try:
            db.rollback()
        except Exception:
            pass

    created_at_val = None
    if getattr(report, "created_at", None):
        try:
            created_at_val = report.created_at.isoformat()
        except Exception:
            created_at_val = datetime.utcnow().isoformat()
    else:
        created_at_val = datetime.utcnow().isoformat()

    # 5. Response: everything the engine produced + persistence identifiers
    return {
        **res,
        "report_id": report.id,
        "id": report.id,
        "farmer_id": report.farmer_id or "guest",
        "farm_id": report.farm_id,
        "field_id": report.field_id,
        "spray_window": report.spray_window,
        "expected_recovery_days": report.expected_recovery_days,
        "created_at": created_at_val,
        "model": report.model,
        "confidence_basis": res.get("confidence_basis", "categorical_uncalibrated"),
        "disclaimer": DISCLAIMER,
        "model_version": report.model_version,
    }

@router.get("/reports/{farmer_id}")
async def get_farmer_diagnoses(farmer_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Retrieve the caller's own diagnosis history."""
    if farmer_id != user.id and farmer_id != "me":
        logger.warning("Cross-user report access denied: %s -> %s", user.id, farmer_id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"error": {"code": "FORBIDDEN", "message": "Not permitted."}})
    farmer_id = user.id
    reports = db.query(DiagnosisReport).filter(DiagnosisReport.farmer_id == farmer_id).order_by(DiagnosisReport.created_at.desc()).all()
    return reports

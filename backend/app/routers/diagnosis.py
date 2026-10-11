from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import uuid
import logging
from ..database.connection import get_db
from ..database.models import DiagnosisReport, DiagnosisImage, User, Farm
from ..auth.deps import get_current_user
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
ALLOWED_MIME_TYPES = ["image/jpeg", "image/jpg", "image/png", "image/webp"]

class ApiKeyConfigRequest(BaseModel):
    provider: str = "gemini"  # gemini | openai
    api_key: str

@router.get("/status")
async def get_diagnosis_engine_status():
    """Returns active vision engine status and cloud API key readiness."""
    gemini_key = get_gemini_api_key()
    openai_key = get_openai_api_key()
    has_cloud_vision = bool(gemini_key and len(gemini_key) > 10) or bool(openai_key and len(openai_key) > 10)
    provider = "Gemini 2.0 Flash Vision" if (gemini_key and len(gemini_key) > 10) else (
        "OpenAI GPT-4o-mini Vision" if (openai_key and len(openai_key) > 10) else "None configured (diagnosis unavailable)"
    )
    return {
        "has_cloud_vision": has_cloud_vision,
        "active_engine": provider,
        "pixel_computer_vision_active": False
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
    Analyzes uploaded crop leaf photo using Cloud Vision (if key configured)
    or Local Pixel Computer Vision (Pillow) + ICAR Pathology rules.
    """
    # 0. Enforce server-side entitlement
    check_and_consume_entitlement(db, user.id, "diagnose_leaf", consume=True)

    if farm_id:
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

    # Check for low confidence / invalid leaf
    if res.get("status") == "low_confidence":
        return {
            "status": "low_confidence",
            "message": res.get("message", "The image is not clear enough for a reliable diagnosis."),
            "next_action": res.get("next_action", "Please upload a clear close-up image of one affected leaf.")
        }

    raw_conf = res.get("confidence")
    if isinstance(raw_conf, bool) or not isinstance(raw_conf, (int, float)) or not res.get("disease"):
        logger.error("Vision provider returned an incomplete result (missing confidence/disease)")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": {"code": "INVALID_PROVIDER_RESPONSE", "message": "Diagnosis service returned an incomplete result. No diagnosis was saved.", "retryable": True}}
        )
    confidence = float(raw_conf)
    if confidence > 1.0:
        confidence = confidence / 100.0

    if confidence < 0.50:
        return {
            "status": "low_confidence",
            "message": "The image details are insufficient to identify a specific pathogen.",
            "next_action": "Hold camera 10–15 cm from the leaf with good natural lighting."
        }

    model_name = res.get("model_used", "Gemini 2.0 Flash" if res.get("is_ai_vision") else "Local Pixel CV + ICAR")
    is_live_vision = bool(res.get("is_ai_vision", False))

    # 4. Store Report in Database
    report_id = str(uuid.uuid4())
    report = DiagnosisReport(
        id=report_id,
        farmer_id=user.id,
        farm_id=farm_id,
        field_id=field_id,
        image_url=f"/uploads/diagnosis/{report_id}.jpg",
        crop=res.get("crop") or crop or None,
        disease=res["disease"],
        scientific_name=res.get("scientific_name"),
        confidence=round(confidence, 2),
        severity=res.get("severity"),
        evidence=res.get("evidence", []),
        organic_treatment=res.get("organic_treatment", []),
        chemical_treatment=res.get("chemical_treatment", []),
        dosage=res.get("dosage", []),
        prevention=res.get("prevention", []),
        spray_window=res.get("spray_window"),
        expected_recovery_days=(int(res["expected_recovery_days"]) if isinstance(res.get("expected_recovery_days"), (int, float)) else None),
        warnings=res.get("warnings", []),
        model=model_name,
        model_version="2.0"
    )
    
    db.add(report)
    db.commit()
    db.refresh(report)

    # 5. Return Structured Response Matching Required Schema
    return {
        "report_id": report.id,
        "id": report.id,
        "farmer_id": report.farmer_id,
        "farm_id": report.farm_id,
        "field_id": report.field_id,
        "crop": report.crop,
        "disease": report.disease,
        "scientific_name": report.scientific_name,
        "confidence": report.confidence,
        "severity": report.severity,
        "evidence": report.evidence or [],
        "organic_treatment": report.organic_treatment or [],
        "chemical_treatment": report.chemical_treatment or [],
        "dosage": report.dosage or [],
        "prevention": report.prevention or [],
        "spray_window": report.spray_window,
        "expected_recovery_days": report.expected_recovery_days,
        "warnings": report.warnings or [],
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "model": report.model,
        "is_ai_vision": is_live_vision,
        "confidence_basis": "model_self_reported",
        "disclaimer": "AI-generated assessment, not confirmed by a qualified agricultural expert.",
        "model_version": report.model_version
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

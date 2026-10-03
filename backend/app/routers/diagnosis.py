from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
import uuid
import logging
from ..database.connection import get_db
from ..database.models import DiagnosisReport, DiagnosisImage, User
from ..services.ai_service import analyze_leaf_image, get_expert_fallback_diagnosis

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME_TYPES = ["image/jpeg", "image/jpg", "image/png", "image/webp"]

@router.post("/analyze")
async def analyze_diagnosis(
    image: UploadFile = File(...),
    crop: Optional[str] = Form(None),
    language: Optional[str] = Form("en"),
    farmer_id: Optional[str] = Form(None),
    farm_id: Optional[str] = Form(None),
    field_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    POST /api/diagnosis/analyze
    Analyzes uploaded crop leaf photo using backend AI Vision service.
    Returns structured JSON or low_confidence response.
    """
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
        res = get_expert_fallback_diagnosis(crop or "", language or "en", contents)

    confidence = float(res.get("confidence", 0.0))
    # Normalize if given as percentage e.g. 88 -> 0.88
    if confidence > 1.0:
        confidence = confidence / 100.0

    # 4. Low Confidence Threshold Check (< 0.60)
    if confidence < 0.60:
        return {
            "status": "low_confidence",
            "message": "The image is not clear enough for a reliable diagnosis.",
            "next_action": "Please upload a clear image of one affected leaf."
        }

    # 5. Store Report in Database
    report_id = str(uuid.uuid4())
    report = DiagnosisReport(
        id=report_id,
        farmer_id=farmer_id,
        farm_id=farm_id,
        field_id=field_id,
        image_url=f"/uploads/diagnosis/{report_id}.jpg",
        crop=res.get("crop", crop or "Crop"),
        disease=res.get("disease", "Leaf Condition"),
        scientific_name=res.get("scientific_name"),
        confidence=round(confidence, 2),
        severity=res.get("severity", "moderate"),
        evidence=res.get("evidence", []),
        organic_treatment=res.get("organic_treatment", []),
        chemical_treatment=res.get("chemical_treatment", []),
        dosage=res.get("dosage", []),
        prevention=res.get("prevention", []),
        spray_window=res.get("spray_window", "Early morning before 9 AM"),
        expected_recovery_days=int(res.get("expected_recovery_days", 14)),
        warnings=res.get("warnings", []),
        model="gemini-2.0-flash",
        model_version="1.0"
    )
    
    db.add(report)
    db.commit()
    db.refresh(report)

    # 6. Return Structured Response Matching Required Schema
    return {
        "report_id": report.id,
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
        "model_version": report.model_version
    }

@router.get("/reports/{farmer_id}")
async def get_farmer_diagnoses(farmer_id: str, db: Session = Depends(get_db)):
    """Retrieve diagnosis history for a farmer."""
    reports = db.query(DiagnosisReport).filter(DiagnosisReport.farmer_id == farmer_id).order_by(DiagnosisReport.created_at.desc()).all()
    return reports

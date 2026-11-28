"""Evidence & Answer Verification Layer for AgroGPT and Leaf Diagnosis.

Assigns one of the 6 canonical evidence statuses:
- Verified
- Partially verified
- Conflicting information
- Outdated
- Unverified
- Insufficient information

Never fabricates citations, source names, API responses, or dataset records.
"""
import time
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from ..database.models import DatasetRegistry, EvidenceVerificationLog
from .diagnosis_engine import crops_match

UNVERIFIED_FALLBACK_MESSAGES = {
    "en": "Agro AI could not verify this information with the available agricultural data. Please provide more details or consult a qualified agricultural expert.",
    "kn": "ಲಭ್ಯವಿರುವ ಕೃಷಿ ಮಾಹಿತಿಯೊಂದಿಗೆ ಈ ವಿವರವನ್ನು ಪರಿಶೀಲಿಸಲು Agro AI ಗೆ ಸಾಧ್ಯವಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಹೆಚ್ಚಿನ ವಿವರಗಳನ್ನು ನೀಡಿ ಅಥವಾ ಅರ್ಹ ಕೃಷಿ ತಜ್ಞರನ್ನು (KVK) ಸಂಪರ್ಕಿಸಿ.",
    "hi": "Agro AI उपलब्ध कृषि डेटा के साथ इस जानकारी को सत्यापित नहीं कर सका। कृपया अधिक विवरण प्रदान करें या किसी योग्य कृषि विशेषज्ञ (KVK) से परामर्श लें।",
}


def get_insufficient_evidence_message(language: str = "en") -> str:
    return UNVERIFIED_FALLBACK_MESSAGES.get(language, UNVERIFIED_FALLBACK_MESSAGES["en"])


def evaluate_evidence_bundle(
    db: Session,
    channel: str,
    crop: Optional[str] = None,
    subject: Optional[str] = None,
    retrieved_chunks: Optional[List[Dict[str, Any]]] = None,
    weather_api: Optional[Dict[str, Any]] = None,
    mandi_api: Optional[Dict[str, Any]] = None,
    requires_live_api: Optional[str] = None,  # 'weather' | 'mandi' | None
    has_model_answer: bool = True,
    request_id: Optional[str] = None,
    latency_ms: Optional[int] = None,
) -> Dict[str, Any]:
    """Cross-checks retrieved KB/dataset chunks + live API results and computes canonical `evidence_status`."""
    chunks = retrieved_chunks or []
    official_chunks = [c for c in chunks if c.get("is_official")]
    dataset_chunks = [c for c in chunks if not c.get("is_official")]
    stale_chunks = [c for c in chunks if c.get("is_stale")]

    api_count = 0
    api_fresh = False
    api_stale = False
    sources: List[Dict[str, Any]] = []
    conflicts: List[Dict[str, Any]] = []

    # 1. Inspect live API evidence
    if weather_api and weather_api.get("available"):
        api_count += 1
        st = weather_api.get("freshness_status", "FRESH")
        if st == "FRESH":
            api_fresh = True
        elif st in ("STALE", "DELAYED"):
            api_stale = True
        sources.append({
            "type": "live_api",
            "title": f"Live Weather ({weather_api.get('city')})",
            "publisher": weather_api.get("source", "Open-Meteo"),
            "publication_date": weather_api.get("source_timestamp"),
            "retrieved_at": weather_api.get("retrieved_at"),
            "freshness_status": st,
        })

    if mandi_api and mandi_api.get("available"):
        api_count += 1
        st = mandi_api.get("freshness_status", "UNAVAILABLE")
        if st == "FRESH":
            api_fresh = True
        elif st in ("STALE", "DELAYED"):
            api_stale = True
        sources.append({
            "type": "live_api",
            "title": "AGMARKNET / Mandi Price Registry",
            "publisher": "data.gov.in / Verified Mandi Registry",
            "publication_date": mandi_api.get("latest_reporting_date"),
            "retrieved_at": mandi_api.get("retrieved_at"),
            "freshness_status": st,
        })

    # 2. Inspect KB & Dataset chunks and check for recorded dataset-vs-official conflicts
    ds_ids = {c["dataset_id"] for c in dataset_chunks if c.get("dataset_id")}
    if ds_ids:
        ds_rows = db.query(DatasetRegistry).filter(DatasetRegistry.id.in_(list(ds_ids))).all()
        for d in ds_rows:
            for cf in (d.conflicts_detected or []):
                if not crop or not cf.get("crop") or crops_match(crop, cf.get("crop", "")):
                    conflicts.append({
                        "dataset_name": d.name,
                        "topic": cf.get("topic"),
                        "conflict_type": cf.get("conflict_type"),
                        "detail": cf.get("official_source") or cf.get("official_rule"),
                    })

    # Also detect direct divergence if both official and community dataset chunks exist with opposing cues
    if official_chunks and dataset_chunks:
        off_txt = " ".join(c["content"].lower() for c in official_chunks)
        ds_txt = " ".join(c["content"].lower() for c in dataset_chunks)
        if ("not recommended" in off_txt or "avoid" in off_txt) and ("recommended" in ds_txt):
            conflicts.append({
                "dataset_name": dataset_chunks[0].get("source_name"),
                "topic": crop or subject or "management",
                "conflict_type": "official_vs_uploaded_guidance",
                "detail": f"Official source ({official_chunks[0].get('publisher')}) includes restrictions not reflected in uploaded dataset ({dataset_chunks[0].get('source_name')}).",
            })

    for c in chunks[:5]:
        sources.append({
            "type": "official_kb" if c.get("is_official") else "approved_dataset",
            "title": c.get("title"),
            "publisher": c.get("publisher"),
            "source_url": c.get("source_url"),
            "publication_date": c.get("publication_date"),
            "is_stale": bool(c.get("is_stale")),
            "relevance_score": c.get("relevance_score"),
        })

    # 3. Determine exact canonical status
    if conflicts:
        status = "Conflicting information"
    elif requires_live_api == "mandi" and not (mandi_api and mandi_api.get("available")):
        status = "Insufficient information"
    elif requires_live_api == "weather" and not (weather_api and weather_api.get("available")):
        status = "Insufficient information"
    elif not has_model_answer and not chunks and api_count == 0:
        status = "Insufficient information"
    elif (chunks and len(stale_chunks) == len(chunks) and not api_fresh) or (api_stale and not official_chunks and not api_fresh):
        status = "Outdated"
    elif official_chunks or (requires_live_api and api_fresh):
        status = "Verified"
    elif dataset_chunks or api_count > 0:
        status = "Partially verified"
    elif has_model_answer:
        status = "Unverified"
    else:
        status = "Insufficient information"

    stale_total = len(stale_chunks) + (1 if api_stale else 0)
    try:
        db.add(EvidenceVerificationLog(
            id=str(uuid.uuid4()),
            channel=channel,
            request_id=request_id,
            crop=crop,
            subject=subject,
            evidence_status=status,
            chunks_retrieved=len(chunks),
            official_sources_count=len(official_chunks),
            dataset_sources_count=len(dataset_chunks),
            api_sources_count=api_count,
            conflict_count=len(conflicts),
            stale_count=stale_total,
            latency_ms=latency_ms,
        ))
        db.commit()
    except Exception:
        db.rollback()

    limitations: List[str] = []
    if status == "Conflicting information":
        limitations.append("Conflicting guidance was detected between an uploaded dataset and official agricultural rules; prioritize official ICAR/SAU/KVK guidance.")
    elif status == "Outdated":
        limitations.append("Available records or market/weather observations are older than the freshness window; verify current local conditions.")
    elif status == "Partially verified":
        limitations.append("Supported by an approved dataset or general context, without a matching official ICAR/SAU reference for every detail.")
    elif status == "Unverified":
        limitations.append("General AI agronomic guidance without a matching local dataset or official KB citation.")
    elif status == "Insufficient information":
        limitations.append(get_insufficient_evidence_message("en"))

    return {
        "evidence_status": status,
        "sources": sources,
        "conflicts": conflicts,
        "limitations": limitations,
        "counts": {
            "chunks_retrieved": len(chunks),
            "official_sources": len(official_chunks),
            "dataset_sources": len(dataset_chunks),
            "live_apis": api_count,
            "conflicts": len(conflicts),
            "stale": stale_total,
        },
    }

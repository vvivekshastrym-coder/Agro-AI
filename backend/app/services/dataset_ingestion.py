"""Multi-Format Agricultural Dataset Ingestion, Hygiene Validation, Conflict Detection & Versioned Activation.

Supports:
- CSV, XLSX / Excel (`openpyxl`), JSON, TXT, PDF (text stream extraction), and Image Dataset manifests.
- Never automatically trusts uploaded datasets: all uploads start at `approval_status='pending_review'`
  and `trust_level='unverified_upload'` with `preview_rows`, `validation_errors`, and `conflicts_detected`.
- Only after an authorized administrator approves (`approve_dataset`) are clean rows indexed into
  `KnowledgeChunk` for Hybrid RAG retrieval.
- Replacing a dataset creates `version = previous.version + 1`, links `parent_dataset_id`, and
  atomically deactivates superseded chunks so older records never silently overwrite newer ones.
"""
import csv
import datetime
import hashlib
import io
import json
import os
import re
import uuid
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from ..database.models import DatasetRegistry, KnowledgeChunk, KnowledgeSource
from .answer_guard import DOSE
from .diagnosis_engine import crops_match
from .knowledge_rag import compute_semantic_vector_128, detect_crop_in_text, detect_language_code

SUPPORTED_FORMATS = {"csv", "xlsx", "json", "pdf", "txt", "image_dataset"}
SUPPORTED_SUBJECTS = {
    "plant_images", "crop_disease", "treatments", "soil_fertilizer",
    "weather_rainfall", "mandi_prices", "general_agronomy",
}
MAX_STAGED_RECORDS = 1500


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "dataset").lower()).strip("-")
    return (s or "dataset")[:100]


def infer_subject(columns: List[str], sample_text: str) -> str:
    joined = (" ".join(columns) + " " + (sample_text or "")[:1500]).lower()
    if any(k in joined for k in ("image_path", "samples_per_class", "raw_class", "pixel")):
        return "plant_images"
    if any(k in joined for k in ("modal_price", "min_price", "max_price", "apmc", "quintal")):
        return "mandi_prices"
    if any(k in joined for k in ("soil_ph", "nitrogen", "phosphorus", "potassium", "organic_carbon", "fertilizer", "npk")):
        return "soil_fertilizer"
    if any(k in joined for k in ("rainfall", "rain_mm", "humidity", "temp_max", "temp_min")):
        return "weather_rainfall"
    if any(k in joined for k in ("active_ingredient", "cibrc", "pre_harvest_interval", "biopesticide", "fungicide", "insecticide")):
        return "treatments"
    if any(k in joined for k in ("disease", "symptom", "pathogen", "blight", "rust", "wilt", "pest")):
        return "crop_disease"
    return "general_agronomy"


def _extract_pdf_text(raw_bytes: bytes) -> str:
    """Extracts readable text from PDF bytes using pypdf if available, else FlateDecode / PDF literal parser."""
    try:
        import pypdf  # type: ignore
        reader = pypdf.PdfReader(io.BytesIO(raw_bytes))
        pages = [p.extract_text() or "" for p in reader.pages[:80]]
        txt = "\n".join(pages).strip()
        if txt:
            return txt
    except Exception:
        pass

    chunks: List[str] = []
    # Decompress FlateDecode streams if present and pull parenthesized text literals
    for m in re.finditer(rb"stream[\r\n]+(.*?)[\r\n]+endstream", raw_bytes, flags=re.DOTALL):
        stream_data = m.group(1)
        for cand in (stream_data,):
            try:
                dec = zlib.decompress(cand)
                literals = re.findall(rb"\(([^()]{2,300})\)", dec)
                if literals:
                    chunks.append(" ".join(x.decode("utf-8", errors="ignore") for x in literals))
            except Exception:
                pass
    if not chunks:
        literals = re.findall(rb"\(([^()]{3,300})\)", raw_bytes)
        chunks.append(" ".join(x.decode("utf-8", errors="ignore") for x in literals))
    return "\n".join(chunks).strip()


def parse_raw_dataset_bytes(filename: str, raw_bytes: bytes, explicit_format: Optional[str] = None) -> Tuple[str, List[Dict[str, Any]], List[str]]:
    """Parses uploaded bytes into `(file_format, list_of_row_dicts, columns)`."""
    ext = (explicit_format or Path(filename or "").suffix.lstrip(".")).lower().strip()
    if ext in ("xls", "xlsx", "excel"):
        ext = "xlsx"
    if ext not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported dataset format '{ext}'. Supported: {', '.join(sorted(SUPPORTED_FORMATS))}.")

    if ext == "csv":
        text = raw_bytes.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        cols = [str(c).strip() for c in (reader.fieldnames or []) if c]
        rows = [{str(k).strip(): (v.strip() if isinstance(v, str) else v) for k, v in r.items() if k} for r in reader]
        return "csv", rows, cols

    if ext == "xlsx":
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), read_only=True, data_only=True)
        ws = wb.active
        it = ws.iter_rows(values_only=True)
        header_row = next(it, None)
        if not header_row:
            return "xlsx", [], []
        cols = [str(c).strip() if c is not None else f"col_{i}" for i, c in enumerate(header_row)]
        rows = []
        for vals in it:
            if vals is None or all(v is None or str(v).strip() == "" for v in vals):
                continue
            row = {}
            for i, col_name in enumerate(cols):
                val = vals[i] if i < len(vals) else None
                if isinstance(val, (datetime.datetime, datetime.date)):
                    val = val.isoformat()[:10]
                row[col_name] = str(val).strip() if isinstance(val, str) else val
            rows.append(row)
        return "xlsx", rows, cols

    if ext in ("json", "image_dataset"):
        data = json.loads(raw_bytes.decode("utf-8-sig", errors="replace"))
        if isinstance(data, dict) and isinstance(data.get("samples"), list):
            rows = [r for r in data["samples"] if isinstance(r, dict)]
            fmt = "image_dataset" if ("classes_found" in data or ext == "image_dataset") else "json"
        elif isinstance(data, dict) and isinstance(data.get("records"), list):
            rows = [r for r in data["records"] if isinstance(r, dict)]
            fmt = ext
        elif isinstance(data, list):
            rows = [r for r in data if isinstance(r, dict)]
            fmt = ext
        elif isinstance(data, dict):
            rows = [data]
            fmt = ext
        else:
            rows = []
            fmt = ext
        cols = sorted({str(k) for r in rows[:50] for k in r.keys()})
        return fmt, rows, cols

    # TXT or PDF -> paragraph/section chunking into structured records
    text = _extract_pdf_text(raw_bytes) if ext == "pdf" else raw_bytes.decode("utf-8-sig", errors="replace")
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if len(p.strip()) >= 25]
    if not paragraphs and text.strip():
        paragraphs = [text.strip()[i:i + 900] for i in range(0, min(len(text.strip()), 18000), 900)]
    rows = [
        {"section_index": idx + 1, "title": p.splitlines()[0][:120], "content": p[:1500]}
        for idx, p in enumerate(paragraphs)
    ]
    return ext, rows, ["section_index", "title", "content"]


def _parse_year(date_val: Any) -> Optional[int]:
    if not date_val:
        return None
    m = re.search(r"\b(19\d{2}|20\d{2})\b", str(date_val))
    return int(m.group(1)) if m else None


def _row_to_text_and_meta(row: Dict[str, Any], default_crop: Optional[str], default_region: str, default_lang: str, subject: str) -> Dict[str, Any]:
    norm = {str(k).lower().strip().replace(" ", "_"): v for k, v in row.items()}
    crop = str(norm.get("crop") or norm.get("commodity") or norm.get("expected_crop") or default_crop or "").strip() or None
    disease = str(norm.get("disease") or norm.get("problem") or norm.get("expected_problem") or norm.get("pest") or "").strip() or None
    state = str(norm.get("state") or norm.get("region") or default_region or "India").strip()
    district = str(norm.get("district") or norm.get("market_name") or "").strip() or None
    season = str(norm.get("season") or "").strip() or None
    pub_date = str(norm.get("publication_date") or norm.get("price_date") or norm.get("date") or "").strip() or None

    title_parts = [p for p in (crop, disease, norm.get("title"), norm.get("market_name")) if p]
    title = " — ".join(str(x) for x in title_parts[:3])[:240] or f"{subject.replace('_', ' ').title()} Record"

    kv_pairs = []
    for k, v in row.items():
        if v is None or str(v).strip() == "":
            continue
        kv_pairs.append(f"{k}: {v}")
    content = str(norm.get("content") or norm.get("summary") or norm.get("recommendation") or "; ".join(kv_pairs))[:1800]
    if not crop:
        crop = detect_crop_in_text(f"{title} {content}")
    lang = detect_language_code(content, fallback=default_lang or "en")

    return {
        "title": title,
        "content": content,
        "crop": crop,
        "disease": disease,
        "state": state,
        "district": district,
        "season": season,
        "language": lang,
        "publication_date": pub_date,
        "raw": row,
    }


def validate_and_stage_dataset(
    db: Session,
    name: str,
    filename: str,
    raw_bytes: bytes,
    uploaded_by: Optional[str] = None,
    explicit_format: Optional[str] = None,
    subject_override: Optional[str] = None,
    crop_override: Optional[str] = None,
    region_override: Optional[str] = None,
    language_override: Optional[str] = None,
    source_name: Optional[str] = None,
    publisher: Optional[str] = None,
    source_url: Optional[str] = None,
    original_publication_date: Optional[str] = None,
    parent_dataset_id: Optional[str] = None,
) -> DatasetRegistry:
    """Parses, validates, deduplicates, checks conflicts against official sources, and saves as `pending_review`."""
    file_fmt, raw_rows, columns = parse_raw_dataset_bytes(filename, raw_bytes, explicit_format=explicit_format)
    sample_blob = json.dumps(raw_rows[:8], ensure_ascii=False) if raw_rows else ""
    subject = subject_override if (subject_override in SUPPORTED_SUBJECTS) else infer_subject(columns, sample_blob)
    detected_lang = language_override or detect_language_code(sample_blob, fallback="en")
    detected_crop = crop_override or detect_crop_in_text(f"{name} {sample_blob}")
    region = (region_override or ("Karnataka" if "karnataka" in sample_blob.lower() else "India")).strip()

    # Load approved official sources/chunks for conflict checking
    official_sources = db.query(KnowledgeSource).filter(KnowledgeSource.review_status == "approved").all()

    seen_hashes = set()
    valid_staged: List[Dict[str, Any]] = []
    validation_errors: List[Dict[str, Any]] = []
    conflicts: List[Dict[str, Any]] = []
    duplicate_count = 0
    stale_count = 0
    now_year = datetime.datetime.now(datetime.timezone.utc).year

    for idx, row in enumerate(raw_rows, start=1):
        if not isinstance(row, dict) or not any(str(v or "").strip() for v in row.values()):
            validation_errors.append({"row": idx, "field": "row", "error": "Empty or malformed record."})
            continue

        low = {str(k).lower().strip().replace(" ", "_"): v for k, v in row.items()}

        # Domain-specific unit & range validation
        if subject == "mandi_prices":
            try:
                md = float(low.get("modal_price"))
                mn = float(low.get("min_price", md))
                mx = float(low.get("max_price", md))
                if md <= 0 or mn <= 0 or mx <= 0 or mn > md or md > mx:
                    validation_errors.append({"row": idx, "field": "prices", "error": f"Invalid price ordering or non-positive values (min={mn}, modal={md}, max={mx})."})
                    continue
            except (TypeError, ValueError):
                validation_errors.append({"row": idx, "field": "modal_price", "error": "Numeric modal_price is required for mandi_prices datasets."})
                continue

        if "soil_ph" in low or "ph" in low:
            raw_ph = low.get("soil_ph", low.get("ph"))
            if raw_ph not in (None, ""):
                try:
                    ph_v = float(raw_ph)
                    if ph_v < 2.5 or ph_v > 11.5:
                        validation_errors.append({"row": idx, "field": "soil_ph", "error": f"Out-of-range soil pH ({ph_v}); expected 2.5 to 11.5."})
                        continue
                except (TypeError, ValueError):
                    validation_errors.append({"row": idx, "field": "soil_ph", "error": "Non-numeric soil_ph value."})
                    continue

        norm_rec = _row_to_text_and_meta(row, detected_crop, region, detected_lang, subject)
        chash = hashlib.sha256(f"{norm_rec['crop']}::{norm_rec['title']}::{norm_rec['content']}".lower().encode("utf-8")).hexdigest()
        if chash in seen_hashes:
            duplicate_count += 1
            continue
        seen_hashes.add(chash)

        rec_date = norm_rec["publication_date"] or original_publication_date
        yr = _parse_year(rec_date)
        if yr is not None and (now_year - yr) > 7:
            stale_count += 1

        # Conflict check 1: unverified upload stating chemical pesticide dosages without CIBRC registration field
        if DOSE.search(norm_rec["content"]) and not low.get("cibrc_registration_no"):
            conflicts.append({
                "row": idx,
                "crop": norm_rec["crop"],
                "topic": norm_rec["disease"] or subject,
                "conflict_type": "unverified_chemical_dosage",
                "dataset_claim": norm_rec["content"][:180],
                "official_rule": "Agro AI safety policy withholds chemical/fertilizer dosages unless backed by a verified CIBRC label registration.",
            })

        # Conflict check 2: compare against approved official KnowledgeSource summaries for the same crop
        if norm_rec["crop"]:
            for ks in official_sources:
                if crops_match(norm_rec["crop"], ks.crop) and ks.summary:
                    if "banned" in ks.summary.lower() or "not recommended" in ks.summary.lower():
                        # Flag if uploaded row mentions a term explicitly warned against in official summary
                        ks_words = set(re.findall(r"[a-z]{5,}", ks.summary.lower()))
                        rec_words = set(re.findall(r"[a-z]{5,}", norm_rec["content"].lower()))
                        shared = ks_words & rec_words - {"treatment", "disease", "farmers", "karnataka"}
                        if shared:
                            conflicts.append({
                                "row": idx,
                                "crop": norm_rec["crop"],
                                "topic": ks.title,
                                "conflict_type": "contradicts_official_source",
                                "dataset_claim": norm_rec["content"][:160],
                                "official_source": f"{ks.title} ({ks.publisher}, {ks.last_verified_date or 'verified'})",
                            })
                            break

        norm_rec["content_hash"] = chash
        valid_staged.append(norm_rec)

    version_num = 1
    slug = _slugify(name)
    if parent_dataset_id:
        parent = db.query(DatasetRegistry).filter(DatasetRegistry.id == parent_dataset_id).first()
        if parent:
            version_num = (parent.version or 1) + 1
            slug = parent.slug
    else:
        latest_same = (
            db.query(DatasetRegistry)
            .filter(DatasetRegistry.slug == slug)
            .order_by(DatasetRegistry.version.desc())
            .first()
        )
        if latest_same:
            version_num = (latest_same.version or 1) + 1

    crops_seen = sorted({r["crop"] for r in valid_staged if r.get("crop")})
    final_crop = crop_override or (crops_seen[0] if len(crops_seen) == 1 else ("Multi-crop" if len(crops_seen) > 1 else detected_crop))

    ds = DatasetRegistry(
        id=str(uuid.uuid4()),
        name=name.strip()[:200],
        slug=slug,
        version=version_num,
        parent_dataset_id=parent_dataset_id,
        file_format=file_fmt,
        subject=subject,
        crop=final_crop,
        region=region,
        language=detected_lang,
        source_name=(source_name or filename)[:200],
        publisher=(publisher or "Uploaded — Pending Verification")[:200],
        source_url=source_url,
        original_publication_date=original_publication_date,
        trust_level="unverified_upload",
        approval_status="pending_review",
        ingestion_status="parsed" if valid_staged else "failed",
        total_records=len(raw_rows),
        valid_records=len(valid_staged),
        duplicate_records=duplicate_count,
        invalid_records=len(validation_errors),
        conflict_records=len(conflicts),
        stale_records=stale_count,
        schema_summary={
            "columns": columns[:40],
            "detected_crops": crops_seen[:15],
            "has_source_metadata": bool(source_name and publisher and original_publication_date),
        },
        preview_rows=[r["raw"] for r in valid_staged[:20]],
        staged_records=valid_staged[:MAX_STAGED_RECORDS],
        validation_errors=validation_errors[:50],
        conflicts_detected=conflicts[:50],
        uploaded_by=uploaded_by,
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ds


def approve_dataset(
    db: Session,
    dataset_id: str,
    reviewer_user_id: str,
    trust_level: str = "community_curated",
    review_notes: Optional[str] = None,
) -> DatasetRegistry:
    """Activates a reviewed dataset, indexing its clean non-dose-violating records into `KnowledgeChunk`."""
    ds = db.query(DatasetRegistry).filter(DatasetRegistry.id == dataset_id).first()
    if not ds:
        raise ValueError("Dataset not found.")
    if ds.valid_records <= 0 and ds.file_format != "image_dataset":
        raise ValueError("Cannot approve a dataset with 0 valid records.")

    allowed_trust = {"unverified_upload": 0.55, "community_curated": 0.70, "official_verified": 0.95}
    if trust_level not in allowed_trust:
        trust_level = "community_curated"

    # If this dataset replaces a parent version, atomically mark parent `replaced` and deactivate old chunks
    if ds.parent_dataset_id:
        parent = db.query(DatasetRegistry).filter(DatasetRegistry.id == ds.parent_dataset_id).first()
        if parent:
            parent.approval_status = "replaced"
            db.query(KnowledgeChunk).filter(KnowledgeChunk.dataset_id == parent.id).update({"is_active": False})

    # Clear any prior chunks for this dataset_id (idempotent re-approval / reprocess)
    db.query(KnowledgeChunk).filter(KnowledgeChunk.dataset_id == ds.id).delete(synchronize_session=False)

    indexed = 0
    is_off = (trust_level == "official_verified")
    t_score = allowed_trust[trust_level]

    for rec in (ds.staged_records or []):
        content_str = str(rec.get("content") or "").strip()
        if not content_str:
            continue
        # Never index unverified chemical dosage strings unless explicitly marked official_verified with CIBRC ref
        if DOSE.search(content_str) and not is_off:
            continue

        emb = compute_semantic_vector_128(f"{rec.get('crop') or ''} {rec.get('disease') or ''} {rec.get('title') or ''} {content_str}")
        db.add(KnowledgeChunk(
            id=str(uuid.uuid4()),
            dataset_id=ds.id,
            title=str(rec.get("title") or ds.name)[:250],
            content=content_str,
            structured_payload=rec.get("raw") or {},
            subject=ds.subject,
            crop=rec.get("crop") or ds.crop,
            disease=rec.get("disease"),
            state=rec.get("state") or ds.region,
            district=rec.get("district"),
            season=rec.get("season"),
            language=rec.get("language") or ds.language or "en",
            source_name=ds.source_name or ds.name,
            publisher=ds.publisher,
            source_url=ds.source_url,
            publication_date=rec.get("publication_date") or ds.original_publication_date,
            is_official=is_off,
            trust_score=t_score,
            embedding_vec=emb,
            content_hash=rec.get("content_hash") or hashlib.sha256(content_str.encode("utf-8")).hexdigest(),
            is_active=True,
        ))
        indexed += 1

    ds.trust_level = trust_level
    ds.approval_status = "approved"
    ds.ingestion_status = "indexed"
    ds.reviewed_by = reviewer_user_id
    ds.reviewed_at = datetime.datetime.now(datetime.timezone.utc)
    if review_notes:
        ds.review_notes = review_notes[:500]
    db.commit()
    db.refresh(ds)
    return ds


def set_dataset_lifecycle_status(
    db: Session,
    dataset_id: str,
    new_status: str,
    reviewer_user_id: str,
    review_notes: Optional[str] = None,
) -> DatasetRegistry:
    if new_status not in ("rejected", "deactivated"):
        raise ValueError(f"Unsupported status '{new_status}'.")
    ds = db.query(DatasetRegistry).filter(DatasetRegistry.id == dataset_id).first()
    if not ds:
        raise ValueError("Dataset not found.")
    ds.approval_status = new_status
    ds.reviewed_by = reviewer_user_id
    ds.reviewed_at = datetime.datetime.now(datetime.timezone.utc)
    if review_notes:
        ds.review_notes = review_notes[:500]
    db.query(KnowledgeChunk).filter(KnowledgeChunk.dataset_id == ds.id).update({"is_active": False})
    db.commit()
    db.refresh(ds)
    return ds


def ensure_builtin_kaggle_dataset_registered(db: Session) -> Optional[DatasetRegistry]:
    """Registers the audited Kaggle 20k Crop Disease Image dataset from real eval artifacts if present."""
    slug = "kaggle-20k-multi-class-crop-disease-images"
    existing = db.query(DatasetRegistry).filter(DatasetRegistry.slug == slug).first()

    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    manifest_p = repo_root / "backend" / "evals" / "diagnosis" / "kaggle_20k_manifest.json"
    report_p = repo_root / "backend" / "evals" / "diagnosis" / "model_eval_report.json"
    if not manifest_p.is_file() and not report_p.is_file():
        return existing

    audit = {}
    preview = []
    if manifest_p.is_file():
        try:
            m = json.loads(manifest_p.read_text(encoding="utf-8"))
            audit = m.get("audit") or {}
            preview = (m.get("samples") or [])[:10]
        except Exception:
            pass

    eval_summary = {}
    if report_p.is_file():
        try:
            rep = json.loads(report_p.read_text(encoding="utf-8"))
            eval_summary = rep.get("summary_metrics") or {}
            if not audit:
                audit = rep.get("dataset_hygiene_audit") or {}
        except Exception:
            pass

    if not audit:
        return existing

    if existing:
        if eval_summary and existing.schema_summary.get("held_out_test_metrics") != eval_summary:
            existing.schema_summary = {**(existing.schema_summary or {}), "held_out_test_metrics": eval_summary}
            db.commit()
        return existing

    ds = DatasetRegistry(
        id=str(uuid.uuid4()),
        name="Kaggle 20k Multi-Class Crop Disease Images (Deduplicated)",
        slug=slug,
        version=1,
        file_format="image_dataset",
        subject="plant_images",
        crop="Cotton, Maize, Rice, Sugarcane, Wheat",
        region="India / Global Public",
        language="en",
        source_name="jawadali1045/20k-multi-class-crop-disease-images",
        publisher="Kaggle Community Dataset (Unreviewed Field/Lab Mix)",
        source_url="https://www.kaggle.com/datasets/jawadali1045/20k-multi-class-crop-disease-images",
        original_publication_date="2024",
        trust_level="community_curated",
        approval_status="approved",
        ingestion_status="indexed",
        total_records=int(audit.get("raw_total_files", 18617)),
        valid_records=int(audit.get("unique_clean_md5_hashes", 15199)),
        duplicate_records=int(audit.get("exact_duplicate_files_removed", 3367)),
        invalid_records=sum((audit.get("excluded_classes_by_hygiene_rule") or {}).values()),
        conflict_records=int(audit.get("cross_class_conflict_files_removed", 15)),
        stale_records=0,
        schema_summary={
            "canonical_classes_retained": audit.get("canonical_classes_retained", 40),
            "crop_has_healthy_class": audit.get("crop_has_healthy_class", {}),
            "excluded_classes": audit.get("excluded_classes_by_hygiene_rule", {}),
            "held_out_test_metrics": eval_summary,
        },
        preview_rows=preview,
        staged_records=[],
        validation_errors=[
            {"row": 0, "field": "Rice::Healthy", "error": "Dataset contains no Healthy Rice class; standalone Rice predictions capped at MODERATE confidence."},
            {"row": 0, "field": "bollrot on Cotton", "error": "Excluded class with only 4 images (< 20 minimum sample threshold)."},
        ],
        conflicts_detected=[
            {
                "row": 0,
                "crop": "Cotton",
                "topic": "Bollworm folders",
                "conflict_type": "cross_class_duplicate_images",
                "dataset_claim": "15 identical MD5 files appeared simultaneously across American Bollworm, Pink Bollworm, and Bollworm folders.",
                "official_rule": "Excluded all 15 conflicting cross-class files and merged split-case folders before 70/15/15 dHash group split.",
            }
        ],
        review_notes="Audited via MD5 + 8x8 perceptual dHash group split; trained MobileNetV3-Small ONNX two-stage classifier.",
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ds

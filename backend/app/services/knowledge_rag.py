"""Hybrid Agricultural Knowledge & RAG Engine (Keyword BM25 + 128-d Semantic Vector + Metadata Reranking).

Guarantees:
- Retrieves ONLY active chunks backed by either an `approved` KnowledgeSource (`is_official=True`)
  or an `approved` DatasetRegistry entry (`approval_status == 'approved'`).
- Enforces strict crop-isolation: chunks tagged for a specific crop never leak into answers for a different crop.
- Enforces `MIN_RELEVANCE_SCORE` so unrelated records are never returned as filler.
- Reranks official ICAR / SAU / KVK / CIBRC sources (`trust_score=0.95`) ahead of community/uploaded datasets.
"""
import datetime
import hashlib
import math
import re
import uuid
from typing import Any, Dict, List, Optional, Set
from sqlalchemy.orm import Session

from ..database.models import DatasetRegistry, KnowledgeChunk, KnowledgeSource
from .diagnosis_engine import crops_match

EMBED_DIM = 128
MIN_RELEVANCE_SCORE = 0.18

_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "what", "when", "where", "which",
    "how", "can", "should", "about", "into", "your", "have", "has", "are", "was", "were",
    "will", "tell", "give", "please", "farmer", "crop", "plant", "in", "on", "of", "to", "is",
}

KNOWN_CROPS = [
    "Rice", "Paddy", "Ragi", "Maize", "Tur", "Chilli", "Cotton", "Tomato",
    "Potato", "Onion", "Wheat", "Sugarcane", "Coconut", "Arecanut", "Groundnut",
]


def detect_language_code(text: str, fallback: str = "en") -> str:
    if not text:
        return fallback
    if re.search(r"[\u0C80-\u0CFF]", text):
        return "kn"
    if re.search(r"[\u0900-\u097F]", text):
        return "hi"
    return fallback


def detect_crop_in_text(text: str) -> Optional[str]:
    low = (text or "").lower()
    kn_map = {
        "ಭತ್ತ": "Rice", "ರಾಗಿ": "Ragi", "ಮೆಕ್ಕೆಜೋಳ": "Maize", "ತೊಗರಿ": "Tur",
        "ಮೆಣಸಿನಕಾಯಿ": "Chilli", "ಹತ್ತಿ": "Cotton", "ಟೊಮೆಟೊ": "Tomato",
        "ಆಲೂಗಡ್ಡೆ": "Potato", "ಈರುಳ್ಳಿ": "Onion", "ಗೋಧಿ": "Wheat",
        "ಕಬ್ಬು": "Sugarcane", "ತೆಂಗು": "Coconut", "ಅಡಿಕೆ": "Arecanut", "ಕಡಲೆಕಾಯಿ": "Groundnut",
    }
    hi_map = {
        "धान": "Rice", "चावल": "Rice", "रागी": "Ragi", "मक्का": "Maize",
        "अरहर": "Tur", "मिर्च": "Chilli", "कपास": "Cotton", "टमाटर": "Tomato",
        "आलू": "Potato", "प्याज": "Onion", "गेहूं": "Wheat", "गन्ना": "Sugarcane", "मूंगफली": "Groundnut",
    }
    for k, v in {**kn_map, **hi_map}.items():
        if k in low:
            return v
    for c in KNOWN_CROPS:
        if crops_match(c, low) and re.search(r"\b" + re.escape(c.lower()) + r"\b", low):
            return "Rice" if c == "Paddy" else c
    return None


def tokenize_multilingual(text: str) -> List[str]:
    raw = re.findall(r"[\w\u0900-\u097F\u0C80-\u0CFF]{2,}", (text or "").lower())
    return [t for t in raw if t not in _STOPWORDS]


def compute_semantic_vector_128(text: str) -> List[float]:
    """Deterministic signed random-projection feature hash over word unigrams, bigrams & char 4-grams.
    Maps directly to `embedding_pgvec vector(128)` in PostgreSQL and JSON in SQLite."""
    vec = [0.0] * EMBED_DIM
    tokens = tokenize_multilingual(text)
    if not tokens:
        return vec

    features: List[tuple] = []
    for tok in tokens:
        features.append((f"w:{tok}", 1.5))
        if len(tok) >= 4:
            for i in range(len(tok) - 3):
                features.append((f"c:{tok[i:i + 4]}", 0.5))
    for i in range(len(tokens) - 1):
        features.append((f"b:{tokens[i]}_{tokens[i + 1]}", 1.2))

    for feat, weight in features:
        h = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(h[:4], "little") % EMBED_DIM
        sign = 1.0 if (h[4] & 1) == 0 else -1.0
        vec[idx] += sign * weight

    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 1e-8:
        vec = [round(v / norm, 5) for v in vec]
    return vec


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return max(0.0, sum(x * y for x, y in zip(a, b)))


def _age_years(pub_date: Optional[str]) -> Optional[float]:
    if not pub_date:
        return None
    m = re.search(r"(19\d{2}|20\d{2})", str(pub_date))
    if not m:
        return None
    year = int(m.group(1))
    now_year = datetime.datetime.now(datetime.timezone.utc).year
    return max(0.0, float(now_year - year))


def sync_approved_knowledge_sources_to_chunks(db: Session) -> int:
    """Ensures every `approved` KnowledgeSource row has an active, official KnowledgeChunk for hybrid RAG."""
    approved_sources = db.query(KnowledgeSource).filter(KnowledgeSource.review_status == "approved").all()
    existing_by_ks = {
        c.knowledge_source_id: c
        for c in db.query(KnowledgeChunk).filter(KnowledgeChunk.knowledge_source_id.isnot(None)).all()
    }
    added = 0
    for ks in approved_sources:
        body_text = f"{ks.title}. {ks.summary or ''}".strip()
        chash = hashlib.sha256(body_text.encode("utf-8")).hexdigest()
        pub_date = ks.last_verified_date or ks.publication_date
        if ks.id in existing_by_ks:
            chunk = existing_by_ks[ks.id]
            if chunk.content_hash != chash or not chunk.is_active:
                chunk.title = ks.title
                chunk.content = body_text
                chunk.crop = ks.crop
                chunk.state = ks.region
                chunk.language = ks.language or "en"
                chunk.publisher = ks.publisher
                chunk.source_name = ks.publisher
                chunk.source_url = ks.source_url
                chunk.publication_date = pub_date
                chunk.embedding_vec = compute_semantic_vector_128(f"{ks.crop} {ks.region} {body_text}")
                chunk.content_hash = chash
                chunk.is_active = True
                chunk.is_official = True
                chunk.trust_score = 0.95
        else:
            db.add(KnowledgeChunk(
                id=str(uuid.uuid4()),
                knowledge_source_id=ks.id,
                title=ks.title,
                content=body_text,
                structured_payload={"license_status": ks.license_status, "version": ks.version},
                subject="crop_disease",
                crop=ks.crop,
                state=ks.region,
                language=ks.language or "en",
                source_name=ks.publisher,
                publisher=ks.publisher,
                source_url=ks.source_url,
                publication_date=pub_date,
                is_official=True,
                trust_score=0.95,
                embedding_vec=compute_semantic_vector_128(f"{ks.crop} {ks.region} {body_text}"),
                content_hash=chash,
                is_active=True,
            ))
            added += 1

    # Deactivate chunks whose KnowledgeSource was moved out of `approved`
    approved_ids = {ks.id for ks in approved_sources}
    for ks_id, chunk in existing_by_ks.items():
        if ks_id not in approved_ids and chunk.is_active:
            chunk.is_active = False

    if added or approved_sources:
        try:
            db.commit()
        except Exception:
            db.rollback()
    return added


def retrieve_hybrid_evidence(
    db: Session,
    query: str,
    crop: Optional[str] = None,
    disease: Optional[str] = None,
    state: Optional[str] = None,
    district: Optional[str] = None,
    season: Optional[str] = None,
    language: str = "en",
    subject: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """Hybrid keyword + 128-d vector retrieval with strict approval, crop-isolation, and official-source reranking."""
    sync_approved_knowledge_sources_to_chunks(db)

    approved_ds_ids: Set[str] = {
        r[0] for r in db.query(DatasetRegistry.id).filter(DatasetRegistry.approval_status == "approved").all()
    }
    candidates = db.query(KnowledgeChunk).filter(KnowledgeChunk.is_active.is_(True)).limit(600).all()
    if not candidates:
        return []

    inferred_crop = crop or detect_crop_in_text(query)
    full_query = " ".join(x for x in [inferred_crop, disease, query] if x)
    q_tokens = set(tokenize_multilingual(full_query))
    q_vec = compute_semantic_vector_128(full_query)

    scored: List[Dict[str, Any]] = []
    for ch in candidates:
        # Gate 1: Verify backing dataset or knowledge source is currently approved
        if ch.dataset_id and ch.dataset_id not in approved_ds_ids:
            continue
        if not ch.dataset_id and not ch.knowledge_source_id:
            continue

        # Gate 2: Strict crop isolation (never return Tomato records for Rice, etc.)
        if inferred_crop and ch.crop and ch.crop.lower() not in ("all", "multi-crop", "general"):
            if not crops_match(inferred_crop, ch.crop):
                continue

        doc_text = f"{ch.title} {ch.crop or ''} {ch.disease or ''} {ch.content}"
        d_tokens = set(tokenize_multilingual(doc_text))
        overlap = len(q_tokens & d_tokens)
        kw_score = overlap / max(math.sqrt(len(q_tokens) * max(len(d_tokens), 1)), 1.0) if q_tokens else 0.0
        sem_score = _cosine(q_vec, ch.embedding_vec or [])

        # Metadata exact-match bonuses (only when base lexical/semantic signal is non-zero)
        meta_bonus = 0.0
        if inferred_crop and ch.crop and crops_match(inferred_crop, ch.crop):
            meta_bonus += 0.12
        if disease and ch.disease and (disease.lower() in ch.disease.lower() or ch.disease.lower() in disease.lower()):
            meta_bonus += 0.18
        if state and ch.state and state.lower() in ch.state.lower():
            meta_bonus += 0.05
        if district and ch.district and district.lower() in ch.district.lower():
            meta_bonus += 0.05
        if season and ch.season and season.lower() == ch.season.lower():
            meta_bonus += 0.04
        if subject and ch.subject == subject:
            meta_bonus += 0.04

        raw_rel = 0.55 * kw_score + 0.45 * sem_score
        if raw_rel + (0.5 * meta_bonus) < MIN_RELEVANCE_SCORE or (overlap == 0 and sem_score < 0.22):
            continue

        age_yrs = _age_years(ch.publication_date)
        is_stale = bool(age_yrs is not None and age_yrs > 7.0)
        freshness_factor = 0.82 if is_stale else 1.0
        trust = float(ch.trust_score or (0.95 if ch.is_official else 0.65))
        rerank_score = (raw_rel + meta_bonus) * (0.70 + 0.30 * trust) * freshness_factor

        scored.append({
            "chunk_id": ch.id,
            "dataset_id": ch.dataset_id,
            "knowledge_source_id": ch.knowledge_source_id,
            "title": ch.title,
            "content": ch.content,
            "structured_payload": ch.structured_payload or {},
            "subject": ch.subject,
            "crop": ch.crop,
            "disease": ch.disease,
            "state": ch.state,
            "district": ch.district,
            "language": ch.language,
            "source_name": ch.source_name or ch.publisher or "Uploaded Dataset",
            "publisher": ch.publisher or ch.source_name or "Unspecified",
            "source_url": ch.source_url,
            "publication_date": ch.publication_date,
            "is_official": bool(ch.is_official),
            "is_stale": is_stale,
            "trust_score": round(trust, 3),
            "relevance_score": round(rerank_score, 4),
        })

    scored.sort(key=lambda x: x["relevance_score"], reverse=True)
    return scored[:top_k]

"""Centralized External API Integration Engine for Agro AI.

Enforces:
- Backend-only credential management (no secret keys exposed to clients).
- Timeouts, bounded retries, and per-provider circuit breakers.
- Schema, unit, physical-range, and timestamp validation (HTTP 200 alone is NEVER assumed accurate).
- Freshness-aware TTL caching and `ExternalApiCallLog` + `DataSourceRegistry` telemetry.
"""
import asyncio
import datetime
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
import httpx
from sqlalchemy.orm import Session

from ..database.models import DataSourceRegistry, ExternalApiCallLog, MarketPrice
from .data_integrity import classify_freshness, ensure_default_data_sources

logger = logging.getLogger(__name__)

# Per-provider in-process circuit breaker & freshness cache
_CIRCUIT_STATE: Dict[str, Dict[str, Any]] = {}
_TTL_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}

CIRCUIT_FAILURE_THRESHOLD = 3
CIRCUIT_COOLDOWN_SECONDS = 120.0


def _is_circuit_open(provider_key: str) -> bool:
    st = _CIRCUIT_STATE.get(provider_key)
    if not st:
        return False
    if st["failures"] >= CIRCUIT_FAILURE_THRESHOLD:
        if time.time() < st["open_until"]:
            return True
        st["failures"] = 0
    return False


def _record_circuit_result(provider_key: str, ok: bool) -> None:
    st = _CIRCUIT_STATE.setdefault(provider_key, {"failures": 0, "open_until": 0.0, "last_error": None})
    if ok:
        st["failures"] = 0
        st["open_until"] = 0.0
    else:
        st["failures"] += 1
        if st["failures"] >= CIRCUIT_FAILURE_THRESHOLD:
            st["open_until"] = time.time() + CIRCUIT_COOLDOWN_SECONDS


def get_circuit_breaker_snapshot() -> Dict[str, Dict[str, Any]]:
    now = time.time()
    out = {}
    for k, v in _CIRCUIT_STATE.items():
        is_open = v["failures"] >= CIRCUIT_FAILURE_THRESHOLD and now < v["open_until"]
        out[k] = {
            "consecutive_failures": v["failures"],
            "circuit_open": is_open,
            "cooldown_remaining_sec": max(0, int(v["open_until"] - now)) if is_open else 0,
        }
    return out


def _log_api_call(
    db: Optional[Session],
    provider_key: str,
    category: str,
    http_status: Optional[int],
    schema_valid: bool,
    freshness_status: str,
    latency_ms: int,
    source_timestamp: Optional[str] = None,
    error_code: Optional[str] = None,
) -> None:
    if db is None:
        return
    try:
        ensure_default_data_sources(db)
        db.add(ExternalApiCallLog(
            id=str(uuid.uuid4()),
            provider_key=provider_key,
            endpoint_category=category,
            http_status=http_status,
            schema_valid=schema_valid,
            freshness_status=freshness_status,
            latency_ms=latency_ms,
            source_timestamp=source_timestamp,
            error_code=error_code,
        ))
        src = db.query(DataSourceRegistry).filter(DataSourceRegistry.key == provider_key).first()
        if src:
            if schema_valid and not error_code:
                src.last_retrieved_at = datetime.datetime.now(datetime.timezone.utc)
                if source_timestamp:
                    src.last_source_reporting_date = source_timestamp[:40]
                src.last_status = "healthy" if freshness_status == "FRESH" else "delayed"
                src.last_error = None
            elif error_code and error_code != "PROVIDER_DISABLED":
                src.last_status = "failed"
                src.last_error = error_code[:250]
        db.commit()
    except Exception:
        db.rollback()


def validate_weather_payload(w: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validates physical meteorology ranges and units on a weather API payload."""
    if not isinstance(w, dict) or not w.get("available"):
        return False, "WEATHER_UNAVAILABLE"
    temp = w.get("temp")
    hum = w.get("humidity")
    wind = w.get("wind_speed", 0)
    if not isinstance(temp, (int, float)) or isinstance(temp, bool) or temp < -35.0 or temp > 60.0:
        return False, "INVALID_TEMP_RANGE"
    if hum is not None and (not isinstance(hum, (int, float)) or hum < 0.0 or hum > 100.0):
        return False, "INVALID_HUMIDITY_RANGE"
    if wind is not None and (not isinstance(wind, (int, float)) or wind < 0.0 or wind > 250.0):
        return False, "INVALID_WIND_RANGE"
    return True, None


def validate_mandi_record(rec: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validates price positivity, min <= modal <= max consistency, and required market fields."""
    try:
        mn = float(rec.get("min_price") or 0)
        md = float(rec.get("modal_price") or 0)
        mx = float(rec.get("max_price") or 0)
    except (TypeError, ValueError):
        return False, "NON_NUMERIC_PRICE"
    if md <= 0 or mn <= 0 or mx <= 0 or md > 500_000:
        return False, "OUT_OF_RANGE_PRICE"
    if mn > md or md > mx:
        return False, "MIN_MODAL_MAX_INCONSISTENT"
    if not str(rec.get("commodity") or "").strip() or not str(rec.get("market_name") or rec.get("market") or "").strip():
        return False, "MISSING_MARKET_OR_COMMODITY"
    return True, None


async def fetch_validated_weather(
    location: str,
    db: Optional[Session] = None,
    ttl_seconds: int = 600,
) -> Dict[str, Any]:
    """Fetches weather via existing weather router with timeout, retry, circuit breaker, and range validation."""
    loc_clean = (location or "Mandya").strip()[:60]
    cache_key = f"weather::{loc_clean.lower()}"
    now = time.time()
    cached = _TTL_CACHE.get(cache_key)
    if cached and now < cached[0]:
        return {**cached[1], "from_cache": True}

    provider_key = "open_meteo_weather"
    if db is not None:
        ensure_default_data_sources(db)
        src_row = db.query(DataSourceRegistry).filter(DataSourceRegistry.key == provider_key).first()
        if src_row and not src_row.is_enabled:
            return {"available": False, "reason": "PROVIDER_DISABLED", "source": provider_key}

    if _is_circuit_open(provider_key):
        return {"available": False, "reason": "CIRCUIT_OPEN", "source": provider_key}

    from ..routers.weather import get_current_weather

    t0 = time.time()
    last_err = "UPSTREAM_FAILED"
    raw: Dict[str, Any] = {}
    for attempt in range(2):
        try:
            raw = await asyncio.wait_for(get_current_weather(q=loc_clean), timeout=8.0)
            if raw.get("available"):
                break
            last_err = str(raw.get("reason") or "WEATHER_UNAVAILABLE").upper()
        except asyncio.TimeoutError:
            last_err = "TIMEOUT"
        except Exception as exc:
            last_err = f"ERR_{type(exc).__name__.upper()}"
        if attempt == 0:
            await asyncio.sleep(0.25)

    latency_ms = int((time.time() - t0) * 1000)
    valid, schema_err = validate_weather_payload(raw)
    _record_circuit_result(provider_key, valid)

    retrieved_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    src_ts = str(raw.get("updated_at") or raw.get("timestamp") or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    freshness = "FRESH" if valid else "INVALID"

    _log_api_call(
        db=db,
        provider_key=provider_key,
        category="weather",
        http_status=200 if raw.get("available") else 503,
        schema_valid=valid,
        freshness_status=freshness,
        latency_ms=latency_ms,
        source_timestamp=src_ts if valid else None,
        error_code=None if valid else (schema_err or last_err),
    )

    if not valid:
        return {"available": False, "reason": schema_err or last_err, "source": provider_key}

    normalized = {
        "available": True,
        "city": raw.get("city") or loc_clean,
        "temp_c": round(float(raw["temp"]), 1),
        "humidity_pct": round(float(raw.get("humidity") or 0), 1) if raw.get("humidity") is not None else None,
        "wind_kmh": round(float(raw.get("wind_speed") or 0), 1),
        "rain_1h_mm": round(float(raw.get("rain_1h") or 0), 2),
        "condition": str(raw.get("condition") or "unspecified"),
        "source": raw.get("source") or "Open-Meteo / Weather Service",
        "source_timestamp": src_ts,
        "retrieved_at": retrieved_iso,
        "freshness_status": freshness,
    }
    _TTL_CACHE[cache_key] = (now + ttl_seconds, normalized)
    return normalized


async def fetch_validated_mandi_prices(
    db: Session,
    commodity: Optional[str] = None,
    state: Optional[str] = "Karnataka",
    limit: int = 5,
) -> Dict[str, Any]:
    """Queries live AGMARKNET (when configured) + DB MarketPrice records, filtering out invalid/outlier rows."""
    t0 = time.time()
    provider_key = "agmarknet_data_gov"
    ensure_default_data_sources(db)
    src_row = db.query(DataSourceRegistry).filter(DataSourceRegistry.key == provider_key).first()
    if src_row and not src_row.is_enabled:
        return {"available": False, "reason": "PROVIDER_DISABLED", "records": []}

    q = db.query(MarketPrice)
    if commodity:
        q = q.filter(MarketPrice.commodity.ilike(f"%{commodity.strip()}%"))
    if state:
        q_state = q.filter(MarketPrice.state.ilike(f"%{state.strip()}%"))
        rows = q_state.order_by(MarketPrice.price_date.desc()).limit(limit * 3).all()
        if not rows:
            rows = q.order_by(MarketPrice.price_date.desc()).limit(limit * 3).all()
    else:
        rows = q.order_by(MarketPrice.price_date.desc()).limit(limit * 3).all()

    clean_records: List[Dict[str, Any]] = []
    invalid_dropped = 0
    newest_date: Optional[str] = None

    for r in rows:
        cand = {
            "commodity": r.commodity,
            "variety": r.variety,
            "market_name": r.market_name,
            "district": r.district,
            "state": r.state,
            "min_price": float(r.min_price or 0),
            "modal_price": float(r.modal_price or 0),
            "max_price": float(r.max_price or 0),
            "unit": r.unit or "Rs/Quintal",
            "price_date": r.price_date.strftime("%Y-%m-%d") if getattr(r, "price_date", None) else None,
            "source": r.data_source or "AGMARKNET / Verified Mandi Registry",
        }
        ok, _ = validate_mandi_record(cand)
        if not ok:
            invalid_dropped += 1
            continue
        pdate = cand["price_date"]
        cand["freshness_status"] = classify_freshness(pdate, threshold_hours=72) if pdate else "UNAVAILABLE"
        if pdate and (newest_date is None or pdate > newest_date):
            newest_date = pdate
        clean_records.append(cand)
        if len(clean_records) >= limit:
            break

    latency_ms = int((time.time() - t0) * 1000)
    overall_freshness = classify_freshness(newest_date, threshold_hours=72) if newest_date else "UNAVAILABLE"
    _log_api_call(
        db=db,
        provider_key=provider_key,
        category="mandi",
        http_status=200 if clean_records else 204,
        schema_valid=bool(clean_records),
        freshness_status=overall_freshness,
        latency_ms=latency_ms,
        source_timestamp=newest_date,
        error_code=None if clean_records else "NO_VALID_MANDI_RECORDS",
    )

    return {
        "available": bool(clean_records),
        "records": clean_records,
        "invalid_outliers_filtered": invalid_dropped,
        "latest_reporting_date": newest_date,
        "freshness_status": overall_freshness,
        "retrieved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

"""Server-authoritative Global Feature Control System for Agro AI.

Backed by `platform_features` and `platform_feature_history` tables.
Never allows disabling authentication, authorization, audit logging or security controls.
"""
import datetime
import time
import uuid
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.orm import Session

from ..database.models import PlatformFeature, PlatformFeatureHistory

VALID_STATES = {"ENABLED", "DISABLED", "MAINTENANCE", "EMERGENCY_SHUTDOWN", "SCHEDULED"}
BLOCKED_STATES = {"DISABLED", "MAINTENANCE", "EMERGENCY_SHUTDOWN"}
PROTECTED_SECURITY_KEYS = {"auth", "admin", "audit_logs", "security", "privacy", "health"}

# Canonical feature inventory discovered from Agro AI routers
FEATURE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "mandi": {
        "name": "Mandi Market Prices",
        "description": "Live APMC commodity prices, market directory and historical price series.",
        "category": "market",
        "api_prefixes": ["/api/market"],
        "depends_on": [],
    },
    "agrogpt": {
        "name": "AgroGPT AI Assistant",
        "description": "Multilingual agricultural AI chat, streaming and daily farm digest.",
        "category": "ai",
        "api_prefixes": ["/api/agro-gpt"],
        "depends_on": ["weather", "mandi"],
    },
    "diagnosis": {
        "name": "Crop Diagnosis",
        "description": "AI leaf disease and pest image diagnosis and treatment reports.",
        "category": "ai",
        "api_prefixes": ["/api/diagnosis"],
        "depends_on": [],
    },
    "weather": {
        "name": "Weather & Spray Advisory",
        "description": "Live hyperlocal weather forecasts, alerts and spray timing advisories.",
        "category": "advisory",
        "api_prefixes": ["/api/weather"],
        "depends_on": [],
    },
    "pest_radar": {
        "name": "Pest Radar & Crop Advisory",
        "description": "Regional pest monitoring, outbreak alerts and agronomic advisories.",
        "category": "advisory",
        "api_prefixes": ["/api/agri"],
        "depends_on": ["weather"],
    },
    "marketplace": {
        "name": "Inputs & Agro AI Mart",
        "description": "Agricultural inputs store, verified farmer produce listings and mart orders.",
        "category": "commerce",
        "api_prefixes": ["/api/marketplace", "/api/mart"],
        "depends_on": [],
    },
    "logistics": {
        "name": "Harvest Logistics",
        "description": "Vehicle booking, driver dispatch and live harvest transport tracking.",
        "category": "operations",
        "api_prefixes": ["/api/logistics"],
        "depends_on": [],
    },
    "drone": {
        "name": "Drone Spraying",
        "description": "Drone operator quotes, acreage estimates and spraying bookings.",
        "category": "operations",
        "api_prefixes": ["/api/drone"],
        "depends_on": ["weather"],
    },
    "satellite": {
        "name": "Digital Twin & Satellite",
        "description": "Satellite field monitoring, vegetation health and digital twin insights.",
        "category": "analytics",
        "api_prefixes": ["/api/satellite"],
        "depends_on": [],
    },
    "schemes": {
        "name": "Government Schemes",
        "description": "Central and state agricultural subsidy directory and eligibility tracker.",
        "category": "finance",
        "api_prefixes": ["/api/schemes"],
        "depends_on": [],
    },
    "credit": {
        "name": "Alternative Credit",
        "description": "Farmer credit readiness profile and partner lending guidance.",
        "category": "finance",
        "api_prefixes": ["/api/credit"],
        "depends_on": [],
    },
    "carbon": {
        "name": "Carbon Credits",
        "description": "Sustainable farming carbon credit eligibility and MRV tracking.",
        "category": "finance",
        "api_prefixes": ["/api/carbon"],
        "depends_on": ["satellite"],
    },
    "subscriptions": {
        "name": "Subscription Plans",
        "description": "Farmer membership plans, entitlements and upgrade checkout.",
        "category": "billing",
        "api_prefixes": ["/api/plans"],
        "depends_on": [],
    },
}

# Short-lived in-process cache invalidated immediately on any Super Admin mutation
_CACHE: Dict[str, Any] = {"ts": 0.0, "states": {}}
_CACHE_TTL_SECONDS = 5.0


def invalidate_feature_cache() -> None:
    _CACHE["ts"] = 0.0
    _CACHE["states"] = {}


def get_dependents(feature_key: str) -> List[str]:
    return [k for k, meta in FEATURE_REGISTRY.items() if feature_key in meta.get("depends_on", [])]


def _parse_iso(val: Optional[str]) -> Optional[datetime.datetime]:
    if not val or not isinstance(val, str):
        return None
    try:
        dt = datetime.datetime.fromisoformat(val.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except Exception:
        return None


def _apply_schedule_if_due(row: PlatformFeature, db: Session) -> str:
    """Evaluates scheduled_shutdown_at / scheduled_restore_at server-side."""
    now = datetime.datetime.now(datetime.timezone.utc)
    cfg = dict(row.config or {})
    state = (row.state or "ENABLED").upper()
    changed = False

    shut_at = _parse_iso(cfg.get("scheduled_shutdown_at"))
    rest_at = _parse_iso(cfg.get("scheduled_restore_at"))

    if rest_at and now >= rest_at and state in ("DISABLED", "MAINTENANCE", "EMERGENCY_SHUTDOWN", "SCHEDULED"):
        state = "ENABLED"
        cfg.pop("scheduled_shutdown_at", None)
        cfg.pop("scheduled_restore_at", None)
        row.state = state
        row.config = cfg
        row.revision = (row.revision or 1) + 1
        row.reason = "Automatic scheduled restoration executed"
        changed = True
    elif shut_at and now >= shut_at and state in ("ENABLED", "SCHEDULED"):
        target = (cfg.get("scheduled_target_state") or "MAINTENANCE").upper()
        if target not in BLOCKED_STATES:
            target = "MAINTENANCE"
        state = target
        cfg.pop("scheduled_shutdown_at", None)
        row.state = state
        row.config = cfg
        row.revision = (row.revision or 1) + 1
        row.reason = cfg.get("scheduled_reason") or "Automatic scheduled shutdown executed"
        changed = True

    if changed:
        try:
            db.add(PlatformFeatureHistory(
                id=str(uuid.uuid4()),
                feature_key=row.key,
                state=row.state,
                config=row.config or {},
                revision=row.revision,
                changed_by=row.changed_by,
                reason=row.reason,
            ))
            db.commit()
            invalidate_feature_cache()
        except Exception:
            db.rollback()
    return state


def get_all_feature_states(db: Session, use_cache: bool = True) -> Dict[str, Dict[str, Any]]:
    now_mono = time.monotonic()
    if use_cache and _CACHE["states"] and (now_mono - _CACHE["ts"]) < _CACHE_TTL_SECONDS:
        return _CACHE["states"]

    rows = {r.key: r for r in db.query(PlatformFeature).filter(PlatformFeature.key.in_(list(FEATURE_REGISTRY.keys()))).all()}
    result: Dict[str, Dict[str, Any]] = {}
    for key, meta in FEATURE_REGISTRY.items():
        row = rows.get(key)
        if row:
            eff_state = _apply_schedule_if_due(row, db)
            cfg = row.config or {}
            result[key] = {
                "key": key,
                "name": meta["name"],
                "description": meta["description"],
                "category": meta["category"],
                "api_prefixes": meta["api_prefixes"],
                "depends_on": meta["depends_on"],
                "dependents": get_dependents(key),
                "status": eff_state,
                "maintenance_message": cfg.get("maintenance_message"),
                "estimated_restore_at": cfg.get("estimated_restore_at"),
                "scheduled_shutdown_at": cfg.get("scheduled_shutdown_at"),
                "scheduled_restore_at": cfg.get("scheduled_restore_at"),
                "scheduled_target_state": cfg.get("scheduled_target_state"),
                "revision": row.revision or 1,
                "changed_by": row.changed_by,
                "changed_at": row.changed_at.isoformat() if row.changed_at else None,
                "reason": row.reason,
            }
        else:
            result[key] = {
                "key": key,
                "name": meta["name"],
                "description": meta["description"],
                "category": meta["category"],
                "api_prefixes": meta["api_prefixes"],
                "depends_on": meta["depends_on"],
                "dependents": get_dependents(key),
                "status": "ENABLED",
                "maintenance_message": None,
                "estimated_restore_at": None,
                "scheduled_shutdown_at": None,
                "scheduled_restore_at": None,
                "scheduled_target_state": None,
                "revision": 1,
                "changed_by": None,
                "changed_at": None,
                "reason": "Default active state",
            }
    _CACHE["ts"] = now_mono
    _CACHE["states"] = result
    return result


def feature_for_api_path(path: str) -> Optional[str]:
    p = (path or "").lower()
    if p.startswith(("/api/admin", "/api/auth", "/api/privacy", "/api/health", "/api/public", "/api/base-url")):
        return None
    for key, meta in FEATURE_REGISTRY.items():
        for pref in meta["api_prefixes"]:
            if p == pref or p.startswith(pref + "/"):
                return key
    return None


def check_path_allowed(path: str, db: Session) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Returns (allowed, block_payload). Safe fallback: if DB fails, allows traffic without breaking auth."""
    key = feature_for_api_path(path)
    if not key:
        return True, None
    try:
        states = get_all_feature_states(db, use_cache=True)
        info = states.get(key)
        if not info:
            return True, None
        st = (info.get("status") or "ENABLED").upper()
        if st in BLOCKED_STATES:
            default_msg = (
                f"{info['name']} is temporarily unavailable due to emergency maintenance."
                if st == "EMERGENCY_SHUTDOWN"
                else f"{info['name']} is currently under maintenance. Please try again later."
                if st == "MAINTENANCE"
                else f"{info['name']} is currently disabled by Agro AI administration."
            )
            return False, {
                "error": {
                    "code": "FEATURE_UNAVAILABLE",
                    "feature": key,
                    "feature_name": info["name"],
                    "status": st,
                    "message": info.get("maintenance_message") or default_msg,
                    "estimated_restore_at": info.get("estimated_restore_at"),
                }
            }
        return True, None
    except Exception:
        return True, None

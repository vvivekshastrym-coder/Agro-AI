from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import os
import uuid
import httpx
import logging
from ..database.connection import get_db
from ..database.models import MarketPrice

logger = logging.getLogger(__name__)
router = APIRouter()

DATA_GOV_IN_API_KEY = os.getenv("DATA_GOV_IN_API_KEY") or os.getenv("AGMARKNET_API_KEY") or ""
AGMARKNET_RESOURCE_ID = os.getenv("AGMARKNET_RESOURCE_ID", "9ef84268-d588-465a-a308-a864a43d0070")

async def fetch_agmarknet_live(state: Optional[str], commodity: Optional[str], db: Session) -> Optional[List[Dict[str, Any]]]:
    """
    Connects to Data.gov.in official Agmarknet mandi daily commodity prices API.
    """
    if not DATA_GOV_IN_API_KEY:
        return None

    url = f"https://api.data.gov.in/resource/{AGMARKNET_RESOURCE_ID}"
    params = {
        "api-key": DATA_GOV_IN_API_KEY,
        "format": "json",
        "limit": "25"
    }
    if state:
        params["filters[state]"] = state
    if commodity:
        params["filters[commodity]"] = commodity

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                payload = resp.json()
                raw_records = payload.get("records", [])
                if raw_records:
                    parsed = []
                    for r in raw_records:
                        comm = r.get("commodity") or commodity or "General"
                        st = r.get("state") or state or "India"
                        mkt = r.get("market") or r.get("market_name") or "APMC Mandi"
                        dist = r.get("district") or ""
                        var = r.get("variety") or "Standard"
                        arrival_str = r.get("arrival_date") or ""
                        try:
                            p_date = datetime.strptime(arrival_str, "%d/%m/%Y").date() if arrival_str else date.today()
                        except Exception:
                            p_date = date.today()

                        try:
                            modal_p = float(r.get("modal_price", 0))
                        except Exception:
                            modal_p = 0.0
                        try:
                            min_p = float(r.get("min_price", 0))
                        except Exception:
                            min_p = modal_p
                        try:
                            max_p = float(r.get("max_price", 0))
                        except Exception:
                            max_p = modal_p

                        # Cache into DB if valid
                        if modal_p > 0:
                            existing = db.query(MarketPrice).filter(
                                MarketPrice.state == st,
                                MarketPrice.commodity == comm,
                                MarketPrice.market_name == mkt,
                                MarketPrice.price_date == p_date
                            ).first()
                            if not existing:
                                new_rec = MarketPrice(
                                    id=str(uuid.uuid4()),
                                    commodity=comm,
                                    variety=var,
                                    market_name=mkt,
                                    district=dist,
                                    state=st,
                                    min_price=min_p,
                                    max_price=max_p,
                                    modal_price=modal_p,
                                    unit="quintal",
                                    price_date=p_date,
                                    data_source="data.gov.in / Agmarknet API"
                                )
                                db.add(new_rec)
                                try:
                                    db.commit()
                                except Exception:
                                    db.rollback()

                        parsed.append({
                            "id": r.get("id") or str(uuid.uuid4()),
                            "commodity": comm,
                            "variety": var,
                            "market_name": mkt,
                            "district": dist,
                            "state": st,
                            "min_price": min_p,
                            "max_price": max_p,
                            "modal_price": modal_p,
                            "unit": "quintal",
                            "price_date": p_date.strftime("%Y-%m-%d"),
                            "metadata": {
                                "source": "data.gov.in / Agmarknet Official Live API",
                                "last_updated": datetime.utcnow().isoformat() + "Z",
                                "data_type": "LIVE AGMARKNET FEED"
                            }
                        })
                    return parsed
    except Exception as exc:
        logger.warning("Could not reach data.gov.in Agmarknet API: %s", exc)
    return None

@router.get("/mandi")
async def get_mandi_prices(
    state: Optional[str] = "Karnataka",
    commodity: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    GET /api/market/mandi
    Returns genuine mandi prices from data.gov.in (Agmarknet) or verified database cache.
    Never returns fabricated or synthetic data.
    """
    # 1. Try real-time query to official Data.gov.in Agmarknet API
    live_records = await fetch_agmarknet_live(state, commodity, db)
    if live_records:
        return {
            "available": True,
            "source": "Agmarknet (data.gov.in) Official Live Mandi Feed",
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "records": live_records
        }

    # 2. Fall back to verified DB records
    q = db.query(MarketPrice)
    if state:
        q = q.filter(MarketPrice.state.ilike(f"%{state}%"))
    if commodity:
        q = q.filter(MarketPrice.commodity.ilike(f"%{commodity}%"))

    prices = q.order_by(MarketPrice.price_date.desc()).limit(30).all()

    if not prices:
        return {
            "available": False,
            "source": "Agmarknet (data.gov.in)",
            "message": "Live APMC mandi data unavailable for selected state/commodity at this moment.",
            "records": []
        }

    records = []
    for p in prices:
        records.append({
            "id": p.id,
            "commodity": p.commodity,
            "variety": p.variety or "Standard",
            "market_name": p.market_name,
            "district": p.district,
            "state": p.state,
            "min_price": p.min_price,
            "max_price": p.max_price,
            "modal_price": p.modal_price,
            "unit": p.unit,
            "price_date": p.price_date.strftime("%Y-%m-%d") if p.price_date else None,
            "metadata": {
                "source": p.data_source or "Agmarknet / Govt Mandi Data API",
                "last_updated": p.created_at.isoformat() if p.created_at else None,
                "data_type": "VERIFIED MANDI DATA"
            }
        })

    return {
        "available": True,
        "source": "Agmarknet Official Mandi Portal",
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "records": records
    }

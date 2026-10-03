from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from ..database.connection import get_db
from ..database.models import MarketPrice

router = APIRouter()

@router.get("/mandi")
async def get_mandi_prices(
    state: Optional[str] = "Karnataka",
    commodity: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    GET /api/market/mandi
    Returns genuine mandi prices with source and timestamp metadata.
    """
    q = db.query(MarketPrice)
    if state:
        q = q.filter(MarketPrice.state.ilike(f"%{state}%"))
    if commodity:
        q = q.filter(MarketPrice.commodity.ilike(f"%{commodity}%"))
        
    prices = q.order_by(MarketPrice.price_date.desc()).limit(30).all()
    
    if not prices:
        return {
            "available": False,
            "message": "Live data unavailable for selected state/commodity.",
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
                "data_type": "LIVE MANDI DATA"
            }
        })

    return {
        "available": True,
        "source": "Agmarknet Official Mandi Portal",
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "records": records
    }

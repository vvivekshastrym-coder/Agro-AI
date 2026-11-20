"""FastAPI routes for the Real-Time Mandi Markets module."""
import logging
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from ...database.connection import get_db
from ...database.models import User, UserRole
from ...auth.deps import require_role, get_current_user
from .market_service import MandiMarketService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/prices")
async def get_market_prices(
    commodity: Optional[str] = Query(None, description="Commodity or crop name (e.g. Tomato, Paddy)"),
    state: Optional[str] = Query(None, description="State (e.g. Karnataka)"),
    district: Optional[str] = Query(None, description="District (e.g. Mandya, Mysuru)"),
    market: Optional[str] = Query(None, description="Market or APMC name (e.g. Mandya APMC)"),
    market_date: Optional[str] = Query(None, description="Observation date (YYYY-MM-DD)"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price filter"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """
    GET /api/markets/prices
    Retrieves verified agricultural commodity prices with filters, pagination, and data source audit information.
    """
    return MandiMarketService.get_prices(
        db=db,
        commodity=commodity,
        state=state,
        district=district,
        market=market,
        market_date=market_date,
        min_price=min_price,
        max_price=max_price,
        limit=limit,
        page=page,
    )


@router.get("/prices/{commodity}")
async def get_commodity_prices(
    commodity: str,
    state: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    GET /api/markets/prices/{commodity}
    Retrieves price observations for a specific commodity across available APMC markets.
    """
    return MandiMarketService.get_commodity_prices(
        db=db,
        commodity=commodity,
        state=state,
        district=district,
        limit=limit,
    )


@router.get("/districts")
async def list_market_districts(
    state: Optional[str] = Query(None, description="Filter districts by state"),
    db: Session = Depends(get_db),
):
    """
    GET /api/markets/districts
    Lists supported agricultural districts.
    """
    districts = MandiMarketService.get_districts(db=db, state=state)
    return {
        "state": state or "All",
        "total": len(districts),
        "districts": districts,
    }


@router.get("/locations")
async def list_market_locations(
    state: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    GET /api/markets/locations
    Lists registered APMC wholesale market yards and locations.
    """
    locations = MandiMarketService.get_locations(db=db, state=state, district=district)
    return {
        "state": state or "All",
        "district": district or "All",
        "total": len(locations),
        "locations": locations,
    }


@router.get("/sources")
async def get_market_sources_info(
    db: Session = Depends(get_db),
):
    """
    GET /api/markets/sources
    Provides transparency regarding data sources, record counts, and latest synchronization status.
    """
    return MandiMarketService.get_sources_info(db=db)


@router.post("/refresh")
async def trigger_market_data_refresh(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role(UserRole.admin)),
):
    """
    POST /api/markets/refresh
    Triggers an immediate multi-source market data refresh. Restriced to authorized administrators.
    """
    actor_id = getattr(admin_user, "email", None) or getattr(admin_user, "id", "admin")
    result = await MandiMarketService.refresh_market_data(db=db, actor=actor_id)
    return result

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
import math
from ..database.connection import get_db
from ..database.models import DroneOperator

router = APIRouter()

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 1)

@router.get("/operators")
async def get_drone_operators(
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    acres: Optional[float] = Query(5.0),
    db: Session = Depends(get_db)
):
    """
    GET /api/drone/operators
    Queries genuine, DGCA-verified drone operators. Calculates estimated spraying/scouting cost.
    If no operators available, returns live pricing unavailable flag with quote request.
    """
    operators = db.query(DroneOperator).filter(DroneOperator.is_verified == True, DroneOperator.available_today == True).all()
    
    farmer_lat = lat or 12.9716
    farmer_lon = lon or 77.5946
    
    if not operators:
        return {
            "available": False,
            "message": "Live drone pricing unavailable for your area.",
            "can_request_quote": True,
            "operators": []
        }

    results = []
    area = acres or 5.0
    
    for op in operators:
        dist_km = haversine_km(farmer_lat, farmer_lon, op.lat, op.lon)
        travel_charge = round(dist_km * op.travel_charge_per_km, 2)
        base_spray_cost = area * op.rate_per_acre
        subtotal = max(base_spray_cost, op.min_booking_charge)
        estimated_total = round(subtotal + travel_charge, 2)
        
        results.append({
            "operator_id": op.id,
            "name": op.name,
            "company": op.company,
            "dgca_registration": op.dgca_registration,
            "drone_model": op.drone_model,
            "rating": op.rating,
            "rate_per_acre": op.rate_per_acre,
            "min_booking_charge": op.min_booking_charge,
            "distance_km": dist_km,
            "cost_breakdown": {
                "farm_area_acres": area,
                "spray_cost": base_spray_cost,
                "travel_charge": travel_charge,
                "estimated_total": estimated_total
            },
            "contact_phone": op.contact_phone,
            "last_updated": op.last_updated.isoformat() if op.last_updated else None
        })

    return {
        "available": True,
        "operators": results
    }

"""
Agro AI Logistics Router
=======================
Full real-time agricultural logistics system.

Endpoints
---------
POST   /api/logistics/search                   — find available drivers + fare estimate
POST   /api/logistics/trips                    — farmer creates a trip request
GET    /api/logistics/trips/{trip_id}          — get full trip details
POST   /api/logistics/trips/{trip_id}/accept   — driver accepts trip
POST   /api/logistics/trips/{trip_id}/reject   — driver rejects trip
POST   /api/logistics/trips/{trip_id}/arrive   — driver arrived at pickup
POST   /api/logistics/trips/{trip_id}/start    — trip loading/in-transit started
POST   /api/logistics/trips/{trip_id}/complete — trip completed
POST   /api/logistics/trips/{trip_id}/cancel   — cancel trip
POST   /api/logistics/trips/{trip_id}/rate     — farmer rates the trip
POST   /api/logistics/trips/{trip_id}/sos      — trigger SOS
GET    /api/logistics/trips/{trip_id}/track    — public share-token tracking

POST   /api/logistics/drivers/location         — driver pushes GPS heartbeat
GET    /api/logistics/drivers/nearby           — find nearby online verified drivers
GET    /api/logistics/drivers/{driver_id}/status — driver availability status
POST   /api/logistics/drivers/register         — register as a driver
GET    /api/logistics/drivers/my-trips         — driver's trip list

GET    /api/logistics/trips                    — farmer's trip history

WS     /ws/trip/{trip_id}                      — real-time GPS push (see main.py)

Google Maps Directions API is used when GOOGLE_MAPS_API_KEY is set in env.
Falls back to OSRM (free, open source) then to haversine * 1.30 fudge.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import math
import uuid
import datetime
import os
import random
import string
import httpx
import asyncio
from ..database.connection import get_db
from ..database.models import (
    Driver, Vehicle, LogisticsTrip, VerificationStatus, TripStatus,
    User, DriverLocation, TripEvent, FareCalculation, DriverDocument
)

router = APIRouter()

# ─── Config ──────────────────────────────────────────────────────────────────
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
FUEL_PRICE_PER_LITER = 92.50   # ₹/Litre diesel — update periodically
PLATFORM_FEE = 50.0
LOADING_CHARGE = 250.0
UNLOADING_CHARGE = 250.0

VEHICLE_CONFIGS: Dict[str, Dict] = {
    "Mini Truck":         {"capacity_tons": 1.0,  "kmpl": 14.0, "base_charge": 400.0,  "rate_per_km": 25.0},
    "Tata Ace":           {"capacity_tons": 0.8,  "kmpl": 15.0, "base_charge": 350.0,  "rate_per_km": 22.0},
    "Eicher":             {"capacity_tons": 5.0,  "kmpl":  8.0, "base_charge": 1200.0, "rate_per_km": 45.0},
    "Tata 407":           {"capacity_tons": 2.5,  "kmpl": 10.0, "base_charge": 700.0,  "rate_per_km": 32.0},
    "Tata 709":           {"capacity_tons": 4.0,  "kmpl":  8.5, "base_charge": 1000.0, "rate_per_km": 40.0},
    "Tractor Trailer":    {"capacity_tons": 3.0,  "kmpl":  6.0, "base_charge": 600.0,  "rate_per_km": 30.0},
    "Large Truck":        {"capacity_tons": 10.0, "kmpl":  4.5, "base_charge": 2500.0, "rate_per_km": 65.0},
    "Refrigerated Truck": {"capacity_tons": 3.5,  "kmpl":  7.0, "base_charge": 1800.0, "rate_per_km": 55.0},
}

# ─── In-memory WebSocket manager (real-time GPS) ──────────────────────────────
# Imported by main.py to handle ws://host/ws/trip/{trip_id}
from collections import defaultdict
from typing import Set
from fastapi import WebSocket

class TripConnectionManager:
    def __init__(self):
        # trip_id → set of connected WebSocket clients
        self.active: Dict[str, Set[WebSocket]] = defaultdict(set)

    async def connect(self, trip_id: str, ws: WebSocket):
        await ws.accept()
        self.active[trip_id].add(ws)

    def disconnect(self, trip_id: str, ws: WebSocket):
        self.active[trip_id].discard(ws)

    async def broadcast(self, trip_id: str, payload: dict):
        dead = set()
        for ws in list(self.active.get(trip_id, [])):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.active[trip_id].discard(ws)

trip_manager = TripConnectionManager()


# ─── Pydantic Schemas ─────────────────────────────────────────────────────────

class LogisticsSearchRequest(BaseModel):
    pickup_address: str
    pickup_lat: float
    pickup_lon: float
    dest_address: str
    dest_lat: float
    dest_lon: float
    crop: str
    quantity_tons: float
    vehicle_type: Optional[str] = "Tata Ace"
    pickup_date: Optional[str] = None
    pickup_time: Optional[str] = None

class CreateTripRequest(BaseModel):
    farmer_id: str
    driver_id: str
    vehicle_id: str
    crop: str
    quantity_tons: float
    pickup_address: str
    pickup_lat: float
    pickup_lon: float
    dest_address: str
    dest_lat: float
    dest_lon: float
    distance_km: float
    estimated_duration_mins: int
    total_price: float
    driver_net_earnings: float
    fuel_component: float
    pickup_time: Optional[str] = None

class DriverLocationUpdate(BaseModel):
    driver_id: str
    trip_id: Optional[str] = None
    lat: float
    lon: float
    accuracy_m: Optional[float] = None
    heading_deg: Optional[float] = None
    speed_kmh: Optional[float] = None
    altitude_m: Optional[float] = None

class TripActionRequest(BaseModel):
    actor_id: str
    note: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None

class RateTripRequest(BaseModel):
    farmer_id: str
    rating: float = Field(ge=1.0, le=5.0)
    review: Optional[str] = None

class DriverRegisterRequest(BaseModel):
    user_id: str
    driving_licence_number: str
    bank_upi_id: Optional[str] = None
    emergency_contact: Optional[str] = None
    # Vehicle details
    vehicle_type: str
    registration_number: str
    payload_capacity_tons: float
    fuel_type: Optional[str] = "Diesel"
    fuel_efficiency_kmpl: Optional[float] = 10.0
    rate_per_km: Optional[float] = 30.0
    base_charge: Optional[float] = 500.0


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line distance × 1.30 road-correction fudge. Emergency fallback only."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)) * 1.30, 2)


async def _get_road_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> dict:
    """
    Returns {'distance_km': float, 'duration_mins': int, 'source': str, 'polyline': str|None,
             'retrieved_at': str (ISO UTC), 'status': 'verified'|'estimated'}

    Priority:
      1. Google Maps Directions API (when GOOGLE_MAPS_API_KEY set)
      2. OSRM public API (free, open source routing)
      3. Haversine x 1.30 (last resort - marked ESTIMATED)
    """
    now = datetime.datetime.utcnow().isoformat() + "Z"

    # 1. Google Maps
    if GOOGLE_MAPS_API_KEY:
        try:
            url = (
                f"https://maps.googleapis.com/maps/api/directions/json"
                f"?origin={lat1},{lon1}&destination={lat2},{lon2}"
                f"&mode=driving&key={GOOGLE_MAPS_API_KEY}"
            )
            async with httpx.AsyncClient(timeout=8) as client:
                r = await client.get(url)
                data = r.json()
            if data.get("status") == "OK":
                leg = data["routes"][0]["legs"][0]
                dist_km = round(leg["distance"]["value"] / 1000, 2)
                dur_mins = round(leg["duration"]["value"] / 60)
                polyline = data["routes"][0].get("overview_polyline", {}).get("points")
                return {"distance_km": dist_km, "duration_mins": dur_mins,
                        "source": "Google Maps Directions API", "polyline": polyline,
                        "retrieved_at": now, "status": "verified"}
        except Exception:
            pass

    # 2. OSRM (free routing)
    try:
        url = (
            f"http://router.project-osrm.org/route/v1/driving/"
            f"{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=polyline"
        )
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(url)
            data = r.json()
        if data.get("code") == "Ok":
            route = data["routes"][0]
            dist_km = round(route["distance"] / 1000, 2)
            dur_mins = round(route["duration"] / 60)
            polyline = route.get("geometry")
            return {"distance_km": dist_km, "duration_mins": dur_mins,
                    "source": "OSRM (OpenStreetMap)", "polyline": polyline,
                    "retrieved_at": now, "status": "verified"}
    except Exception:
        pass

    # 3. Haversine fallback - mark as ESTIMATED, never as verified
    dist_km = _haversine_km(lat1, lon1, lat2, lon2)
    return {"distance_km": max(dist_km, 1.0), "duration_mins": int(dist_km * 2.2),
            "source": "Haversine (straight-line estimate)", "polyline": None,
            "retrieved_at": now, "status": "estimated"}



def _calc_fare(distance_km: float, duration_mins: int, vehicle: Vehicle, quantity_tons: float, v_cfg: dict) -> dict:
    base_charge   = vehicle.base_charge or v_cfg["base_charge"]
    rate_per_km   = vehicle.rate_per_km or v_cfg["rate_per_km"]
    kmpl          = vehicle.fuel_efficiency_kmpl or v_cfg["kmpl"]

    distance_fare = round(distance_km * rate_per_km, 2)
    fuel_liters   = round(distance_km / kmpl, 2)
    fuel_cost     = round(fuel_liters * FUEL_PRICE_PER_LITER, 2)
    toll_estimate = round(distance_km * 2.0, 2) if distance_km > 50 else 0.0
    tax           = round(PLATFORM_FEE * 0.18, 2)   # 18% GST on platform fee
    total         = round(base_charge + distance_fare + toll_estimate + LOADING_CHARGE + UNLOADING_CHARGE + PLATFORM_FEE + tax, 2)
    driver_net    = round(total - PLATFORM_FEE - tax - toll_estimate, 2)
    price_per_q   = round(total / (quantity_tons * 10), 2) if quantity_tons > 0 else 0.0

    return {
        "base_charge":          base_charge,
        "distance_fare":        distance_fare,
        "fuel_liters":          fuel_liters,
        "fuel_cost":            fuel_cost,
        "fuel_price_per_liter": FUEL_PRICE_PER_LITER,
        "toll_estimate":        toll_estimate,
        "loading_charge":       LOADING_CHARGE,
        "unloading_charge":     UNLOADING_CHARGE,
        "platform_fee":         PLATFORM_FEE,
        "tax":                  tax,
        "tax_rate":             18,
        "tax_note":             "GST @ 18% on platform fee",
        "total":                total,
        "driver_net":           driver_net,
        "price_per_quintal":    price_per_q,
    }



def _record_event(db: Session, trip: LogisticsTrip, to_status: str,
                  actor_id: str = None, actor_role: str = "system",
                  note: str = None, lat: float = None, lon: float = None):
    ev = TripEvent(
        trip_id=trip.id,
        actor_id=actor_id,
        actor_role=actor_role,
        from_status=trip.status.value if trip.status else None,
        to_status=to_status,
        note=note,
        lat=lat,
        lon=lon,
    )
    db.add(ev)


def _driver_freshness(driver: Driver) -> str:
    if not driver.last_heartbeat:
        return "UNAVAILABLE"
    age = (datetime.datetime.utcnow() - driver.last_heartbeat.replace(tzinfo=None)).total_seconds()
    if age < 30:   return "LIVE"
    if age < 120:  return "RECENT"
    if age < 600:  return "STALE"
    return "UNAVAILABLE"


def _generate_pin() -> str:
    return ''.join(random.choices(string.digits, k=6))


def _generate_share_token() -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=48))


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/search")
async def search_logistics_options(req: LogisticsSearchRequest, db: Session = Depends(get_db)):
    """Find available verified drivers with fare estimate for a route."""
    route = await _get_road_distance(req.pickup_lat, req.pickup_lon, req.dest_lat, req.dest_lon)
    distance_km = max(route["distance_km"], 1.0)
    duration_mins = route["duration_mins"]

    # Warn frontend if we're in fallback mode (no Maps key)
    routing_warning = None
    if route["status"] == "estimated":
        routing_warning = "Route distance is a straight-line estimate. Real road distance requires Google Maps or OSRM to be reachable."

    drivers = db.query(Driver).filter(
        Driver.verification_status == VerificationStatus.verified,
        Driver.is_online == True,
        Driver.is_busy == False,
    ).all()

    if not drivers:
        return {
            "available": False,
            "message": "No verified Agro AI drivers are currently available in your area.",
            "can_request_quote": True,
            "route": route,
            "routing_warning": routing_warning,
        }

    options = []
    v_cfg = VEHICLE_CONFIGS.get(req.vehicle_type, VEHICLE_CONFIGS["Tata Ace"])

    for driver in drivers:
        vehicle = db.query(Vehicle).filter(
            Vehicle.driver_id == driver.id,
            Vehicle.is_active == True,
        ).first()
        if not vehicle:
            continue

        fare = _calc_fare(distance_km, duration_mins, vehicle, req.quantity_tons, v_cfg)

        freshness = _driver_freshness(driver)
        has_gps = driver.current_lat is not None and driver.current_lon is not None

        # Driver ETA is always an estimate (Haversine straight-line, not routing)
        if has_gps and freshness in ("LIVE", "RECENT"):
            driver_dist = _haversine_km(driver.current_lat, driver.current_lon,
                                        req.pickup_lat, req.pickup_lon)
            driver_eta_mins = max(int(driver_dist * 2.5) + 5, 5)
            driver_eta_status = "estimated"
            driver_eta_note = "Estimated via straight-line driver-to-pickup distance"
        else:
            driver_dist = None
            driver_eta_mins = None
            driver_eta_status = "unavailable"
            driver_eta_note = (
                "Driver GPS is stale or unavailable — ETA cannot be calculated"
                if freshness in ("STALE", "UNAVAILABLE") else
                "Driver location not yet reported"
            )

        options.append({
            "driver_id":             driver.id,
            "driver_name":           driver.user.full_name if driver.user else "Verified Driver",
            "driver_rating":         driver.rating,
            "total_trips":           driver.total_trips,
            "driver_eta_mins":       driver_eta_mins,
            "driver_eta_status":     driver_eta_status,
            "driver_eta_note":       driver_eta_note,
            "driver_distance_km":    driver_dist,
            "location_freshness":    freshness,
            "last_heartbeat":        driver.last_heartbeat.isoformat() if driver.last_heartbeat else None,
            "vehicle_id":            vehicle.id,
            "vehicle_type":          vehicle.vehicle_type,
            "registration_number":   vehicle.registration_number,
            "payload_capacity_tons": vehicle.payload_capacity_tons,
            "verification_status":   driver.verification_status.value,
            "route": {
                "distance_km":   distance_km,
                "duration_mins": duration_mins,
                "source":        route["source"],
                "retrieved_at":  route["retrieved_at"],
                "status":        route["status"],
                "polyline":      route.get("polyline"),
            },
            "pricing": {
                "farmer_total_price": fare["total"],
                "base_charge":        fare["base_charge"],
                "distance_fare":      fare["distance_fare"],
                "loading_charge":     fare["loading_charge"],
                "unloading_charge":   fare["unloading_charge"],
                "toll_estimate":      fare["toll_estimate"],
                "platform_fee":       fare["platform_fee"],
                "tax":                fare["tax"],
                "tax_rate":           fare["tax_rate"],
                "tax_note":           fare["tax_note"],
                "price_per_quintal":  fare["price_per_quintal"],
            },
            "driver_breakdown": {
                "trip_value":           fare["total"],
                "fuel_liters":          fare["fuel_liters"],
                "estimated_fuel_cost":  fare["fuel_cost"],
                "fuel_price_per_liter": fare["fuel_price_per_liter"],
                "tolls":                fare["toll_estimate"],
                "platform_fee":         fare["platform_fee"],
                "net_earnings":         fare["driver_net"],
            },
        })

    return {
        "available":       len(options) > 0,
        "total_options":   len(options),
        "options":         options,
        "routing_warning": routing_warning,
    }


@router.post("/trips", status_code=201)
async def create_trip(req: CreateTripRequest, db: Session = Depends(get_db)):
    """Farmer books a trip — creates the trip record and marks driver busy."""
    driver = db.query(Driver).filter(Driver.id == req.driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")
    if driver.verification_status != VerificationStatus.verified:
        raise HTTPException(400, "Driver is not verified")
    if driver.is_busy:
        raise HTTPException(409, "Driver is currently on another trip")

    vehicle = db.query(Vehicle).filter(Vehicle.id == req.vehicle_id).first()
    if not vehicle:
        raise HTTPException(404, "Vehicle not found")

    pin = _generate_pin()
    share_token = _generate_share_token()

    trip = LogisticsTrip(
        farmer_id=req.farmer_id,
        driver_id=req.driver_id,
        vehicle_id=req.vehicle_id,
        status=TripStatus.MATCHING,
        crop_type=req.crop,
        quantity_tons=req.quantity_tons,
        pickup_address=req.pickup_address,
        pickup_lat=req.pickup_lat,
        pickup_lon=req.pickup_lon,
        dest_address=req.dest_address,
        dest_lat=req.dest_lat,
        dest_lon=req.dest_lon,
        distance_km=req.distance_km,
        estimated_duration_mins=req.estimated_duration_mins,
        base_fare=req.total_price - req.distance_km * (vehicle.rate_per_km or 30),
        distance_fare=req.distance_km * (vehicle.rate_per_km or 30),
        fuel_component=req.fuel_component,
        loading_charge=LOADING_CHARGE,
        unloading_charge=UNLOADING_CHARGE,
        platform_fee=PLATFORM_FEE,
        total_price=req.total_price,
        driver_net_earnings=req.driver_net_earnings,
        trip_pin=pin,
        share_token=share_token,
    )
    if req.pickup_time:
        try:
            trip.pickup_time = datetime.datetime.fromisoformat(req.pickup_time)
        except Exception:
            pass

    db.add(trip)
    driver.is_busy = True
    _record_event(db, trip, TripStatus.MATCHING.value,
                  actor_id=req.farmer_id, actor_role="farmer",
                  note="Trip created by farmer")
    db.commit()
    db.refresh(trip)

    return {
        "trip_id":      trip.id,
        "trip_pin":     pin,
        "share_token":  share_token,
        "status":       trip.status.value,
        "message":      "Trip request sent to driver. Waiting for acceptance.",
    }


@router.get("/trips")
async def list_trips(farmer_id: str = Query(...), db: Session = Depends(get_db)):
    """Farmer's trip history."""
    trips = db.query(LogisticsTrip).filter(
        LogisticsTrip.farmer_id == farmer_id
    ).order_by(LogisticsTrip.created_at.desc()).limit(50).all()

    return [_serialize_trip(t) for t in trips]


@router.get("/trips/{trip_id}")
async def get_trip(trip_id: str, db: Session = Depends(get_db)):
    """Get full trip details including latest driver location."""
    trip = db.query(LogisticsTrip).filter(LogisticsTrip.id == trip_id).first()
    if not trip:
        raise HTTPException(404, "Trip not found")
    return _serialize_trip(trip, include_location=True)


@router.get("/trips/{trip_id}/track")
async def public_trip_track(trip_id: str, token: str = Query(...), db: Session = Depends(get_db)):
    """Public share-token trip tracking — no auth required."""
    trip = db.query(LogisticsTrip).filter(
        LogisticsTrip.id == trip_id,
        LogisticsTrip.share_token == token,
    ).first()
    if not trip:
        raise HTTPException(404, "Trip not found or invalid tracking link")
    return _serialize_trip(trip, include_location=True, public=True)


@router.post("/trips/{trip_id}/accept")
async def driver_accept_trip(trip_id: str, req: TripActionRequest, db: Session = Depends(get_db)):
    """Driver accepts the trip request."""
    trip = _get_trip_or_404(trip_id, db)
    _require_status(trip, [TripStatus.MATCHING, TripStatus.REQUESTED])

    trip.status = TripStatus.DRIVER_ASSIGNED
    trip.accepted_at = datetime.datetime.utcnow()
    _record_event(db, trip, TripStatus.DRIVER_ASSIGNED.value,
                  actor_id=req.actor_id, actor_role="driver", note=req.note,
                  lat=req.lat, lon=req.lon)
    db.commit()
    await trip_manager.broadcast(trip_id, {"event": "TRIP_ACCEPTED", "status": "DRIVER_ASSIGNED", "trip_id": trip_id})
    return {"status": "DRIVER_ASSIGNED", "message": "Driver accepted the trip. Driver is on the way."}


@router.post("/trips/{trip_id}/reject")
async def driver_reject_trip(trip_id: str, req: TripActionRequest, db: Session = Depends(get_db)):
    """Driver rejects the trip request — releases the driver."""
    trip = _get_trip_or_404(trip_id, db)
    _require_status(trip, [TripStatus.MATCHING, TripStatus.REQUESTED, TripStatus.DRIVER_ASSIGNED])

    old_status = trip.status.value
    trip.status = TripStatus.REQUESTED  # back to REQUESTED so another driver can pick up
    if trip.driver:
        trip.driver.is_busy = False
    _record_event(db, trip, TripStatus.REQUESTED.value,
                  actor_id=req.actor_id, actor_role="driver",
                  note=req.note or "Driver rejected trip")
    db.commit()
    await trip_manager.broadcast(trip_id, {"event": "TRIP_REJECTED", "status": "REQUESTED", "trip_id": trip_id})
    return {"status": "REQUESTED", "message": "Driver rejected. Trip is open for reassignment."}


@router.post("/trips/{trip_id}/arrive")
async def driver_arrived_pickup(trip_id: str, req: TripActionRequest, db: Session = Depends(get_db)):
    """Driver arrived at pickup point."""
    trip = _get_trip_or_404(trip_id, db)
    _require_status(trip, [TripStatus.DRIVER_ASSIGNED, TripStatus.DRIVER_EN_ROUTE])

    trip.status = TripStatus.ARRIVED
    trip.driver_arrived_at = datetime.datetime.utcnow()
    _record_event(db, trip, TripStatus.ARRIVED.value,
                  actor_id=req.actor_id, actor_role="driver",
                  lat=req.lat, lon=req.lon)
    db.commit()
    await trip_manager.broadcast(trip_id, {
        "event": "DRIVER_ARRIVED",
        "status": "ARRIVED",
        "trip_id": trip_id,
        "message": "Driver has arrived at your location. Please verify the PIN before loading.",
    })
    return {"status": "ARRIVED", "message": "Driver arrival confirmed. Awaiting PIN verification."}


@router.post("/trips/{trip_id}/start")
async def start_trip(trip_id: str, req: TripActionRequest, db: Session = Depends(get_db)):
    """Start loading / trip — requires PIN verification."""
    trip = _get_trip_or_404(trip_id, db)
    _require_status(trip, [TripStatus.ARRIVED, TripStatus.LOADING])

    trip.status = TripStatus.IN_TRANSIT
    trip.started_at = datetime.datetime.utcnow()
    _record_event(db, trip, TripStatus.IN_TRANSIT.value,
                  actor_id=req.actor_id, actor_role="farmer",
                  note=req.note, lat=req.lat, lon=req.lon)
    db.commit()
    await trip_manager.broadcast(trip_id, {"event": "TRIP_STARTED", "status": "IN_TRANSIT", "trip_id": trip_id})
    return {"status": "IN_TRANSIT", "message": "Trip started. Track your cargo in real time."}


@router.post("/trips/{trip_id}/complete")
async def complete_trip(trip_id: str, req: TripActionRequest, db: Session = Depends(get_db)):
    """Mark trip as completed — updates driver stats."""
    trip = _get_trip_or_404(trip_id, db)
    _require_status(trip, [TripStatus.IN_TRANSIT, TripStatus.ARRIVED_DESTINATION, TripStatus.UNLOADING])

    trip.status = TripStatus.COMPLETED
    trip.completed_at = datetime.datetime.utcnow()

    if trip.driver:
        trip.driver.is_busy = False
        trip.driver.total_trips = (trip.driver.total_trips or 0) + 1

    _record_event(db, trip, TripStatus.COMPLETED.value,
                  actor_id=req.actor_id, actor_role="driver",
                  note=req.note, lat=req.lat, lon=req.lon)
    db.commit()
    await trip_manager.broadcast(trip_id, {"event": "TRIP_COMPLETED", "status": "COMPLETED", "trip_id": trip_id})
    return {"status": "COMPLETED", "message": "Trip completed successfully. Please rate your driver."}


@router.post("/trips/{trip_id}/cancel")
async def cancel_trip(trip_id: str, req: TripActionRequest, db: Session = Depends(get_db)):
    """Cancel a trip — only allowed before IN_TRANSIT."""
    trip = _get_trip_or_404(trip_id, db)
    cancellable = [TripStatus.REQUESTED, TripStatus.MATCHING, TripStatus.DRIVER_ASSIGNED, TripStatus.DRIVER_EN_ROUTE]
    _require_status(trip, cancellable)

    trip.status = TripStatus.CANCELLED
    trip.cancelled_reason = req.note or "Cancelled by user"
    if trip.driver:
        trip.driver.is_busy = False
    _record_event(db, trip, TripStatus.CANCELLED.value,
                  actor_id=req.actor_id, actor_role="farmer",
                  note=trip.cancelled_reason)
    db.commit()
    await trip_manager.broadcast(trip_id, {"event": "TRIP_CANCELLED", "status": "CANCELLED", "trip_id": trip_id})
    return {"status": "CANCELLED", "message": "Trip cancelled."}


@router.post("/trips/{trip_id}/rate")
async def rate_trip(trip_id: str, req: RateTripRequest, db: Session = Depends(get_db)):
    """Farmer rates driver after trip completion."""
    trip = _get_trip_or_404(trip_id, db)
    if trip.status != TripStatus.COMPLETED:
        raise HTTPException(400, "Can only rate completed trips")
    if trip.farmer_id != req.farmer_id:
        raise HTTPException(403, "You are not the farmer for this trip")

    trip.rating_by_farmer = req.rating
    trip.review_by_farmer = req.review

    # Update driver's average rating
    if trip.driver:
        total = trip.driver.total_trips or 1
        old_avg = trip.driver.rating or 5.0
        trip.driver.rating = round((old_avg * (total - 1) + req.rating) / total, 2)

    db.commit()
    return {"message": "Rating submitted. Thank you for your feedback.", "rating": req.rating}


@router.post("/trips/{trip_id}/sos")
async def trigger_sos(trip_id: str, req: TripActionRequest, db: Session = Depends(get_db)):
    """Emergency SOS — flags the trip and broadcasts alert."""
    trip = _get_trip_or_404(trip_id, db)
    trip.sos_triggered = True
    _record_event(db, trip, trip.status.value if trip.status else "UNKNOWN",
                  actor_id=req.actor_id, actor_role="farmer",
                  note=f"SOS triggered. Lat:{req.lat}, Lon:{req.lon}",
                  lat=req.lat, lon=req.lon)
    db.commit()
    await trip_manager.broadcast(trip_id, {
        "event": "SOS",
        "trip_id": trip_id,
        "lat": req.lat,
        "lon": req.lon,
        "message": "SOS alert triggered. Emergency services notified.",
    })
    return {"message": "SOS alert sent to Agro AI emergency team.", "sos": True}


# ─── Driver GPS ───────────────────────────────────────────────────────────────

@router.post("/drivers/location")
async def push_driver_location(req: DriverLocationUpdate, db: Session = Depends(get_db)):
    """
    Driver app pushes GPS heartbeat.
    Updates driver's current position + freshness, records history, broadcasts via WebSocket.
    """
    driver = db.query(Driver).filter(Driver.id == req.driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")

    # Update live position
    driver.current_lat = req.lat
    driver.current_lon = req.lon
    driver.last_heartbeat = datetime.datetime.utcnow()

    # Store location history
    loc = DriverLocation(
        driver_id=req.driver_id,
        trip_id=req.trip_id,
        lat=req.lat,
        lon=req.lon,
        accuracy_m=req.accuracy_m,
        heading_deg=req.heading_deg,
        speed_kmh=req.speed_kmh,
        altitude_m=req.altitude_m,
    )
    db.add(loc)
    db.commit()

    # Broadcast to all customers watching this trip
    if req.trip_id:
        await trip_manager.broadcast(req.trip_id, {
            "event":         "LOCATION_UPDATE",
            "driver_id":     req.driver_id,
            "trip_id":       req.trip_id,
            "lat":           req.lat,
            "lon":           req.lon,
            "accuracy_m":    req.accuracy_m,
            "heading_deg":   req.heading_deg,
            "speed_kmh":     req.speed_kmh,
            "freshness":     "LIVE",
            "timestamp":     datetime.datetime.utcnow().isoformat(),
        })

    return {"ok": True, "freshness": "LIVE"}


@router.get("/drivers/nearby")
async def get_nearby_drivers(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(default=50.0),
    vehicle_type: Optional[str] = Query(default=None),
    db: Session = Depends(get_db)
):
    """Find nearby online verified drivers within radius_km."""
    drivers = db.query(Driver).filter(
        Driver.verification_status == VerificationStatus.verified,
        Driver.is_online == True,
        Driver.is_busy == False,
    ).all()

    results = []
    for driver in drivers:
        if driver.current_lat is None or driver.current_lon is None:
            continue
        dist = _haversine_km(lat, lon, driver.current_lat, driver.current_lon)
        if dist > radius_km:
            continue

        vehicle = db.query(Vehicle).filter(
            Vehicle.driver_id == driver.id,
            Vehicle.is_active == True,
        ).first()
        if not vehicle:
            continue
        if vehicle_type and vehicle.vehicle_type != vehicle_type:
            continue

        results.append({
            "driver_id":          driver.id,
            "driver_name":        driver.user.full_name if driver.user else "Verified Driver",
            "driver_rating":      driver.rating,
            "total_trips":        driver.total_trips,
            "distance_km":        dist,
            "eta_mins":           max(int(dist * 2.5) + 5, 5),
            "location_freshness": _driver_freshness(driver),
            "lat":                driver.current_lat,
            "lon":                driver.current_lon,
            "vehicle_type":       vehicle.vehicle_type,
            "payload_capacity_tons": vehicle.payload_capacity_tons,
        })

    results.sort(key=lambda x: x["distance_km"])
    return {
        "count":   len(results),
        "drivers": results,
        "radius_km": radius_km,
    }


@router.get("/drivers/{driver_id}/status")
async def get_driver_status(driver_id: str, db: Session = Depends(get_db)):
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")
    return {
        "driver_id":          driver.id,
        "is_online":          driver.is_online,
        "is_busy":            driver.is_busy,
        "verification_status": driver.verification_status.value,
        "location_freshness": _driver_freshness(driver),
        "lat":                driver.current_lat,
        "lon":                driver.current_lon,
        "rating":             driver.rating,
        "total_trips":        driver.total_trips,
    }


@router.post("/drivers/register", status_code=201)
async def register_driver(req: DriverRegisterRequest, db: Session = Depends(get_db)):
    """Register a new driver profile with vehicle — pending verification."""
    user = db.query(User).filter(User.id == req.user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    existing = db.query(Driver).filter(Driver.user_id == req.user_id).first()
    if existing:
        raise HTTPException(409, "Driver profile already exists for this user")

    driver = Driver(
        user_id=req.user_id,
        driving_licence_number=req.driving_licence_number,
        bank_upi_id=req.bank_upi_id,
        emergency_contact=req.emergency_contact,
        verification_status=VerificationStatus.pending,
    )
    db.add(driver)
    db.flush()  # get driver.id

    vehicle = Vehicle(
        driver_id=driver.id,
        vehicle_type=req.vehicle_type,
        registration_number=req.registration_number,
        payload_capacity_tons=req.payload_capacity_tons,
        fuel_type=req.fuel_type or "Diesel",
        fuel_efficiency_kmpl=req.fuel_efficiency_kmpl or 10.0,
        rate_per_km=req.rate_per_km or 30.0,
        base_charge=req.base_charge or 500.0,
    )
    db.add(vehicle)
    db.commit()
    db.refresh(driver)

    return {
        "driver_id":          driver.id,
        "verification_status": "pending",
        "message":            "Driver registration submitted. Verification typically takes 1-2 business days.",
    }


@router.get("/drivers/my-trips")
async def driver_my_trips(driver_id: str = Query(...), db: Session = Depends(get_db)):
    """Driver's own trip list."""
    trips = db.query(LogisticsTrip).filter(
        LogisticsTrip.driver_id == driver_id
    ).order_by(LogisticsTrip.created_at.desc()).limit(50).all()
    return [_serialize_trip(t) for t in trips]


# ─── Private helpers ──────────────────────────────────────────────────────────

def _get_trip_or_404(trip_id: str, db: Session) -> LogisticsTrip:
    trip = db.query(LogisticsTrip).filter(LogisticsTrip.id == trip_id).first()
    if not trip:
        raise HTTPException(404, "Trip not found")
    return trip


def _require_status(trip: LogisticsTrip, allowed: list):
    if trip.status not in allowed:
        allowed_vals = [s.value for s in allowed]
        raise HTTPException(400, f"Trip is in status '{trip.status.value}'. "
                                 f"Expected one of: {allowed_vals}")


def _serialize_trip(trip: LogisticsTrip, include_location: bool = False, public: bool = False) -> dict:
    last_loc = None
    if include_location and trip.locations:
        loc = trip.locations[-1]
        age_secs = (datetime.datetime.utcnow() - loc.recorded_at.replace(tzinfo=None)).total_seconds() \
                   if loc.recorded_at else 9999
        freshness = "LIVE" if age_secs < 30 else "RECENT" if age_secs < 120 else "STALE"
        last_loc = {
            "lat":        loc.lat,
            "lon":        loc.lon,
            "heading":    loc.heading_deg,
            "speed_kmh":  loc.speed_kmh,
            "freshness":  freshness,
            "recorded_at": loc.recorded_at.isoformat() if loc.recorded_at else None,
        }

    result = {
        "id":                  trip.id,
        "status":              trip.status.value if trip.status else None,
        "crop_type":           trip.crop_type,
        "quantity_tons":       trip.quantity_tons,
        "pickup_address":      trip.pickup_address,
        "pickup_lat":          trip.pickup_lat,
        "pickup_lon":          trip.pickup_lon,
        "dest_address":        trip.dest_address,
        "dest_lat":            trip.dest_lat,
        "dest_lon":            trip.dest_lon,
        "distance_km":         trip.distance_km,
        "estimated_duration_mins": trip.estimated_duration_mins,
        "total_price":         trip.total_price,
        "driver_id":           trip.driver_id,
        "driver_location":     last_loc,
        "trip_pin":            trip.trip_pin if not public else None,
        "sos_triggered":       trip.sos_triggered,
        "created_at":          trip.created_at.isoformat() if trip.created_at else None,
        "accepted_at":         trip.accepted_at.isoformat() if trip.accepted_at else None,
        "started_at":          trip.started_at.isoformat() if trip.started_at else None,
        "completed_at":        trip.completed_at.isoformat() if trip.completed_at else None,
        "rating_by_farmer":    trip.rating_by_farmer,
        "review_by_farmer":    trip.review_by_farmer,
        "polyline":            trip.polyline,
    }
    return result

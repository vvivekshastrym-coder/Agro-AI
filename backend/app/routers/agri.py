from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from ..database.connection import get_db
from ..database.models import Farm, User
from ..auth.deps import get_current_user

router = APIRouter()


def _unavailable(feature: str, blocker: str) -> dict:
    """Truthful 'not available' contract. No placeholder or example values are ever returned."""
    return {
        "available": False,
        "status": "UNAVAILABLE",
        "feature": feature,
        "reason": "not_connected",
        "message": f"{feature} is not available yet: {blocker}",
    }


from pydantic import BaseModel
import uuid
from ..database.models import FarmCrop

class FarmCreateRequest(BaseModel):
    village: str
    district: Optional[str] = None
    state: Optional[str] = "Karnataka"
    pincode: Optional[str] = None
    total_acres: float
    owned_acres: Optional[float] = None
    leased_acres: Optional[float] = 0.0
    irrigation_method: Optional[str] = None
    soil_type: Optional[str] = None
    water_source: Optional[str] = None
    crop_name: Optional[str] = None

class FarmCropCreateRequest(BaseModel):
    crop_name: str
    crop_variety: Optional[str] = None
    season: Optional[str] = "Kharif"
    area_acres: float

# --- Farm profiles (scoped to the authenticated caller) -------------------------------
@router.get("/farms")
async def list_caller_farms(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    farms = db.query(Farm).filter(Farm.user_id == user.id).all()
    res = []
    for f in farms:
        crops = db.query(FarmCrop).filter(FarmCrop.farm_id == f.id).all()
        res.append({
            "id": f.id,
            "village": f.village,
            "district": f.district,
            "state": f.state,
            "total_acres": f.total_acres,
            "soil_type": f.soil_type,
            "irrigation_method": f.irrigation_method,
            "crops": [{"id": c.id, "crop_name": c.crop_name, "area_acres": c.area_acres} for c in crops]
        })
    return {"farms": res}

@router.post("/farms")
async def create_farm(req: FarmCreateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    farm = Farm(
        id=str(uuid.uuid4()),
        user_id=user.id,
        village=req.village,
        district=req.district or req.village,
        state=req.state or "Karnataka",
        pincode=req.pincode or "",
        total_acres=req.total_acres,
        owned_acres=req.owned_acres or req.total_acres,
        leased_acres=req.leased_acres or 0.0,
        irrigation_method=req.irrigation_method,
        soil_type=req.soil_type,
        water_source=req.water_source
    )
    db.add(farm)
    db.commit()
    db.refresh(farm)

    if req.crop_name:
        crop = FarmCrop(
            id=str(uuid.uuid4()),
            farm_id=farm.id,
            crop_name=req.crop_name,
            season="Current",
            area_acres=req.total_acres
        )
        db.add(crop)
        db.commit()

    return {"status": "success", "farm_id": farm.id, "village": farm.village, "total_acres": farm.total_acres}

@router.get("/farms/{farmer_id}")
async def get_farmer_farms(farmer_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if farmer_id != user.id and farmer_id != "me":
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Not permitted."}})
    farms = db.query(Farm).filter(Farm.user_id == user.id).all()
    return {"farms": farms}

@router.post("/farms/{farm_id}/crops")
async def add_crop_to_farm(farm_id: str, req: FarmCropCreateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    farm = db.query(Farm).filter(Farm.id == farm_id, Farm.user_id == user.id).first()
    if not farm:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Farm not found."}})
    crop = FarmCrop(
        id=str(uuid.uuid4()),
        farm_id=farm.id,
        crop_name=req.crop_name,
        crop_variety=req.crop_variety,
        season=req.season or "Kharif",
        area_acres=req.area_acres
    )
    db.add(crop)
    db.commit()
    return {"status": "success", "crop_id": crop.id, "crop_name": crop.crop_name}



# --- Modules below previously returned hardcoded example data (invented soil results,
#     credit score, insurance policy, carbon payout, passport records). They now report
#     truthfully that no real data source is connected. --------------------------------
@router.get("/soil/report")
async def get_soil_report(user: User = Depends(get_current_user)):
    return _unavailable("Soil report", "no soil-test records or laboratory integration exist for this account")


@router.get("/credit/profile")
async def get_credit_profile(user: User = Depends(get_current_user)):
    return _unavailable("Credit information", "no authorized lender or credit-bureau integration is configured")


@router.get("/carbon/summary")
async def get_carbon_summary(user: User = Depends(get_current_user)):
    return _unavailable("Carbon estimate", "no recorded farming practices or verified calculation method exist for this account")


@router.get("/insurance/status")
async def get_insurance_status(user: User = Depends(get_current_user)):
    return _unavailable("Crop insurance status", "no insurer or PMFBY integration is configured and no policy is recorded")


@router.get("/passport/trace")
async def get_farm_passport(user: User = Depends(get_current_user)):
    return _unavailable("Farm passport", "no recorded farm activity events exist for this account")

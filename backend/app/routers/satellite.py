from fastapi import APIRouter
import datetime

router = APIRouter()

@router.get("/ndvi")
async def get_ndvi_analysis(lat: float = 12.9716, lon: float = 77.5946):
    return {
        "ndvi_mean": 0.74,
        "health_category": "Vigorous Vegetation",
        "last_satellite_pass": datetime.date.today().isoformat(),
        "provider": "Sentinel-2 L2A European Space Agency"
    }

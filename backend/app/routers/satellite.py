from fastapi import APIRouter, Depends

from ..auth.deps import get_current_user
from ..database.models import User

router = APIRouter()


@router.get("/ndvi")
async def get_ndvi_analysis(user: User = Depends(get_current_user)):
    """No satellite provider is integrated, so no NDVI is reported (it was previously a constant 0.74)."""
    return {
        "available": False,
        "status": "UNAVAILABLE",
        "feature": "Satellite NDVI",
        "reason": "not_connected",
        "message": "Satellite monitoring is not available yet: no imagery provider or registered field boundary is configured.",
    }

from fastapi import APIRouter
from ..model_router import get_active_model

router = APIRouter()

@router.get("/model")
async def get_model_info():
    """
    Retourneert het actieve AI-model van Loesoe.
    """
    model = get_active_model()
    return {"active_model": model, "status": "ok"}

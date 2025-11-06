from fastapi import APIRouter, HTTPException
from ..model_router import generate_response

router = APIRouter()

@router.post("/chat")
async def chat_endpoint(data: dict):
    """
    Ontvangt een prompt en retourneert AI-antwoord.
    """
    prompt = data.get("prompt")
    if not prompt:
        raise HTTPException(status_code=400, detail="Geen prompt opgegeven.")

    result = generate_response(prompt)
    return result

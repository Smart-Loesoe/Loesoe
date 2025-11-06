from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["persona"])

class Persona(BaseModel):
    tone: str = "casual"
    verbosity: str = "normaal"
    emojis: bool = True
    mode: str = "straat"  # of "jip-en-janneke", "zakelijk"

_current = Persona()

@router.get("/persona")
def get_persona():
    return _current

@router.post("/persona")
def set_persona(p: Persona):
    global _current
    _current = p
    return {"ok": True, "persona": _current}

@router.patch("/persona")
def patch_persona(p: Persona):
    global _current
    data = _current.model_dump()
    for k, v in p.model_dump().items():
        if v is not None:
            data[k] = v
    _current = Persona(**data)
    return {"ok": True, "persona": _current}

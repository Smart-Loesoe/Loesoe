# loesoe/api/dev.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from ..dev.assistant import generate, review_code

router = APIRouter()

class GenerateSpec(BaseModel):
    goal: Optional[str] = None
    inputs: Optional[Dict[str, str]] = None
    outputs: Optional[Dict[str, str]] = None
    rules: Optional[list[str]] = None
    examples: Optional[list[dict]] = None
    limits: Optional[list[str]] = None
    name: Optional[str] = None
    persona: Optional[Dict[str, Any]] = None
    template: Optional[str] = "function"
    mode: Optional[str] = "tests-eerst"

class ReviewSpec(BaseModel):
    code: str

@router.post("/generate")
def post_generate(spec: GenerateSpec):
    if not spec.goal or not spec.inputs or not spec.outputs:
        raise HTTPException(status_code=400, detail="goal, inputs en outputs zijn verplicht.")
    persona = spec.persona or {"language": "nl", "verbosity": "kort"}
    try:
        payload = generate(spec.__dict__, persona=persona)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return payload

@router.post("/review")
def post_review(body: ReviewSpec):
    if not body.code or not body.code.strip():
        raise HTTPException(status_code=400, detail="code is verplicht.")
    return review_code(body.code)

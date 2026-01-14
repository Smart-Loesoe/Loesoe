# api/auth/routes.py
from fastapi import APIRouter, HTTPException, status, Header, Request
from pydantic import BaseModel, EmailStr, ValidationError
from typing import Optional, Dict
from datetime import datetime, timedelta
from jose import jwt, JWTError
import os
from types import SimpleNamespace
from urllib.parse import parse_qs

router = APIRouter()

# === Config ===
AUTH_SECRET = os.getenv(
    "AUTH_SECRET",
    "CHANGE_ME_SUPER_SECRET_AT_LEAST_64_CHARS_LONG________________________________",
)
ALGO = "HS256"
ACCESS_MIN = 60 * 24  # 24 uur

# === In-memory storage (demo users) ===
_users: Dict[str, Dict] = {
    "richard@test.com": {
        "id": 1,
        "name": "Richard",
        "email": "richard@test.com",
        # DEMO: plaintext password – NIET voor productie
        "password": "Test1234!",
    },
    "richard@example.com": {
        "id": 2,
        "name": "Richard",
        "email": "richard@example.com",
        # zelfde wachtwoord voor het gemak
        "password": "Test1234!",
    },
}

# === Schemas ===
class RegisterIn(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


# === Helpers ===
def create_token(payload: dict, minutes: int = ACCESS_MIN) -> str:
    to_encode = payload.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(minutes=minutes)
    return jwt.encode(to_encode, AUTH_SECRET, algorithm=ALGO)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, AUTH_SECRET, algorithms=[ALGO])
    except JWTError:
        # ❌ Geen demo-fallback meer: gewoon 401
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


def get_user_from_bearer(authorization: Optional[str]) -> Dict:
    """
    Ondersteunt:
    - 'Bearer <token>'
    - '<token>'
    """

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing token",
        )

    auth = authorization.strip()
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
    else:
        token = auth

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing token",
        )

    data = decode_token(token)
    email = data.get("email")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = _users.get(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


# Dependency – voor /dashboard, /me, etc.
async def get_current_user(
    authorization: Optional[str] = Header(None),
) -> SimpleNamespace:
    user = get_user_from_bearer(authorization)
    return SimpleNamespace(
        id=int(user["id"]), name=str(user["name"]), email=user["email"]
    )


# === Routes ===
@router.post("/register", summary="Register")
def register(inp: RegisterIn):
    if inp.email in _users:
        raise HTTPException(status_code=409, detail="User exists")

    _users[inp.email] = {
        "id": len(_users) + 1,
        "name": inp.name,
        "email": inp.email,
        "password": inp.password,
    }
    return {"ok": True}


async def _login_core(request: Request) -> TokenOut:
    """
    Gedeelde login-logica voor /login en /auth/login
    """
    content_type = (request.headers.get("content-type") or "").lower()
    raw = (await request.body()).decode(errors="ignore")

    data: Dict[str, str] = {}

    if "application/json" in content_type:
        data = await request.json()
    else:
        parsed = parse_qs(raw)
        data = {k: v[0] for k, v in parsed.items()}

    # username -> email fallback
    if "email" not in data and "username" in data:
        data["email"] = data["username"]

    try:
        inp = LoginIn(**data)
    except ValidationError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid login fields",
        )

    user = _users.get(inp.email)
    if not user or user["password"] != inp.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = create_token(
        {"email": inp.email, "id": user["id"], "name": user["name"]}
    )
    return TokenOut(access_token=token, token_type="bearer")


@router.post("/login", response_model=TokenOut, summary="Login (root)")
async def login_root(request: Request):
    return await _login_core(request)


@router.post(
    "/auth/login", response_model=TokenOut, summary="Login (compatibility)"
)
async def login_compat(request: Request):
    """
    Compatibel endpoint voor bestaande frontend die naar /auth/login post.
    """
    return await _login_core(request)


@router.get("/me")
def me(authorization: Optional[str] = Header(None)):
    u = get_user_from_bearer(authorization)
    return {"id": u["id"], "name": u["name"], "email": u["email"]}

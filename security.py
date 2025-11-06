# C:\Loesoe\loesoe\core\security.py
from __future__ import annotations
import os, time
from typing import Any, Dict
from dotenv import load_dotenv
from jose import jwt, JWTError
from passlib.context import CryptContext

load_dotenv(override=True)

ALGORITHM = "HS256"
AUTH_SECRET = os.getenv("AUTH_SECRET", "")
if not AUTH_SECRET or len(AUTH_SECRET) < 32:
    raise RuntimeError("AUTH_SECRET must be set (>=32 chars)")

ACCESS_TTL = int(os.getenv("ACCESS_TOKEN_TTL", "900"))
REFRESH_TTL = int(os.getenv("REFRESH_TOKEN_TTL", "2592000"))

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(pw: str) -> str:
    return pwd_ctx.hash(pw)

def verify_password(pw: str, hashed: str) -> bool:
    return pwd_ctx.verify(pw, hashed)

def create_token(sub: str, ttl: int) -> str:
    now = int(time.time())
    payload = {"sub": sub, "iat": now, "exp": now + ttl}
    return jwt.encode(payload, AUTH_SECRET, algorithm=ALGORITHM)

def create_access_token(sub: str) -> str:
    return create_token(sub, ACCESS_TTL)

def create_refresh_token(sub: str) -> str:
    return create_token(sub, REFRESH_TTL)

def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, AUTH_SECRET, algorithms=[ALGORITHM])

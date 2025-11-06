from __future__ import annotations
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy import String, select
from sqlalchemy.orm import Mapped, mapped_column, declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# --- Config
AUTH_SECRET = os.getenv("AUTH_SECRET", "")
if not AUTH_SECRET or len(AUTH_SECRET) < 32:
    raise RuntimeError("AUTH_SECRET must be set (>=32 chars)")

# Support both names; prefer ACCESS_TOKEN_EXPIRE_MINUTES
_access_minutes = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")
_access_ttl_fallback = os.getenv("ACCESS_TOKEN_TTL")  # legacy
if _access_minutes is not None:
    ACCESS_TOKEN_EXPIRE_MINUTES = int(_access_minutes)
elif _access_ttl_fallback is not None:
    ACCESS_TOKEN_EXPIRE_MINUTES = int(_access_ttl_fallback)
else:
    ACCESS_TOKEN_EXPIRE_MINUTES = 15

ALGORITHM = os.getenv("JWT_ALG", "HS256")

DATABASE_URL = os.getenv("DATABASE_URL") or ""
if not DATABASE_URL.startswith("postgresql+asyncpg://"):
    raise RuntimeError("DATABASE_URL must use postgresql+asyncpg")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

router = APIRouter(prefix="/auth", tags=["auth"])
Base = declarative_base()

# --- DB setup
engine = create_async_engine(DATABASE_URL, future=True, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session

# --- Models
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[Optional[str]] = mapped_column(String(120), default=None)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

# --- Schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: Optional[str] = None

# --- Helpers
def create_access_token(sub: str, minutes: int | None = None) -> str:
    ttl = minutes if minutes is not None else ACCESS_TOKEN_EXPIRE_MINUTES
    expire = datetime.utcnow() + timedelta(minutes=ttl)
    to_encode = {"sub": sub, "exp": expire}
    return jwt.encode(to_encode, AUTH_SECRET, algorithm=ALGORITHM)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def hash_password(plain: str) -> str:
    # bcrypt max 72 bytes – expliciet afvangen
    if len(plain.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Password too long (max 72 bytes)")
    return pwd_context.hash(plain)

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    creds_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, AUTH_SECRET, algorithms=[ALGORITHM])
        sub: str = payload.get("sub")
        if sub is None:
            raise creds_exc
    except JWTError:
        raise creds_exc

    result = await db.execute(select(User).where(User.email == sub))
    user = result.scalar_one_or_none()
    if not user:
        raise creds_exc
    return user

# --- Lifecycle
@router.on_event("startup")
async def _startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# --- Routes
@router.post("/register", response_model=UserOut)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.email == payload.email.lower()))
    exists = res.scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        name=payload.name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserOut(id=user.id, email=user.email, name=user.name)

@router.post("/login", response_model=TokenOut)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.email == form.username.lower()))
    user = res.scalar_one_or_none()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    token = create_access_token(sub=user.email)
    return TokenOut(access_token=token)

@router.get("/me", response_model=UserOut)
async def me(current: User = Depends(get_current_user)):
    return UserOut(id=current.id, email=current.email, name=current.name)

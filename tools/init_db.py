# tools/init_db.py
import os, sys, asyncio, types, importlib
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine

APP = Path("/app")
PKG = APP / "loesoe"              # jouw package root: /app/loesoe

# Zorg dat beide paden importeerbaar zijn
for p in (str(PKG), str(APP)):
    if p not in sys.path:
        sys.path.insert(0, p)

print("[init_db] sys.path head:", sys.path[:3])

# --- Maak alias: 'api' == 'loesoe.api' ---
try:
    loesoe_api = importlib.import_module("loesoe.api")
    sys.modules["api"] = loesoe_api
    sys.modules.setdefault("api.auth", importlib.import_module("loesoe.api.auth"))
    print("[init_db] Alias gezet: api -> loesoe.api (OK)")
except Exception as e:
    print(f"[init_db] Kon alias niet zetten: {e}")

# --- Shim: 'api.auth.database' -> 'api.database' (zoals je app doet) ---
try:
    import api.database as _db
    sys.modules["api.auth.database"] = _db
    print("[init_db] Shim: api.auth.database -> api.database (OK)")
except Exception as e:
    print(f"[init_db] Shim mislukte: {e}")

# --- Importeer nu de echte Base waar User staat ---
Base = None
errors = []
for path in (
    "api.auth.models",          # <- dit willen we
    "loesoe.api.auth.models",   # fallback
    "api.models",
):
    try:
        mod = importlib.import_module(path)
        Base = getattr(mod, "Base")
        print(f"[init_db] Using Base from: {path}")
        break
    except Exception as e:
        errors.append(f"{path}: {e!r}")

if Base is None:
    raise RuntimeError("Kon Base niet importeren:\n" + "\n".join(errors))

async def main():
    db_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(db_url, future=True, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("✅ DB schema aangemaakt (inclusief users)")

if __name__ == "__main__":
    asyncio.run(main())

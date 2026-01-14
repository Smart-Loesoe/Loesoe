import os
import asyncio
import asyncpg
from openai import OpenAI

DATABASE_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("EMBEDDING_MODEL") or "text-embedding-3-small"

if not DATABASE_URL:
    raise SystemExit("DATABASE_URL missing")
if not OPENAI_API_KEY:
    raise SystemExit("OPENAI_API_KEY missing")

client = OpenAI(api_key=OPENAI_API_KEY)

async def main():
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch(
        "SELECT id, content FROM public.memory_embeddings WHERE embedding IS NULL ORDER BY id"
    )
    print("rows_to_backfill:", len(rows))

    for r in rows:
        emb = client.embeddings.create(model=MODEL, input=r["content"]).data[0].embedding
        emb_txt = "[" + ",".join(str(x) for x in emb) + "]"
        await conn.execute(
            "UPDATE public.memory_embeddings SET embedding = $1::vector WHERE id = $2",
            emb_txt, r["id"]
        )
        print("backfilled id", r["id"])

    await conn.close()

asyncio.run(main())

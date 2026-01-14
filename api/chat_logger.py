# api/chat_logger.py

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# Standaard pad binnen de container
DEFAULT_LOG_DIR = "/app/logboek/chat_history"

LOG_DIR = Path(os.getenv("LOESOE_CHAT_LOG_DIR", DEFAULT_LOG_DIR))
LOG_FILE = LOG_DIR / "chat_history.jsonl"


def log_chat(message: str, reply: str, meta: Dict[str, Any] | None = None) -> None:
    """
    Log één chat-bericht als JSON-regel in chat_history.jsonl
    """
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "message": message,
            "reply": reply,
            "meta": meta or {},
        }

        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    except Exception as e:
        # Fout bij loggen mag de API nooit laten crashen
        print(f"[chat_logger] Failed to log chat: {e}")

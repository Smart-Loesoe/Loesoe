import base64, hmac, hashlib, json, time
from typing import Optional

class UrlSigner:
    def __init__(self, secret: str):
        if not secret or len(secret) < 16:
            raise ValueError("SIGNER_SECRET too short")
        self.key = secret.encode("utf-8")

    def _sig(self, payload_bytes: bytes) -> str:
        mac = hmac.new(self.key, payload_bytes, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(mac).decode().rstrip("=")

    def sign(self, filename: str, session_id: str, ttl: int) -> str:
        exp = int(time.time()) + max(1, int(ttl))
        payload = {"f": filename, "s": session_id, "e": exp}
        raw = json.dumps(payload, separators=(',', ':')).encode()
        sig = self._sig(raw)
        token = base64.urlsafe_b64encode(raw).decode().rstrip("=") + "." + sig
        return token

    def verify(self, token: str) -> Optional[dict]:
        try:
            raw_b64, sig = token.split(".", 1)
            pad = "=" * (-len(raw_b64) % 4)
            raw = base64.urlsafe_b64decode(raw_b64 + pad)
            expected = self._sig(raw)
            if not hmac.compare_digest(expected, sig):
                return None
            payload = json.loads(raw.decode())
            if int(payload.get("e", 0)) < int(time.time()):
                return None
            return payload
        except Exception:
            return None

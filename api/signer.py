# api/signer.py
import hmac, hashlib, time, base64
from typing import Tuple

def sign(id: str, secret: str, ttl_seconds: int) -> str:
    exp = int(time.time()) + ttl_seconds
    payload = f"{id}.{exp}".encode()
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    token = base64.urlsafe_b64encode(payload + b"." + sig).decode().rstrip("=")
    return token

def verify(token: str, secret: str) -> Tuple[str, int]:
    try:
        pad = "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(token + pad)
        id_b, exp_b, sig = raw.split(b".", 2)
        payload = id_b + b"." + exp_b
        exp = int(exp_b.decode())
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, sig):
            raise ValueError("invalid_signature")
        if int(time.time()) > exp:
            raise ValueError("expired")
        return id_b.decode(), exp
    except ValueError as e:
        raise
    except Exception:
        raise ValueError("malformed")

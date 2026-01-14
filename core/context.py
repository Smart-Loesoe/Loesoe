CODE_HINTS = {"script","code","functie","roadmap","plan","endpoint","api","tests"}
KIDS_HINTS = {"kind","8 jaar","jip","jip en janneke","simpel"}

def detect_context(user_text: str, endpoint: str = ""):
    t = (user_text or "").lower()
    if any(w in t for w in CODE_HINTS) or endpoint.startswith("/dev"):
        return {"intent":"code","confidence":0.8}
    if any(w in t for w in KIDS_HINTS):
        return {"intent":"kids","confidence":0.8}
    return {"intent":"chat","confidence":0.6}

# api/auth/utils.py
def normalize_user(u):
    return {
        "id": getattr(u, "id", None) or getattr(u, "user_id", None) or (u.get("id") if isinstance(u, dict) else None),
        "name": getattr(u, "name", None) or getattr(u, "username", None) or getattr(u, "email", None)
                or (u.get("name") if isinstance(u, dict) else None)
                or (u.get("username") if isinstance(u, dict) else None)
                or (u.get("email") if isinstance(u, dict) else None),
        "email": getattr(u, "email", None) or (u.get("email") if isinstance(u, dict) else None),
    }

import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
GROUP_CHAT_ID = os.environ.get("GROUP_CHAT_ID", "")
try:
    _gid = GROUP_CHAT_ID.strip()
    GROUP_CHAT_ID_INT = int(_gid) if _gid else None
except ValueError:
    GROUP_CHAT_ID_INT = None

_ADMIN = os.environ.get("ADMIN_USERNAMES", "")
ADMIN_USERNAMES = {u.strip().lower().lstrip("@") for u in _ADMIN.split(",") if u.strip()}


def is_admin(username: str | None, user_id: int | None) -> bool:
    if not username and not user_id:
        return False
    if username:
        if username.lower().lstrip("@") in ADMIN_USERNAMES:
            return True
    return False

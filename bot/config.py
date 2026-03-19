import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
GROUP_CHAT_ID = os.environ.get("GROUP_CHAT_ID", "")
try:
    _gid = GROUP_CHAT_ID.strip()
    GROUP_CHAT_ID_INT = int(_gid) if _gid else None
except ValueError:
    GROUP_CHAT_ID_INT = None

# ID темы (топика) в супергруппе с темами. Если задан — опрос и сообщения уходят в эту тему.
_GROUP_TOPIC = os.environ.get("GROUP_TOPIC_ID", "").strip()
GROUP_TOPIC_ID = int(_GROUP_TOPIC) if _GROUP_TOPIC else None

_ADMIN = os.environ.get("ADMIN_USERNAMES", "")
ADMIN_USERNAMES: set[str] = set()
ADMIN_IDS: set[int] = set()

# ADMIN_USERNAMES допускает два формата через запятую:
# - "username" (или "@username") -> проверка по Telegram username
# - "123456789" -> проверка по Telegram user_id
for raw in _ADMIN.split(","):
    token = raw.strip()
    if not token:
        continue
    token = token.lstrip("@").strip()
    if token.isdigit():
        # user_id обычно помещается в int без проблем, но страховка не помешает
        try:
            ADMIN_IDS.add(int(token))
        except (ValueError, OverflowError):
            pass
    else:
        ADMIN_USERNAMES.add(token.lower())


def is_admin(username: str | None, user_id: int | None) -> bool:
    if not username and not user_id:
        return False
    if user_id is not None and user_id in ADMIN_IDS:
        return True
    if username:
        return username.lower().lstrip("@") in ADMIN_USERNAMES
    return False

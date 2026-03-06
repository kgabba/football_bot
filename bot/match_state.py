"""
Глобальное состояние матча: голосование и капитанская дуэль.
Храним в JSON-файле, чтобы пережить перезапуск бота.
"""
import json
import os
from typing import Any

BOT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(BOT_DIR, "data", "match_state.json")


def _load() -> dict[str, Any]:
    if not os.path.exists(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=0)


def is_voting_active() -> bool:
    return _load().get("voting_active", False)


def get_voted_user_ids() -> set[int]:
    return set(_load().get("voted_user_ids", []))


def get_match_player_indices() -> list[int]:
    return list(_load().get("match_player_indices", []))


def get_match_user_ids() -> set[int]:
    """User_id тех, кто в списке на матч (проголосовали и есть в таблице)."""
    return set(_load().get("match_user_ids", []))


def has_match_players() -> bool:
    return len(get_match_player_indices()) >= 2


def start_voting() -> None:
    d = _load()
    d["voting_active"] = True
    d["voted_user_ids"] = []
    d["active_poll_id"] = None
    d.pop("match_player_indices", None)
    d.pop("match_user_ids", None)
    d.pop("draft", None)
    d.pop("captain_queue", None)
    _save(d)


def set_active_poll_id(poll_id: str) -> None:
    d = _load()
    d["active_poll_id"] = poll_id
    _save(d)


def get_active_poll_id() -> str | None:
    return _load().get("active_poll_id")


def add_vote(user_id: int) -> None:
    d = _load()
    ids = list(d.get("voted_user_ids", []))
    if user_id not in ids:
        ids.append(user_id)
    d["voted_user_ids"] = ids
    _save(d)


def finish_voting(match_player_indices: list[int], match_user_ids: list[int]) -> None:
    d = _load()
    d["voting_active"] = False
    d["match_player_indices"] = match_player_indices
    d["match_user_ids"] = match_user_ids
    d.pop("active_poll_id", None)
    d.pop("draft", None)
    d.pop("captain_queue", None)
    _save(d)


def get_draft() -> dict[str, Any] | None:
    return _load().get("draft")


def set_draft(
    captain1_uid: int,
    captain2_uid: int,
    red_captain_uid: int,
    blue_captain_uid: int,
    match_indices: list[int],
    captain1_sheet_index: int,
    captain2_sheet_index: int,
) -> None:
    """Старт драфта: капитаны исключены из пула, уже в своих командах."""
    red_sheet = captain1_sheet_index if red_captain_uid == captain1_uid else captain2_sheet_index
    blue_sheet = captain2_sheet_index if blue_captain_uid == captain2_uid else captain1_sheet_index
    pool = [i for i in match_indices if i not in (captain1_sheet_index, captain2_sheet_index)]
    d = _load()
    d["draft"] = {
        "captain1_uid": captain1_uid,
        "captain2_uid": captain2_uid,
        "red_captain_uid": red_captain_uid,
        "blue_captain_uid": blue_captain_uid,
        "red_team": [red_sheet],
        "blue_team": [blue_sheet],
        "pool": pool,
        "current_turn": "red",
        "messages": {},
    }
    _save(d)


def draft_pick(sheet_index: int, team: str) -> bool:
    """Вносит выбор в команду и переключает ход. team = 'red' | 'blue'. Возвращает True если драфт завершён."""
    d = _load()
    draft = d.get("draft")
    if not draft or sheet_index not in draft.get("pool", []):
        return False
    draft["pool"] = [i for i in draft["pool"] if i != sheet_index]
    draft[f"{team}_team"].append(sheet_index)
    draft["current_turn"] = "blue" if team == "red" else "red"
    _save(d)
    return len(draft["pool"]) == 0


def draft_get_state() -> dict[str, Any] | None:
    return _load().get("draft")


def draft_add_message(user_id: int, message_id: int) -> None:
    d = _load()
    draft = d.get("draft")
    if not draft:
        return
    msgs = draft.get("messages") or {}
    msgs[str(user_id)] = message_id
    draft["messages"] = msgs
    _save(d)


def clear_draft() -> None:
    d = _load()
    d.pop("draft", None)
    d.pop("captain_queue", None)
    _save(d)


def get_captain_queue() -> list[int]:
    return list(_load().get("captain_queue", []))


def add_captain_candidate(user_id: int) -> list[int]:
    """Добавляет в очередь капитанов. Возвращает текущую очередь (до 2)."""
    d = _load()
    q = list(d.get("captain_queue", []))
    if user_id in q:
        return q
    q.append(user_id)
    d["captain_queue"] = q[:2]
    _save(d)
    return d["captain_queue"]


def reset_match() -> None:
    _save({})

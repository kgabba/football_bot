"""In-memory state per user for the lineup flow."""
from typing import Any

# user_id -> state dict
_user_state: dict[int, dict[str, Any]] = {}


def get_state(user_id: int) -> dict[str, Any]:
    if user_id not in _user_state:
        _user_state[user_id] = {
            "step": None,
            "selected": set(),
            "selected_list": [],
            "distribution": [],
            "current_index": 0,
        }
    return _user_state[user_id]


def clear_state(user_id: int) -> None:
    _user_state.pop(user_id, None)

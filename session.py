import fcntl
import json
import os
from datetime import datetime, timezone

SESSION_FILE = os.path.join(os.path.dirname(__file__), "session.json")
_EXPIRY_HOURS = 24


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_all(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            return json.load(f)
        except (json.JSONDecodeError, ValueError):
            return {}
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _write_all(path: str, data: dict) -> None:
    with open(path, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            json.dump(data, f, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def load_session(user_id: int) -> dict | None:
    data = _read_all(SESSION_FILE)
    return data.get(str(user_id))


def save_session(user_id: int, session: dict) -> None:
    data = _read_all(SESSION_FILE)
    data[str(user_id)] = session
    _write_all(SESSION_FILE, data)


def is_expired(session: dict) -> bool:
    last_active = session.get("last_active")
    if not last_active:
        return True
    delta = datetime.now(timezone.utc) - datetime.fromisoformat(last_active)
    return delta.total_seconds() > _EXPIRY_HOURS * 3600


def clear_session(user_id: int) -> None:
    data = _read_all(SESSION_FILE)
    data.pop(str(user_id), None)
    _write_all(SESSION_FILE, data)


def refresh_session(user_id: int) -> None:
    data = _read_all(SESSION_FILE)
    key = str(user_id)
    if key not in data:
        data[key] = {}
    data[key]["last_active"] = _now_iso()
    _write_all(SESSION_FILE, data)

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

import session as sm


@pytest.fixture(autouse=True)
def tmp_session_file(tmp_path):
    path = str(tmp_path / "session.json")
    with patch.object(sm, "SESSION_FILE", path):
        yield path


def _make_session(hours_old: float) -> dict:
    ts = datetime.now(timezone.utc) - timedelta(hours=hours_old)
    return {"last_active": ts.isoformat()}


# --- load_session ---

def test_load_session_new_user():
    assert sm.load_session(999) is None


def test_load_session_returns_saved():
    sm.save_session(1, {"last_active": "2026-01-01T00:00:00+00:00", "starting_point": None})
    result = sm.load_session(1)
    assert result is not None
    assert result["starting_point"] is None


# --- is_expired ---

def test_is_expired_fresh_session():
    session = _make_session(hours_old=0.5)
    assert sm.is_expired(session) is False


def test_is_expired_old_session():
    session = _make_session(hours_old=25)
    assert sm.is_expired(session) is True


def test_is_expired_exactly_boundary():
    session = _make_session(hours_old=24.01)
    assert sm.is_expired(session) is True


def test_is_expired_missing_last_active():
    assert sm.is_expired({}) is True


# --- refresh_session ---

def test_refresh_session_updates_last_active():
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat()
    sm.save_session(42, {"last_active": old_ts})

    sm.refresh_session(42)

    updated = sm.load_session(42)
    new_ts = datetime.fromisoformat(updated["last_active"])
    assert (datetime.now(timezone.utc) - new_ts).total_seconds() < 5


def test_refresh_session_creates_record_if_absent():
    sm.refresh_session(77)
    result = sm.load_session(77)
    assert result is not None
    assert "last_active" in result


# --- clear_session ---

def test_clear_session_removes_user():
    sm.save_session(5, _make_session(1))
    sm.clear_session(5)
    assert sm.load_session(5) is None


def test_clear_session_nonexistent_user_is_noop():
    sm.clear_session(9999)  # must not raise


def test_clear_session_leaves_other_users_intact():
    sm.save_session(1, _make_session(1))
    sm.save_session(2, _make_session(1))
    sm.clear_session(1)
    assert sm.load_session(1) is None
    assert sm.load_session(2) is not None

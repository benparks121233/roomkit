# tests/test_account_deletion.py
# Tests for DELETE /account cascade — all Supabase calls mocked.

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("TESTING", "1")

from app.api.routes import _designs, _invalidate_user_cache
from app.api.schemas import DesignResponse, SlotResult, StyleResult
from app.auth import get_current_user, _deleted_users, mark_user_deleted
from app.main import app

_USER_A = {"user_id": "user-aaa-111", "email": "a@test.com", "token": "tok-a"}
_USER_B = {"user_id": "user-bbb-222", "email": "b@test.com", "token": "tok-b"}

client = TestClient(app)


def _make_design(run_id: str, user_id: str) -> DesignResponse:
    return DesignResponse(
        run_id=run_id,
        room_type="bedroom",
        style=StyleResult(
            style_name="warm_minimalist",
            keywords=["wood"],
            mood="calm",
            confidence=0.9,
            fallback=False,
        ),
        target_budget=1000.0,
        total_spent=800.0,
        is_feasible=True,
        slots=[],
        user_id=user_id,
    )


@pytest.fixture(autouse=True)
def _clear():
    _designs.clear()
    _deleted_users.discard(_USER_B["user_id"])
    prev = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: _USER_B
    yield
    _designs.clear()
    _deleted_users.discard(_USER_B["user_id"])
    if prev is not None:
        app.dependency_overrides[get_current_user] = prev
    else:
        app.dependency_overrides.pop(get_current_user, None)


def _mock_supabase_table(table_name: str):
    mock = MagicMock()
    mock.select.return_value = mock
    mock.delete.return_value = mock
    mock.eq.return_value = mock
    mock.execute.return_value = MagicMock(data=[], count=0)
    return mock


class TestDeleteAccount:

    @patch("services.supabase_client.delete_user")
    @patch("services.supabase_client.get_client")
    def test_full_cascade_success(self, mock_get_client, mock_delete_user):
        mock_client = MagicMock()

        def table_factory(name):
            t = _mock_supabase_table(name)
            if name == "designs":
                designs_select = MagicMock()
                designs_select.eq.return_value = designs_select
                designs_select.execute.return_value = MagicMock(data=[{"run_id": "run-1"}])
                t.select.return_value = designs_select

                designs_delete = MagicMock()
                designs_delete.eq.return_value = designs_delete
                designs_delete.execute.return_value = MagicMock(data=[])
                t.delete.return_value = designs_delete
            return t

        mock_client.table.side_effect = table_factory
        mock_get_client.return_value = mock_client
        mock_delete_user.return_value = True

        _designs["run-1"] = _make_design("run-1", _USER_B["user_id"])

        resp = client.delete("/account")

        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] is True
        assert "auth_delete" in data["completed_steps"]
        assert "render_files" in data["completed_steps"]
        assert "designs" in data["completed_steps"]
        assert "cache_invalidate" in data["completed_steps"]
        assert data["failed_step"] is None
        assert "run-1" not in _designs

    @patch("services.supabase_client.delete_user")
    @patch("services.supabase_client.get_client")
    def test_auth_failure_returns_no_data_removed(self, mock_get_client, mock_delete_user):
        mock_client = MagicMock()
        designs_mock = _mock_supabase_table("designs")
        designs_select = MagicMock()
        designs_select.eq.return_value = designs_select
        designs_select.execute.return_value = MagicMock(data=[])
        designs_mock.select.return_value = designs_select
        mock_client.table.return_value = designs_mock
        mock_get_client.return_value = mock_client

        mock_delete_user.side_effect = RuntimeError("Supabase auth API down")

        resp = client.delete("/account")
        data = resp.json()

        assert data["deleted"] is False
        assert data["failed_step"] == "auth_delete"
        assert "No data was removed" in data["message"]
        assert "login credentials have been removed" not in data["message"]

    @patch("services.supabase_client.delete_user")
    @patch("services.supabase_client.get_client")
    def test_post_auth_failure_returns_credentials_removed(self, mock_get_client, mock_delete_user):
        mock_client = MagicMock()

        call_count = {"n": 0}
        def table_factory(name):
            t = _mock_supabase_table(name)
            if name == "designs":
                designs_select = MagicMock()
                designs_select.eq.return_value = designs_select
                designs_select.execute.return_value = MagicMock(data=[])
                t.select.return_value = designs_select

                designs_delete = MagicMock()
                designs_delete.eq.return_value = designs_delete
                designs_delete.execute.return_value = MagicMock(data=[])
                t.delete.return_value = designs_delete
            if name == "selections":
                t.delete.return_value = t
                t.eq.side_effect = RuntimeError("DB connection lost")
            return t

        mock_client.table.side_effect = table_factory
        mock_get_client.return_value = mock_client
        mock_delete_user.return_value = True

        resp = client.delete("/account")
        data = resp.json()

        assert data["deleted"] is False
        assert data["failed_step"] == "selections"
        assert "login credentials have been removed" in data["message"]

    @patch("services.supabase_client.delete_user")
    @patch("services.supabase_client.get_client")
    def test_client_unavailable(self, mock_get_client, mock_delete_user):
        mock_get_client.return_value = None

        resp = client.delete("/account")
        data = resp.json()

        assert data["deleted"] is False
        assert data["failed_step"] == "init"


class TestCacheInvalidation:

    def test_removes_matching_user(self):
        _designs["r1"] = _make_design("r1", "user-x")
        _designs["r2"] = _make_design("r2", "user-y")
        _designs["r3"] = _make_design("r3", "user-x")

        evicted = _invalidate_user_cache("user-x")

        assert evicted == 2
        assert "r1" not in _designs
        assert "r3" not in _designs
        assert "r2" in _designs

    def test_no_match_evicts_zero(self):
        _designs["r1"] = _make_design("r1", "user-x")
        evicted = _invalidate_user_cache("user-z")
        assert evicted == 0
        assert "r1" in _designs

    def test_cross_user_isolation(self):
        """Deleting user B's cache must not touch user A's entries."""
        _designs["a1"] = _make_design("a1", _USER_A["user_id"])
        _designs["b1"] = _make_design("b1", _USER_B["user_id"])

        _invalidate_user_cache(_USER_B["user_id"])

        assert "a1" in _designs
        assert "b1" not in _designs
        assert _designs["a1"].user_id == _USER_A["user_id"]


class TestDeletedUserBlocked:

    def test_mark_user_deleted_blocks_requests(self):
        """A deleted user's JWT must be rejected even if cryptographically valid."""
        app.dependency_overrides.pop(get_current_user, None)
        mark_user_deleted(_USER_B["user_id"])

        from unittest.mock import patch as _p

        fake_payload = {"sub": _USER_B["user_id"], "email": _USER_B["email"], "aud": "authenticated"}
        with _p("app.auth._get_jwks_client") as mock_jwks:
            mock_key = MagicMock()
            mock_jwks.return_value = mock_key
            mock_key.get_signing_key_from_jwt.return_value = MagicMock(key="fake")
            with _p("jwt.decode", return_value=fake_payload):
                resp = client.get(
                    "/design/nonexistent",
                    headers={"Authorization": "Bearer fake-token"},
                )

        assert resp.status_code == 401
        assert "deleted" in resp.json()["detail"].lower()

    def test_non_deleted_user_not_blocked(self):
        """Users not in the deleted set pass through normally."""
        assert _USER_A["user_id"] not in _deleted_users
        mark_user_deleted("some-other-id")
        assert _USER_B["user_id"] not in _deleted_users

    @patch("services.supabase_client.delete_user")
    @patch("services.supabase_client.get_client")
    def test_cascade_marks_user_deleted(self, mock_get_client, mock_delete_user):
        """After successful deletion, the user_id is in the blocked set."""
        mock_client = MagicMock()
        def table_factory(name):
            t = _mock_supabase_table(name)
            if name == "designs":
                sel = MagicMock()
                sel.eq.return_value = sel
                sel.execute.return_value = MagicMock(data=[])
                t.select.return_value = sel
                d = MagicMock()
                d.eq.return_value = d
                d.execute.return_value = MagicMock(data=[])
                t.delete.return_value = d
            return t
        mock_client.table.side_effect = table_factory
        mock_get_client.return_value = mock_client
        mock_delete_user.return_value = True

        assert _USER_B["user_id"] not in _deleted_users
        resp = client.delete("/account")
        assert resp.json()["deleted"] is True
        assert _USER_B["user_id"] in _deleted_users


class TestDeletedUserRedis:

    def test_mark_writes_to_redis(self):
        """mark_user_deleted should write to Redis when available."""
        mock_redis = MagicMock()
        with patch("app.auth.get_redis" if False else "services.redis_client.get_redis", return_value=mock_redis):
            from app.auth import _redis_mark_deleted
            _redis_mark_deleted("user-redis-1")
        mock_redis.setex.assert_called_once_with("deleted_user:user-redis-1", 7200, "1")

    def test_mark_survives_redis_failure(self):
        """If Redis is down, mark_user_deleted still adds to local set."""
        mock_redis = MagicMock()
        mock_redis.setex.side_effect = ConnectionError("redis down")
        with patch("services.redis_client.get_redis", return_value=mock_redis):
            mark_user_deleted("user-redis-2")
        assert "user-redis-2" in _deleted_users

    def test_redis_check_blocks_user(self):
        """A user marked in Redis (but not local set) should still be blocked."""
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 1
        from app.auth import _redis_is_deleted
        with patch("services.redis_client.get_redis", return_value=mock_redis):
            assert _redis_is_deleted("user-redis-3") is True
        mock_redis.exists.assert_called_once_with("deleted_user:user-redis-3")

    def test_redis_unavailable_falls_through(self):
        """When Redis is None, _redis_is_deleted returns False (local set is fallback)."""
        from app.auth import _redis_is_deleted
        with patch("services.redis_client.get_redis", return_value=None):
            assert _redis_is_deleted("user-redis-4") is False

    def test_full_flow_checks_redis(self):
        """get_current_user should block a user found in Redis but not local set."""
        uid = "user-redis-5"
        assert uid not in _deleted_users

        app.dependency_overrides.pop(get_current_user, None)
        from unittest.mock import patch as _p

        fake_payload = {"sub": uid, "email": "r@test.com", "aud": "authenticated"}
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 1

        with _p("app.auth._get_jwks_client") as mock_jwks:
            mock_key = MagicMock()
            mock_jwks.return_value = mock_key
            mock_key.get_signing_key_from_jwt.return_value = MagicMock(key="fake")
            with _p("jwt.decode", return_value=fake_payload):
                with _p("services.redis_client.get_redis", return_value=mock_redis):
                    resp = client.get(
                        "/design/nonexistent",
                        headers={"Authorization": "Bearer fake-token"},
                    )

        assert resp.status_code == 401
        assert "deleted" in resp.json()["detail"].lower()
        # Should have cached locally after Redis hit
        assert uid in _deleted_users

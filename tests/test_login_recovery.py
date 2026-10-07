"""A damaged account record must not turn login into a 500, and the server
operator can recover access with scripts/maven-users."""

import asyncio
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from tests.test_set_admin import _fresh_auth_manager

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("record", [
    {"password_hash": "not-a-bcrypt-hash"},
    {"password_hash": None},
    {},
])
def test_bad_hash_fails_closed_instead_of_raising(tmp_path, record):
    import bcrypt

    auth_mod, mgr = _fresh_auth_manager(tmp_path)
    # The real bcrypt check, which raises on a bad hash (the helper stubs it).
    auth_mod._verify_password = lambda pw, hashed: bcrypt.checkpw(pw.encode(), hashed.encode())
    mgr._config["users"] = {"admin": {"is_admin": True, **record}}

    assert mgr.verify_password("admin", "anything") is False
    assert mgr.account_problems() == [
        {"username": "admin", "problem": "missing or invalid password hash"}]


def test_login_route_returns_401_not_500_for_a_bad_hash(tmp_path):
    import bcrypt
    from routes.auth_routes import LoginRequest, setup_auth_routes

    auth_mod, mgr = _fresh_auth_manager(tmp_path)
    auth_mod._verify_password = lambda pw, hashed: bcrypt.checkpw(pw.encode(), hashed.encode())
    mgr._config["users"] = {"admin": {"is_admin": True, "password_hash": "broken"}}
    router = setup_auth_routes(mgr)
    login = next(r.endpoint for r in router.routes
                 if getattr(r, "path", "") == "/api/auth/login")
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), cookies={},
                              headers={}, url=SimpleNamespace(scheme="http"))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(login(body=LoginRequest(username="admin", password="whatever1"),
                          request=request, response=SimpleNamespace()))
    assert exc.value.status_code == 401


def test_reset_password_sets_a_working_password_and_signs_out(tmp_path):
    _, mgr = _fresh_auth_manager(tmp_path)
    mgr.create_user("admin", "old-password", is_admin=True)
    token = mgr.create_session_trusted("admin")

    assert mgr.reset_password("Admin", "new-password-1") is True
    assert mgr.verify_password("admin", "new-password-1") is True
    assert mgr.verify_password("admin", "old-password") is False
    assert mgr.get_username_for_token(token) is None


def test_reset_password_refuses_short_passwords_and_unknown_users(tmp_path):
    _, mgr = _fresh_auth_manager(tmp_path)
    mgr.create_user("admin", "old-password", is_admin=True)
    assert mgr.reset_password("admin", "x") is False
    assert mgr.reset_password("ghost", "new-password-1") is False
    assert mgr.verify_password("admin", "old-password") is True


def test_grant_admin_local(tmp_path):
    auth_mod, mgr = _fresh_auth_manager(tmp_path)
    mgr.create_user("bob", "pw-123456")
    assert mgr.grant_admin_local("Bob") is True
    assert mgr.is_admin("bob") is True
    assert mgr.users["bob"]["privileges"] == auth_mod.ADMIN_PRIVILEGES
    assert mgr.grant_admin_local("ghost") is False


def test_maven_users_check_reports_problems(tmp_path):
    (tmp_path / "auth.json").write_text(
        '{"users": {"admin": {"is_admin": true, "password_hash": "broken"}}}',
        encoding="utf-8")
    env = {"MAVEN_AI_DATA_DIR": str(tmp_path), "PATH": "", "SYSTEMROOT": ""}
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "maven-users"), "check"],
        capture_output=True, text=True, encoding="utf-8", env=env, cwd=ROOT,
    )
    assert proc.returncode == 1, proc.stderr
    assert '"username": "admin"' in proc.stdout

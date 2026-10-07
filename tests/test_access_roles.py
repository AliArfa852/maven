"""Roles, clearance and the admin console's access rules (plan v2 §3, D-2-2, D-2-8).

Covers the pure model in src/access.py, the AuthManager storage of roles and
clearance (with the last-admin guard), and which roles may read or change
users through the auth routes, using a real AuthManager on a temp auth.json.
"""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src import access
from tests.test_set_admin import _fresh_auth_manager


# ---------------------------------------------------------------------------
# Pure model
# ---------------------------------------------------------------------------

def test_everyone_holds_basic_and_admin_comes_only_from_is_admin():
    assert access.effective_roles([], False) == ["basic"]
    # A stored "admin" entry must not grant Admin; is_admin decides.
    assert access.effective_roles(["admin", "manager"], False) == ["basic", "manager"]
    assert access.effective_roles(["manager"], True) == ["basic", "manager", "admin"]


def test_unknown_roles_are_dropped_and_reported():
    assert access.normalize_roles(["Manager", "superuser", "manager"]) == ["manager"]
    assert access.invalid_roles(["manager", "superuser"]) == ["superuser"]


def test_capabilities_are_the_union_of_roles():
    assert access.capabilities_for(["basic"]) == []
    assert access.capabilities_for(["manager"]) == ["admin.view"]
    assert access.capabilities_for(["manager", "compliance_officer"]) == [
        "admin.view", "compliance.review"]
    assert access.capabilities_for(["admin"]) == ["admin.manage", "admin.view"]


def test_admin_does_not_review_flags_separation_of_duties():
    assert access.COMPLIANCE_REVIEW not in access.capabilities_for(["admin"])
    assert access.ADMIN_MANAGE not in access.capabilities_for(["compliance_officer"])


def test_default_clearance_is_the_highest_role_default():
    assert access.default_clearance(["basic"]) == "internal"
    assert access.default_clearance(["admin"]) == "internal"
    assert access.default_clearance(["basic", "manager"]) == "confidential"
    assert access.default_clearance(["admin", "general_manager"]) == "restricted"


def test_override_wins_and_invalid_override_falls_back():
    assert access.effective_clearance(["general_manager"], "public") == "public"
    assert access.effective_clearance(["manager"], "top-secret") == "confidential"


def test_clearance_allows_fails_closed():
    assert access.clearance_allows("confidential", "internal") is True
    assert access.clearance_allows("internal", "confidential") is False
    assert access.clearance_allows("restricted", "unknown") is False
    assert access.clearance_allows("", "public") is False


# ---------------------------------------------------------------------------
# AuthManager storage
# ---------------------------------------------------------------------------

def _mgr(tmp_path):
    auth_mod, mgr = _fresh_auth_manager(tmp_path)
    mgr.create_user("admin", "pw-123456", is_admin=True)
    mgr.create_user("bob", "pw-123456")
    return auth_mod, mgr


def test_existing_users_need_no_migration(tmp_path):
    _, mgr = _mgr(tmp_path)
    assert mgr.get_roles("admin") == ["basic", "admin"]
    assert mgr.get_roles("bob") == ["basic"]
    assert mgr.access_summary("bob")["clearance"] == "internal"


def test_multiple_roles_and_their_clearance(tmp_path):
    auth_mod, mgr = _mgr(tmp_path)
    R = auth_mod.AccessChangeResult
    assert mgr.set_roles("bob", ["manager", "compliance_officer"], "admin") is R.OK
    summary = mgr.access_summary("bob")
    assert summary["roles"] == ["basic", "manager", "compliance_officer"]
    assert summary["capabilities"] == ["admin.view", "compliance.review"]
    assert summary["clearance"] == "restricted"
    assert mgr.is_admin("bob") is False


def test_granting_admin_through_roles_uses_the_admin_flag(tmp_path):
    auth_mod, mgr = _mgr(tmp_path)
    assert mgr.set_roles("bob", ["admin", "manager"], "admin") is auth_mod.AccessChangeResult.OK
    assert mgr.is_admin("bob") is True
    assert mgr.users["bob"]["privileges"] == auth_mod.ADMIN_PRIVILEGES
    assert "admin" not in mgr.users["bob"]["roles"]  # not stored twice


def test_last_admin_cannot_drop_admin_and_nothing_changes(tmp_path):
    auth_mod, mgr = _mgr(tmp_path)
    result = mgr.set_roles("admin", ["manager"], "admin")
    assert result is auth_mod.AccessChangeResult.LAST_ADMIN
    assert mgr.get_roles("admin") == ["basic", "admin"]


def test_only_admins_change_roles_or_clearance(tmp_path):
    auth_mod, mgr = _mgr(tmp_path)
    R = auth_mod.AccessChangeResult
    mgr.set_roles("bob", ["manager"], "admin")
    mgr.create_user("carol", "pw-123456")
    assert mgr.set_roles("carol", ["general_manager"], "bob") is R.NOT_AUTHORIZED
    assert mgr.set_clearance("carol", "restricted", "bob") is R.NOT_AUTHORIZED
    assert mgr.get_roles("carol") == ["basic"]


def test_invalid_input_is_refused(tmp_path):
    auth_mod, mgr = _mgr(tmp_path)
    R = auth_mod.AccessChangeResult
    assert mgr.set_roles("bob", ["superuser"], "admin") is R.INVALID
    assert mgr.set_clearance("bob", "top-secret", "admin") is R.INVALID
    assert mgr.set_roles("ghost", ["manager"], "admin") is R.USER_NOT_FOUND


def test_clearance_override_and_reset(tmp_path):
    auth_mod, mgr = _mgr(tmp_path)
    mgr.set_roles("bob", ["manager"], "admin")
    assert mgr.set_clearance("bob", "restricted", "admin") is auth_mod.AccessChangeResult.OK
    assert mgr.access_summary("bob")["clearance"] == "restricted"
    assert mgr.set_clearance("bob", None, "admin") is auth_mod.AccessChangeResult.OK
    assert mgr.access_summary("bob")["clearance"] == "confidential"


def test_roles_and_clearance_survive_reload(tmp_path):
    auth_mod, mgr = _mgr(tmp_path)
    mgr.set_roles("bob", ["advanced", "manager"], "admin")
    mgr.set_clearance("bob", "restricted", "admin")
    again = auth_mod.AuthManager(str(tmp_path / "auth.json"))
    assert again.get_roles("bob") == ["basic", "advanced", "manager"]
    assert again.access_summary("bob")["clearance"] == "restricted"


# ---------------------------------------------------------------------------
# Routes with a real AuthManager: who may read, who may change
# ---------------------------------------------------------------------------

def _routes(tmp_path):
    from routes.auth_routes import SESSION_COOKIE, setup_auth_routes

    auth_mod, mgr = _mgr(tmp_path)
    mgr.create_user("mary", "pw-123456")
    mgr.create_user("cora", "pw-123456")
    mgr.set_roles("mary", ["manager"], "admin")
    mgr.set_roles("cora", ["compliance_officer"], "admin")
    router = setup_auth_routes(mgr)

    def endpoint(path, method):
        for route in router.routes:
            if getattr(route, "path", "") == path and method in getattr(route, "methods", set()):
                return route.endpoint
        raise AssertionError(f"{method} {path} not registered")

    def request_as(username):
        token = mgr.create_session_trusted(username)
        return SimpleNamespace(cookies={SESSION_COOKIE: token},
                               client=SimpleNamespace(host="127.0.0.1"))

    return mgr, endpoint, request_as


@pytest.mark.parametrize("who", ["admin", "mary", "cora"])
def test_console_viewers_can_list_users_and_roles(tmp_path, who):
    _, endpoint, request_as = _routes(tmp_path)
    users = asyncio.run(endpoint("/api/auth/users", "GET")(request=request_as(who)))
    assert {u["username"] for u in users["users"]} >= {"admin", "bob", "mary", "cora"}
    roles = asyncio.run(endpoint("/api/auth/roles", "GET")(request=request_as(who)))
    assert [r["id"] for r in roles["roles"]] == list(access.ROLES)


def test_basic_user_cannot_open_the_console(tmp_path):
    _, endpoint, request_as = _routes(tmp_path)
    for path in ("/api/auth/users", "/api/auth/roles"):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(endpoint(path, "GET")(request=request_as("bob")))
        assert exc.value.status_code == 403


@pytest.mark.parametrize("who", ["mary", "cora", "bob"])
def test_only_admin_changes_roles_and_clearance(tmp_path, who):
    from routes.auth_routes import SetClearanceRequest, SetRolesRequest

    mgr, endpoint, request_as = _routes(tmp_path)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint("/api/auth/users/{username}/roles", "PUT")(
            username="bob", body=SetRolesRequest(roles=["general_manager"]),
            request=request_as(who)))
    assert exc.value.status_code == 403
    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint("/api/auth/users/{username}/clearance", "PUT")(
            username="bob", body=SetClearanceRequest(clearance="restricted"),
            request=request_as(who)))
    assert exc.value.status_code == 403
    assert mgr.get_roles("bob") == ["basic"]
    assert mgr.access_summary("bob")["clearance_override"] is None


def test_admin_changes_roles_and_gets_the_new_summary(tmp_path):
    from routes.auth_routes import SetRolesRequest

    _, endpoint, request_as = _routes(tmp_path)
    out = asyncio.run(endpoint("/api/auth/users/{username}/roles", "PUT")(
        username="Bob", body=SetRolesRequest(roles=["advanced", "manager"]),
        request=request_as("admin")))
    assert out["ok"] is True and out["self"] is False
    assert out["roles"] == ["basic", "advanced", "manager"]
    assert out["clearance"] == "confidential"


def test_route_maps_refusals_to_status_codes(tmp_path):
    from routes.auth_routes import SetClearanceRequest, SetRolesRequest

    _, endpoint, request_as = _routes(tmp_path)
    put_roles = endpoint("/api/auth/users/{username}/roles", "PUT")
    cases = [
        ("admin", ["manager"], 400),   # last admin
        ("bob", ["superuser"], 400),   # unknown role
        ("ghost", ["manager"], 404),
    ]
    for username, roles, code in cases:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(put_roles(username=username, body=SetRolesRequest(roles=roles),
                                  request=request_as("admin")))
        assert exc.value.status_code == code
    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint("/api/auth/users/{username}/clearance", "PUT")(
            username="bob", body=SetClearanceRequest(clearance="top-secret"),
            request=request_as("admin")))
    assert exc.value.status_code == 400


def test_require_capability_gate():
    from core.middleware import require_capability

    mgr = SimpleNamespace(is_configured=True,
                          has_capability=lambda user, cap: user == "mary" and cap == "admin.view")
    def req(user):
        return SimpleNamespace(headers={}, state=SimpleNamespace(current_user=user),
                               app=SimpleNamespace(state=SimpleNamespace(auth_manager=mgr)))

    require_capability(req("mary"), "admin.view")  # allowed: no exception
    for user, cap in (("mary", "admin.manage"), ("bob", "admin.view"), (None, "admin.view")):
        with pytest.raises(HTTPException) as exc:
            require_capability(req(user), cap)
        assert exc.value.status_code == 403

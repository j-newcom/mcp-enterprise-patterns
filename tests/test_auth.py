"""Tests for mcp_patterns.auth."""

import pytest

from mcp_patterns.auth import (
    AuthError,
    ForbiddenError,
    KeyRegistry,
    RoleManager,
    require_auth,
)


# --- KeyRegistry ---


def test_valid_key_returns_entry():
    reg = KeyRegistry()
    reg.register("my-key", "alice", "admin")
    entry = reg.validate("my-key")
    assert entry.identity == "alice"
    assert entry.role == "admin"


def test_invalid_key_raises():
    reg = KeyRegistry()
    reg.register("my-key", "alice", "admin")
    with pytest.raises(AuthError):
        reg.validate("wrong-key")


@pytest.mark.parametrize("key", ["", "   ", None])
def test_empty_or_none_key_raises(key):
    reg = KeyRegistry()
    with pytest.raises(AuthError):
        reg.validate(key)


def test_deactivated_key_raises():
    reg = KeyRegistry()
    reg.register("my-key", "alice", "admin")
    entry = reg.validate("my-key")
    # Deactivate
    for e in reg._entries.values():
        e.active = False
    with pytest.raises(AuthError):
        reg.validate("my-key")


def test_from_env():
    reg = KeyRegistry.from_env("KEYS", env={"KEYS": "k1:alice:admin,k2:bob:reader"})
    assert reg.validate("k1").identity == "alice"
    assert reg.validate("k2").role == "reader"


def test_from_env_empty():
    reg = KeyRegistry.from_env("MISSING", env={})
    with pytest.raises(AuthError):
        reg.validate("anything")


# --- RoleManager ---


def test_admin_wildcard():
    rm = RoleManager()
    rm.define("admin", {"*"})
    assert rm.check_access("admin", "any_tool") is True


def test_reader_allowed():
    rm = RoleManager()
    rm.define("reader", {"get_inventory", "get_forecast"})
    assert rm.check_access("reader", "get_inventory") is True


def test_reader_denied():
    rm = RoleManager()
    rm.define("reader", {"get_inventory"})
    with pytest.raises(ForbiddenError):
        rm.check_access("reader", "create_po")


def test_unknown_role():
    rm = RoleManager()
    with pytest.raises(ForbiddenError):
        rm.check_access("ghost", "anything")


def test_get_allowed_tools():
    rm = RoleManager()
    rm.define("writer", {"create_po", "transfer"})
    assert rm.get_allowed_tools("writer") == {"create_po", "transfer"}


# --- @require_auth ---


def test_require_auth_passes():
    reg = KeyRegistry()
    reg.register("valid", "tester", "admin")
    rm = RoleManager()
    rm.define("admin", {"*"})

    @require_auth(reg, rm)
    def my_tool(args, auth=None):
        return {"caller": auth.identity}

    result = my_tool({"x-api-key": "valid", "data": 1})
    assert result["caller"] == "tester"


def test_require_auth_missing_key():
    reg = KeyRegistry()

    @require_auth(reg)
    def my_tool(args, auth=None):
        return {}

    with pytest.raises(AuthError):
        my_tool({"data": 1})


def test_require_auth_forbidden_tool():
    reg = KeyRegistry()
    reg.register("key", "bob", "reader")
    rm = RoleManager()
    rm.define("reader", {"get_data"})

    @require_auth(reg, rm)
    def create_po(args, auth=None):
        return {}

    with pytest.raises(ForbiddenError):
        create_po({"x-api-key": "key"})


# --- Security ---


def test_key_never_in_error():
    reg = KeyRegistry()
    try:
        reg.validate("super-secret-key-12345")
    except AuthError as e:
        assert "super-secret" not in e.message
        assert "super-secret" not in str(e.details)

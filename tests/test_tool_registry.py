"""Tests for mcp_patterns.tool_registry."""

import io

import pytest

from mcp_patterns.tool_registry import ToolRegistry
from mcp_patterns.errors import ValidationError


def _quiet_registry(name):
    reg = ToolRegistry(name, "ERROR")
    reg._logger.handlers[0].stream = io.StringIO()
    return reg


def test_register_and_dispatch_success():
    reg = _quiet_registry("t.success")

    @reg.register("get_inventory", "Get stock", {"type": "object"})
    def get_inventory(args):
        return {"sku": args["sku"], "qty": 100}

    r = reg.dispatch("get_inventory", {"sku": "ABC"})
    assert r["ok"] is True
    assert r["data"] == {"sku": "ABC", "qty": 100}


def test_dispatch_raising_tool_becomes_structured_error():
    reg = _quiet_registry("t.raise")

    @reg.register("flaky")
    def flaky(args):
        raise ValidationError("bad", details={"field": "sku"})

    r = reg.dispatch("flaky", {})
    assert r["ok"] is False
    assert r["error"]["code"] == "validation_error"
    assert r["error"]["details"] == {"field": "sku"}


def test_dispatch_unknown_exception_sanitized():
    reg = _quiet_registry("t.boom")

    @reg.register("boom")
    def boom(args):
        raise RuntimeError("SECRET xyz")

    r = reg.dispatch("boom", {})
    assert r["error"]["code"] == "internal_error"
    assert "SECRET" not in str(r) and "xyz" not in str(r)


def test_unknown_tool():
    reg = _quiet_registry("t.unknown")
    r = reg.dispatch("nope", {})
    assert r["ok"] is False and r["error"]["code"] == "not_found"


def test_list_tools_metadata():
    reg = _quiet_registry("t.list")

    @reg.register("a", "desc-a", {"type": "object"})
    def a(args):
        return 1

    tools = reg.list_tools()
    assert tools[0]["name"] == "a"
    assert tools[0]["description"] == "desc-a"
    assert tools[0]["input_schema"] == {"type": "object"}


def test_duplicate_registration_raises():
    reg = _quiet_registry("t.dup")

    @reg.register("x")
    def x(args):
        return 1

    with pytest.raises(ValueError):
        @reg.register("x")
        def x2(args):
            return 2

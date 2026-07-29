"""Tests for mcp_patterns.errors."""

from mcp_patterns.errors import (
    NotFoundError, UpstreamError, ValidationError, ok, safe_tool, to_error_payload,
)


def test_taxonomy_codes():
    assert ValidationError("x").code == "validation_error"
    assert NotFoundError("x").code == "not_found"
    assert UpstreamError("x").code == "upstream_error"
    assert NotFoundError("x").http_status == 404


def test_known_error_payload_preserves_fields():
    p = to_error_payload(ValidationError("bad sku", details={"field": "sku"}))
    assert p["ok"] is False
    assert p["error"]["code"] == "validation_error"
    assert p["error"]["message"] == "bad sku"
    assert p["error"]["details"] == {"field": "sku"}


def test_unknown_exception_is_sanitized():
    p = to_error_payload(RuntimeError("SECRET internal xyz"))
    assert p["error"]["code"] == "internal_error"
    assert p["error"]["message"] == "An internal error occurred."
    assert "SECRET" not in str(p) and "xyz" not in str(p)


def test_include_trace_toggle():
    try:
        raise UpstreamError("erp down")
    except UpstreamError as e:
        assert "trace" in to_error_payload(e, include_trace=True)["error"]
    assert "trace" not in to_error_payload(ValidationError("x"))["error"]


def test_safe_tool_success_wraps():
    @safe_tool
    def good(sku):
        return {"sku": sku}
    r = good("ABC")
    assert r["ok"] is True and r["data"] == {"sku": "ABC"}


def test_safe_tool_catches_and_sanitizes():
    @safe_tool
    def boom():
        raise ValueError("raw boom")
    r = boom()
    assert r["ok"] is False and r["error"]["code"] == "internal_error"
    assert "boom" not in str(r)


def test_safe_tool_parametrized_trace():
    @safe_tool(include_trace=True)
    def boom():
        raise ValueError("dbg")
    assert "trace" in boom()["error"]


def test_safe_tool_envelope_passthrough():
    @safe_tool
    def enveloped():
        return {"ok": False, "error": {"code": "custom", "message": "m", "details": {}}}
    assert enveloped()["error"]["code"] == "custom"

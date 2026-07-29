"""Tests for mcp_patterns.observability."""

import io
import json
import logging

from mcp_patterns.observability import get_logger, redact, timed


def test_redact_top_level():
    r = redact({"user": "justin", "password": "hunter2", "token": "ghp_abc"})
    assert r["password"] == "***REDACTED***"
    assert r["token"] == "***REDACTED***"
    assert r["user"] == "justin"


def test_redact_nested_and_lists_case_insensitive():
    r = redact({
        "Authorization": "Bearer x",
        "nested": {"api_key": "k", "safe": 1},
        "items": [{"secret": "s", "name": "ok"}],
    })
    assert r["Authorization"] == "***REDACTED***"
    assert r["nested"]["api_key"] == "***REDACTED***"
    assert r["nested"]["safe"] == 1
    assert r["items"][0]["secret"] == "***REDACTED***"
    assert r["items"][0]["name"] == "ok"


def test_redact_does_not_mutate_input():
    orig = {"secret": "s"}
    redact(orig)
    assert orig["secret"] == "s"


def test_redact_bridge_secret():
    assert redact({"x-bridge-secret": "s"})["x-bridge-secret"] == "***REDACTED***"


def test_timed_success_logs_and_returns(monkeypatch):
    logger = get_logger("test.obs.success", "INFO")
    buf = io.StringIO()
    logger.handlers[0].stream = buf

    @timed(logger, "get_x")
    def get_x(v):
        return v * 2

    assert get_x(21) == 42
    lines = [json.loads(x) for x in buf.getvalue().strip().splitlines()]
    assert any(l["msg"] == "tool.start" for l in lines)
    assert any(l["msg"] == "tool.end" and l["ok"] is True for l in lines)
    assert any("duration_ms" in l for l in lines)


def test_timed_failure_logs_code_and_reraises():
    logger = get_logger("test.obs.fail", "INFO")
    buf = io.StringIO()
    logger.handlers[0].stream = buf

    class Err(Exception):
        code = "upstream_error"

    @timed(logger, "call_erp")
    def call_erp():
        raise Err("down")

    raised = False
    try:
        call_erp()
    except Err:
        raised = True
    assert raised
    lines = [json.loads(x) for x in buf.getvalue().strip().splitlines()]
    assert any(l["msg"] == "tool.error" and l.get("error_code") == "upstream_error" for l in lines)

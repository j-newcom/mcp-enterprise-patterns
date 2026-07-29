"""Structured logging and request timing for MCP servers.

Production MCP servers need observability that is (a) structured (JSON lines,
easy to ship to any log aggregator), (b) safe (never logs secrets), and
(c) low-overhead. This module provides:

- `get_logger(name)` — a stdlib logging.Logger configured for JSON output
- `redact(mapping, keys)` — strip sensitive keys before logging
- `@timed(logger, tool_name)` — decorator that logs start/end + duration_ms
  for a tool call, and logs failures with the error code (never the raw trace)

Uses only the standard library.
"""

from __future__ import annotations

import functools
import json
import logging
import sys
import time
from typing import Any, Callable, Iterable

# Keys that must never appear in logs, regardless of nesting depth.
DEFAULT_SENSITIVE_KEYS = frozenset({
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "authorization", "auth", "x-bridge-secret", "bridge_secret",
    "access_key", "secret_key", "aws_secret_access_key", "credential", "credentials",
})


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Attach structured extras placed on the record via `extra=`
        for key, val in getattr(record, "_structured", {}).items():
            payload[key] = val
        return json.dumps(payload, default=str)


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    return logger


def _log(logger: logging.Logger, level: int, msg: str, **structured: Any) -> None:
    logger.log(level, msg, extra={"_structured": structured})


def redact(mapping: dict, keys: Iterable[str] = DEFAULT_SENSITIVE_KEYS) -> dict:
    """Return a deep copy of `mapping` with sensitive keys replaced by
    '***REDACTED***'. Case-insensitive key matching. Recurses into nested
    dicts and lists."""
    sensitive = {k.lower() for k in keys}

    def _scrub(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {
                k: ("***REDACTED***" if k.lower() in sensitive else _scrub(v))
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [_scrub(item) for item in obj]
        return obj

    return _scrub(mapping)


def timed(logger: logging.Logger, tool_name: str) -> Callable:
    """Decorator that logs structured start/end/duration for a tool call.

    On success: logs level INFO with duration_ms and ok=True.
    On failure: logs level ERROR with duration_ms, ok=False, and the error
    code if available (never the raw traceback). The exception is re-raised
    so an outer @safe_tool can render the structured error response.
    """

    def decorate(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            _log(logger, logging.INFO, "tool.start", tool=tool_name)
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001
                dur = round((time.perf_counter() - start) * 1000, 2)
                code = getattr(exc, "code", "internal_error")
                _log(logger, logging.ERROR, "tool.error",
                     tool=tool_name, duration_ms=dur, ok=False, error_code=code)
                raise
            dur = round((time.perf_counter() - start) * 1000, 2)
            _log(logger, logging.INFO, "tool.end",
                 tool=tool_name, duration_ms=dur, ok=True)
            return result

        return wrapper

    return decorate

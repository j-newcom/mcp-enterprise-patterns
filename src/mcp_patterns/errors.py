"""Structured error taxonomy for MCP tools.

Production MCP tools must never leak raw stack traces to the client. Instead
they return a consistent, structured error payload with a stable machine-
readable code, a human-readable message, and optional non-sensitive details.

This module provides:
- A small taxonomy of error types (validation / not_found / upstream / internal)
- A `to_error_payload` helper that renders any exception into a safe dict
- A `@safe_tool` decorator that wraps a tool function so ANY exception becomes
  a structured error response instead of crashing the server.

The decorator is the pattern behind "crash-proof tools": one misbehaving tool
call can never take down the whole server.
"""

from __future__ import annotations

import functools
import traceback
from typing import Any, Callable


class MCPError(Exception):
    """Base class for structured MCP errors. `code` is a stable string."""

    code = "internal_error"
    http_status = 500

    def __init__(self, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(MCPError):
    code = "validation_error"
    http_status = 400


class NotFoundError(MCPError):
    code = "not_found"
    http_status = 404


class UpstreamError(MCPError):
    """A dependency (DB, API, ERP, etc.) failed."""

    code = "upstream_error"
    http_status = 502


class InternalError(MCPError):
    code = "internal_error"
    http_status = 500


def to_error_payload(exc: Exception, *, include_trace: bool = False) -> dict[str, Any]:
    """Render any exception into a safe, structured error dict.

    Known MCPError subclasses keep their code/message/details. Unknown
    exceptions are mapped to a generic internal error whose message does NOT
    echo the raw exception text by default (avoids leaking internals). Set
    include_trace=True only in local/debug runs.
    """
    if isinstance(exc, MCPError):
        payload = {
            "ok": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        }
    else:
        payload = {
            "ok": False,
            "error": {
                "code": "internal_error",
                "message": "An internal error occurred.",
                "details": {},
            },
        }
    if include_trace:
        payload["error"]["trace"] = traceback.format_exc()
    return payload


def ok(data: Any) -> dict[str, Any]:
    """Wrap a successful tool result in the standard envelope."""
    return {"ok": True, "data": data}


def safe_tool(_fn: Callable | None = None, *, include_trace: bool = False) -> Callable:
    """Decorator: wrap an MCP tool so any exception becomes a structured error.

    Usage:
        @safe_tool
        def get_inventory(sku: str) -> dict: ...

        @safe_tool(include_trace=True)   # local/debug only
        def ...
    """

    def decorate(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - deliberate catch-all
                return to_error_payload(exc, include_trace=include_trace)
            # If the tool already returned an envelope, pass it through.
            if isinstance(result, dict) and "ok" in result:
                return result
            return ok(result)

        return wrapper

    # Support both @safe_tool and @safe_tool(include_trace=True)
    if _fn is not None and callable(_fn):
        return decorate(_fn)
    return decorate

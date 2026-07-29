"""Input validation helpers for MCP tools.

MCP tools receive arguments from an LLM client — they must validate inputs
defensively before acting. These helpers raise ValidationError (from errors.py)
with a clear, non-sensitive message so the @safe_tool decorator renders them
as a structured validation_error response.

All helpers return the coerced/validated value so they compose cleanly:

    sku = require_str(args, "sku", max_len=64)
    qty = require_int(args, "quantity", minimum=1)

Dependency-free.
"""

from __future__ import annotations

from typing import Any, Iterable

from .errors import ValidationError


def require(args: dict, name: str) -> Any:
    """Return args[name] or raise ValidationError if missing/None."""
    if name not in args or args[name] is None:
        raise ValidationError(f"Missing required argument: {name}", details={"field": name})
    return args[name]


def require_str(args: dict, name: str, *, min_len: int = 1, max_len: int | None = None,
                strip: bool = True) -> str:
    val = require(args, name)
    if not isinstance(val, str):
        raise ValidationError(f"Argument {name} must be a string", details={"field": name})
    if strip:
        val = val.strip()
    if len(val) < min_len:
        raise ValidationError(
            f"Argument {name} must be at least {min_len} character(s)",
            details={"field": name},
        )
    if max_len is not None and len(val) > max_len:
        raise ValidationError(
            f"Argument {name} must be at most {max_len} character(s)",
            details={"field": name},
        )
    return val


def require_int(args: dict, name: str, *, minimum: int | None = None,
                maximum: int | None = None) -> int:
    val = require(args, name)
    # Reject bools masquerading as ints (bool is a subclass of int in Python)
    if isinstance(val, bool):
        raise ValidationError(f"Argument {name} must be an integer",
                              details={"field": name})
    if not isinstance(val, int):
        # allow int-like strings, reject everything else
        try:
            val = int(val)
        except (TypeError, ValueError):
            raise ValidationError(f"Argument {name} must be an integer",
                                  details={"field": name}) from None
    if minimum is not None and val < minimum:
        raise ValidationError(f"Argument {name} must be >= {minimum}", details={"field": name})
    if maximum is not None and val > maximum:
        raise ValidationError(f"Argument {name} must be <= {maximum}", details={"field": name})
    return val


def require_enum(args: dict, name: str, allowed: Iterable[Any]) -> Any:
    val = require(args, name)
    allowed = list(allowed)
    if val not in allowed:
        raise ValidationError(
            f"Argument {name} must be one of {allowed}",
            details={"field": name, "allowed": allowed},
        )
    return val


def optional_str(args: dict, name: str, default: str | None = None, *,
                 max_len: int | None = None) -> str | None:
    if name not in args or args[name] is None:
        return default
    return require_str(args, name, min_len=0, max_len=max_len)

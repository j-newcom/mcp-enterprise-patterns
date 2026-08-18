"""Authentication and authorization patterns for MCP servers.

Production MCP servers need to:
1. Validate that callers present a valid credential (API key, token, header)
2. Map authenticated identities to roles with scoped tool access
3. Reject unauthorized callers with structured errors (not leaked internals)
4. Never log or surface credentials in error responses

This module provides:
- `KeyRegistry` — validate API keys against a configurable registry
- `RoleManager` — map identities to allowed tool sets
- `@require_auth` — decorator that wraps a tool to enforce auth before execution
- `AuthError` — structured error for auth failures (extends MCPError)

Zero dependencies beyond the other mcp_patterns modules.
"""

from __future__ import annotations

import functools
import hashlib
import os
from dataclasses import dataclass, field
from typing import Any, Callable

from .errors import MCPError


class AuthError(MCPError):
    """Raised when authentication or authorization fails."""

    code = "auth_error"
    http_status = 401


class ForbiddenError(MCPError):
    """Raised when an authenticated caller lacks permission for the action."""

    code = "forbidden"
    http_status = 403


# =============================================================================
# KEY REGISTRY
# =============================================================================


@dataclass
class KeyEntry:
    """A registered API key with associated identity and role."""

    key_hash: str
    identity: str
    role: str
    active: bool = True


class KeyRegistry:
    """Validate API keys against a registry.

    Keys are stored as SHA-256 hashes — the plaintext key is never persisted.
    Load keys from environment variables (comma-separated) or a list.

    Usage:
        registry = KeyRegistry.from_env("MCP_API_KEYS")
        # env: MCP_API_KEYS="key1:user1:admin,key2:user2:reader"

        identity = registry.validate("key1")  # returns KeyEntry or raises AuthError
    """

    def __init__(self, entries: list[KeyEntry] | None = None):
        self._entries: dict[str, KeyEntry] = {}
        for entry in (entries or []):
            self._entries[entry.key_hash] = entry

    @staticmethod
    def _hash_key(key: str) -> str:
        return hashlib.sha256(key.strip().encode()).hexdigest()

    def register(self, key: str, identity: str, role: str) -> None:
        """Register a new API key (stores only the hash)."""
        self._entries[self._hash_key(key)] = KeyEntry(
            key_hash=self._hash_key(key), identity=identity, role=role
        )

    def validate(self, key: str) -> KeyEntry:
        """Validate a key and return the associated entry. Raises AuthError if invalid."""
        if not key or not key.strip():
            raise AuthError("Missing API key", details={"reason": "no_key_provided"})
        h = self._hash_key(key)
        entry = self._entries.get(h)
        if entry is None:
            raise AuthError("Invalid API key", details={"reason": "key_not_found"})
        if not entry.active:
            raise AuthError("API key is deactivated", details={"reason": "key_deactivated"})
        return entry

    @classmethod
    def from_env(cls, env_var: str = "MCP_API_KEYS", env: dict[str, str] | None = None) -> "KeyRegistry":
        """Load keys from an environment variable.

        Format: key1:identity1:role1,key2:identity2:role2,...
        """
        env = env if env is not None else dict(os.environ)
        raw = env.get(env_var, "").strip()
        registry = cls()
        if not raw:
            return registry
        for entry_str in raw.split(","):
            parts = entry_str.strip().split(":")
            if len(parts) >= 3:
                key, identity, role = parts[0], parts[1], parts[2]
                registry.register(key, identity, role)
        return registry


# =============================================================================
# ROLE-BASED TOOL SCOPING
# =============================================================================


class RoleManager:
    """Map roles to allowed tool sets.

    Usage:
        roles = RoleManager()
        roles.define("admin", allowed_tools={"*"})  # wildcard = all tools
        roles.define("reader", allowed_tools={"get_inventory", "get_forecast"})
        roles.define("writer", allowed_tools={"get_inventory", "create_po", "transfer"})

        roles.check_access("reader", "create_po")  # raises ForbiddenError
        roles.check_access("admin", "anything")     # passes (wildcard)
    """

    def __init__(self):
        self._roles: dict[str, set[str]] = {}

    def define(self, role: str, allowed_tools: set[str]) -> None:
        """Define a role with its allowed tool set. Use {"*"} for all-access."""
        self._roles[role] = allowed_tools

    def check_access(self, role: str, tool_name: str) -> bool:
        """Check if a role has access to a tool. Raises ForbiddenError if denied."""
        allowed = self._roles.get(role)
        if allowed is None:
            raise ForbiddenError(
                f"Unknown role: {role}",
                details={"role": role, "tool": tool_name},
            )
        if "*" in allowed:
            return True
        if tool_name in allowed:
            return True
        raise ForbiddenError(
            f"Role '{role}' does not have access to tool '{tool_name}'",
            details={"role": role, "tool": tool_name, "allowed_tools": sorted(allowed)},
        )

    def get_allowed_tools(self, role: str) -> set[str]:
        """Return the set of tools allowed for a role."""
        return self._roles.get(role, set())


# =============================================================================
# AUTH DECORATOR
# =============================================================================


def require_auth(
    registry: KeyRegistry,
    roles: RoleManager | None = None,
    key_header: str = "x-api-key",
) -> Callable:
    """Decorator factory: enforce authentication (and optionally authorization)
    before a tool executes.

    The decorated function receives an extra `auth` kwarg with the validated
    KeyEntry — so the tool can use the caller's identity/role in its logic.

    Usage:
        @require_auth(registry, roles)
        def get_inventory(args: dict, auth: KeyEntry = None) -> dict:
            # auth.identity, auth.role available here
            ...

    The decorator extracts the key from args[key_header] (for MCP, the key
    is typically passed as a tool argument or in request metadata).
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(args: dict, **kwargs: Any) -> dict:
            # Extract key from args
            key = args.pop(key_header, None) or args.pop("api_key", None)
            if key is None:
                raise AuthError(
                    f"Missing authentication: provide '{key_header}' in arguments",
                    details={"reason": "no_key_in_request"},
                )

            # Validate
            entry = registry.validate(key)

            # Check role-based access if roles are configured
            if roles is not None:
                tool_name = getattr(fn, "__name__", "unknown")
                roles.check_access(entry.role, tool_name)

            # Call the tool with auth context
            return fn(args, auth=entry, **kwargs)

        return wrapper

    return decorator

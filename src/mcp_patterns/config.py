"""Structured configuration loading for MCP servers.

Every production MCP server needs to read configuration from the environment
with validation, sensible defaults, and clear errors when something required
is missing. This module extracts that pattern into a small, dependency-free
helper (consistent with the env-var config approach in agent-bridge-mcp and
supply-chain-mcp-server).

Design goals:
- Fail fast and loud: a missing required var raises ConfigError with the exact
  variable name, never a silent None that surfaces as a confusing error later.
- Typed reads: str / int / bool / float with explicit coercion and clear
  messages when coercion fails.
- Defaults are explicit and only apply to optional vars.
- No third-party dependencies.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


_TRUE = {"1", "true", "yes", "on", "y", "t"}
_FALSE = {"0", "false", "no", "off", "n", "f"}


def _get_raw(name: str, env: dict[str, str]) -> str | None:
    val = env.get(name)
    if val is None:
        return None
    val = val.strip()
    return val if val != "" else None


def get_str(name: str, default: str | None = None, *, required: bool = False,
            env: dict[str, str] | None = None) -> str | None:
    env = env if env is not None else dict(os.environ)
    val = _get_raw(name, env)
    if val is None:
        if required:
            raise ConfigError(f"Missing required environment variable: {name}")
        return default
    return val


def get_int(name: str, default: int | None = None, *, required: bool = False,
            env: dict[str, str] | None = None) -> int | None:
    env = env if env is not None else dict(os.environ)
    val = _get_raw(name, env)
    if val is None:
        if required:
            raise ConfigError(f"Missing required environment variable: {name}")
        return default
    try:
        return int(val)
    except ValueError:
        raise ConfigError(f"Environment variable {name}={val!r} is not a valid integer") from None


def get_float(name: str, default: float | None = None, *, required: bool = False,
              env: dict[str, str] | None = None) -> float | None:
    env = env if env is not None else dict(os.environ)
    val = _get_raw(name, env)
    if val is None:
        if required:
            raise ConfigError(f"Missing required environment variable: {name}")
        return default
    try:
        return float(val)
    except ValueError:
        raise ConfigError(f"Environment variable {name}={val!r} is not a valid float") from None


def get_bool(name: str, default: bool | None = None, *, required: bool = False,
             env: dict[str, str] | None = None) -> bool | None:
    env = env if env is not None else dict(os.environ)
    val = _get_raw(name, env)
    if val is None:
        if required:
            raise ConfigError(f"Missing required environment variable: {name}")
        return default
    lowered = val.lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    raise ConfigError(
        f"Environment variable {name}={val!r} is not a valid boolean "
        f"(expected one of {sorted(_TRUE | _FALSE)})"
    )


@dataclass
class ServerConfig:
    """Common baseline configuration shared by MCP servers.

    Extend this dataclass per server with your own fields, loading them in
    `from_env` via the typed getters above.
    """

    server_name: str
    log_level: str = "INFO"
    request_timeout_s: int = 30
    use_synthetic_data: bool = True

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "ServerConfig":
        return cls(
            server_name=get_str("MCP_SERVER_NAME", required=True, env=env),
            log_level=get_str("MCP_LOG_LEVEL", "INFO", env=env),
            request_timeout_s=get_int("MCP_REQUEST_TIMEOUT_S", 30, env=env),
            use_synthetic_data=get_bool("MCP_USE_SYNTHETIC_DATA", True, env=env),
        )

    def redacted(self) -> dict[str, Any]:
        """Return a dict safe for logging (no secrets in the base config)."""
        return {
            "server_name": self.server_name,
            "log_level": self.log_level,
            "request_timeout_s": self.request_timeout_s,
            "use_synthetic_data": self.use_synthetic_data,
        }

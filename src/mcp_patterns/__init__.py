"""mcp_patterns — reusable production patterns for MCP servers.

Modules:
    config          typed environment configuration loading
    errors          structured error taxonomy + @safe_tool
    validation      defensive input validation helpers
    observability   JSON logging, secret redaction, @timed
    tool_registry   register + dispatch tools (auto crash-proof + observable)
    auth            API key validation, role-based scoping, @require_auth
"""

from .config import ConfigError, ServerConfig, get_bool, get_float, get_int, get_str
from .errors import (
    InternalError,
    MCPError,
    NotFoundError,
    UpstreamError,
    ValidationError,
    ok,
    safe_tool,
    to_error_payload,
)
from .observability import DEFAULT_SENSITIVE_KEYS, get_logger, redact, timed
from .tool_registry import ToolRegistry, ToolSpec
from .auth import AuthError, ForbiddenError, KeyRegistry, RoleManager, require_auth
from .validation import (
    optional_str,
    require,
    require_enum,
    require_int,
    require_str,
)

__all__ = [
    "ConfigError", "ServerConfig", "get_bool", "get_float", "get_int", "get_str",
    "MCPError", "ValidationError", "NotFoundError", "UpstreamError", "InternalError",
    "to_error_payload", "ok", "safe_tool",
    "DEFAULT_SENSITIVE_KEYS", "get_logger", "redact", "timed",
    "ToolRegistry", "ToolSpec",
    "require", "require_str", "require_int", "require_enum", "optional_str",
    "AuthError", "ForbiddenError", "KeyRegistry", "RoleManager", "require_auth",
]

__version__ = "0.1.0"

"""Tool registry and dispatch for MCP servers.

Rather than scattering tool definitions across a server, register them in one
place. Every registered tool is automatically wrapped so it is:

  - crash-proof   (via @safe_tool — exceptions become structured errors)
  - observable    (via @timed — start/end/duration logged, secrets never)

The registry gives you a single `dispatch(name, args)` entry point that an MCP
transport layer can call, plus `list_tools()` for tool discovery/metadata.

Dependency-free; composes the other pattern modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .errors import safe_tool, NotFoundError, to_error_payload
from .observability import timed, get_logger


@dataclass
class ToolSpec:
    name: str
    description: str
    handler: Callable
    input_schema: dict = field(default_factory=dict)


class ToolRegistry:
    def __init__(self, server_name: str = "mcp-server", log_level: str = "INFO"):
        self._tools: dict[str, ToolSpec] = {}
        self._logger = get_logger(server_name, log_level)

    def register(self, name: str, description: str = "", input_schema: dict | None = None) -> Callable:
        """Decorator to register a tool. The handler is automatically wrapped
        with timing (outer) and crash-proofing (inner) so a raised exception
        is both logged and returned as a structured error payload."""
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")

        def decorate(fn: Callable) -> Callable:
            # inner: safe_tool converts exceptions to structured payloads.
            # outer: timed logs duration. We want timing to see the raw raise,
            # so wrap timed OUTSIDE safe_tool would swallow the exception before
            # timing logs it. Instead: time the raw fn, then safe-wrap the timed fn.
            timed_fn = timed(self._logger, name)(fn)
            safe_fn = safe_tool(timed_fn)
            self._tools[name] = ToolSpec(
                name=name,
                description=description,
                handler=safe_fn,
                input_schema=input_schema or {},
            )
            return fn  # return original so the module-level name is unwrapped

        return decorate

    def list_tools(self) -> list[dict]:
        return [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in self._tools.values()
        ]

    def dispatch(self, name: str, args: dict | None = None) -> dict:
        """Call a registered tool by name with an args dict. Always returns a
        structured envelope (never raises), so a transport layer can serialize
        it directly."""
        args = args or {}
        spec = self._tools.get(name)
        if spec is None:
            return to_error_payload(NotFoundError(f"Unknown tool: {name}", details={"tool": name}))
        return spec.handler(args)

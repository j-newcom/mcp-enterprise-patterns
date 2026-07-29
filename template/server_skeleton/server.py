"""Starter MCP server skeleton.

Copy this file (and adjust) to start a new MCP server on the enterprise patterns.
Fill in your own tools where marked. Everything else — config, validation,
crash-proofing, logging — is handled by the pattern library.

Run:  python server.py   (runs the built-in smoke check)
"""

from __future__ import annotations

from mcp_patterns import (
    ServerConfig,
    ToolRegistry,
    NotFoundError,
    require_str,
)


def build_server(config: ServerConfig | None = None) -> ToolRegistry:
    config = config or ServerConfig(server_name="my-mcp-server")
    registry = ToolRegistry(config.server_name, config.log_level)

    # ---- Define your tools below -------------------------------------------
    @registry.register(
        "echo",
        "Echo back the provided message (replace with a real tool).",
        {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]},
    )
    def echo(args: dict) -> dict:
        message = require_str(args, "message", max_len=500)
        return {"echo": message}

    # Example of the not-found pattern:
    @registry.register("get_item", "Fetch an item by id.")
    def get_item(args: dict) -> dict:
        item_id = require_str(args, "id", max_len=64)
        store = {"1": {"name": "Widget"}}  # replace with your data source
        item = store.get(item_id)
        if item is None:
            raise NotFoundError(f"Unknown item: {item_id}", details={"id": item_id})
        return {"id": item_id, **item}
    # ------------------------------------------------------------------------

    return registry


if __name__ == "__main__":
    # Minimal smoke check — replace with your real transport (stdio, HTTP, etc.)
    reg = build_server(ServerConfig(server_name="my-mcp-server", log_level="ERROR"))
    print("Registered tools:", [t["name"] for t in reg.list_tools()])
    print("echo:", reg.dispatch("echo", {"message": "hello"}))
    print("get_item (missing):", reg.dispatch("get_item", {"id": "999"}))

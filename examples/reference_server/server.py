"""Reference MCP server — wires every pattern module together.

This is a runnable, self-contained example showing the full stack:
  - ServerConfig.from_env        (config.py)   — typed configuration
  - ToolRegistry                 (tool_registry.py) — register + dispatch
  - require_* validation helpers (validation.py) — defensive input checks
  - @safe_tool + @timed          (applied automatically by the registry)
  - structured logging + redact  (observability.py)

It serves synthetic supply-chain data (no real data, no external deps) so you
can run it anywhere and see the patterns in action.

Run the built-in smoke test:  python examples/reference_server/server.py
"""

from __future__ import annotations

import os
import sys

# Make the pattern library importable when run from the repo root or in CI.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

from mcp_patterns.config import ServerConfig
from mcp_patterns.tool_registry import ToolRegistry
from mcp_patterns.validation import require_str, require_int, require_enum
from mcp_patterns.errors import NotFoundError

# --- Synthetic data (clearly fake; safe to run anywhere) -----------------------
_INVENTORY = {
    "SKU-1001": {"on_hand": 240, "location": "DC-EAST"},
    "SKU-1002": {"on_hand": 15, "location": "DC-WEST"},
    "SKU-1003": {"on_hand": 0, "location": "DC-EAST"},
}
_SUPPLIERS = {
    "ACME": {"risk_score": 12, "lead_time_days": 5},
    "GLOBEX": {"risk_score": 68, "lead_time_days": 21},
}


def build_server(config: ServerConfig | None = None) -> ToolRegistry:
    config = config or ServerConfig(server_name="reference-mcp-server")
    registry = ToolRegistry(config.server_name, config.log_level)

    @registry.register(
        "get_inventory",
        "Get on-hand inventory for a SKU.",
        {"type": "object", "properties": {"sku": {"type": "string"}}, "required": ["sku"]},
    )
    def get_inventory(args: dict) -> dict:
        sku = require_str(args, "sku", max_len=32)
        record = _INVENTORY.get(sku)
        if record is None:
            raise NotFoundError(f"Unknown SKU: {sku}", details={"sku": sku})
        return {"sku": sku, **record}

    @registry.register(
        "get_supplier_status",
        "Get risk score and lead time for a supplier.",
        {"type": "object", "properties": {"supplier": {"type": "string"}}, "required": ["supplier"]},
    )
    def get_supplier_status(args: dict) -> dict:
        supplier = require_str(args, "supplier", max_len=32).upper()
        record = _SUPPLIERS.get(supplier)
        if record is None:
            raise NotFoundError(f"Unknown supplier: {supplier}", details={"supplier": supplier})
        return {"supplier": supplier, **record}

    @registry.register(
        "check_reorder",
        "Return whether a SKU needs reordering below a threshold.",
        {"type": "object",
         "properties": {"sku": {"type": "string"}, "threshold": {"type": "integer"}},
         "required": ["sku", "threshold"]},
    )
    def check_reorder(args: dict) -> dict:
        sku = require_str(args, "sku", max_len=32)
        threshold = require_int(args, "threshold", minimum=0, maximum=100000)
        record = _INVENTORY.get(sku)
        if record is None:
            raise NotFoundError(f"Unknown SKU: {sku}", details={"sku": sku})
        needs = record["on_hand"] < threshold
        return {"sku": sku, "on_hand": record["on_hand"], "threshold": threshold, "needs_reorder": needs}

    return registry


def _smoke_test() -> int:
    """Exercise the server through the registry the way a transport would."""
    registry = build_server(ServerConfig(server_name="reference-mcp-server", log_level="ERROR"))
    checks = []

    r = registry.dispatch("get_inventory", {"sku": "SKU-1001"})
    checks.append(("get_inventory ok", r["ok"] is True and r["data"]["on_hand"] == 240))

    r = registry.dispatch("get_inventory", {"sku": "NOPE"})
    checks.append(("unknown sku -> not_found", r["ok"] is False and r["error"]["code"] == "not_found"))

    r = registry.dispatch("get_inventory", {})
    checks.append(("missing arg -> validation_error", r["ok"] is False and r["error"]["code"] == "validation_error"))

    r = registry.dispatch("check_reorder", {"sku": "SKU-1002", "threshold": 20})
    checks.append(("reorder true", r["ok"] is True and r["data"]["needs_reorder"] is True))

    r = registry.dispatch("check_reorder", {"sku": "SKU-1001", "threshold": 20})
    checks.append(("reorder false", r["ok"] is True and r["data"]["needs_reorder"] is False))

    r = registry.dispatch("get_supplier_status", {"supplier": "globex"})
    checks.append(("supplier normalized", r["ok"] is True and r["data"]["risk_score"] == 68))

    r = registry.dispatch("nonexistent_tool", {})
    checks.append(("unknown tool -> not_found", r["ok"] is False and r["error"]["code"] == "not_found"))

    tools = registry.list_tools()
    checks.append(("lists 3 tools", len(tools) == 3))

    all_ok = True
    for label, passed in checks:
        print(f"  {'✅' if passed else '❌'} {label}")
        all_ok = all_ok and passed
    print("RESULT:", "✅ reference server smoke test passed" if all_ok else "❌ FAILED")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(_smoke_test())

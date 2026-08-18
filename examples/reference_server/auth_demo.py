"""Auth-enabled reference server — demonstrates the full 6-module stack.

Extends the base reference server with:
  - KeyRegistry           (auth.py) — API key validation
  - RoleManager           (auth.py) — role-based tool scoping
  - @require_auth         (auth.py) — decorator enforcing auth per tool

Two roles:
  - "admin"  → access to all tools (get_inventory, get_supplier_status, check_reorder)
  - "reader" → access to read-only tools (get_inventory, check_reorder)

Run the built-in smoke test:
    MCP_API_KEYS="admin-key-123:ops-team:admin,reader-key-456:analyst:reader" \
    python examples/reference_server/auth_demo.py
"""

from __future__ import annotations

import io
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

from mcp_patterns.config import ServerConfig
from mcp_patterns.tool_registry import ToolRegistry
from mcp_patterns.validation import require_str, require_int
from mcp_patterns.errors import NotFoundError
from mcp_patterns.auth import KeyRegistry, RoleManager, AuthError, ForbiddenError

# --- Synthetic data ---
_INVENTORY = {
    "SKU-1001": {"on_hand": 240, "location": "DC-EAST"},
    "SKU-1002": {"on_hand": 15, "location": "DC-WEST"},
}
_SUPPLIERS = {
    "ACME": {"risk_score": 12, "lead_time_days": 5},
    "GLOBEX": {"risk_score": 68, "lead_time_days": 21},
}


def build_auth_server(env: dict[str, str] | None = None) -> tuple:
    """Build the auth-enabled server. Returns (registry, key_registry, roles)."""
    env = env or dict(os.environ)

    config = ServerConfig(server_name="auth-reference-server", log_level="ERROR")
    registry = ToolRegistry(config.server_name, config.log_level)

    # Set up auth
    key_registry = KeyRegistry.from_env("MCP_API_KEYS", env=env)
    roles = RoleManager()
    roles.define("admin", {"get_inventory", "get_supplier_status", "check_reorder"})
    roles.define("reader", {"get_inventory", "check_reorder"})

    # Register tools (same as base server)
    @registry.register("get_inventory", "Get on-hand inventory for a SKU.")
    def get_inventory(args: dict) -> dict:
        sku = require_str(args, "sku", max_len=32)
        record = _INVENTORY.get(sku)
        if record is None:
            raise NotFoundError(f"Unknown SKU: {sku}", details={"sku": sku})
        return {"sku": sku, **record}

    @registry.register("get_supplier_status", "Get risk score and lead time for a supplier.")
    def get_supplier_status(args: dict) -> dict:
        supplier = require_str(args, "supplier", max_len=32).upper()
        record = _SUPPLIERS.get(supplier)
        if record is None:
            raise NotFoundError(f"Unknown supplier: {supplier}", details={"supplier": supplier})
        return {"supplier": supplier, **record}

    @registry.register("check_reorder", "Return whether a SKU needs reordering.")
    def check_reorder(args: dict) -> dict:
        sku = require_str(args, "sku", max_len=32)
        threshold = require_int(args, "threshold", minimum=0, maximum=100000)
        record = _INVENTORY.get(sku)
        if record is None:
            raise NotFoundError(f"Unknown SKU: {sku}", details={"sku": sku})
        return {"sku": sku, "on_hand": record["on_hand"], "needs_reorder": record["on_hand"] < threshold}

    return registry, key_registry, roles


def dispatch_with_auth(registry, key_registry, roles, tool_name: str, args: dict, api_key: str) -> dict:
    """Dispatch a tool call with authentication and authorization checks.

    This is the pattern for wiring auth into dispatch:
    1. Validate the API key → get identity + role
    2. Check role has access to the requested tool
    3. If both pass, dispatch the tool normally
    """
    from mcp_patterns.errors import to_error_payload

    try:
        # Step 1: Authenticate
        entry = key_registry.validate(api_key)
        # Step 2: Authorize
        roles.check_access(entry.role, tool_name)
    except (AuthError, ForbiddenError) as exc:
        return to_error_payload(exc)

    # Step 3: Dispatch (already crash-proof via registry)
    return registry.dispatch(tool_name, args)


def _smoke_test() -> int:
    """Exercise the auth-enabled server."""
    env = {"MCP_API_KEYS": "admin-key:ops-team:admin,reader-key:analyst:reader"}
    registry, key_registry, roles = build_auth_server(env=env)

    # Silence logging
    registry._logger.handlers[0].stream = io.StringIO()

    checks = []

    # Admin can access all tools
    r = dispatch_with_auth(registry, key_registry, roles, "get_inventory", {"sku": "SKU-1001"}, "admin-key")
    checks.append(("admin → get_inventory", r["ok"] is True and r["data"]["on_hand"] == 240))

    r = dispatch_with_auth(registry, key_registry, roles, "get_supplier_status", {"supplier": "acme"}, "admin-key")
    checks.append(("admin → get_supplier_status", r["ok"] is True and r["data"]["risk_score"] == 12))

    # Reader can access read-only tools
    r = dispatch_with_auth(registry, key_registry, roles, "get_inventory", {"sku": "SKU-1002"}, "reader-key")
    checks.append(("reader → get_inventory", r["ok"] is True and r["data"]["on_hand"] == 15))

    r = dispatch_with_auth(registry, key_registry, roles, "check_reorder", {"sku": "SKU-1002", "threshold": 20}, "reader-key")
    checks.append(("reader → check_reorder", r["ok"] is True and r["data"]["needs_reorder"] is True))

    # Reader CANNOT access get_supplier_status (forbidden)
    r = dispatch_with_auth(registry, key_registry, roles, "get_supplier_status", {"supplier": "acme"}, "reader-key")
    checks.append(("reader → supplier (FORBIDDEN)", r["ok"] is False and r["error"]["code"] == "forbidden"))

    # Invalid key is rejected
    r = dispatch_with_auth(registry, key_registry, roles, "get_inventory", {"sku": "SKU-1001"}, "bad-key")
    checks.append(("bad key → auth_error", r["ok"] is False and r["error"]["code"] == "auth_error"))

    # Missing key is rejected
    r = dispatch_with_auth(registry, key_registry, roles, "get_inventory", {"sku": "SKU-1001"}, "")
    checks.append(("empty key → auth_error", r["ok"] is False and r["error"]["code"] == "auth_error"))

    # Key never leaks in error response
    r = dispatch_with_auth(registry, key_registry, roles, "get_inventory", {"sku": "SKU-1001"}, "super-secret-key-xyz")
    checks.append(("key not in error", "super-secret" not in str(r)))

    all_ok = True
    for label, passed in checks:
        print(f"  {'✅' if passed else '❌'} {label}")
        all_ok = all_ok and passed

    print(f"\nRESULT: {'✅ auth demo passed' if all_ok else '❌ FAILED'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(_smoke_test())

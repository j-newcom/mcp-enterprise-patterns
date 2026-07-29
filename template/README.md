# Server Template

A minimal starting point for a new MCP server built on `mcp_patterns`.

## Use it

1. Copy `server_skeleton/server.py` into your new project.
2. Install the pattern library (from this repo, or vendor `src/mcp_patterns/`).
3. Replace the `echo` / `get_item` example tools with your own — each tool is a
   function `(args: dict) -> dict` registered via `@registry.register(...)`.
4. Set config via environment variables (see below) and wire `build_server()`
   into your transport (stdio, HTTP, etc.).

## Environment variables

| Var | Required | Default | Meaning |
|-----|----------|---------|---------|
| `MCP_SERVER_NAME` | yes | — | Logical server name (used in logs) |
| `MCP_LOG_LEVEL` | no | `INFO` | Logging level |
| `MCP_REQUEST_TIMEOUT_S` | no | `30` | Per-request timeout (seconds) |
| `MCP_USE_SYNTHETIC_DATA` | no | `true` | Whether to serve synthetic data |

## What you get for free

Every tool you register is automatically:
- **validated** — use the `require_*` helpers for defensive input checks
- **crash-proof** — a raised exception becomes a structured error, never a crash
- **observable** — start/end/duration logged as JSON, secrets redacted

See the repo README and `docs/PATTERNS.md` for the full guide.

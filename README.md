# MCP Enterprise Patterns

Production-grade building blocks for enterprise **Model Context Protocol (MCP)**
servers. Stop reinventing config loading, error handling, input validation,
observability, and tool dispatch on every server — compose these tested patterns
instead.

Extracted from real MCP servers ([agent-bridge-mcp](https://github.com/j-newcom/agent-bridge-mcp),
[supply-chain-mcp-server](https://github.com/j-newcom/supply-chain-mcp-server)) and
hardened for reuse. Zero runtime dependencies — the entire pattern library is
standard-library Python.

## Why this exists

Most MCP examples show you a "hello world" server. Going to production means
answering the questions the examples skip:

- How do I load config and **fail fast** when a required env var is missing?
- How do I make sure a raised exception **never crashes the server** or **leaks a
  stack trace** to the model?
- How do I **validate** arguments an LLM hands my tools?
- How do I get **structured logs** and timing **without ever logging a secret**?
- How do I register and dispatch tools **consistently**?

This repo answers each with a small, tested module — and a reference server that
wires them all together.

## What's inside

| Deliverable | Path | What it gives you |
|-------------|------|-------------------|
| **Pattern modules** | `src/mcp_patterns/` | 5 composable modules (below) |
| **Reference server** | `examples/reference_server/` | A runnable server using every pattern |
| **Server template** | `template/server_skeleton/` | Clonable starting point for a new server |
| **Client recipes** | `recipes/` | Copy-paste config for Claude Desktop, Amazon Q, Kiro, Amazon Quick |
| **Best-practices guide** | `docs/PATTERNS.md` | The "why" behind each pattern |

### The five patterns

| Module | Responsibility |
|--------|----------------|
| `config.py` | Typed environment config loading. Fails fast with the exact missing var name. |
| `errors.py` | Error taxonomy (`validation` / `not_found` / `upstream` / `internal`) + `@safe_tool` — turns any exception into a structured response, never a leaked trace. |
| `validation.py` | Defensive input helpers (`require_str`, `require_int`, `require_enum`, …) that raise clean validation errors. |
| `observability.py` | JSON structured logging, `@timed` for per-tool duration, and `redact()` that strips secrets at any nesting depth. |
| `tool_registry.py` | Register + dispatch tools. Every registered tool is automatically crash-proof and observable. |

## Quick start

```bash
git clone https://github.com/j-newcom/mcp-enterprise-patterns.git
cd mcp-enterprise-patterns

# Run the reference server's smoke test (standard library only — no install)
python examples/reference_server/server.py
```

You'll see each tool exercised — success, not-found, and validation-error paths —
all returning clean structured envelopes.

### Use the patterns in your own server

```python
from mcp_patterns import ToolRegistry, ServerConfig, require_str, NotFoundError

config = ServerConfig.from_env()          # reads MCP_SERVER_NAME etc.
registry = ToolRegistry(config.server_name, config.log_level)

@registry.register("get_order", "Fetch an order by id.")
def get_order(args: dict) -> dict:
    order_id = require_str(args, "order_id", max_len=32)   # validates input
    order = db.get(order_id)
    if order is None:
        raise NotFoundError(f"Unknown order: {order_id}")  # -> structured error
    return order                                           # -> {"ok": True, "data": ...}

# Your transport layer just calls:
result = registry.dispatch("get_order", {"order_id": "A-100"})
```

That tool is now automatically validated, crash-proof, timed, and logged — with
zero secret leakage — because the registry composes all five patterns.

## Development

```bash
pip install -e ".[dev]"
pytest -v
```

CI runs the full suite plus the reference-server smoke test on Python 3.11 and 3.12.

## Design principles

- **Zero runtime dependencies.** The pattern library is pure standard library.
- **Secrets never leak.** `redact()` and the sanitized internal-error path are
  tested to prove no secret reaches a log or a client response.
- **Crash-proof by construction.** A registered tool that raises returns a
  structured error; it can never take the server down.
- **Synthetic data only.** The reference server uses fabricated data — safe to run
  anywhere.

## Related work

- [agent-bridge-mcp](https://github.com/j-newcom/agent-bridge-mcp) — MCP server these patterns were extracted from
- [supply-chain-mcp-server](https://github.com/j-newcom/supply-chain-mcp-server) — the second server that informed these patterns
- [retail-cpg-eval-datasets](https://github.com/j-newcom/retail-cpg-eval-datasets) — evaluate the tools you build with these patterns

## License

Apache-2.0 — see [LICENSE](LICENSE).

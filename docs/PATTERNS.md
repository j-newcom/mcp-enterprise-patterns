# Production MCP Patterns — Best-Practices Guide

The "why" behind each module. These patterns were extracted from building real
MCP servers and hardened for reuse.

---

## 1. Config: fail fast, fail loud

**Problem.** A server that reads `os.environ["BUCKET"]` deep inside a handler
crashes at request time with a `KeyError` — long after startup, with no hint
about what's misconfigured.

**Pattern.** Load and validate all config at startup with typed getters
(`get_str`, `get_int`, `get_bool`, `get_float`). A missing *required* var raises
`ConfigError` naming the exact variable. Optional vars get explicit defaults.
Blank strings are treated as missing (a common `.env` foot-gun).

```python
config = ServerConfig.from_env()   # raises immediately if MCP_SERVER_NAME is unset
```

**Rule of thumb.** If the server can't run correctly without it, mark it
`required=True` and discover the problem at boot, not mid-request.

---

## 2. Errors: never leak, never crash

**Problem.** An unhandled exception in a tool either crashes the server or —
worse — serializes a stack trace (with file paths, queries, secrets) straight
back to the model/client.

**Pattern.** A small error taxonomy with stable machine codes:

| Exception | code | Use when |
|-----------|------|----------|
| `ValidationError` | `validation_error` | Bad/missing input |
| `NotFoundError` | `not_found` | Entity doesn't exist |
| `UpstreamError` | `upstream_error` | A dependency (DB/API/ERP) failed |
| `InternalError` | `internal_error` | Anything else |

`@safe_tool` wraps a handler so **any** exception becomes a structured
`{"ok": false, "error": {...}}` payload. Known errors keep their message; unknown
exceptions are replaced with a generic message so **internal details never leak**.
Turn on `include_trace=True` only for local debugging.

---

## 3. Validation: distrust every argument

**Problem.** Tool arguments come from an LLM. They will be missing, the wrong
type, out of range, or `True` where you expected an int.

**Pattern.** Compose small `require_*` helpers that validate *and* return the
coerced value, raising `ValidationError` (rendered as `validation_error`) on
failure.

```python
sku = require_str(args, "sku", max_len=64)
qty = require_int(args, "quantity", minimum=1, maximum=100_000)
kind = require_enum(args, "doc_type", ["850", "856"])
```

**Gotcha handled for you.** `bool` is a subclass of `int` in Python, so a naive
`isinstance(x, int)` accepts `True`. `require_int` rejects booleans explicitly.

---

## 4. Observability: structured, timed, and secret-safe

**Problem.** Plain-text logs are hard to query, and it's easy to accidentally log
an auth header or a bucket secret.

**Pattern.**
- `get_logger()` emits **JSON lines** — one object per event, easy to ship to any
  aggregator.
- `@timed` logs `tool.start` / `tool.end` with `duration_ms`, and on failure logs
  `tool.error` with the error *code* (never the trace).
- `redact()` strips sensitive keys (`password`, `token`, `authorization`,
  `x-bridge-secret`, …) at **any nesting depth**, case-insensitively, without
  mutating the input.

**Rule of thumb.** Log the *shape* of a request, never its secrets. Run inputs
through `redact()` before logging.

---

## 5. Tool registry: one place, consistent behavior

**Problem.** Tools defined ad hoc across a server get inconsistent error handling
and logging — some crash-proof, some not.

**Pattern.** Register every tool in one `ToolRegistry`. The registry composes
`@timed` (observability) and `@safe_tool` (crash-proofing) automatically, so every
registered tool behaves identically:

```python
@registry.register("get_inventory", "Get stock by SKU.")
def get_inventory(args): ...

result = registry.dispatch("get_inventory", {"sku": "SKU-1"})  # always a clean envelope
```

`list_tools()` gives you discovery metadata for the MCP handshake, and unknown
tool names return a `not_found` envelope rather than raising.

---

## 6. Auth: validate, scope, never leak

**Problem.** An MCP server exposed without authentication lets any caller invoke
any tool. Even with auth, a common failure is logging the API key in error
messages or returning it in structured error responses.

**Pattern.** Three components:

- `KeyRegistry` — stores API keys as SHA-256 hashes (never plaintext). Validates
  incoming keys and returns the associated identity + role. Load from environment:

```python
# env: MCP_API_KEYS="key1:alice:admin,key2:bob:reader"
registry = KeyRegistry.from_env("MCP_API_KEYS")
entry = registry.validate(request_key)  # returns KeyEntry(identity, role) or raises AuthError
```

- `RoleManager` — maps roles to allowed tool sets. Wildcard `{"*"}` grants all.

```python
roles = RoleManager()
roles.define("admin", {"*"})
roles.define("reader", {"get_inventory", "get_forecast"})
roles.check_access("reader", "create_po")  # raises ForbiddenError
```

- `@require_auth` — decorator that validates the key and checks the role before
  the tool executes. Injects the caller's identity so the tool can use it.

```python
@require_auth(registry, roles)
def get_inventory(args: dict, auth: KeyEntry = None) -> dict:
    # auth.identity = "alice", auth.role = "admin"
    ...
```

**Security guarantees:**
- Keys are hashed with SHA-256 — the registry never stores plaintext.
- `AuthError` and `ForbiddenError` messages **never** contain the presented key.
- The `redact()` function (from observability) catches `api_key`, `token`,
  `authorization` in log output — but auth errors are additionally hardened to
  never echo the credential even in the `details` dict.

**Rule of thumb.** Auth should fail closed: if the key is missing, empty, or
invalid, reject immediately. Never fall through to a "default" identity.

See `examples/reference_server/auth_demo.py` for the full pattern wired into a
working server with admin + reader roles.

---

## Putting it together

See `examples/reference_server/server.py` for a server using the core five
patterns, and `examples/reference_server/auth_demo.py` for the full six-module
stack with authentication. The composition order matters: **timing wraps the raw call**
(so it can measure and log even a failure), and **safe_tool wraps the timed call**
(so the logged failure still becomes a clean client response). Auth validates
*before* dispatch — if the caller lacks permission, the tool never fires.
The registry handles timing + safe_tool; auth wraps the dispatch layer.

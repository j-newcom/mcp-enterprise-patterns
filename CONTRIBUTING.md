# Contributing

Contributions that add patterns, harden existing ones, or expand the recipes are
welcome.

## Ground rules

1. **Zero runtime dependencies** in `src/mcp_patterns/`. The pattern library must
   stay pure standard library. Dev/test dependencies belong in the `dev` extra.
2. **No secrets, ever.** No real credentials, tokens, internal hostnames, or
   customer data in code, tests, or docs. The reference server uses synthetic data.
3. **Every pattern is tested.** New behavior needs tests — especially the security
   properties (no secret leakage, crash-proofing).

## Adding a pattern

1. Add `src/mcp_patterns/<pattern>.py` — pure functions/classes, type-hinted,
   `from __future__ import annotations`.
2. Export public names in `src/mcp_patterns/__init__.py`.
3. Add `tests/test_<pattern>.py` with success, failure, and edge cases.
4. If it's security-relevant, add an explicit test proving the safe behavior.
5. Document it in `docs/PATTERNS.md` and the README table.

## Running the suite

```bash
pip install -e ".[dev]"
pytest -v
python examples/reference_server/server.py
```

Both must pass. CI runs them on Python 3.11 and 3.12.

## Style

- Small, single-purpose functions.
- Explicit error messages (they become the client-facing message).
- Match the existing module structure and docstring style.

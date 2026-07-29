# Client Integration Recipes

Copy-paste configuration for connecting an MCP server (built with these patterns)
to common clients. Replace `/path/to/your-server` and any env values with your own.

> All snippets assume a stdio MCP server started via `uv run server.py`. Adjust the
> command/args if you package your server differently.

---

## Claude Desktop

Add to `claude_desktop_config.json`
(macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "my-server": {
      "command": "uv",
      "args": ["run", "server.py"],
      "cwd": "/path/to/your-server",
      "env": {
        "MCP_SERVER_NAME": "my-server",
        "MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

---

## Amazon Q Developer CLI

Add to `~/.aws/amazonq/mcp.json`:

```json
{
  "mcpServers": {
    "my-server": {
      "command": "uv",
      "args": ["run", "server.py"],
      "cwd": "/path/to/your-server",
      "env": { "MCP_SERVER_NAME": "my-server" }
    }
  }
}
```

---

## Kiro

In Kiro's MCP settings (`.kiro/settings/mcp.json` in your workspace, or the global
equivalent):

```json
{
  "mcpServers": {
    "my-server": {
      "command": "uv",
      "args": ["run", "server.py"],
      "cwd": "/path/to/your-server",
      "env": { "MCP_SERVER_NAME": "my-server" },
      "disabled": false
    }
  }
}
```

---

## Amazon Quick

Settings → Capabilities → MCP → Add Server:

- **Command:** `uv`
- **Args:** `run server.py`
- **Working directory:** `/path/to/your-server`
- **Env:** `MCP_SERVER_NAME=my-server`

---

## Notes

- **Secrets:** pass secrets via `env` in the client config or your OS keychain —
  never hard-code them in the server. The observability layer redacts common
  secret keys from logs, but the safest secret is one that never enters your code.
- **Absolute paths:** most clients don't expand `~`. Use absolute paths for `cwd`.
- **`uv` not found:** ensure `uv` is on the PATH the client launches with, or use
  an absolute path to the `uv` binary.

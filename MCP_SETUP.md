# MCP server setup for Claude

Homebrew's Python is externally managed, so we use a **dedicated venv** in your home directory.

## One-time setup

From the project root, run:

```bash
chmod +x scripts/setup_mcp_venv.sh
./scripts/setup_mcp_venv.sh
```

This creates `~/venvs/automotive-mcp`, installs the MCP + backend dependencies there, and prints the paths to use.

## Claude config

Copy the contents of `claude_mcp_config.json` into Claude's config (Settings → Developer → Edit Config). The config is already set to use `~/venvs/automotive-mcp/bin/python`. Save and restart Claude.

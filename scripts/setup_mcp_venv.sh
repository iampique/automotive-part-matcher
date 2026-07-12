#!/usr/bin/env bash
# One-time setup: create a venv for the MCP server (avoids Homebrew's externally-managed Python).
# Run from the project root:  ./scripts/setup_mcp_venv.sh

set -e
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$HOME/venvs/automotive-mcp}"

echo "Creating venv at: $VENV_DIR"
mkdir -p "$(dirname "$VENV_DIR")"
python3 -m venv "$VENV_DIR"

echo "Installing MCP + backend dependencies..."
"$VENV_DIR/bin/pip" install -r "$PROJECT_ROOT/mcp/requirements.txt"

echo "Done. Add this to your MCP client config (command/args):"
echo "  \"command\": \"$VENV_DIR/bin/python\","
echo "  \"args\": [\"$PROJECT_ROOT/mcp/server.py\"],"
echo "  \"cwd\": \"$PROJECT_ROOT\","
echo "  \"env\": { \"PYTHONPATH\": \"$PROJECT_ROOT\" }"
echo ""
echo "See mcp/README.md for full setup notes."

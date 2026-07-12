# MCP server

Exposes Automotive Connector Matcher search and graph tools to MCP-compatible clients (e.g. Claude Desktop).

## Setup

From the repository root:

```bash
./scripts/setup_mcp_venv.sh
```

Or manually:

```bash
python3 -m venv ~/venvs/automotive-mcp
source ~/venvs/automotive-mcp/bin/activate
pip install -r mcp/requirements.txt
```

Configure `backend/.env` (same keys as the API). The server loads `mcp/.env` then `backend/.env`.

## Run / client config

`PYTHONPATH` must be the **repository root** so `backend.app` imports resolve.

Example Claude Desktop / MCP config:

```json
{
  "mcpServers": {
    "automotive-part-matcher": {
      "command": "/path/to/venvs/automotive-mcp/bin/python",
      "args": ["/path/to/automotive-part-matcher/mcp/server.py"],
      "cwd": "/path/to/automotive-part-matcher",
      "env": {
        "PYTHONPATH": "/path/to/automotive-part-matcher"
      }
    }
  }
}
```

Or:

```bash
cd /path/to/automotive-part-matcher
PYTHONPATH=. python mcp/server.py
```

## Tools

| Tool | Description |
|------|-------------|
| `search_connectors` | Semantic / hybrid connector search |
| `get_similar_connectors` | Similar parts for a part number |
| `get_part_impact` | Impact analysis (Neo4j) |
| `get_assembly_compliance` | Compliance inheritance (Neo4j) |
| `get_supplier_risk` | Supplier concentration risk (Neo4j) |
| `get_part_sourcing` | Primary supplier for a part (Neo4j) |
| `analyze_disruption` | Full disruption mitigation workflow |

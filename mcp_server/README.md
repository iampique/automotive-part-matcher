# MCP server

Exposes the full Automotive Connector Matcher product core to MCP clients such as **Claude Desktop**: Qdrant search plus Neo4j graph and disruption tools in one process.

> **Note:** This directory is named `mcp_server/` (not `mcp/`) so it does not shadow the PyPI [`mcp`](https://pypi.org/project/mcp/) package when `PYTHONPATH` is the repo root.

## Requirements

- Python 3.10+
- `backend/.env` configured with **Qdrant**, **LLM** keys, and **Neo4j** (both stores are required for the full experience)
- Graph data ingested (`python ingest_data.py --with-graph` or `ingest_graph.py`)

## Setup

From the repository root:

```bash
./scripts/setup_mcp_venv.sh
```

Or manually:

```bash
python3 -m venv ~/venvs/automotive-mcp
source ~/venvs/automotive-mcp/bin/activate
pip install -r mcp_server/requirements.txt
```

After backend dependency changes, reinstall into the MCP venv:

```bash
~/venvs/automotive-mcp/bin/pip install -r mcp_server/requirements.txt
```

## Claude Desktop config

`cwd` should be the repository root. The server also adjusts `sys.path` so `backend.app` and `app.*` imports resolve.

```json
{
  "mcpServers": {
    "automotive-part-matcher": {
      "command": "/path/to/venvs/automotive-mcp/bin/python",
      "args": ["/path/to/automotive-part-matcher/mcp_server/server.py"],
      "cwd": "/path/to/automotive-part-matcher",
      "env": {
        "PYTHONPATH": "/path/to/automotive-part-matcher:/path/to/automotive-part-matcher/backend"
      }
    }
  }
}
```

Or run directly:

```bash
cd /path/to/automotive-part-matcher
PYTHONPATH=.:backend python mcp_server/server.py
```

Fully quit and reopen Claude Desktop after changing this file or the server code.

### Cold start

The first tool call in a session imports the FastAPI stack and connects to Qdrant/Neo4j — expect a few seconds of delay. Later calls in the same process are much faster.

## Routing (server instructions)

Claude receives intent→tool routing instructions (not a fixed pipeline):

| Intent | Tool |
|--------|------|
| Mitigate shortage / obsolete part | `analyze_disruption` directly |
| Find parts by requirements | `search_connectors` |
| What breaks if part X is gone | `get_part_impact` |
| Compliance / suppliers / SPOF | matching Neo4j `get_*` tools |
| Connectivity check | `get_health` only when asked or after a failure |

Large tools default to `detail="summary"`; pass `detail="full"` for complete payloads.

## Tools

All tools are annotated read-only.

### Health

| Tool | Description |
|------|-------------|
| `get_health` | Qdrant + Neo4j connectivity status |

### Search (Qdrant)

| Tool | Description |
|------|-------------|
| `search_connectors` | Natural-language / document connector search |
| `get_connector` | Catalog details for a part number |
| `get_similar_connectors` | Vector-similar alternatives |

### Graph (Neo4j)

| Tool | Description |
|------|-------------|
| `get_part_impact` | Vehicles/assemblies affected if a part is unavailable |
| `get_assembly_compliance` | Requirements cascading through an assembly |
| `get_connector_compliance` | Compliance gaps for a connector part |
| `get_part_sourcing` | Primary supplier for a part |
| `get_supplier_risk` | Supplier concentration risk |
| `get_supplier_spof` | Sole-source (SPOF) critical parts |
| `get_supplier_connectors` | Connectors for a given supplier id |

### Disruption (Neo4j + Qdrant)

| Tool | Description |
|------|-------------|
| `analyze_disruption` | Full mitigation workflow: impact → alternatives → compliance → supplier risk |

## Prompts

| Prompt | Purpose |
|--------|---------|
| `mitigate_shortage` | Starter for disruption analysis on a part (default `EC-2024-3441`) |
| `find_connector` | Starter for catalog search from free-text requirements |

## Resources

| URI | Contents |
|-----|----------|
| `catalog://demo/hero-parts` | Demo part numbers |
| `catalog://demo/sample-queries` | Example search strings |

## Typical Claude flows

1. **Find a part:** `search_connectors` → `get_connector`
2. **What breaks?** `get_part_impact` → `get_connector_compliance`
3. **Supplier risk:** `get_supplier_risk` → `get_supplier_spof` → `get_supplier_connectors`
4. **Mitigate shortage:** `analyze_disruption` on the disrupted part number (no health check required)

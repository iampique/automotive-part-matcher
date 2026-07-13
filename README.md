# Automotive Connector Matcher

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

AI-powered matching for automotive electrical connectors. Engineers describe requirements in natural language (or upload a PDF/DOCX), and the system searches a catalog of 500+ connector variants using semantic search, structured scoring, and graph analysis over vehicle/BOM/supplier relationships.

## Features

- **Semantic + hybrid search** — vector similarity (Qdrant) with full-text matching for part names
- **LLM requirement extraction** — Claude or GPT parses free text into structured specs
- **ACORN filtered search** — better recall when many hard filters are applied
- **LangGraph workflow** — parse → search → score → rank with an execution trace
- **Document upload** — PDF / DOCX requirements
- **Neo4j knowledge graph** — impact analysis, compliance inheritance, supplier risk, disruption mitigation
- **MCP server** — expose search and graph tools to MCP-compatible clients

## Architecture

```text
Requirements (text / PDF)
        │
        ▼
   LangGraph agent
   parse → search → score → rank
        │
   ┌────┴────┐
   ▼         ▼
 Qdrant     Neo4j
 vectors    relationships
```

| Store | Role |
|-------|------|
| **Qdrant** | Semantic connector matching and similar-part recommendations |
| **Neo4j** | Impact, compliance cascading, supplier topology, disruption workflows |

Both stores are required for the full product experience. Qdrant answers “what matches these specs?”; Neo4j answers “what breaks, who supplies it, and what compliance cascades apply?”

## Quick start

**Prerequisites:** Python 3.9+, Node.js 18+, Qdrant (local Docker or cloud), Neo4j (AuraDB or local), OpenAI API key (embeddings), and Anthropic or OpenAI for extraction.

```bash
# 1. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit with Qdrant, Neo4j, and LLM keys
./setup_local_qdrant.sh  # or point QDRANT_URL at cloud
python ingest_data.py --with-graph
uvicorn app.main:app --reload --port 8000

# 2. Frontend (new terminal)
cd frontend
cp .env.example .env.local   # optional
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). API docs: [http://localhost:8000/docs](http://localhost:8000/docs).

One-shot demo helper: `./scripts/start_demo.sh`

## Documentation

| Doc | Contents |
|-----|----------|
| [Setup](docs/setup.md) | Env vars, Qdrant, Neo4j, ingestion |
| [Architecture](docs/architecture.md) | Dual-store design, workflow, ACORN/hybrid |
| [Configuration](docs/configuration.md) | Matching tolerances and thresholds |
| [Testing](docs/testing.md) | Pytest, manual UI checks |
| [MCP](mcp_server/README.md) | MCP server setup |
| [Contributing](CONTRIBUTING.md) | How to contribute |
| [Security](SECURITY.md) | Vulnerability reporting |

## Sample data

- Catalog: [`data/raw/connector_catalog.json`](data/raw/connector_catalog.json)
- Graph seed: [`data/raw/graph_seed.json`](data/raw/graph_seed.json)
- Example requirements: [`data/sample_requirements/`](data/sample_requirements/)

## License

MIT — see [LICENSE](LICENSE).

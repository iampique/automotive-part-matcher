# Setup

## Prerequisites

- Python 3.9+
- Node.js 18+
- Docker (for local Qdrant and/or Neo4j)
- API keys: OpenAI (embeddings), Anthropic and/or OpenAI (requirement extraction)
- Optional: [Qdrant Cloud](https://cloud.qdrant.io) and/or [Neo4j AuraDB](https://neo4j.com/cloud/platform/aura-graph-database/)

## Environment

```bash
cd backend
cp .env.example .env
```

Edit `.env` with your credentials. Required for core search:

| Variable | Description |
|----------|-------------|
| `QDRANT_URL` | Local (`http://localhost:6333`) or cloud URL |
| `QDRANT_API_KEY` | Required for Qdrant Cloud; empty for local |
| `OPENAI_API_KEY` | Embeddings (`text-embedding-3-large`) |
| `ANTHROPIC_API_KEY` | Claude extraction (if `LLM_PROVIDER=claude`) |
| `LLM_PROVIDER` | `claude` or `openai` |

Optional Neo4j (graph features disabled if unset):

| Variable | Description |
|----------|-------------|
| `NEO4J_URI` | e.g. `neo4j+s://….databases.neo4j.io` or `bolt://localhost:7687` |
| `NEO4J_USERNAME` | Default `neo4j` |
| `NEO4J_PASSWORD` | Database password |

Frontend (optional):

```bash
cd frontend
cp .env.example .env.local
```

`NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000`.

## Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Local Qdrant

```bash
./setup_local_qdrant.sh
```

This starts a Docker container on port 6333 and updates `.env`. Dashboard: [http://localhost:6333/dashboard](http://localhost:6333/dashboard).

If port 6333 is busy:

```bash
docker stop qdrant && docker rm qdrant
# or map another host port and set QDRANT_URL accordingly
```

### Ingest connector data

```bash
python ingest_data.py
```

Loads `data/raw/connector_catalog.json`, creates the collection, and uploads embeddings.

Useful helpers:

| Script | Purpose |
|--------|---------|
| `ingest_data.py` | Qdrant catalog ingest (`--with-graph` also loads Neo4j) |
| `ingest_graph.py` | Neo4j graph ingest (`--dry-run` supported) |
| `ensure_indexes.py` | Ensure Qdrant indexes |
| `check_ingestion_status.py` / `monitor_ingestion.py` | Ingest status |
| `check_duplicates.py` | Duplicate checks |
| `scripts/preflight_demo.py` | Demo health checks |
| `test_system.py` | End-to-end smoke test against live services |

### Run API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API: `http://localhost:8000`
- OpenAPI: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

## Frontend

```bash
cd frontend
npm install
npm run dev
```

UI: [http://localhost:3000](http://localhost:3000).

Or start both from the repo root:

```bash
./scripts/start_demo.sh
```

## Neo4j (optional)

Without `NEO4J_URI` / `NEO4J_PASSWORD`, search still works; graph endpoints return `503`.

### AuraDB Free

1. Create an instance at Neo4j Aura.
2. Set `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` in `backend/.env`.
3. Generate seed (if needed) and ingest:

```bash
cd backend
python scripts/generate_graph_seed.py
python ingest_graph.py
# or: python ingest_data.py --with-graph
```

### Local Neo4j

```bash
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5-community
```

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
```

### Graph endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/graph/impact/{part_number}` | Vehicles/assemblies affected by part unavailability |
| `GET /api/graph/compliance/{assembly_id}` | Inherited requirements for an assembly |
| `GET /api/graph/compliance/connector/{part_number}` | Compliance gaps for a connector |
| `GET /api/graph/suppliers/risk` | Supplier concentration risk |
| `GET /api/graph/suppliers/spof` | Sole-source critical parts |
| `GET /api/graph/suppliers/{supplier_id}/connectors` | Connectors by supplier |

Verify:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/graph/suppliers/risk
```

## MCP

See [mcp/README.md](../mcp/README.md).

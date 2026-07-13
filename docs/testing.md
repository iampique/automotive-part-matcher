# Testing

## Automated tests (backend)

```bash
cd backend
source .venv/bin/activate   # or your venv
pip install -r requirements.txt
pytest tests/ -v
```

| Suite | Needs live Neo4j? |
|-------|-------------------|
| `tests/test_neo4j_service.py` | No (mocked) |
| `tests/test_mitigation_scoring.py` | No |
| `tests/test_disruption_agent.py` | No |
| `tests/test_graph_api.py` | Yes (`NEO4J_URI`, `NEO4J_PASSWORD`) |

```bash
# Unit / offline
pytest tests/test_neo4j_service.py -v

# Graph API integration
NEO4J_URI=... NEO4J_PASSWORD=... pytest tests/test_graph_api.py -m neo4j -v
```

## Smoke test against live services

With `.env` configured and Qdrant reachable:

```bash
cd backend
python test_system.py
```

Checks config load, Qdrant connectivity, embeddings, sample upload, and search.

## Manual UI + API check

1. Start backend: `uvicorn app.main:app --reload --port 8000`
2. Start frontend: `cd frontend && npm run dev`
3. Open [http://localhost:3000](http://localhost:3000) and [http://localhost:8000/docs](http://localhost:8000/docs)

Try:

- Text search, e.g. `48-pin connector for EV battery, 48V, IP67, automotive grade`
- Upload a file from `data/sample_requirements/`
- Advanced options: Claude vs OpenAI, ACORN on/off
- Graph / disruption pages and `/health` showing `"neo4j": "connected"`

Health:

```bash
curl http://localhost:8000/health
```

## Common issues

| Symptom | Check |
|---------|--------|
| Backend won’t start | `.env` present; required keys set; port 8000 free |
| Frontend API errors | Backend up; `NEXT_PUBLIC_API_URL`; CORS for localhost:3000 |
| No search results | Run `ingest_data.py`; Qdrant URL/key; collection exists |
| Graph 503 | `NEO4J_URI` / `NEO4J_PASSWORD`; run `ingest_graph.py` |

# Neo4j AuraDB Setup

This guide covers provisioning Neo4j AuraDB Free and connecting it to the automotive part matcher.

## Why Neo4j?

Qdrant handles **vector search** (find similar connectors). Neo4j handles **graph questions** vectors cannot answer:

- **Impact analysis** — which vehicles/assemblies are affected when a part is unavailable
- **Compliance inheritance** — requirements that cascade through assembly hierarchies
- **Supplier topology** — concentration risk and single points of failure

Neo4j is **optional**. If `NEO4J_URI` is unset, the app runs normally and graph endpoints return `503`.

## 1. Create AuraDB Free Instance

1. Go to [neo4j.com/cloud/aura](https://neo4j.com/cloud/platform/aura-graph-database/)
2. Create a free AuraDB instance
3. Save the connection credentials:
   - **URI**: `neo4j+s://xxxx.databases.neo4j.io`
   - **Username**: `neo4j`
   - **Password**: (generated once — save it)

Aura Free limits (~200k nodes, ~400k relationships) are more than enough for this demo.

## 2. Configure Environment

Add to `backend/.env`:

```env
NEO4J_URI=neo4j+s://xxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-aura-password
```

## 3. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

## 4. Generate Graph Seed Data

```bash
python3 scripts/generate_graph_seed.py
```

This creates `data/raw/graph_seed.json` from the connector catalog (vehicles, assemblies, BOM lines, suppliers).

## 5. Ingest Graph Data

```bash
cd backend
python3 ingest_graph.py
```

Or combine with Qdrant ingestion:

```bash
python3 ingest_data.py --with-graph
```

Validate without writing:

```bash
python3 ingest_graph.py --dry-run
```

## 6. Verify

```bash
curl http://localhost:8000/health
# Expect: "neo4j": "connected"

curl http://localhost:8000/api/graph/suppliers/risk
curl http://localhost:8000/api/graph/impact/EC-2024-3441
```

## Local Development (Docker Alternative)

```bash
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5-community
```

Then set:

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
```

## Graph API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/graph/impact/{part_number}` | Vehicles/assemblies affected by part unavailability |
| `GET /api/graph/compliance/{assembly_id}` | Inherited requirements for an assembly |
| `GET /api/graph/compliance/connector/{part_number}` | Compliance gaps for a connector |
| `GET /api/graph/suppliers/risk` | Supplier concentration risk |
| `GET /api/graph/suppliers/spof` | Sole-source critical parts |
| `GET /api/graph/suppliers/{supplier_id}/connectors` | Connectors by supplier |

## Testing

```bash
# Unit tests (no Neo4j required)
pytest tests/test_neo4j_service.py -v

# Integration tests (requires Neo4j env vars)
NEO4J_URI=... NEO4J_PASSWORD=... pytest tests/test_graph_api.py -m neo4j -v
```

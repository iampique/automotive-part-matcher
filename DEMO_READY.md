# Live Demo / YouTube — Ready Checklist

Use this before your recording session.

## Current status (automated check)

```bash
cd backend && source .venv/bin/activate
python scripts/preflight_demo.py
```

**Must pass all checks** before recording the graph portions.

---

## 1. Start servers

**Terminal 1 — Backend**
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Frontend**
```bash
cd frontend
npm run dev
```

| URL | Purpose |
|-----|---------|
| http://localhost:3000 | Search (Act 1) |
| http://localhost:3000/disruption | Full disruption demo (Act 3) |
| http://localhost:3000/graph | Supplier risk dashboard |
| http://localhost:3000/workflow | Search workflow diagram |

---

## 2. Fix Neo4j (required for graph showcase)

If preflight shows `Neo4j: disconnected`, your Aura hostname is not reachable.

**Verify DNS** (should return an IP, not NXDOMAIN):
```bash
nslookup YOUR_INSTANCE_ID.databases.neo4j.io
```

If DNS fails, the Aura **Free instance was likely paused >30 days and deleted**. Create a new one:

1. Open [console.neo4j.io](https://console.neo4j.io)
2. **Create instance** → AuraDB Free
3. Save the new **URI** and **password**
4. Update `backend/.env`:
   ```
   NEO4J_URI=neo4j+s://<new-id>.databases.neo4j.io
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=<new-password>
   AURA_INSTANCEID=<new-id>
   ```
5. **Ingest graph data** (required once per new instance):
   ```bash
   cd backend && source .venv/bin/activate
   python ingest_graph.py
   ```
6. **Restart backend** (Ctrl+C, then uvicorn again)
7. Confirm: `curl http://localhost:8000/health` → `"neo4j": "connected"`

---

## 3. Hero demo script

**Query (paste on home page):**
```
11-pin wire-to-board connector for battery management and infotainment, 24V, IP67, automotive ECU
```

**Hero part:** `EC-2024-3441` (should be top match ~88%)

### Act 1 — Search (2 min)
- Run query → expand top match

### Act 2 — Graph Insights (5 min)
- Click **Graph Insights** on `EC-2024-3441`
- **Impact** → 4 vehicles, BMS critical path
- **Compliance** → certifications + inherited requirements
- **Supplier Risk** → Hirose concentration

### Act 3 — Mitigation (5 min)
- **Mitigation** tab → **Analyze Disruption**
- Or open http://localhost:3000/disruption → **Load demo part**
- Show execution trace + ranked alternatives (Preferred / Caution)

### Code walkthrough (10 min)
1. `backend/app/services/neo4j_service.py` → `get_impact()`
2. `backend/app/disruption_agent.py` → workflow nodes
3. `backend/app/services/qdrant_service.py` → `find_similar_connectors()`
4. `backend/app/services/mitigation_scoring.py`

**Workflow diagram API:** `GET http://localhost:8000/api/disruption/workflow-diagram`

---

## 4. Quick API smoke tests

```bash
# Health
curl http://localhost:8000/health

# Impact
curl http://localhost:8000/api/graph/impact/EC-2024-3441

# Disruption
curl -X POST http://localhost:8000/api/disruption/analyze \
  -H 'Content-Type: application/json' \
  -d '{"part_number":"EC-2024-3441","max_alternatives":8,"min_similarity":55}'
```

---

## 5. Recording tips

- Browser zoom **125%**
- Hide `backend/.env` from screen share
- Run preflight **5 minutes before** going live
- Keep this tab open: http://localhost:3000/disruption as backup entry point

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Graph Insights shows Neo4j error | Fix Aura + `ingest_graph.py` + restart backend |
| Search returns no results | `python ingest_data.py` (Qdrant) |
| Port 8000 in use | Stop old uvicorn: `lsof -ti:8000 \| xargs kill` |
| Disruption shows 0 vehicles | Neo4j not ingested — run `ingest_graph.py` |

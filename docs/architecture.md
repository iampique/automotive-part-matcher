# Architecture

## Dual store: Qdrant + Neo4j

The system is built around two complementary stores. Both are core to the product.

| Store | Role | Typical questions |
|-------|------|-------------------|
| **Qdrant** | Vector search over connector embeddings | “Which connectors match these specs?” / “What’s similar to this part?” |
| **Neo4j** | Graph of vehicles, assemblies, BOM, suppliers, and requirements | “What breaks if this part is unavailable?” / “Where is supplier concentration risk?” / “Does this substitute inherit the right compliance?” |

Vector search finds similar connectors. The graph answers relationship questions vectors cannot — impact across vehicle programs, compliance inheritance through assemblies, and supplier topology / SPOF risk. Disruption mitigation chains both: Neo4j for impact and compliance, Qdrant for alternative discovery.

## Matching workflow (LangGraph)

```text
┌─────────────────────┐
│ parse_requirements  │  LLM → structured CustomerRequirement
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│   search_qdrant     │  Embeddings + filters; optional ACORN / hybrid
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│   score_matches     │  Hard gates + soft preference scoring
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│   rank_results      │  Top-K by score
└─────────────────────┘
```

1. **Parse** — Natural language or document text → voltage, current, pins, temperature, IP, certifications, etc.
2. **Search** — Embed query, apply filters, retrieve candidates (often top ~50 for scoring).
3. **Score** — Fail hard requirements (score 0); score soft fit 0–100 with explanations.
4. **Rank** — Return top-K matches plus an execution trace for the UI.

A separate **disruption mitigation** workflow combines Neo4j impact analysis, Qdrant similar-part search, compliance subgraphs, and supplier risk scoring.

## ACORN (Qdrant)

ACORN improves recall when filters are highly selective (many hard constraints). Controlled by:

- `ACORN_ENABLED` (default `true`)
- `ACORN_MAX_SELECTIVITY` (default `0.4`) — when estimated selectivity is below this, ACORN is preferred

Trade-off: typically higher latency (often 2–10×) for better filtered recall. Simple unfiltered queries can keep ACORN off.

## Hybrid search

When the query looks like it contains product/brand names, the system combines:

- **Vector search** — semantic similarity
- **Full-text matching** — exact names and terminology

That improves hits on queries like “TE Connectivity AMPSEAL …” while still handling descriptive EV/high-voltage language.

## Scoring and tolerances

Hard vs soft matching and numeric tolerances (pins, voltage, current, temperature, IP) live in `backend/app/matching_config.py`. See [configuration.md](configuration.md).

## Frontend

Next.js app talks to the FastAPI backend (`NEXT_PUBLIC_API_URL`). Main surfaces:

- Search + workflow trace
- Graph insights (supplier risk, impact, compliance)
- Disruption mitigation workflow

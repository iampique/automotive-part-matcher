"""MCP server for Automotive Connector Matcher (Claude Desktop / MCP clients).

Exposes Qdrant search and Neo4j graph/disruption tools via a single FastMCP process.
Requires backend/.env with Qdrant, LLM, and Neo4j credentials.
"""

import base64
import io
import json
import logging
import os
import sys
from typing import Annotated, Any, Dict, Literal, Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

# Load env from mcp_server/ then backend/
_here = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.dirname(_here)
_backend_dir = os.path.join(_repo_root, "backend")

# backend.app.* needs repo root; app.* needs backend/.
# Append backend (do not insert at front) so backend/neo4j/ does not shadow PyPI neo4j.
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _backend_dir not in sys.path:
    sys.path.append(_backend_dir)

load_dotenv(os.path.join(_here, ".env"))
load_dotenv(os.path.join(_backend_dir, ".env"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVER_INSTRUCTIONS = """
Automotive connector dual-store tools (Qdrant catalog + Neo4j graph).

Route by user intent — do not run a fixed pipeline:
- Shortage / obsolete / mitigate / "what should we do if this part fails" → analyze_disruption(part_number) directly.
- Find parts by electrical/mechanical requirements → search_connectors; then get_connector if details are needed.
- "What vehicles/assemblies break if X is unavailable" → get_part_impact.
- Compliance for a part → get_connector_compliance; for an assembly id → get_assembly_compliance.
- Supplier concentration / sole-source → get_supplier_risk, get_supplier_spof, get_supplier_connectors.
- Catalog lookalikes only (not full mitigation) → get_similar_connectors.
- get_health only if the user asks about connectivity or a prior tool failed.

Prefer detail="summary" (default) to keep responses small; use detail="full" only when asked for complete payloads.
Demo hero part: EC-2024-3441.
""".strip()

READONLY = ToolAnnotations(
    readOnlyHint=True,
    idempotentHint=True,
    openWorldHint=True,
)

server = FastMCP(
    "automotive-part-matcher",
    instructions=SERVER_INSTRUCTIONS,
)

DetailLevel = Literal["summary", "full"]

PartNumber = Annotated[
    str,
    Field(
        description="Connector part number from the catalog, e.g. 'EC-2024-3441'",
        min_length=1,
    ),
]
AssemblyId = Annotated[
    str,
    Field(
        description="Assembly id from graph/impact results, e.g. 'asm-bms-harness'",
        min_length=1,
    ),
]
SupplierId = Annotated[
    str,
    Field(
        description="Supplier id from get_supplier_risk results, e.g. 'sup-te-connectivity'",
        min_length=1,
    ),
]
DetailArg = Annotated[
    DetailLevel,
    Field(
        description=(
            "Response size: 'summary' (default, trimmed for chat) or "
            "'full' (complete API payload including traces)"
        ),
    ),
]


def _to_dict(result: Any) -> Dict:
    """Serialize Pydantic models or pass through dicts for MCP responses."""
    if result is None:
        return {}
    if isinstance(result, dict):
        return result
    if hasattr(result, "model_dump"):
        return result.model_dump()
    if hasattr(result, "dict"):
        return result.dict()
    return {"value": result}


def _error_payload(exc: Exception) -> Dict:
    """Normalize FastAPI HTTPException and generic errors for Claude."""
    detail = getattr(exc, "detail", None)
    if detail is not None:
        return {"error": detail if isinstance(detail, str) else str(detail)}
    return {"error": str(exc)}


def _truncate(text: Optional[str], max_len: int = 240) -> Optional[str]:
    if not text:
        return text
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _summarize_search(data: Dict) -> Dict:
    matches = []
    for m in data.get("matches") or []:
        connector = m.get("connector") or {}
        matches.append(
            {
                "part_number": m.get("part_number") or connector.get("part_number"),
                "name": m.get("name") or connector.get("name"),
                "match_score": m.get("match_score"),
                "match_explanation": _truncate(m.get("match_explanation")),
                "is_fallback_match": m.get("is_fallback_match", False),
            }
        )
    return {
        "matches": matches,
        "processing_time_ms": data.get("processing_time_ms"),
        "query_summary": data.get("query_summary"),
        "acorn_used": data.get("acorn_used"),
        "hybrid_search_used": data.get("hybrid_search_used"),
        "matches_passed_hard_requirements": data.get(
            "matches_passed_hard_requirements"
        ),
        "detail": "summary",
    }


def _summarize_similar(data: Dict) -> Dict:
    similar = []
    for item in data.get("similar_connectors") or data.get("matches") or []:
        if isinstance(item, dict):
            connector = item.get("connector") or item
            similar.append(
                {
                    "part_number": item.get("part_number")
                    or connector.get("part_number"),
                    "name": item.get("name") or connector.get("name"),
                    "similarity_score": item.get("similarity_score")
                    or item.get("score")
                    or item.get("match_score"),
                }
            )
    return {
        "part_number": data.get("part_number"),
        "similar_connectors": similar,
        "detail": "summary",
    }


def _summarize_connector(data: Dict) -> Dict:
    specs = data.get("specifications") or {}
    return {
        "part_number": data.get("part_number"),
        "name": data.get("name"),
        "manufacturer": data.get("manufacturer"),
        "connector_type": data.get("connector_type"),
        "specifications": {
            "pin_count": specs.get("pin_count"),
            "voltage_rating": specs.get("voltage_rating"),
            "current_rating": specs.get("current_rating"),
            "ip_rating": specs.get("ip_rating"),
            "min_operating_temp": specs.get("min_operating_temp"),
            "max_operating_temp": specs.get("max_operating_temp"),
        },
        "certifications": data.get("certifications"),
        "applications": data.get("applications"),
        "detail": "summary",
    }


def _summarize_impact(data: Dict) -> Dict:
    vehicles = data.get("affected_vehicles") or []
    assemblies = data.get("affected_assemblies") or []
    return {
        "part_number": data.get("part_number"),
        "connector_name": data.get("connector_name"),
        "affected_vehicle_count": len(vehicles),
        "affected_vehicles": [
            v.get("name") or v.get("id") if isinstance(v, dict) else v
            for v in vehicles[:8]
        ],
        "affected_assembly_count": len(assemblies),
        "affected_assemblies": [
            a.get("name") or a.get("id") if isinstance(a, dict) else a
            for a in assemblies[:8]
        ],
        "total_bom_qty": data.get("total_bom_qty"),
        "detail": "summary",
    }


def _summarize_disruption(data: Dict) -> Dict:
    alts = []
    for a in data.get("alternatives") or []:
        alts.append(
            {
                "part_number": a.get("part_number"),
                "name": a.get("name") or a.get("connector_name"),
                "recommendation": a.get("recommendation") or a.get("tier"),
                "similarity_score": a.get("similarity_score") or a.get("score"),
                "rationale": _truncate(
                    a.get("rationale") or a.get("explanation") or a.get("summary"),
                    180,
                ),
            }
        )
    trace = [
        {
            "node": s.get("node"),
            "duration_ms": s.get("duration_ms"),
            "status": s.get("status"),
        }
        for s in (data.get("execution_trace") or [])
    ]
    return {
        "disrupted_part_number": data.get("disrupted_part_number"),
        "disrupted_connector_name": data.get("disrupted_connector_name"),
        "summary": data.get("summary"),
        "disrupted_is_spof": data.get("disrupted_is_spof"),
        "graph_enabled": data.get("graph_enabled"),
        "warnings": data.get("warnings") or [],
        "processing_time_ms": data.get("processing_time_ms"),
        "impact": _summarize_impact(_to_dict(data.get("impact") or {})),
        "alternatives": alts[:8],
        "execution_trace": trace,
        "detail": "summary",
    }


def _maybe_summarize(kind: str, data: Dict, detail: DetailLevel) -> Dict:
    if detail == "full" or data.get("error"):
        if isinstance(data, dict) and "detail" not in data and not data.get("error"):
            data = {**data, "detail": "full"}
        return data
    summarizers = {
        "search": _summarize_search,
        "similar": _summarize_similar,
        "connector": _summarize_connector,
        "impact": _summarize_impact,
        "disruption": _summarize_disruption,
    }
    fn = summarizers.get(kind)
    return fn(data) if fn else data


# ---------------------------------------------------------------------------
# Resources & prompts
# ---------------------------------------------------------------------------


@server.resource(
    "catalog://demo/hero-parts",
    name="hero_parts",
    title="Demo hero parts",
    description="Known-good part numbers for demos and smoke tests",
    mime_type="application/json",
)
def hero_parts_resource() -> str:
    return json.dumps(
        {
            "hero_part": "EC-2024-3441",
            "notes": "Use for disruption / impact demos when graph data is ingested.",
            "sample_parts": [
                "EC-2024-3441",
                "EC-2024-1868",
                "EC-2021-1719",
            ],
        },
        indent=2,
    )


@server.resource(
    "catalog://demo/sample-queries",
    name="sample_queries",
    title="Sample search queries",
    description="Example natural-language connector searches",
    mime_type="application/json",
)
def sample_queries_resource() -> str:
    return json.dumps(
        {
            "queries": [
                (
                    "11-pin wire-to-board connector for battery management and "
                    "infotainment, 24V, IP67, automotive ECU"
                ),
                "48-pin EV battery connector, 48V, IP67, automotive grade",
                "Safety-critical brake connector, ASIL-D, 24 pins, 12V, IP68",
            ]
        },
        indent=2,
    )


@server.prompt(
    name="mitigate_shortage",
    title="Mitigate part shortage",
    description="Ask Claude to run full disruption mitigation for a part number",
)
def mitigate_shortage_prompt(
    part_number: Annotated[
        str, Field(description="Disrupted connector part number, e.g. EC-2024-3441")
    ] = "EC-2024-3441",
) -> str:
    return (
        f"A supply disruption hit connector {part_number}. "
        f"Call analyze_disruption for that part (detail=summary is fine). "
        f"Summarize impacted vehicles, whether it is a SPOF, top alternatives "
        f"with recommendation tier, and any compliance or supplier warnings."
    )


@server.prompt(
    name="find_connector",
    title="Find matching connectors",
    description="Ask Claude to search the catalog from free-text requirements",
)
def find_connector_prompt(
    requirements: Annotated[
        str,
        Field(description="Natural-language connector requirements"),
    ] = (
        "11-pin wire-to-board connector for battery management, 24V, IP67, "
        "automotive ECU"
    ),
) -> str:
    return (
        f"Find connectors matching these requirements using search_connectors "
        f"(detail=summary): {requirements}\n"
        f"List the top matches with part numbers and scores. Offer to call "
        f"get_connector on the best match if more detail is needed."
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@server.tool(annotations=READONLY)
async def get_health() -> Dict:
    """Check backend health: Qdrant and Neo4j connectivity.

    Use only when the user asks if systems are up, or after a tool failure.
    Do not call this automatically before search or disruption workflows.
    """
    from backend.app.api import health_check as api_health_check

    try:
        return _to_dict(await api_health_check())
    except Exception as e:
        logger.error("Health check failed: %s", e)
        return _error_payload(e)


# ---------------------------------------------------------------------------
# Qdrant search / catalog
# ---------------------------------------------------------------------------


@server.tool(annotations=READONLY)
async def search_connectors(
    text_input: Annotated[
        Optional[str],
        Field(description="Free-text requirements, e.g. pin count, voltage, IP rating"),
    ] = None,
    file_content: Annotated[
        Optional[str],
        Field(description="Optional base64-encoded PDF/DOCX content"),
    ] = None,
    file_name: Annotated[
        Optional[str],
        Field(description="Filename when file_content is provided"),
    ] = None,
    llm_provider: Annotated[
        Optional[str],
        Field(description="Override extraction LLM: 'claude' or 'openai'"),
    ] = None,
    top_k: Annotated[
        int,
        Field(description="Number of ranked matches (1-20)", ge=1, le=20),
    ] = 10,
    enable_acorn: Annotated[
        bool,
        Field(description="Use Qdrant ACORN for restrictive filters"),
    ] = True,
    detail: DetailArg = "summary",
) -> Dict:
    """Search the connector catalog with natural language (Qdrant + LLM).

    Use for finding parts that match electrical/mechanical requirements.
    Does not answer graph questions (impact, suppliers, compliance cascades);
    use Neo4j tools for those.
    """
    from backend.app.api import search_connectors as api_search_connectors

    file_upload = None
    if file_content and file_name:
        try:
            file_bytes = base64.b64decode(file_content)
            from fastapi.datastructures import UploadFile as FastAPIUploadFile

            file_upload = FastAPIUploadFile(
                filename=file_name,
                file=io.BytesIO(file_bytes),
            )
        except Exception as e:
            logger.error("Failed to decode file content: %s", e)
            return {"error": f"Failed to decode file content: {e}"}

    try:
        result = await api_search_connectors(
            text_input=text_input,
            file=file_upload,
            llm_provider=llm_provider,
            top_k=top_k,
            enable_acorn=enable_acorn,
        )
        return _maybe_summarize("search", _to_dict(result), detail)
    except Exception as e:
        logger.error("Search connectors failed: %s", e)
        return _error_payload(e)


@server.tool(annotations=READONLY)
async def get_connector(
    part_number: PartNumber,
    detail: DetailArg = "summary",
) -> Dict:
    """Fetch catalog details for one connector by part number (Qdrant).

    Use after search to inspect specifications, certifications, applications,
    and pricing for a specific part (e.g. EC-2024-3441).
    """
    from backend.app.api import get_connector as api_get_connector

    try:
        return _maybe_summarize(
            "connector",
            _to_dict(await api_get_connector(part_number=part_number)),
            detail,
        )
    except Exception as e:
        logger.error("Get connector failed: %s", e)
        return _error_payload(e)


@server.tool(annotations=READONLY)
async def get_similar_connectors(
    part_number: PartNumber,
    limit: Annotated[
        int,
        Field(description="Max similar parts to return (1-20)", ge=1, le=20),
    ] = 5,
    detail: DetailArg = "summary",
) -> Dict:
    """Find similar connectors via Qdrant recommendation (vector similarity).

    Use to explore catalog alternatives to a known part number. For full
    supply-disruption mitigation (impact + compliance + supplier risk), prefer
    analyze_disruption instead.
    """
    from backend.app.api import get_similar_connectors as api_get_similar_connectors

    try:
        result = await api_get_similar_connectors(
            part_number=part_number, limit=limit
        )
        return _maybe_summarize("similar", _to_dict(result), detail)
    except Exception as e:
        logger.error("Get similar connectors failed: %s", e)
        return _error_payload(e)


# ---------------------------------------------------------------------------
# Neo4j graph
# ---------------------------------------------------------------------------


@server.tool(annotations=READONLY)
async def get_part_impact(
    part_number: PartNumber,
    detail: DetailArg = "summary",
) -> Dict:
    """Neo4j impact analysis: vehicles and assemblies affected if a part is unavailable.

    Use when asking what breaks if a connector goes out of stock or is obsolete.
    Requires Neo4j to be connected.
    """
    from backend.app.api import get_part_impact as api_get_part_impact

    try:
        return _maybe_summarize(
            "impact",
            _to_dict(await api_get_part_impact(part_number=part_number)),
            detail,
        )
    except Exception as e:
        logger.error("Get part impact failed: %s", e)
        return _error_payload(e)


@server.tool(annotations=READONLY)
async def get_assembly_compliance(assembly_id: AssemblyId) -> Dict:
    """Neo4j compliance inheritance for an assembly hierarchy.

    Returns requirements that cascade through the assembly tree. Use when you
    have an assembly id (e.g. from impact results). For a connector part number,
    use get_connector_compliance instead.
    """
    from backend.app.api import get_assembly_compliance as api_get_assembly_compliance

    try:
        return _to_dict(await api_get_assembly_compliance(assembly_id=assembly_id))
    except Exception as e:
        logger.error("Get assembly compliance failed: %s", e)
        return _error_payload(e)


@server.tool(annotations=READONLY)
async def get_connector_compliance(part_number: PartNumber) -> Dict:
    """Neo4j compliance gaps for a connector vs inherited assembly requirements.

    Compares the part's certifications against requirements cascading from
    assemblies that use it. Use for a specific part number (not assembly id).
    """
    from backend.app.api import get_connector_compliance as api_get_connector_compliance

    try:
        return _to_dict(await api_get_connector_compliance(part_number=part_number))
    except Exception as e:
        logger.error("Get connector compliance failed: %s", e)
        return _error_payload(e)


@server.tool(annotations=READONLY)
async def get_part_sourcing(part_number: PartNumber) -> Dict:
    """Neo4j primary supplier and supply share for a connector part.

    Use to see who supplies a part and concentration for that SKU.
    """
    from backend.app.api import get_part_sourcing as api_get_part_sourcing

    try:
        return _to_dict(await api_get_part_sourcing(part_number=part_number))
    except Exception as e:
        logger.error("Get part sourcing failed: %s", e)
        return _error_payload(e)


@server.tool(annotations=READONLY)
async def get_supplier_risk() -> Dict:
    """Neo4j supplier concentration risk across critical parts and assemblies.

    Use for portfolio-level supplier risk. Follow up with get_supplier_spof for
    sole-source failures, or get_supplier_connectors to list a supplier's parts.
    """
    from backend.app.api import get_supplier_risk as api_get_supplier_risk

    try:
        return _to_dict(await api_get_supplier_risk())
    except Exception as e:
        logger.error("Get supplier risk failed: %s", e)
        return _error_payload(e)


@server.tool(annotations=READONLY)
async def get_supplier_spof() -> Dict:
    """Neo4j single points of failure: sole-source critical connectors.

    Lists parts with only one supplier and which vehicles they affect.
    """
    from backend.app.api import get_supplier_spof as api_get_supplier_spof

    try:
        return _to_dict(await api_get_supplier_spof())
    except Exception as e:
        logger.error("Get supplier SPOF failed: %s", e)
        return _error_payload(e)


@server.tool(annotations=READONLY)
async def get_supplier_connectors(supplier_id: SupplierId) -> Dict:
    """Neo4j drill-down: connectors supplied by a given supplier id.

    Use after get_supplier_risk when you have a supplier_id and want that
    supplier's connector catalog in the graph.
    """
    from backend.app.api import get_supplier_connectors as api_get_supplier_connectors

    try:
        return _to_dict(await api_get_supplier_connectors(supplier_id=supplier_id))
    except Exception as e:
        logger.error("Get supplier connectors failed: %s", e)
        return _error_payload(e)


# ---------------------------------------------------------------------------
# Disruption (Neo4j + Qdrant)
# ---------------------------------------------------------------------------


@server.tool(annotations=READONLY)
async def analyze_disruption(
    part_number: PartNumber,
    max_alternatives: Annotated[
        int,
        Field(description="Max alternatives to rank (1-20)", ge=1, le=20),
    ] = 8,
    min_similarity: Annotated[
        float,
        Field(description="Minimum similarity score threshold (0-100)", ge=0, le=100),
    ] = 55.0,
    detail: DetailArg = "summary",
) -> Dict:
    """Full disruption mitigation workflow (Neo4j impact + Qdrant alternatives).

    Orchestrates impact analysis, similar-part discovery, compliance validation,
    and supplier risk into ranked mitigation options. Prefer this over calling
    individual graph/search tools when the user asks how to mitigate a shortage
    or obsolete part. Call directly — no need to call get_health first.
    """
    from backend.app.api import analyze_disruption as api_analyze_disruption
    from backend.app.models import DisruptionRequest

    try:
        result = await api_analyze_disruption(
            DisruptionRequest(
                part_number=part_number,
                max_alternatives=max_alternatives,
                min_similarity=min_similarity,
            )
        )
        return _maybe_summarize("disruption", _to_dict(result), detail)
    except Exception as e:
        logger.error("Analyze disruption failed: %s", e)
        return _error_payload(e)


if __name__ == "__main__":
    server.run()

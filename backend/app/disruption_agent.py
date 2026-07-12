"""
LangGraph workflow for supply-disruption mitigation analysis.

Chains Neo4j impact/compliance/supplier queries with Qdrant similar-part
discovery to rank viable alternatives for a disrupted connector.
"""

import logging
import time
from typing import Dict, List, Optional, Tuple

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from app.models import (
    Connector,
    DisruptionExecutionStep,
    DisruptionResponse,
    ImpactAnalysisResponse,
    MitigationCandidate,
    PartSourcing,
)
from app.services.mitigation_scoring import build_mitigation_candidate, rank_mitigation_candidates
from app.services.neo4j_service import Neo4jService
from app.services.qdrant_service import QdrantService

logger = logging.getLogger(__name__)


class DisruptionState(TypedDict, total=False):
    part_number: str
    max_alternatives: int
    min_similarity: float
    impact: Optional[ImpactAnalysisResponse]
    disrupted_connector_name: Optional[str]
    disrupted_sourcing: Optional[PartSourcing]
    disrupted_is_spof: bool
    raw_alternatives: List[Tuple[Connector, float]]
    candidates: List[MitigationCandidate]
    compliance_by_part: Dict
    sourcing_by_part: Dict
    spof_part_numbers: List[str]
    execution_trace: List[Dict]
    warnings: List[str]
    graph_enabled: bool
    error: Optional[str]


class DisruptionAgent:
    """Orchestrates graph + vector analysis for disruption response."""

    def __init__(
        self,
        qdrant_service: QdrantService,
        neo4j_service: Optional[Neo4jService] = None,
    ) -> None:
        self.qdrant_service = qdrant_service
        self.neo4j_service = neo4j_service
        self.graph = self._build_graph()
        logger.info(
            "DisruptionAgent initialized (Neo4j: %s)",
            "enabled" if neo4j_service and neo4j_service.enabled else "disabled",
        )

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(DisruptionState)
        workflow.add_node("analyze_impact", self._analyze_impact_node)
        workflow.add_node("find_alternatives", self._find_alternatives_node)
        workflow.add_node("validate_compliance", self._validate_compliance_node)
        workflow.add_node("assess_supplier_risk", self._assess_supplier_risk_node)
        workflow.add_node("rank_mitigation", self._rank_mitigation_node)

        workflow.set_entry_point("analyze_impact")
        workflow.add_edge("analyze_impact", "find_alternatives")
        workflow.add_edge("find_alternatives", "validate_compliance")
        workflow.add_edge("validate_compliance", "assess_supplier_risk")
        workflow.add_edge("assess_supplier_risk", "rank_mitigation")
        workflow.add_edge("rank_mitigation", END)
        return workflow.compile()

    def _trace(
        self,
        state: DisruptionState,
        node: str,
        start: float,
        output: str,
        status: str = "success",
    ) -> None:
        state["execution_trace"].append(
            {
                "node": node,
                "duration_ms": (time.time() - start) * 1000,
                "output": output,
                "status": status,
            }
        )

    def _analyze_impact_node(self, state: DisruptionState) -> DisruptionState:
        start = time.time()
        node = "analyze_impact"
        part_number = state["part_number"]

        try:
            if not state["graph_enabled"] or not self.neo4j_service:
                state["impact"] = ImpactAnalysisResponse(
                    part_number=part_number,
                    affected_vehicles=[],
                    affected_assemblies=[],
                    critical_paths=[],
                    total_bom_qty=0,
                )
                state["warnings"].append(
                    "Neo4j unavailable — impact analysis skipped; alternatives ranked on similarity and catalog data only."
                )
                self._trace(state, node, start, "Skipped (Neo4j disabled)")
                return state

            impact = self.neo4j_service.get_impact(part_number)
            state["impact"] = impact
            state["disrupted_connector_name"] = impact.connector_name
            state["disrupted_sourcing"] = self.neo4j_service.get_part_sourcing(part_number)
            state["disrupted_is_spof"] = self.neo4j_service.is_part_spof(part_number)

            if not impact.affected_assemblies:
                state["warnings"].append(
                    f"Part '{part_number}' has no BOM relationships in the graph."
                )

            output = (
                f"{len(impact.affected_vehicles)} vehicles, "
                f"{len(impact.affected_assemblies)} assemblies, "
                f"{len(impact.critical_paths)} critical paths"
            )
            self._trace(state, node, start, output)
        except Exception as e:
            msg = f"Impact analysis failed: {e}"
            logger.warning(msg)
            state["impact"] = ImpactAnalysisResponse(
                part_number=part_number,
                affected_vehicles=[],
                affected_assemblies=[],
                critical_paths=[],
                total_bom_qty=0,
            )
            state["warnings"].append(
                "Neo4j impact query failed — continuing with vector alternatives only."
            )
            self._trace(state, node, start, "Degraded (Neo4j error)", "success")
        return state

    def _find_alternatives_node(self, state: DisruptionState) -> DisruptionState:
        start = time.time()
        node = "find_alternatives"
        if state.get("error"):
            return state

        part_number = state["part_number"]
        try:
            similar = self.qdrant_service.find_similar_connectors(
                connector_part_number=part_number,
                limit=state["max_alternatives"] + 5,
            )
            min_sim = state["min_similarity"]
            filtered = [
                (conn, score)
                for conn, score in similar
                if conn.part_number != part_number and score >= min_sim
            ][: state["max_alternatives"]]
            state["raw_alternatives"] = filtered

            if not filtered:
                state["warnings"].append(
                    f"No alternatives found above {min_sim:.0f}% similarity."
                )

            self._trace(
                state,
                node,
                start,
                f"{len(filtered)} alternatives (min similarity {min_sim:.0f}%)",
            )
        except Exception as e:
            msg = f"Alternative search failed: {e}"
            logger.error(msg)
            state["error"] = msg
            self._trace(state, node, start, msg, "error")
        return state

    def _validate_compliance_node(self, state: DisruptionState) -> DisruptionState:
        start = time.time()
        node = "validate_compliance"
        if state.get("error"):
            return state

        alternatives = state.get("raw_alternatives", [])
        part_numbers = [c.part_number for c, _ in alternatives]

        if not state["graph_enabled"] or not self.neo4j_service:
            state["compliance_by_part"] = {}
            self._trace(state, node, start, "Skipped (Neo4j disabled)")
            return state

        try:
            compliance_map = self.neo4j_service.get_connector_compliance_batch(part_numbers)
            state["compliance_by_part"] = compliance_map
            gap_count = sum(len(c.gaps) for c in compliance_map.values())
            self._trace(
                state,
                node,
                start,
                f"Validated {len(part_numbers)} parts, {gap_count} total compliance gaps",
            )
        except Exception as e:
            msg = f"Compliance validation failed: {e}"
            logger.warning(msg)
            state["compliance_by_part"] = {}
            state["warnings"].append("Compliance validation skipped due to Neo4j error.")
            self._trace(state, node, start, "Degraded (Neo4j error)", "success")
        return state

    def _assess_supplier_risk_node(self, state: DisruptionState) -> DisruptionState:
        start = time.time()
        node = "assess_supplier_risk"
        if state.get("error"):
            return state

        alternatives = state.get("raw_alternatives", [])
        part_numbers = [c.part_number for c, _ in alternatives]

        if not state["graph_enabled"] or not self.neo4j_service:
            state["sourcing_by_part"] = {}
            state["spof_part_numbers"] = []
            self._trace(state, node, start, "Skipped (Neo4j disabled)")
            return state

        try:
            sourcing_map = self.neo4j_service.get_part_sourcing_batch(part_numbers)
            spof_entries = self.neo4j_service.get_spof()
            spof_pns = {e.part_number for e in spof_entries.entries}
            state["sourcing_by_part"] = sourcing_map
            state["spof_part_numbers"] = list(spof_pns)
            sole_count = sum(1 for s in sourcing_map.values() if s.sole_source)
            self._trace(
                state,
                node,
                start,
                f"Assessed {len(sourcing_map)} suppliers, {sole_count} sole-source alts",
            )
        except Exception as e:
            msg = f"Supplier risk assessment failed: {e}"
            logger.warning(msg)
            state["sourcing_by_part"] = {}
            state["spof_part_numbers"] = []
            state["warnings"].append("Supplier risk assessment skipped due to Neo4j error.")
            self._trace(state, node, start, "Degraded (Neo4j error)", "success")
        return state

    def _rank_mitigation_node(self, state: DisruptionState) -> DisruptionState:
        start = time.time()
        node = "rank_mitigation"
        if state.get("error"):
            return state

        compliance_map = state.get("compliance_by_part", {})
        sourcing_map = state.get("sourcing_by_part", {})
        spof_pns = set(state.get("spof_part_numbers", []))
        impact = state.get("impact")

        candidates: List[MitigationCandidate] = []
        for connector, similarity in state.get("raw_alternatives", []):
            pn = connector.part_number
            compliance = compliance_map.get(pn)
            gaps = compliance.gaps if compliance else []
            sourcing = sourcing_map.get(pn)
            candidates.append(
                build_mitigation_candidate(
                    connector=connector,
                    similarity_score=similarity,
                    gaps=gaps,
                    sourcing=sourcing,
                    impact=impact,
                    is_spof=pn in spof_pns,
                )
            )

        state["candidates"] = rank_mitigation_candidates(candidates)
        preferred = sum(1 for c in state["candidates"] if c.verdict == "preferred")
        self._trace(
            state,
            node,
            start,
            f"Ranked {len(candidates)} alternatives, {preferred} preferred",
        )
        return state

    def _build_summary(
        self,
        part_number: str,
        impact: ImpactAnalysisResponse,
        candidates: List[MitigationCandidate],
        graph_enabled: bool,
    ) -> str:
        vehicle_count = len(impact.affected_vehicles)
        critical_count = len(impact.critical_paths)
        preferred = [c for c in candidates if c.verdict == "preferred"]

        if not graph_enabled:
            if candidates:
                top = candidates[0]
                return (
                    f"Found {len(candidates)} similar alternatives for {part_number}. "
                    f"Top option: {top.part_number} ({top.similarity_score:.0f}% similar). "
                    "Enable Neo4j for impact and compliance validation."
                )
            return f"No similar alternatives found for {part_number}."

        if preferred:
            top = preferred[0]
            return (
                f"Disruption on {part_number} affects {vehicle_count} vehicle program(s) "
                f"with {critical_count} critical BOM path(s). "
                f"Recommended substitute: {top.part_number} "
                f"(mitigation score {top.mitigation_score:.0f}, {top.similarity_score:.0f}% similar)."
            )
        if candidates:
            top = candidates[0]
            return (
                f"Disruption on {part_number} affects {vehicle_count} vehicle program(s). "
                f"No fully preferred substitutes; best cautious option is {top.part_number} "
                f"(mitigation score {top.mitigation_score:.0f})."
            )
        return (
            f"Disruption on {part_number} affects {vehicle_count} vehicle program(s), "
            "but no viable alternatives met the similarity threshold."
        )

    def run(
        self,
        part_number: str,
        max_alternatives: int = 10,
        min_similarity: float = 50.0,
    ) -> DisruptionResponse:
        start_time = time.time()
        graph_enabled = bool(self.neo4j_service and self.neo4j_service.enabled)

        initial_state: DisruptionState = {
            "part_number": part_number,
            "max_alternatives": max_alternatives,
            "min_similarity": min_similarity,
            "impact": None,
            "disrupted_connector_name": None,
            "disrupted_sourcing": None,
            "disrupted_is_spof": False,
            "raw_alternatives": [],
            "candidates": [],
            "compliance_by_part": {},
            "sourcing_by_part": {},
            "spof_part_numbers": [],
            "execution_trace": [],
            "warnings": [],
            "graph_enabled": graph_enabled,
            "error": None,
        }

        final_state = self.graph.invoke(initial_state)
        if final_state.get("error"):
            raise RuntimeError(final_state["error"])

        impact = final_state.get("impact") or ImpactAnalysisResponse(
            part_number=part_number,
            affected_vehicles=[],
            affected_assemblies=[],
            critical_paths=[],
            total_bom_qty=0,
        )
        candidates = final_state.get("candidates", [])
        trace = [
            DisruptionExecutionStep(**step)
            for step in final_state.get("execution_trace", [])
        ]
        processing_ms = (time.time() - start_time) * 1000

        return DisruptionResponse(
            disrupted_part_number=part_number,
            disrupted_connector_name=final_state.get("disrupted_connector_name"),
            impact=impact,
            disrupted_sourcing=final_state.get("disrupted_sourcing"),
            disrupted_is_spof=final_state.get("disrupted_is_spof", False),
            alternatives=candidates,
            execution_trace=trace,
            graph_enabled=graph_enabled,
            warnings=final_state.get("warnings", []),
            processing_time_ms=round(processing_ms, 2),
            summary=self._build_summary(part_number, impact, candidates, graph_enabled),
        )

    def export_workflow_diagram(self) -> str:
        return """%%{init: {'flowchart': {'curve': 'basis'}, 'theme': 'base'}}%%
graph LR
    Start([Disrupted Part]):::startclass
    Impact["`**1. Impact Analysis**
    Neo4j BOM traversal`"]:::graphclass
    Alternatives["`**2. Find Alternatives**
    Qdrant vector similarity`"]:::vectorclass
    Compliance["`**3. Validate Compliance**
    Neo4j requirement subgraphs`"]:::graphclass
    Supplier["`**4. Supplier Risk**
    Neo4j topology / SPOF`"]:::graphclass
    Rank["`**5. Rank Mitigation**
    Weighted scoring`"]:::processclass
    End([Ranked Alternatives]):::endclass

    Start --> Impact
    Impact --> Alternatives
    Alternatives --> Compliance
    Compliance --> Supplier
    Supplier --> Rank
    Rank --> End

    classDef startclass fill:#ffebee,stroke:#c62828,stroke-width:2px
    classDef endclass fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    classDef graphclass fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef vectorclass fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    classDef processclass fill:#fff8e1,stroke:#f9a825,stroke-width:2px
"""

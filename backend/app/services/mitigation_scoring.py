"""
Mitigation scoring for disruption-response alternative ranking.

Combines vector similarity, Neo4j compliance fit, and supplier topology
into a single mitigation score and human-readable verdict.
"""

from typing import List, Optional, Set

from app.models import (
    ComplianceGap,
    Connector,
    ImpactAnalysisResponse,
    MitigationCandidate,
    MitigationVerdict,
    PartSourcing,
)

WEIGHT_SIMILARITY = 0.40
WEIGHT_COMPLIANCE = 0.30
WEIGHT_SUPPLIER = 0.20
WEIGHT_LEAD_TIME = 0.10

PREFERRED_THRESHOLD = 75.0
CAUTION_THRESHOLD = 50.0


def _critical_assembly_names(impact: Optional[ImpactAnalysisResponse]) -> Set[str]:
    if not impact:
        return set()
    return {a.name for a in impact.affected_assemblies if a.critical}


def _critical_gaps(
    gaps: List[ComplianceGap],
    critical_assembly_names: Set[str],
) -> List[ComplianceGap]:
    if not critical_assembly_names:
        return gaps
    return [g for g in gaps if g.source_assembly_name in critical_assembly_names]


def _compliance_score(
    gaps: List[ComplianceGap],
    critical_gaps: List[ComplianceGap],
) -> float:
    if not gaps and not critical_gaps:
        return 100.0
    if critical_gaps:
        penalty = min(100.0, len(critical_gaps) * 35.0 + len(gaps) * 10.0)
        return max(0.0, 100.0 - penalty)
    penalty = min(100.0, len(gaps) * 20.0)
    return max(0.0, 100.0 - penalty)


def _supplier_score(sourcing: Optional[PartSourcing]) -> float:
    if sourcing is None:
        return 50.0
    if sourcing.sole_source:
        return 15.0
    if sourcing.share_pct >= 90:
        return 55.0
    if sourcing.share_pct >= 70:
        return 75.0
    return 100.0


def _lead_time_score(lead_time_days: Optional[int]) -> float:
    if lead_time_days is None:
        return 60.0
    if lead_time_days <= 30:
        return 100.0
    if lead_time_days <= 45:
        return 85.0
    if lead_time_days <= 60:
        return 70.0
    if lead_time_days <= 90:
        return 50.0
    return 30.0


def _verdict(
    mitigation_score: float,
    critical_gaps: List[ComplianceGap],
    sourcing: Optional[PartSourcing],
) -> MitigationVerdict:
    if critical_gaps or (sourcing and sourcing.sole_source):
        return "caution" if mitigation_score >= CAUTION_THRESHOLD else "not_recommended"
    if mitigation_score >= PREFERRED_THRESHOLD:
        return "preferred"
    if mitigation_score >= CAUTION_THRESHOLD:
        return "caution"
    return "not_recommended"


def _recommendation_text(
    verdict: MitigationVerdict,
    critical_gaps: List[ComplianceGap],
    sourcing: Optional[PartSourcing],
    similarity_score: float,
) -> str:
    if verdict == "preferred":
        return (
            f"Strong substitute ({similarity_score:.0f}% similar) with no critical compliance gaps "
            "and acceptable supplier risk."
        )
    parts: List[str] = []
    if critical_gaps:
        names = ", ".join({g.requirement_name for g in critical_gaps[:2]})
        parts.append(f"critical compliance gaps ({names})")
    if sourcing and sourcing.sole_source:
        parts.append(f"sole-source supplier ({sourcing.supplier_name})")
    elif sourcing and sourcing.share_pct >= 90:
        parts.append(f"high supplier concentration ({sourcing.share_pct:.0f}% from {sourcing.supplier_name})")
    if not parts:
        return f"Viable with caveats ({similarity_score:.0f}% similar); review before approval."
    return f"Use with caution: {'; '.join(parts)}."


def build_mitigation_candidate(
    connector: Connector,
    similarity_score: float,
    gaps: List[ComplianceGap],
    sourcing: Optional[PartSourcing],
    impact: Optional[ImpactAnalysisResponse],
    is_spof: bool = False,
) -> MitigationCandidate:
    critical_names = _critical_assembly_names(impact)
    critical_gaps = _critical_gaps(gaps, critical_names)
    compliance_component = _compliance_score(gaps, critical_gaps)
    supplier_component = _supplier_score(sourcing)
    lead_time = connector.pricing.lead_time_days if connector.pricing else None
    lead_time_component = _lead_time_score(lead_time)

    mitigation_score = round(
        similarity_score * WEIGHT_SIMILARITY
        + compliance_component * WEIGHT_COMPLIANCE
        + supplier_component * WEIGHT_SUPPLIER
        + lead_time_component * WEIGHT_LEAD_TIME,
        2,
    )

    verdict = _verdict(mitigation_score, critical_gaps, sourcing)
    recommendation = _recommendation_text(verdict, critical_gaps, sourcing, similarity_score)

    return MitigationCandidate(
        part_number=connector.part_number,
        name=connector.name,
        connector=connector,
        similarity_score=round(similarity_score, 2),
        mitigation_score=mitigation_score,
        verdict=verdict,
        recommendation=recommendation,
        compliance_gaps=gaps,
        critical_compliance_gaps=critical_gaps,
        certifications=list(connector.certifications),
        sourcing=sourcing,
        is_spof=is_spof,
    )


def rank_mitigation_candidates(
    candidates: List[MitigationCandidate],
) -> List[MitigationCandidate]:
    order = {"preferred": 0, "caution": 1, "not_recommended": 2}
    return sorted(
        candidates,
        key=lambda c: (order.get(c.verdict, 3), -c.mitigation_score, -c.similarity_score),
    )

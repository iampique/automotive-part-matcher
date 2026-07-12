"""
Tests for mitigation scoring logic.
"""

from app.models import ComplianceGap, Connector, ConnectorPricing, ConnectorSpecifications, ImpactAnalysisResponse, AffectedAssembly
from app.services.mitigation_scoring import build_mitigation_candidate, rank_mitigation_candidates


def _connector(pn: str, lead_time: int = 45, certs=None) -> Connector:
    return Connector(
        part_number=pn,
        name=f"Test {pn}",
        description="test",
        connector_type="Wire-to-Board",
        specifications=ConnectorSpecifications(
            pin_count=11,
            voltage_rating=24,
            current_rating=10,
            min_operating_temp=-20,
            max_operating_temp=100,
            ip_rating="IP67",
            housing_material="Polycarbonate",
            contact_material="Copper",
            contact_plating="Tin",
        ),
        certifications=certs or ["RoHS", "REACH", "AEC-Q200"],
        applications=["Battery Management"],
        pricing=ConnectorPricing(unit_price_usd=1.5, lead_time_days=lead_time),
    )


def test_preferred_candidate_ranks_first():
    impact = ImpactAnalysisResponse(
        part_number="EC-ORIG",
        affected_vehicles=[],
        affected_assemblies=[
            AffectedAssembly(
                id="asm-bms",
                name="Battery Management System",
                criticality="high",
                qty=3,
                critical=True,
            )
        ],
        critical_paths=["Battery Management System (qty 3)"],
        total_bom_qty=3,
    )
    from app.models import PartSourcing

    good = build_mitigation_candidate(
        connector=_connector("GOOD"),
        similarity_score=85,
        gaps=[],
        sourcing=PartSourcing(
            part_number="GOOD",
            supplier_id="s1",
            supplier_name="Dual Source Co",
            region="EU",
            tier=1,
            share_pct=60,
            sole_source=False,
        ),
        impact=impact,
    )
    bad = build_mitigation_candidate(
        connector=_connector("BAD"),
        similarity_score=88,
        gaps=[
            ComplianceGap(
                requirement_id="req-reach",
                requirement_name="REACH Compliance",
                standard="REACH",
                source_assembly_id="asm-bms",
                source_assembly_name="Battery Management System",
            )
        ],
        sourcing=PartSourcing(
            part_number="BAD",
            supplier_id="s2",
            supplier_name="Sole Co",
            region="APAC",
            tier=2,
            share_pct=100,
            sole_source=True,
        ),
        impact=impact,
        is_spof=True,
    )
    ranked = rank_mitigation_candidates([bad, good])
    assert ranked[0].part_number == "GOOD"
    assert ranked[0].verdict == "preferred"
    assert ranked[1].verdict in ("caution", "not_recommended")

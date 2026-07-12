"""Tests for DisruptionAgent with mocked services."""

from unittest.mock import MagicMock, patch

import pytest

from app.disruption_agent import DisruptionAgent
from app.models import (
    AffectedAssembly,
    AffectedVehicle,
    ComplianceGap,
    Connector,
    ConnectorComplianceResponse,
    ConnectorPricing,
    ConnectorSpecifications,
    ImpactAnalysisResponse,
    PartSourcing,
)


def _make_connector(pn: str) -> Connector:
    return Connector(
        part_number=pn,
        name=f"Connector {pn}",
        description="test connector",
        connector_type="Wire-to-Board",
        specifications=ConnectorSpecifications(
            pin_count=11,
            voltage_rating=24,
            current_rating=10,
            min_operating_temp=-20,
            max_operating_temp=100,
            ip_rating="IP67",
            housing_material="PC",
            contact_material="Cu",
            contact_plating="Tin",
        ),
        certifications=["RoHS", "REACH", "AEC-Q200"],
        applications=["Battery Management"],
        pricing=ConnectorPricing(unit_price_usd=1.5, lead_time_days=30),
    )


@pytest.fixture
def mock_neo4j():
    neo = MagicMock()
    neo.enabled = True
    neo.get_impact.return_value = ImpactAnalysisResponse(
        part_number="EC-2024-3441",
        connector_name="W2B-11",
        affected_vehicles=[
            AffectedVehicle(
                id="v1",
                name="Aurora EV Sedan",
                platform="EV-Sedan",
                model_year=2025,
            )
        ],
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
    neo.get_part_sourcing.return_value = PartSourcing(
        part_number="EC-2024-3441",
        supplier_id="sup-hirose",
        supplier_name="Hirose Electric",
        region="Asia-Pacific",
        tier=2,
        share_pct=99.0,
        sole_source=False,
    )
    neo.is_part_spof.return_value = False
    neo.get_connector_compliance_batch.return_value = {
        "EC-ALT-GOOD": ConnectorComplianceResponse(
            part_number="EC-ALT-GOOD",
            assemblies=["Battery Management System"],
            requirements=[],
            certifications=["RoHS", "REACH", "AEC-Q200"],
            gaps=[],
        ),
        "EC-ALT-BAD": ConnectorComplianceResponse(
            part_number="EC-ALT-BAD",
            assemblies=["Battery Management System"],
            requirements=[],
            certifications=["ISO 9001"],
            gaps=[
                ComplianceGap(
                    requirement_id="req-reach",
                    requirement_name="REACH Compliance",
                    standard="REACH",
                    source_assembly_id="asm-bms",
                    source_assembly_name="Battery Management System",
                )
            ],
        ),
    }
    neo.get_part_sourcing_batch.return_value = {
        "EC-ALT-GOOD": PartSourcing(
            part_number="EC-ALT-GOOD",
            supplier_id="s1",
            supplier_name="Molex",
            region="Americas",
            tier=1,
            share_pct=55.0,
            sole_source=False,
        ),
        "EC-ALT-BAD": PartSourcing(
            part_number="EC-ALT-BAD",
            supplier_id="s2",
            supplier_name="Amphenol",
            region="Americas",
            tier=1,
            share_pct=100.0,
            sole_source=True,
        ),
    }
    neo.get_spof.return_value = MagicMock(entries=[])
    return neo


def test_disruption_agent_run(mock_neo4j):
    qdrant = MagicMock()
    qdrant.find_similar_connectors.return_value = [
        (_make_connector("EC-ALT-BAD"), 90.0),
        (_make_connector("EC-ALT-GOOD"), 85.0),
    ]

    agent = DisruptionAgent(qdrant_service=qdrant, neo4j_service=mock_neo4j)
    result = agent.run("EC-2024-3441", max_alternatives=5, min_similarity=50.0)

    assert result.disrupted_part_number == "EC-2024-3441"
    assert len(result.execution_trace) == 5
    assert len(result.alternatives) == 2
    assert result.alternatives[0].part_number == "EC-ALT-GOOD"
    assert result.alternatives[0].verdict == "preferred"
    assert "Recommended substitute" in result.summary or "EC-ALT-GOOD" in result.summary

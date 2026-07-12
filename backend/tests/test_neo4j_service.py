"""
Tests for Neo4jService with mocked driver.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.models import GraphSeedData
from app.services.neo4j_service import Neo4jService


@pytest.fixture
def mock_settings():
    with patch("app.services.neo4j_service.settings") as mock:
        mock.neo4j_enabled = True
        mock.neo4j_uri = "neo4j+s://test.databases.neo4j.io"
        mock.neo4j_username = "neo4j"
        mock.neo4j_password = "test-password"
        yield mock


@pytest.fixture
def mock_driver():
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__ = MagicMock(return_value=session)
    driver.session.return_value.__exit__ = MagicMock(return_value=False)
    return driver, session


def test_neo4j_disabled_when_no_uri():
    with patch("app.services.neo4j_service.settings") as mock:
        mock.neo4j_enabled = False
        mock.neo4j_uri = None
        mock.neo4j_password = None
        service = Neo4jService()
        assert not service.enabled


def test_verify_connectivity(mock_settings, mock_driver):
    driver, _ = mock_driver
    with patch("app.services.neo4j_service.GraphDatabase") as gdb:
        gdb.driver.return_value = driver
        service = Neo4jService()
        assert service.verify_connectivity() is True
        driver.verify_connectivity.assert_called_once()


def test_get_impact_empty(mock_settings, mock_driver):
    driver, session = mock_driver
    result_mock = MagicMock()
    result_mock.__iter__ = MagicMock(return_value=iter([]))
    session.run.return_value = result_mock

    with patch("app.services.neo4j_service.GraphDatabase") as gdb:
        gdb.driver.return_value = driver
        service = Neo4jService()
        impact = service.get_impact("EC-2024-3441")
        assert impact.part_number == "EC-2024-3441"
        assert impact.affected_vehicles == []
        assert impact.total_bom_qty == 0


def test_get_impact_with_data(mock_settings, mock_driver):
    driver, session = mock_driver
    record = {
        "connector_name": "Test Connector",
        "assembly_id": "asm-bms",
        "assembly_name": "BMS",
        "criticality": "high",
        "qty": 2,
        "critical": True,
        "vehicle_list": [
            {"id": "veh-1", "name": "EV Sedan", "platform": "EV", "model_year": 2025}
        ],
    }
    result_mock = MagicMock()
    result_mock.__iter__ = MagicMock(return_value=iter([record]))
    session.run.return_value = result_mock

    with patch("app.services.neo4j_service.GraphDatabase") as gdb:
        gdb.driver.return_value = driver
        service = Neo4jService()
        impact = service.get_impact("EC-2024-3441")
        assert len(impact.affected_vehicles) == 1
        assert impact.total_bom_qty == 2
        assert len(impact.critical_paths) == 1


def test_graph_seed_validation():
    seed = {
        "vehicles": [{"id": "v1", "name": "Test", "platform": "EV", "model_year": 2025}],
        "assemblies": [{"id": "a1", "name": "BMS", "criticality": "high"}],
        "bom_lines": [{"assembly_id": "a1", "part_number": "P1", "qty": 1, "critical": True}],
        "suppliers": [{"id": "s1", "name": "Supplier", "region": "US", "tier": 1}],
        "sourcing": [{"part_number": "P1", "supplier_id": "s1", "share_pct": 100, "sole_source": True}],
        "requirements": [{"id": "r1", "name": "RoHS", "standard": "RoHS", "severity": "medium"}],
    }
    data = GraphSeedData.model_validate(seed)
    assert len(data.vehicles) == 1
    assert len(data.bom_lines) == 1

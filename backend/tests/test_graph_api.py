"""
Integration tests for graph API endpoints.
Skipped when Neo4j is not configured.
"""

import os

import pytest
from fastapi.testclient import TestClient

neo4j_configured = bool(os.getenv("NEO4J_URI") and os.getenv("NEO4J_PASSWORD"))

pytestmark = pytest.mark.skipif(
    not neo4j_configured,
    reason="Neo4j not configured (set NEO4J_URI and NEO4J_PASSWORD)",
)


@pytest.fixture
def client():
    from app.api import app
    return TestClient(app)


@pytest.mark.neo4j
def test_health_includes_neo4j(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "neo4j" in data


@pytest.mark.neo4j
def test_supplier_risk_endpoint(client):
    response = client.get("/api/graph/suppliers/risk")
    assert response.status_code == 200
    data = response.json()
    assert "suppliers" in data


@pytest.mark.neo4j
def test_impact_endpoint_not_found(client):
    response = client.get("/api/graph/impact/NONEXISTENT-PART")
    assert response.status_code == 404


@pytest.mark.neo4j
def test_part_sourcing_hero_part(client):
    response = client.get("/api/graph/sourcing/EC-2024-3441")
    assert response.status_code == 200
    data = response.json()
    assert data["part_number"] == "EC-2024-3441"
    assert data["supplier_name"]
    assert data["share_pct"] > 0

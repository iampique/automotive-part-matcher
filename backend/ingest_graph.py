"""
Graph data ingestion script for Neo4j.

Loads graph_seed.json and connector catalog, validates with Pydantic models,
and upserts nodes and relationships into Neo4j AuraDB.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from app.models import Connector, GraphSeedData
from app.services.neo4j_service import Neo4jService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_catalog(catalog_path: Path) -> list:
    with open(catalog_path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("connectors", [])


def transform_connector_data(item: dict) -> dict:
    """Normalize catalog field names to match Connector model."""
    specs = item.get("specifications", {})
    transformed = {**item}
    if "voltage_rating_v" in specs:
        transformed["specifications"] = {
            "pin_count": specs["pin_count"],
            "voltage_rating": specs["voltage_rating_v"],
            "current_rating": specs["current_rating_a"],
            "min_operating_temp": specs["min_operating_temp_c"],
            "max_operating_temp": specs["max_operating_temp_c"],
            "ip_rating": specs["ip_rating"],
            "housing_material": specs["housing_material"],
            "contact_material": specs["contact_material"],
            "contact_plating": specs["contact_plating"],
        }
    return transformed


def validate_seed(seed_path: Path) -> GraphSeedData:
    with open(seed_path, encoding="utf-8") as f:
        raw = json.load(f)
    return GraphSeedData.model_validate(raw)


def validate_connectors(raw_data: list) -> list:
    connectors = []
    for item in raw_data:
        transformed = transform_connector_data(item)
        connectors.append(Connector.model_validate(transformed))
    return connectors


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest graph data into Neo4j")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate seed and catalog without writing to Neo4j",
    )
    parser.add_argument(
        "--seed",
        type=Path,
        default=None,
        help="Path to graph_seed.json",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=None,
        help="Path to connector_catalog.json",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    seed_path = args.seed or script_dir.parent / "data" / "raw" / "graph_seed.json"
    catalog_path = args.catalog or script_dir.parent / "data" / "raw" / "connector_catalog.json"

    logger.info("Loading graph seed from %s", seed_path)
    seed = validate_seed(seed_path)
    logger.info("✓ Graph seed validated")

    logger.info("Loading connector catalog from %s", catalog_path)
    connectors = validate_connectors(load_catalog(catalog_path))
    logger.info("✓ %d connectors validated", len(connectors))

    if args.dry_run:
        logger.info("Dry run complete — no data written to Neo4j")
        return 0

    service = Neo4jService()
    if not service.enabled:
        logger.error("Neo4j is not configured. Set NEO4J_URI and NEO4J_PASSWORD in backend/.env")
        return 1

    if not service.verify_connectivity():
        logger.error("Cannot connect to Neo4j. Check credentials and network.")
        return 1

    logger.info("Upserting graph data...")
    counts = service.upsert_graph(seed, connectors)
    stats = service.get_graph_stats()

    logger.info("=" * 60)
    logger.info("GRAPH INGESTION COMPLETE")
    logger.info("=" * 60)
    for key, val in counts.items():
        logger.info("  %s: %d", key, val)
    logger.info("Database totals: %s", stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())

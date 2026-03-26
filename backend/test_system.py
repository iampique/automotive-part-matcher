"""
Comprehensive test script for the automotive part matcher system.

This script tests:
1. Configuration loading
2. Qdrant connection and collection management
3. Embedding generation
4. Connector upload
5. Search functionality with ACORN support
"""

import logging
import sys
from typing import List

from app.config import settings
from app.models import Connector, ConnectorPricing, ConnectorSpecifications
from app.services.qdrant_service import QdrantService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_sample_connectors() -> List[Connector]:
    """Create sample connector data for testing."""
    return [
        Connector(
            part_number="CONN-001",
            name="Automotive Circular Connector 12-Pin",
            description="High-performance 12-pin circular connector designed for automotive applications. Features IP67 rating for protection against dust and water ingress. Suitable for engine control units and transmission systems.",
            connector_type="Circular",
            specifications=ConnectorSpecifications(
                pin_count=12,
                voltage_rating=24,
                current_rating=10,
                min_operating_temp=-40,
                max_operating_temp=125,
                ip_rating="IP67",
                housing_material="Nylon",
                contact_material="Copper",
                contact_plating="Tin"
            ),
            certifications=["ISO 9001", "UL", "CE"],
            applications=["Engine Control", "Transmission", "ABS Systems"],
            pricing=ConnectorPricing(
                unit_price_usd=15.99,
                lead_time_days=14
            )
        ),
        Connector(
            part_number="CONN-002",
            name="Rectangular Connector 8-Pin",
            description="Compact 8-pin rectangular connector for automotive lighting systems. Features IP65 rating and high-temperature resistance. Ideal for LED headlights and taillights.",
            connector_type="Rectangular",
            specifications=ConnectorSpecifications(
                pin_count=8,
                voltage_rating=12,
                current_rating=5,
                min_operating_temp=-30,
                max_operating_temp=105,
                ip_rating="IP65",
                housing_material="Polyamide",
                contact_material="Brass",
                contact_plating="Gold"
            ),
            certifications=["ISO 9001", "CE"],
            applications=["LED Lighting", "Headlights", "Taillights"],
            pricing=ConnectorPricing(
                unit_price_usd=8.50,
                lead_time_days=7
            )
        ),
        Connector(
            part_number="CONN-003",
            name="High-Voltage Connector 16-Pin",
            description="Heavy-duty 16-pin connector for high-voltage automotive applications. Designed for electric vehicle battery management systems. Features IP68 rating and extended temperature range.",
            connector_type="Circular",
            specifications=ConnectorSpecifications(
                pin_count=16,
                voltage_rating=400,
                current_rating=50,
                min_operating_temp=-40,
                max_operating_temp=150,
                ip_rating="IP68",
                housing_material="Metal",
                contact_material="Copper",
                contact_plating="Silver"
            ),
            certifications=["ISO 9001", "UL", "IEC 62196"],
            applications=["EV Battery Management", "Charging Systems", "Power Distribution"],
            pricing=ConnectorPricing(
                unit_price_usd=45.00,
                lead_time_days=21
            )
        ),
    ]


def test_configuration():
    """Test 1: Configuration loading."""
    logger.info("=" * 60)
    logger.info("TEST 1: Configuration Loading")
    logger.info("=" * 60)
    
    try:
        logger.info(f"✓ Qdrant URL: {settings.qdrant_url[:30]}..." if len(settings.qdrant_url) > 30 else f"✓ Qdrant URL: {settings.qdrant_url}")
        logger.info(f"✓ Collection Name: {settings.collection_name}")
        logger.info(f"✓ Embedding Model: {settings.embedding_model}")
        logger.info(f"✓ Embedding Dimensions: {settings.embedding_dimensions}")
        logger.info(f"✓ LLM Provider: {settings.llm_provider}")
        logger.info(f"✓ ACORN Enabled: {settings.acorn_enabled}")
        logger.info(f"✓ ACORN Max Selectivity: {settings.acorn_max_selectivity}")
        logger.info("✓ Configuration loaded successfully!")
        return True
    except Exception as e:
        logger.error(f"✗ Configuration loading failed: {e}")
        return False


def test_qdrant_connection():
    """Test 2: Qdrant connection."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Qdrant Connection")
    logger.info("=" * 60)
    
    try:
        service = QdrantService()
        logger.info("✓ Qdrant service initialized successfully!")
        return service, True
    except Exception as e:
        logger.error(f"✗ Qdrant connection failed: {e}")
        logger.error("  Make sure your QDRANT_URL and QDRANT_API_KEY are correct in .env")
        return None, False


def test_collection_creation(service: QdrantService):
    """Test 3: Collection creation."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Collection Creation")
    logger.info("=" * 60)
    
    try:
        collection_info = service.create_collection()
        logger.info(f"✓ Collection '{collection_info['name']}' ready")
        logger.info(f"  Status: {collection_info['status']}")
        logger.info(f"  Points: {collection_info['points_count']}")
        logger.info(f"  Indexed Vectors: {collection_info.get('indexed_vectors_count', 0)}")
        return True
    except Exception as e:
        logger.error(f"✗ Collection creation failed: {e}")
        return False


def test_embedding_generation(service: QdrantService):
    """Test 4: Embedding generation."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Embedding Generation")
    logger.info("=" * 60)
    
    try:
        test_text = "Automotive connector with 12 pins, 24V rating"
        embedding = service._create_embedding(test_text)
        logger.info(f"✓ Generated embedding with {len(embedding)} dimensions")
        logger.info(f"  First 5 values: {embedding[:5]}")
        return True
    except Exception as e:
        logger.error(f"✗ Embedding generation failed: {e}")
        logger.error("  Make sure your OPENAI_API_KEY is correct in .env")
        return False


def test_connector_upload(service: QdrantService):
    """Test 5: Connector upload."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 5: Connector Upload")
    logger.info("=" * 60)
    
    try:
        sample_connectors = create_sample_connectors()
        logger.info(f"Uploading {len(sample_connectors)} sample connectors...")
        
        uploaded_count = service.upload_connectors(sample_connectors, batch_size=2)
        logger.info(f"✓ Successfully uploaded {uploaded_count} connectors")
        return True
    except Exception as e:
        logger.error(f"✗ Connector upload failed: {e}")
        return False


def test_search(service: QdrantService):
    """Test 6: Search functionality."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 6: Search Functionality")
    logger.info("=" * 60)
    
    try:
        # Test 6a: Basic search
        logger.info("\n6a. Basic semantic search:")
        results = service.search(
            query_text="12 pin connector for engine control",
            limit=3
        )
        logger.info(f"✓ Found {len(results)} results")
        for i, (connector, score) in enumerate(results, 1):
            logger.info(f"  {i}. {connector.name} (Score: {score:.2f})")
        
        # Test 6b: Search with filters
        logger.info("\n6b. Search with filters (voltage >= 20V):")
        results = service.search(
            query_text="high voltage connector",
            filters={"gte": {"specifications.voltage_rating": 20}},
            limit=3
        )
        logger.info(f"✓ Found {len(results)} filtered results")
        for i, (connector, score) in enumerate(results, 1):
            logger.info(f"  {i}. {connector.name} - {connector.specifications.voltage_rating}V (Score: {score:.2f})")
        
        # Test 6c: Search with ACORN
        logger.info("\n6c. Search with ACORN enabled:")
        results = service.search(
            query_text="automotive connector",
            enable_acorn=True,
            limit=3
        )
        logger.info(f"✓ Found {len(results)} results with ACORN")
        for i, (connector, score) in enumerate(results, 1):
            logger.info(f"  {i}. {connector.name} (Score: {score:.2f})")
        
        return True
    except Exception as e:
        logger.error(f"✗ Search failed: {e}")
        return False


def test_collection_stats(service: QdrantService):
    """Test 7: Collection statistics."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 7: Collection Statistics")
    logger.info("=" * 60)
    
    try:
        stats = service.get_collection_stats()
        logger.info(f"✓ Collection Statistics:")
        logger.info(f"  Total Points: {stats['points_count']}")
        logger.info(f"  Indexed Vectors: {stats['indexed_vectors_count']}")
        logger.info(f"  Segments: {stats.get('segments_count', 'N/A')}")
        logger.info(f"  Status: {stats['status']}")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to get collection statistics: {e}")
        return False


def main():
    """Run all tests."""
    logger.info("\n" + "=" * 60)
    logger.info("AUTOMOTIVE PART MATCHER - SYSTEM TEST")
    logger.info("=" * 60)
    
    results = []
    
    # Test 1: Configuration
    results.append(("Configuration", test_configuration()))
    
    # Test 2: Qdrant Connection
    service, success = test_qdrant_connection()
    results.append(("Qdrant Connection", success))
    
    if not success or service is None:
        logger.error("\n" + "=" * 60)
        logger.error("CRITICAL: Cannot proceed without Qdrant connection")
        logger.error("=" * 60)
        logger.error("\nPlease check:")
        logger.error("1. Your .env file exists in the backend/ directory")
        logger.error("2. QDRANT_URL and QDRANT_API_KEY are set correctly")
        logger.error("3. Your Qdrant Cloud instance is accessible")
        sys.exit(1)
    
    # Test 3: Collection Creation
    results.append(("Collection Creation", test_collection_creation(service)))
    
    # Test 4: Embedding Generation
    results.append(("Embedding Generation", test_embedding_generation(service)))
    
    # Test 5: Connector Upload
    results.append(("Connector Upload", test_connector_upload(service)))
    
    # Test 6: Search
    results.append(("Search Functionality", test_search(service)))
    
    # Test 7: Collection Stats
    results.append(("Collection Statistics", test_collection_stats(service)))
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        logger.info(f"{status}: {test_name}")
    
    logger.info(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("\n🎉 All tests passed! System is working correctly.")
    else:
        logger.warning(f"\n⚠️  {total - passed} test(s) failed. Please review the errors above.")


if __name__ == "__main__":
    main()


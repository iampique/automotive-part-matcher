"""
Data ingestion script for loading automotive part data.

This script loads connector data from JSON files, validates it using Pydantic models,
and uploads valid connectors to Qdrant with comprehensive error handling and
progress reporting.

The script performs the following operations:
1. Loads connector data from JSON file
2. Validates each connector against the Connector model schema
3. Initializes Qdrant service and ensures collection exists
4. Uploads valid connectors in batches for optimal performance
5. Verifies upload success by checking collection statistics
6. Performs sample search to demonstrate end-to-end functionality

Why validate before uploading:
- Prevents invalid data from entering the database
- Provides clear error messages for data quality issues
- Allows processing to continue even if some records fail
- Saves API costs by not uploading invalid data

Batch uploading improves performance:
- Reduces number of API calls to Qdrant
- Allows parallel processing of embeddings
- Provides progress feedback during long uploads
- More efficient use of network resources

Verification step importance:
- Ensures data integrity after upload
- Catches silent failures or partial uploads
- Provides confidence that all data was stored correctly
- Helps identify issues early in the process
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import List, Tuple

from app.models import Connector
from app.services.qdrant_service import QdrantService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_connector_data(file_path: Path) -> List[dict]:
    """
    Load connector data from JSON file.
    
    Args:
        file_path: Path to the JSON file containing connector data
        
    Returns:
        List of dictionaries representing connector data
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
    """
    logger.info(f"Loading connector data from: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle both array and object with 'connectors' key
        if isinstance(data, list):
            connectors = data
        elif isinstance(data, dict) and 'connectors' in data:
            connectors = data['connectors']
        else:
            raise ValueError("JSON file must contain an array or an object with 'connectors' key")
        
        logger.info(f"✓ Successfully loaded {len(connectors)} connectors from file")
        return connectors
        
    except FileNotFoundError:
        logger.error(f"✗ File not found: {file_path}")
        logger.error("  Please ensure the connector_catalog.json file exists in data/raw/")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"✗ Invalid JSON in file: {e}")
        raise
    except Exception as e:
        logger.error(f"✗ Error loading file: {e}")
        raise


def transform_connector_data(item: dict) -> dict:
    """
    Transform connector data to match model field names.
    
    Maps field names with suffixes (e.g., voltage_rating_v) to model field names
    (e.g., voltage_rating) to handle data format variations.
    
    Args:
        item: Raw connector dictionary
        
    Returns:
        Transformed connector dictionary with correct field names
    """
    transformed = item.copy()
    
    # Transform specifications if present
    if 'specifications' in transformed and isinstance(transformed['specifications'], dict):
        spec = transformed['specifications'].copy()
        
        # Map field names with suffixes to model field names
        field_mapping = {
            'voltage_rating_v': 'voltage_rating',
            'current_rating_a': 'current_rating',
            'min_operating_temp_c': 'min_operating_temp',
            'max_operating_temp_c': 'max_operating_temp',
        }
        
        for old_key, new_key in field_mapping.items():
            if old_key in spec:
                spec[new_key] = spec.pop(old_key)
        
        transformed['specifications'] = spec
    
    return transformed


def validate_connectors(raw_data: List[dict]) -> Tuple[List[Connector], List[dict]]:
    """
    Validate connector data using Pydantic models.
    
    Args:
        raw_data: List of dictionaries containing raw connector data
        
    Returns:
        Tuple of (valid_connectors, errors) where:
        - valid_connectors: List of validated Connector models
        - errors: List of error dictionaries with part_number and reason
    """
    logger.info("\n" + "=" * 60)
    logger.info("VALIDATION PHASE")
    logger.info("=" * 60)
    logger.info(f"Validating {len(raw_data)} connector records...")
    
    valid_connectors: List[Connector] = []
    errors: List[dict] = []
    
    for idx, item in enumerate(raw_data, start=1):
        try:
            # Transform field names to match model
            transformed_item = transform_connector_data(item)
            
            # Try to parse as Connector model
            connector = Connector(**transformed_item)
            valid_connectors.append(connector)
            
            # Log progress every 50 items
            if idx % 50 == 0:
                logger.info(f"  Processed {idx}/{len(raw_data)} items... ({len(valid_connectors)} valid)")
                
        except Exception as e:
            # Extract part_number if available, otherwise use index
            part_number = item.get('part_number', f'index_{idx}')
            
            error_info = {
                'part_number': part_number,
                'index': idx,
                'reason': str(e)
            }
            errors.append(error_info)
            
            logger.warning(f"  ✗ Validation failed for {part_number}: {e}")
            continue
    
    # Log validation summary
    logger.info("\n" + "-" * 60)
    logger.info("VALIDATION SUMMARY")
    logger.info("-" * 60)
    logger.info(f"  Total items processed: {len(raw_data)}")
    logger.info(f"  ✓ Valid connectors: {len(valid_connectors)}")
    logger.info(f"  ✗ Validation errors: {len(errors)}")
    
    if errors:
        logger.warning(f"\n  First 5 errors:")
        for error in errors[:5]:
            logger.warning(f"    - {error['part_number']}: {error['reason'][:100]}")
        if len(errors) > 5:
            logger.warning(f"    ... and {len(errors) - 5} more errors")
    
    return valid_connectors, errors


def initialize_qdrant() -> QdrantService:
    """
    Initialize Qdrant service and ensure collection exists.
    
    Returns:
        Initialized QdrantService instance
        
    Raises:
        Exception: If Qdrant connection or collection creation fails
    """
    logger.info("\n" + "=" * 60)
    logger.info("QDRANT INITIALIZATION PHASE")
    logger.info("=" * 60)
    
    try:
        logger.info("Connecting to Qdrant Cloud...")
        service = QdrantService()
        logger.info("✓ Qdrant service initialized successfully")
        
        logger.info("Ensuring collection exists...")
        collection_info = service.create_collection()
        logger.info(f"✓ Collection '{collection_info['name']}' is ready")
        logger.info(f"  Current points: {collection_info['points_count']}")
        
        return service
        
    except Exception as e:
        logger.error(f"✗ Failed to initialize Qdrant: {e}")
        logger.error("  Please check your QDRANT_URL and QDRANT_API_KEY in .env file")
        raise


def upload_connectors(service: QdrantService, connectors: List[Connector]) -> int:
    """
    Upload connectors to Qdrant with progress reporting.
    
    Args:
        service: QdrantService instance
        connectors: List of validated Connector models to upload
        
    Returns:
        Number of connectors successfully uploaded
    """
    logger.info("\n" + "=" * 60)
    logger.info("DATA UPLOAD PHASE")
    logger.info("=" * 60)
    logger.info(f"Uploading {len(connectors)} connectors to Qdrant...")
    logger.info("  (Batch size: 50 connectors per batch)")
    
    # Record start time
    start_time = time.time()
    
    try:
        # Upload connectors (batch size of 50 for optimal performance)
        uploaded_count = service.upload_connectors(
            connectors=connectors,
            batch_size=50
        )
        
        # Calculate elapsed time
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Log upload summary
        logger.info("\n" + "-" * 60)
        logger.info("UPLOAD SUMMARY")
        logger.info("-" * 60)
        logger.info(f"  ✓ Successfully uploaded: {uploaded_count} connectors")
        logger.info(f"  ⏱️  Total time: {elapsed_time:.2f} seconds")
        logger.info(f"  ⚡ Average time per connector: {elapsed_time/len(connectors):.3f} seconds")
        
        return uploaded_count
        
    except Exception as e:
        logger.error(f"✗ Upload failed: {e}")
        raise


def verify_upload(service: QdrantService, expected_count: int) -> bool:
    """
    Verify that uploaded connectors match expected count.
    
    Args:
        service: QdrantService instance
        expected_count: Expected number of connectors in collection
        
    Returns:
        True if verification passes, False otherwise
    """
    logger.info("\n" + "=" * 60)
    logger.info("VERIFICATION PHASE")
    logger.info("=" * 60)
    
    try:
        stats = service.get_collection_stats()
        actual_count = stats['points_count']
        
        logger.info(f"Expected points: {expected_count}")
        logger.info(f"Actual points in collection: {actual_count}")
        
        if actual_count == expected_count:
            logger.info("✓ Verification passed: Point count matches expected value")
            return True
        else:
            logger.warning(f"⚠ Verification warning: Point count mismatch")
            logger.warning(f"  Expected: {expected_count}, Got: {actual_count}")
            logger.warning(f"  Difference: {abs(actual_count - expected_count)}")
            return False
            
    except Exception as e:
        logger.error(f"✗ Verification failed: {e}")
        return False


def test_search(service: QdrantService) -> None:
    """
    Perform sample search to demonstrate end-to-end functionality.
    
    Args:
        service: QdrantService instance
    """
    logger.info("\n" + "=" * 60)
    logger.info("TESTING PHASE")
    logger.info("=" * 60)
    
    try:
        query = "48V connector with IP67 rating"
        logger.info(f"Performing sample search: '{query}'")
        logger.info("  (Limiting to 3 results)")
        
        results = service.search(
            query_text=query,
            limit=3,
            enable_acorn=True
        )
        
        logger.info(f"\n✓ Search completed: Found {len(results)} results")
        logger.info("\n" + "-" * 60)
        logger.info("SEARCH RESULTS")
        logger.info("-" * 60)
        
        for idx, (connector, score) in enumerate(results, start=1):
            logger.info(f"\n  Result {idx}:")
            logger.info(f"    Part Number: {connector.part_number}")
            logger.info(f"    Name: {connector.name}")
            logger.info(f"    Match Score: {score:.2f}")
            logger.info(f"    Voltage: {connector.specifications.voltage_rating}V")
            logger.info(f"    IP Rating: {connector.specifications.ip_rating}")
        
        logger.info("\n✓ End-to-end system test completed successfully")
        
    except Exception as e:
        logger.warning(f"⚠ Test search failed: {e}")
        logger.warning("  This is not critical - data upload was successful")


def main() -> int:
    """
    Main function orchestrating the data ingestion process.
    
    Returns:
        Exit code: 0 for success, 1 for errors
    """
    parser = argparse.ArgumentParser(description="Ingest connector catalog into Qdrant")
    parser.add_argument(
        "--with-graph",
        action="store_true",
        help="Also ingest graph relationships into Neo4j after Qdrant upload",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("AUTOMOTIVE CONNECTOR DATA INGESTION")
    logger.info("=" * 60)
    logger.info("This script will:")
    logger.info("  1. Load connector data from JSON file")
    logger.info("  2. Validate all connectors")
    logger.info("  3. Upload valid connectors to Qdrant")
    logger.info("  4. Verify upload success")
    logger.info("  5. Perform sample search test")
    logger.info("")
    
    try:
        # ============================================================
        # DATA LOADING PHASE
        # ============================================================
        script_dir = Path(__file__).parent
        data_file = script_dir.parent / "data" / "raw" / "connector_catalog.json"
        
        raw_data = load_connector_data(data_file)
        
        if not raw_data:
            logger.error("✗ No data found in file")
            return 1
        
        # ============================================================
        # DATA VALIDATION PHASE
        # ============================================================
        valid_connectors, errors = validate_connectors(raw_data)
        
        if not valid_connectors:
            logger.error("\n✗ No valid connectors found. Cannot proceed with upload.")
            logger.error("  Please fix data validation errors and try again.")
            return 1
        
        # ============================================================
        # QDRANT INITIALIZATION PHASE
        # ============================================================
        service = initialize_qdrant()
        
        # ============================================================
        # DATA UPLOAD PHASE
        # ============================================================
        uploaded_count = upload_connectors(service, valid_connectors)
        
        if uploaded_count != len(valid_connectors):
            logger.warning(f"⚠ Warning: Expected to upload {len(valid_connectors)} connectors, "
                         f"but only {uploaded_count} were uploaded")
        
        # ============================================================
        # VERIFICATION PHASE
        # ============================================================
        verification_passed = verify_upload(service, uploaded_count)
        
        if not verification_passed:
            logger.warning("⚠ Verification warning - please check collection manually")
        
        # ============================================================
        # TESTING PHASE
        # ============================================================
        test_search(service)
        
        # ============================================================
        # FINAL SUMMARY
        # ============================================================
        logger.info("\n" + "=" * 60)
        logger.info("INGESTION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"✓ Successfully processed {len(valid_connectors)} connectors")
        logger.info(f"✓ Uploaded {uploaded_count} connectors to Qdrant")
        if errors:
            logger.info(f"⚠ {len(errors)} connectors had validation errors (see above)")
        logger.info("\n🎉 Data ingestion completed successfully!")

        if args.with_graph:
            logger.info("\nStarting graph ingestion (--with-graph)...")
            from ingest_graph import main as ingest_graph_main
            graph_exit = ingest_graph_main()
            if graph_exit != 0:
                logger.error("Graph ingestion failed")
                return graph_exit
            logger.info("Graph ingestion completed successfully")
        
        return 0
        
    except FileNotFoundError as e:
        logger.error(f"\n✗ File not found: {e}")
        logger.error("  Please ensure connector_catalog.json exists in data/raw/")
        return 1
        
    except json.JSONDecodeError as e:
        logger.error(f"\n✗ JSON parsing error: {e}")
        logger.error("  Please check the JSON file format")
        return 1
        
    except KeyboardInterrupt:
        logger.warning("\n⚠ Ingestion interrupted by user")
        return 1
        
    except Exception as e:
        logger.error(f"\n✗ Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

"""
Script to ensure Qdrant collection indexes are properly set up.

This script ensures all required indexes exist, including the text index
on the 'name' field needed for hybrid search functionality.

Run this script if you encounter index-related errors:
    python ensure_indexes.py
"""

import logging
import sys

from app.services.qdrant_service import QdrantService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def main() -> int:
    """
    Ensure all required indexes are created in the Qdrant collection.
    
    Returns:
        Exit code: 0 for success, 1 for errors
    """
    logger.info("=" * 60)
    logger.info("ENSURING QDRANT COLLECTION INDEXES")
    logger.info("=" * 60)
    
    try:
        logger.info("Connecting to Qdrant...")
        service = QdrantService()
        logger.info("✓ Connected to Qdrant successfully")
        
        logger.info("\nEnsuring collection and indexes exist...")
        collection_info = service.create_collection()
        
        logger.info("\n" + "-" * 60)
        logger.info("INDEX SETUP COMPLETE")
        logger.info("-" * 60)
        logger.info(f"Collection: {collection_info['name']}")
        logger.info(f"Status: {collection_info['status']}")
        logger.info(f"Points: {collection_info['points_count']}")
        logger.info(f"Indexed vectors: {collection_info['indexed_vectors_count']}")
        logger.info("\n✓ All indexes have been ensured")
        logger.info("  The text index on 'name' field is now available for hybrid search")
        
        return 0
        
    except Exception as e:
        logger.error(f"\n✗ Failed to ensure indexes: {e}", exc_info=True)
        logger.error("  Please check your QDRANT_URL and QDRANT_API_KEY in .env file")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)


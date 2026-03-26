#!/usr/bin/env python3
"""
Check for duplicate connectors in Qdrant collection.

This script retrieves all connectors and checks for duplicates based on:
- Part numbers (should be unique)
- Exact data matches
"""

import logging
from collections import Counter, defaultdict
from app.services.qdrant_service import QdrantService
from app.models import Connector

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def check_duplicates():
    """Check for duplicate connectors in the collection."""
    logger.info("=" * 70)
    logger.info("DUPLICATE CHECK")
    logger.info("=" * 70)
    
    try:
        service = QdrantService()
        
        # Get collection stats
        stats = service.get_collection_stats()
        total_points = stats['points_count']
        logger.info(f"Total points in collection: {total_points}")
        logger.info("")
        
        # Retrieve all points (scroll through collection)
        logger.info("Retrieving all connectors from collection...")
        all_points = []
        offset = None
        batch_size = 100
        
        while True:
            # Use scroll to get points in batches
            scroll_result = service.client.scroll(
                collection_name=service.collection_name,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )
            
            points = scroll_result[0]  # Points
            next_offset = scroll_result[1]  # Next offset
            
            all_points.extend(points)
            
            if len(points) < batch_size or next_offset is None:
                break
            
            offset = next_offset
            logger.info(f"  Retrieved {len(all_points)}/{total_points} points...")
        
        logger.info(f"✓ Retrieved {len(all_points)} points total\n")
        
        # Parse connectors and check for duplicates
        logger.info("Analyzing connectors for duplicates...")
        connectors = []
        part_numbers = []
        part_number_to_points = defaultdict(list)
        
        for point in all_points:
            try:
                connector = Connector(**point.payload)
                connectors.append(connector)
                part_numbers.append(connector.part_number)
                part_number_to_points[connector.part_number].append({
                    'point_id': point.id,
                    'connector': connector
                })
            except Exception as e:
                logger.warning(f"  Failed to parse point {point.id}: {e}")
                continue
        
        # Check for duplicate part numbers
        part_number_counts = Counter(part_numbers)
        duplicates_by_part_number = {
            pn: count for pn, count in part_number_counts.items() if count > 1
        }
        
        # Check for exact duplicates (same data, different point IDs)
        exact_duplicates = []
        seen_data = {}
        
        for point in all_points:
            try:
                connector = Connector(**point.payload)
                # Create a hash of the connector data (excluding point ID)
                data_key = (
                    connector.part_number,
                    connector.name,
                    connector.description,
                    str(connector.specifications.model_dump()),
                    str(connector.certifications),
                    str(connector.applications),
                    str(connector.pricing.model_dump())
                )
                
                if data_key in seen_data:
                    exact_duplicates.append({
                        'point_id_1': seen_data[data_key],
                        'point_id_2': point.id,
                        'part_number': connector.part_number
                    })
                else:
                    seen_data[data_key] = point.id
            except Exception as e:
                continue
        
        # Report results
        logger.info("=" * 70)
        logger.info("RESULTS")
        logger.info("=" * 70)
        
        logger.info(f"\nTotal connectors analyzed: {len(connectors)}")
        logger.info(f"Unique part numbers: {len(set(part_numbers))}")
        
        # Report duplicate part numbers
        if duplicates_by_part_number:
            logger.warning(f"\n⚠️  Found {len(duplicates_by_part_number)} duplicate part numbers:")
            logger.warning("-" * 70)
            for part_number, count in sorted(duplicates_by_part_number.items()):
                logger.warning(f"  Part Number: {part_number} (appears {count} times)")
                for item in part_number_to_points[part_number]:
                    logger.warning(f"    - Point ID: {item['point_id']}, Name: {item['connector'].name}")
        else:
            logger.info("\n✓ No duplicate part numbers found")
        
        # Report exact duplicates
        if exact_duplicates:
            logger.warning(f"\n⚠️  Found {len(exact_duplicates)} exact duplicate entries:")
            logger.warning("-" * 70)
            for dup in exact_duplicates:
                logger.warning(f"  Part Number: {dup['part_number']}")
                logger.warning(f"    Point ID 1: {dup['point_id_1']}")
                logger.warning(f"    Point ID 2: {dup['point_id_2']}")
        else:
            logger.info("\n✓ No exact duplicate entries found")
        
        # Summary
        logger.info("\n" + "=" * 70)
        if duplicates_by_part_number or exact_duplicates:
            logger.warning("⚠️  DUPLICATES FOUND - Review above for details")
            return 1
        else:
            logger.info("✅ NO DUPLICATES FOUND - Collection is clean!")
            return 0
            
    except Exception as e:
        logger.error(f"Error checking duplicates: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = check_duplicates()
    exit(exit_code)


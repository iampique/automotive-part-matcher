#!/usr/bin/env python3
"""
Quick status checker for ingestion progress.
Shows current status from Qdrant collection.
"""

import sys
from app.services.qdrant_service import QdrantService

def main():
    try:
        service = QdrantService()
        stats = service.get_collection_stats()
        
        print("\n" + "=" * 60)
        print("INGESTION STATUS")
        print("=" * 60)
        print(f"Total Points in Collection: {stats['points_count']}")
        print(f"Indexed Vectors: {stats['indexed_vectors_count']}")
        print(f"Status: {stats['status']}")
        print(f"Segments: {stats.get('segments_count', 'N/A')}")
        print("=" * 60)
        
        if stats['points_count'] >= 500:
            print("\n✅ Ingestion appears complete! (500 connectors expected)")
        else:
            print(f"\n⏳ Ingestion in progress... ({stats['points_count']}/500 connectors)")
            
    except Exception as e:
        print(f"Error checking status: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()


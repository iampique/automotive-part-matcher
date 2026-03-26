#!/usr/bin/env python3
"""
Real-time ingestion monitor.
Shows live progress of connector upload to Qdrant.
"""

import time
import sys
from app.services.qdrant_service import QdrantService

def format_time(seconds):
    """Format seconds into readable time."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs}s"

def main():
    print("\n" + "=" * 70)
    print("REAL-TIME INGESTION MONITOR")
    print("=" * 70)
    print("Press Ctrl+C to stop monitoring\n")
    
    service = QdrantService()
    start_time = time.time()
    last_count = 0
    
    try:
        while True:
            stats = service.get_collection_stats()
            current_count = stats['points_count']
            elapsed = time.time() - start_time
            
            # Calculate progress
            progress_pct = (current_count / 500) * 100
            progress_bar_length = 50
            filled = int(progress_bar_length * current_count / 500)
            bar = "█" * filled + "░" * (progress_bar_length - filled)
            
            # Calculate rate
            if elapsed > 0:
                rate = current_count / elapsed
                remaining = (500 - current_count) / rate if rate > 0 else 0
            else:
                rate = 0
                remaining = 0
            
            # Calculate change since last check
            delta = current_count - last_count
            
            # Clear and print status
            sys.stdout.write("\r" + " " * 70 + "\r")  # Clear line
            sys.stdout.write(f"Progress: [{bar}] {progress_pct:.1f}% | ")
            sys.stdout.write(f"{current_count}/500 connectors | ")
            sys.stdout.write(f"Rate: {rate:.1f}/s | ")
            sys.stdout.write(f"ETA: {format_time(remaining)} | ")
            sys.stdout.write(f"Elapsed: {format_time(elapsed)}")
            if delta > 0:
                sys.stdout.write(f" | +{delta} since last check")
            sys.stdout.flush()
            
            last_count = current_count
            
            # Check if complete
            if current_count >= 500:
                print("\n\n✅ INGESTION COMPLETE!")
                print(f"   Total time: {format_time(elapsed)}")
                print(f"   Average rate: {rate:.2f} connectors/second")
                break
            
            time.sleep(2)  # Update every 2 seconds
            
    except KeyboardInterrupt:
        print("\n\n⏸ Monitoring stopped by user")
        stats = service.get_collection_stats()
        print(f"   Current status: {stats['points_count']}/500 connectors uploaded")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()


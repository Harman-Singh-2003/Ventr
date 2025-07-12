#!/usr/bin/env python3
"""
Network cache management script for the Crime-Aware Routing system.

This script helps manage the OSMnx network cache, including creating, checking,
and updating the cached Toronto street network.
"""

import argparse
import logging
import sys
import os
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from crime_aware_routing_2.mapping.network.network_cache import (
    get_network_cache, 
    ensure_toronto_cache
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_cache(center_lat: float, center_lon: float, radius_km: float) -> None:
    """Create a new network cache."""
    logger.info(f"Creating network cache for {radius_km}km radius around ({center_lat}, {center_lon})")
    
    try:
        cache = get_network_cache()
        center_coords = (center_lat, center_lon)
        radius_m = radius_km * 1000.0
        
        success = cache.create_cache(center_coords, radius_m)
        
        if success:
            logger.info("✅ Cache created successfully!")
            show_cache_info()
        else:
            logger.error("❌ Failed to create cache")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ Error creating cache: {e}")
        sys.exit(1)


def show_cache_info() -> None:
    """Show information about the current cache."""
    cache = get_network_cache()
    info = cache.get_cache_info()
    
    print("\n📊 Network Cache Information")
    print("=" * 40)
    
    if not info['available']:
        print("❌ No cache available")
        print(f"Expected location: {info['cache_file']}")
        return
    
    print("✅ Cache available")
    print(f"📁 File: {info['cache_file']}")
    print(f"📍 Center: ({info['center'][0]:.4f}, {info['center'][1]:.4f})")
    print(f"📏 Radius: {info['radius_km']:.1f} km")
    print(f"🏗️  Nodes: {info['nodes']:,}")
    print(f"🛣️  Edges: {info['edges']:,}")
    
    if info['file_size_mb']:
        print(f"💾 File size: {info['file_size_mb']:.1f} MB")


def test_cache() -> None:
    """Test cache functionality with sample routes."""
    logger.info("Testing cache functionality...")
    
    cache = get_network_cache()
    
    # Try to load cache
    if not cache.load_cache():
        logger.error("❌ No cache to test. Create one first with --create")
        return
    
    # Test routes within Toronto
    test_routes = [
        # Downtown Toronto routes
        ((43.6532, -79.3832), (43.6426, -79.3871), "CN Tower to Union Station"),
        ((43.6544, -79.3807), (43.6505, -79.3840), "Financial District to Entertainment District"),
        ((43.6510, -79.3470), (43.6620, -79.3950), "Beaches to High Park"),
        # Edge cases
        ((43.5800, -79.2000), (43.7200, -79.5000), "Far outside cache area"),
    ]
    
    print("\n🧪 Testing Cache Coverage")
    print("=" * 40)
    
    for start, end, description in test_routes:
        in_cache = cache.is_route_in_cache(start, end)
        status = "✅ Cached" if in_cache else "❌ Not cached"
        print(f"{status}: {description}")
        
        if in_cache:
            # Test extraction
            center_lat = (start[0] + end[0]) / 2
            center_lon = (start[1] + end[1]) / 2
            
            try:
                subgraph = cache.extract_subgraph((center_lat, center_lon), 1000)
                if subgraph:
                    print(f"    ↳ Extracted: {len(subgraph.nodes)} nodes, {len(subgraph.edges)} edges")
                else:
                    print(f"    ↳ ❌ Extraction failed")
            except Exception as e:
                print(f"    ↳ ❌ Extraction error: {e}")


def ensure_cache() -> None:
    """Ensure Toronto cache is available (create if needed)."""
    logger.info("Ensuring Toronto cache is available...")
    
    success = ensure_toronto_cache()
    
    if success:
        logger.info("✅ Toronto cache is ready!")
        show_cache_info()
    else:
        logger.error("❌ Failed to ensure cache availability")
        sys.exit(1)


def delete_cache() -> None:
    """Delete the current cache."""
    cache = get_network_cache()
    
    if not cache.is_cache_available():
        logger.info("No cache file to delete")
        return
    
    try:
        cache.cache_file.unlink()
        logger.info(f"✅ Cache deleted: {cache.cache_file}")
    except Exception as e:
        logger.error(f"❌ Failed to delete cache: {e}")


def main():
    """Main entry point for cache management."""
    parser = argparse.ArgumentParser(
        description="Manage OSMnx network cache for Crime-Aware Routing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create default Toronto cache (30km radius)
  python cache_manager.py --ensure
  
  # Create custom cache
  python cache_manager.py --create --lat 43.6532 --lon -79.3832 --radius 25
  
  # Check cache status
  python cache_manager.py --info
  
  # Test cache functionality
  python cache_manager.py --test
  
  # Delete cache
  python cache_manager.py --delete
        """
    )
    
    parser.add_argument("--create", action="store_true", 
                       help="Create a new cache")
    parser.add_argument("--ensure", action="store_true",
                       help="Ensure Toronto cache exists (create if needed)")
    parser.add_argument("--info", action="store_true",
                       help="Show cache information")
    parser.add_argument("--test", action="store_true", 
                       help="Test cache functionality")
    parser.add_argument("--delete", action="store_true",
                       help="Delete the current cache")
    
    parser.add_argument("--lat", type=float, default=43.6532,
                       help="Center latitude (default: 43.6532 - Toronto downtown)")
    parser.add_argument("--lon", type=float, default=-79.3832,
                       help="Center longitude (default: -79.3832 - Toronto downtown)")
    parser.add_argument("--radius", type=float, default=30.0,
                       help="Cache radius in kilometers (default: 30.0)")
    
    args = parser.parse_args()
    
    # Default to showing info if no action specified
    if not any([args.create, args.ensure, args.info, args.test, args.delete]):
        args.info = True
    
    try:
        if args.delete:
            delete_cache()
        
        if args.create:
            create_cache(args.lat, args.lon, args.radius)
        
        if args.ensure:
            ensure_cache()
        
        if args.info:
            show_cache_info()
        
        if args.test:
            test_cache()
            
    except KeyboardInterrupt:
        logger.info("\n👋 Cache management interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 
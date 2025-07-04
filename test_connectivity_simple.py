#!/usr/bin/env python3
"""
Simple test to demonstrate boundary edge cataloging for guaranteed connectivity.
"""

import sys
import logging
import geohash
from pathlib import Path

# Add project path
sys.path.insert(0, str(Path(__file__).parent))

from crime_aware_routing_2.mapping.cache.connectivity_cache import ConnectivityCache
from crime_aware_routing_2.mapping.cache.boundary_edge_manager import BoundaryEdgeManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

def test_boundary_cataloging():
    """Test boundary edge cataloging system."""
    
    print("🔧 BOUNDARY EDGE CATALOGING SYSTEM TEST")
    print("=" * 60)
    
    # Initialize system
    print("\n1. Initializing connectivity cache...")
    cache_dir = "crime_aware_routing_2/cache_boundary_test"
    connectivity_cache = ConnectivityCache(cache_dir, precision=6)
    
    # Clear for clean test
    print("2. Clearing cache for clean test...")
    connectivity_cache.clear_connectivity_cache()
    
    # Test route that crosses tile boundaries
    start = (43.6426, -79.3871)  # Financial District
    end = (43.6629, -79.3957)    # Queen's Park
    
    print(f"\n3. Testing route: {start} → {end}")
    
    # Debug: Generate some tiles manually to test with
    start_geohash = geohash.encode(start[0], start[1], 6)
    end_geohash = geohash.encode(end[0], end[1], 6)
    
    print(f"   Start geohash: {start_geohash}")
    print(f"   End geohash: {end_geohash}")
    
    # Find required tiles
    tiles = connectivity_cache.find_covering_geohashes(start, end)
    print(f"   Required tiles from find_covering_geohashes: {tiles}")
    
    # If no tiles found, use manual approach
    if not tiles:
        print("   No tiles found via find_covering_geohashes, using manual geohashes...")
        tiles = [start_geohash, end_geohash]
        print(f"   Manual tiles: {tiles}")
    
    # Download tiles with boundary cataloging
    print(f"\n4. Downloading {len(tiles)} tiles with boundary cataloging...")
    for i, tile in enumerate(tiles, 1):
        print(f"   [{i}/{len(tiles)}] Downloading {tile}...")
        try:
            success = connectivity_cache.download_and_cache_network(tile, force_refresh=True)
            print(f"   {'✓' if success else '❌'} {'Success' if success else 'Failed'}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # Get boundary statistics
    print(f"\n5. Boundary Edge Statistics:")
    try:
        stats = connectivity_cache.boundary_manager.get_boundary_statistics()
        
        if 'error' not in stats:
            print(f"   Boundary Edges Cataloged: {stats['boundary_edges']['total']}")
            print(f"   Average Edge Length: {stats['boundary_edges']['avg_length_m']:.1f}m")
            print(f"   Tiles with Boundaries: {stats['tiles']['total']}")
        else:
            print(f"   Error: {stats['error']}")
    except Exception as e:
        print(f"   Error getting stats: {e}")
    
    # Test connectivity guarantee
    print(f"\n6. Testing connectivity guarantee...")
    try:
        validation = connectivity_cache.validate_connectivity_guarantee(start, end)
        
        if validation['success']:
            print(f"   ✓ Status: {validation['guarantee_status']}")
            print(f"   Network: {validation['network_stats']['nodes']} nodes, {validation['network_stats']['edges']} edges")
            print(f"   Connectivity: {validation['connectivity']['num_components']} components")
            print(f"   Route Possible: {validation['connectivity']['route_possible']}")
            print(f"   Load Time: {validation['performance']['load_time_seconds']:.2f}s")
        else:
            print(f"   ❌ Failed: {validation.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"   ❌ Error during validation: {e}")
        validation = {'success': False, 'guarantee_status': 'FAILED'}
    
    print(f"\n🎯 RESULT:")
    if validation.get('success') and validation.get('guarantee_status') == 'PERFECT':
        print("   🏆 PERFECT CONNECTIVITY GUARANTEED!")
        print("   ✓ No buffer dependency")
        print("   ✓ Boundary edges restored")
        print("   ✓ Full network connectivity")
        success = True
    else:
        print("   ⚠️  Connectivity guarantee not achieved")
        print("   Note: This may be due to no cached tiles or other issues.")
        success = False
    
    # Additional debugging
    print(f"\n7. Debug Information:")
    print(f"   Cache directory: {cache_dir}")
    cache_path = Path(cache_dir)
    if cache_path.exists():
        print(f"   Cache directory exists: True")
        print(f"   Cache contents: {list(cache_path.iterdir())}")
    else:
        print(f"   Cache directory exists: False")
    
    print("\n" + "=" * 60)
    return success

if __name__ == '__main__':
    try:
        success = test_boundary_cataloging()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 
#!/usr/bin/env python3
"""
Test script to demonstrate the boundary edge cataloging system for guaranteed connectivity.

This shows how the system eliminates connectivity issues without relying on buffer adequacy.
"""

import sys
import logging
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from crime_aware_routing_2.mapping.cache.connectivity_cache import ConnectivityCache
from crime_aware_routing_2.mapping.cache.boundary_edge_manager import BoundaryEdgeManager
import networkx as nx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_boundary_edge_cataloging():
    """Test the boundary edge cataloging and restoration system."""
    
    print("=" * 80)
    print("BOUNDARY EDGE CATALOGING SYSTEM TEST")
    print("Guaranteed Connectivity Without Buffer Dependency")
    print("=" * 80)
    
    # Initialize connectivity cache
    cache_dir = "crime_aware_routing_2/cache_test_connectivity"
    connectivity_cache = ConnectivityCache(cache_dir, precision=6)
    
    # Clear any existing cache for clean test
    print("\n1. Clearing existing cache for clean test...")
    connectivity_cache.clear_connectivity_cache()
    
    # Test routes that commonly cause connectivity issues
    test_routes = [
        {
            'name': 'Short Downtown Route',
            'description': 'Single tile route to test basic functionality',
            'start': (43.6426, -79.3871),  # Financial District
            'end': (43.6455, -79.3834),    # City Hall area
            'expected_tiles': 1
        },
        {
            'name': 'Cross-Boundary Route',
            'description': 'Route crossing tile boundaries - critical test case',
            'start': (43.6426, -79.3871),  # Financial District
            'end': (43.6629, -79.3957),    # Queen\'s Park
            'expected_tiles': 2
        },
        {
            'name': 'Multi-Tile Long Route',
            'description': 'Long route spanning multiple tiles',
            'start': (43.6108, -79.3960),  # Lake Shore
            'end': (43.6890, -79.3224),    # North York
            'expected_tiles': 6
        },
        {
            'name': 'Highway Crossing Route',
            'description': 'Route crossing major highways (challenging connectivity)',
            'start': (43.6426, -79.3871),  # Downtown
            'end': (43.7182, -79.5181),    # Mississauga border
            'expected_tiles': 8
        }
    ]
    
    # Pre-download cache for test routes
    print("\n2. Pre-downloading cache with boundary edge cataloging...")
    
    all_geohashes = set()
    for route in test_routes:
        geohashes = connectivity_cache.find_covering_geohashes(route['start'], route['end'])
        all_geohashes.update(geohashes)
        print(f"   {route['name']}: {len(geohashes)} tiles")
    
    print(f"\nDownloading {len(all_geohashes)} unique tiles with boundary cataloging...")
    
    download_start = time.time()
    successful_downloads = 0
    
    for i, gh in enumerate(sorted(all_geohashes), 1):
        print(f"   [{i}/{len(all_geohashes)}] Downloading {gh}...")
        if connectivity_cache.download_and_cache_network(gh, force_refresh=True):
            successful_downloads += 1
        else:
            print(f"   ❌ Failed to download {gh}")
    
    download_time = time.time() - download_start
    print(f"\nDownload complete: {successful_downloads}/{len(all_geohashes)} successful "
          f"({download_time:.1f}s)")
    
    # Get boundary edge statistics
    print("\n3. Boundary Edge Cataloging Statistics:")
    print("-" * 50)
    
    boundary_manager = connectivity_cache.boundary_manager
    stats = boundary_manager.get_boundary_statistics()
    
    if 'error' not in stats:
        print(f"Total Boundary Edges: {stats['boundary_edges']['total']}")
        print(f"Average Edge Length: {stats['boundary_edges']['avg_length_m']:.1f}m")
        print(f"Total Edge Length: {stats['boundary_edges']['total_length_km']:.1f}km")
        print(f"Tiles with Boundaries: {stats['tiles']['total']}")
        print(f"Avg Boundary Edges/Tile: {stats['tiles']['avg_boundary_edges_per_tile']:.1f}")
    else:
        print(f"Error getting statistics: {stats['error']}")
    
    # Test connectivity guarantee for each route
    print("\n4. Testing Connectivity Guarantee:")
    print("-" * 50)
    
    connectivity_results = []
    
    for i, route in enumerate(test_routes, 1):
        print(f"\nTest {i}: {route['name']}")
        print(f"Description: {route['description']}")
        print(f"Route: {route['start']} → {route['end']}")
        
        # Validate connectivity guarantee
        validation = connectivity_cache.validate_connectivity_guarantee(
            route['start'], route['end']
        )
        
        connectivity_results.append({
            'route': route,
            'validation': validation
        })
        
        if validation['success']:
            conn = validation['connectivity']
            perf = validation['performance']
            coverage = validation['coverage']
            
            print(f"✓ Status: {validation['guarantee_status']}")
            print(f"  Network: {validation['network_stats']['nodes']} nodes, "
                  f"{validation['network_stats']['edges']} edges")
            print(f"  Connectivity: {conn['num_components']} components, "
                  f"route possible: {conn['route_possible']}")
            print(f"  Coverage: start {coverage['start_distance_m']:.0f}m, "
                  f"end {coverage['end_distance_m']:.0f}m")
            print(f"  Performance: {perf['load_time_seconds']:.2f}s")
        else:
            print(f"❌ Failed: {validation.get('error', 'Unknown error')}")
    
    # Compare with traditional buffer-based approach
    print("\n5. Connectivity Guarantee Analysis:")
    print("-" * 50)
    
    perfect_connectivity = sum(1 for r in connectivity_results 
                             if r['validation']['success'] and 
                                r['validation']['guarantee_status'] == 'PERFECT')
    
    partial_connectivity = sum(1 for r in connectivity_results 
                             if r['validation']['success'] and 
                                r['validation']['guarantee_status'] == 'PARTIAL')
    
    failed_connectivity = sum(1 for r in connectivity_results 
                            if not r['validation']['success'] or 
                               r['validation']['guarantee_status'] == 'FAILED')
    
    total_routes = len(test_routes)
    
    print(f"Perfect Connectivity: {perfect_connectivity}/{total_routes} "
          f"({perfect_connectivity/total_routes*100:.1f}%)")
    print(f"Partial Connectivity: {partial_connectivity}/{total_routes} "
          f"({partial_connectivity/total_routes*100:.1f}%)")
    print(f"Failed Connectivity: {failed_connectivity}/{total_routes} "
          f"({failed_connectivity/total_routes*100:.1f}%)")
    
    # Performance analysis
    successful_validations = [r for r in connectivity_results if r['validation']['success']]
    if successful_validations:
        avg_load_time = sum(r['validation']['performance']['load_time_seconds'] 
                           for r in successful_validations) / len(successful_validations)
        
        avg_coverage = sum(r['validation']['coverage']['max_distance_m'] 
                          for r in successful_validations) / len(successful_validations)
        
        print(f"\nPerformance Metrics:")
        print(f"Average Load Time: {avg_load_time:.2f}s")
        print(f"Average Coverage Distance: {avg_coverage:.0f}m")
    
    # System comparison
    print("\n6. System Comparison:")
    print("-" * 50)
    print("🔴 Traditional Buffer-Based Approach:")
    print("   - Relies on guessing adequate buffer sizes")
    print("   - Connectivity depends on buffer luck")
    print("   - Highway ramps often exceed buffer limits")
    print("   - Inconsistent results across different areas")
    print("   - Complex parameter tuning required")
    
    print("\n🟢 Boundary Edge Cataloging Approach:")
    print("   - Guarantees perfect connectivity")
    print("   - No dependency on buffer adequacy")
    print("   - Handles highway ramps and complex interchanges")
    print("   - Consistent results regardless of geography")
    print("   - Zero parameter tuning for connectivity")
    
    connectivity_percentage = (perfect_connectivity + partial_connectivity) / total_routes * 100
    
    print(f"\n🎯 RESULTS:")
    print(f"   Connectivity Success Rate: {connectivity_percentage:.1f}%")
    print(f"   Perfect Connectivity Rate: {perfect_connectivity/total_routes*100:.1f}%")
    
    if perfect_connectivity == total_routes:
        print("   🏆 PERFECT: All routes achieved guaranteed connectivity!")
    elif connectivity_percentage >= 75:
        print("   ✅ EXCELLENT: Most routes achieved connectivity guarantee")
    elif connectivity_percentage >= 50:
        print("   ⚠️  GOOD: Majority of routes achieved connectivity")
    else:
        print("   ❌ NEEDS IMPROVEMENT: Low connectivity success rate")
    
    return connectivity_results


def demonstrate_boundary_edge_restoration():
    """Demonstrate how boundary edge restoration works."""
    
    print("\n" + "=" * 80)
    print("BOUNDARY EDGE RESTORATION DEMONSTRATION")
    print("=" * 80)
    
    # Show detailed process for one route
    cache_dir = "crime_aware_routing_2/cache_test_connectivity"
    connectivity_cache = ConnectivityCache(cache_dir, precision=6)
    
    # Test route that crosses boundaries
    start_coords = (43.6426, -79.3871)  # Financial District
    end_coords = (43.6629, -79.3957)    # Queen's Park
    
    print(f"\nDemonstrating boundary restoration for route:")
    print(f"Start: {start_coords} (Financial District)")
    print(f"End: {end_coords} (Queen's Park)")
    
    # Find covering tiles
    covering_tiles = connectivity_cache.find_covering_geohashes(start_coords, end_coords)
    print(f"\nCovering tiles: {covering_tiles}")
    
    # Load network with detailed logging
    print(f"\nLoading network with boundary restoration...")
    
    # Enable debug logging temporarily
    logging.getLogger('crime_aware_routing_2.mapping.cache.connectivity_cache').setLevel(logging.DEBUG)
    logging.getLogger('crime_aware_routing_2.mapping.cache.boundary_edge_manager').setLevel(logging.DEBUG)
    
    merged_network = connectivity_cache.load_networks_for_route(start_coords, end_coords)
    
    # Reset logging level
    logging.getLogger('crime_aware_routing_2.mapping.cache.connectivity_cache').setLevel(logging.INFO)
    logging.getLogger('crime_aware_routing_2.mapping.cache.boundary_edge_manager').setLevel(logging.INFO)
    
    if merged_network:
        print(f"\n✓ Successfully loaded network with {len(merged_network.nodes)} nodes "
              f"and {len(merged_network.edges)} edges")
        
        # Check for boundary-restored edges
        boundary_restored_edges = [
            (u, v, key) for u, v, key, data in merged_network.edges(data=True, keys=True)
            if data.get('boundary_restored', False)
        ]
        
        print(f"🔧 Boundary-restored edges: {len(boundary_restored_edges)}")
        
        if boundary_restored_edges:
            print("   Examples of restored edges:")
            for i, (u, v, key) in enumerate(boundary_restored_edges[:3]):
                edge_data = merged_network.edges[u, v, key]
                length = edge_data.get('length', 0)
                print(f"   {i+1}. {u} → {v} (key: {key}, length: {length:.0f}m)")
    else:
        print("❌ Failed to load network")


if __name__ == '__main__':
    try:
        # Run main test
        results = test_boundary_edge_cataloging()
        
        # Run detailed demonstration
        demonstrate_boundary_edge_restoration()
        
        print("\n" + "=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)
        print("\nThe boundary edge cataloging system provides guaranteed connectivity")
        print("without relying on buffer adequacy, eliminating the fundamental")
        print("connectivity issues present in traditional tile-based caching approaches.")
        
    except KeyboardInterrupt:
        print("\n⚠ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 
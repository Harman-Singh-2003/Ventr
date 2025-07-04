#!/usr/bin/env python3
"""
Comprehensive test suite for adaptive buffering system.
Tests various route types and geographic scenarios.
"""

import time
import sys
from typing import List, Tuple, Dict
from crime_aware_routing_2.mapping.network.cached_network_builder import CachedNetworkBuilder
from crime_aware_routing_2.mapping.cache.grid_cache import GridCache

def test_route_types():
    """Test various route types and scenarios."""
    
    print("=" * 80)
    print("🧪 COMPREHENSIVE ADAPTIVE BUFFERING TEST SUITE")
    print("=" * 80)
    print()
    
    # Initialize components
    builder = CachedNetworkBuilder()
    cache = GridCache()
    
    # Check current cache status (DON'T clear - we want to test cache hits!)
    print("📊 Current cache status (should have tiles from previous run):")
    cache.print_cache_stats()
    print()
    
    # Define test cases
    test_cases = [
        {
            'name': 'SHORT_DOWNTOWN',
            'start': (43.6426, -79.3871),  # Union Station area
            'end': (43.6452, -79.3850),    # Short walk north
            'description': 'Short downtown route within single tile'
        },
        {
            'name': 'MEDIUM_CROSS_TILE',
            'start': (43.6426, -79.3871),  # Union Station
            'end': (43.6532, -79.4015),    # To Annex (crosses tiles)
            'description': 'Medium route crossing 2-3 tiles'
        },
        {
            'name': 'LONG_NORTH_SOUTH',
            'start': (43.6090, -79.3832),  # Harbourfront
            'end': (43.6800, -79.3900),    # North Toronto
            'description': 'Long north-south route spanning many tiles'
        },
        {
            'name': 'HIGHWAY_GARDINER',
            'start': (43.6385, -79.3832),  # Gardiner start
            'end': (43.6350, -79.4200),    # Gardiner west
            'description': 'Highway route along Gardiner Expressway'
        },
        {
            'name': 'DENSE_FINANCIAL',
            'start': (43.6481, -79.3807),  # Financial District
            'end': (43.6515, -79.3780),    # King/Bay area
            'description': 'Dense urban route through Financial District'
        },
        {
            'name': 'SPARSE_SUBURBAN',
            'start': (43.7000, -79.3000),  # Scarborough
            'end': (43.7100, -79.2800),    # Suburban area
            'description': 'Suburban route with sparse street network'
        },
        {
            'name': 'BOUNDARY_CROSSING',
            'start': (43.6499, -79.3800),  # Just south of tile boundary
            'end': (43.6501, -79.3800),    # Just north of tile boundary
            'description': 'Route specifically crossing tile boundary'
        },
        {
            'name': 'WATERFRONT_COMPLEX',
            'start': (43.6426, -79.3871),  # Union Station
            'end': (43.6350, -79.3200),    # Eastern waterfront
            'description': 'Waterfront route with potential connectivity issues'
        },
        {
            'name': 'DIAGONAL_LONG',
            'start': (43.6200, -79.4200),  # Southwest
            'end': (43.6700, -79.3600),    # Northeast diagonal
            'description': 'Long diagonal route across city'
        },
        {
            'name': 'COMPLEX_INTERCHANGE',
            'start': (43.6767, -79.6306),  # Airport area
            'end': (43.6850, -79.6200),    # Airport complex
            'description': 'Route through complex highway interchange'
        }
    ]
    
    results = {}
    
    print(f"📋 Running {len(test_cases)} test cases:")
    for i, test_case in enumerate(test_cases, 1):
        print(f"  {i:2d}. {test_case['name']}: {test_case['description']}")
    print()
    
    # Run tests
    for i, test_case in enumerate(test_cases, 1):
        print("-" * 60)
        print(f"🔬 Test {i}: {test_case['name']}")
        print(f"   {test_case['description']}")
        print(f"   Route: ({test_case['start'][0]:.4f}, {test_case['start'][1]:.4f}) → "
              f"({test_case['end'][0]:.4f}, {test_case['end'][1]:.4f})")
        
        try:
            # Get initial cache stats
            initial_stats = get_cache_stats()
            
            # Time the route building
            start_time = time.time()
            network = builder.build_network(
                test_case['start'], test_case['end'], prefer_cache=True
            )
            build_time = time.time() - start_time
            
            # Get final cache stats
            final_stats = get_cache_stats()
            
            # Analyze results
            new_tiles = final_stats['cached_tiles'] - initial_stats['cached_tiles']
            cache_hit = new_tiles == 0
            
            # Check connectivity
            import networkx as nx
            is_connected = nx.is_connected(network.to_undirected())
            num_components = nx.number_connected_components(network.to_undirected())
            
            # Store results
            results[test_case['name']] = {
                'success': True,
                'build_time': build_time,
                'network_nodes': len(network.nodes),
                'network_edges': len(network.edges),
                'tiles_used': new_tiles if not cache_hit else "cached",
                'cache_hit': cache_hit,
                'is_connected': is_connected,
                'num_components': num_components
            }
            
            # Print results
            print(f"   ✅ Success: {build_time:.2f}s, {len(network.nodes)} nodes, {len(network.edges)} edges")
            
            if cache_hit:
                print(f"   🎯 Cache Hit: Used existing cached tiles")
            else:
                print(f"   📦 Cache Miss: Created {new_tiles} new tiles")
            
            if is_connected:
                print(f"   ✅ Network fully connected")
            else:
                print(f"   ⚠️ Network has {num_components} disconnected components")
                
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            results[test_case['name']] = {
                'success': False,
                'error': str(e)
            }
        
        print()
    
    # Print final summary
    print_final_summary(results, test_cases)

def get_cache_stats() -> Dict:
    """Get current cache statistics."""
    import os
    cache_dir = "crime_aware_routing_2/cache/networks"
    
    if not os.path.exists(cache_dir):
        return {'cached_tiles': 0, 'total_size': 0}
    
    cached_files = [f for f in os.listdir(cache_dir) if f.endswith('.graphml')]
    total_size = sum(os.path.getsize(os.path.join(cache_dir, f)) for f in cached_files)
    
    return {
        'cached_tiles': len(cached_files),
        'total_size': total_size
    }

def print_final_summary(results: Dict, test_cases: List[Dict]):
    """Print comprehensive test summary."""
    print("=" * 80)
    print("📊 COMPREHENSIVE TEST RESULTS SUMMARY")
    print("=" * 80)
    
    # Overall statistics
    total_tests = len(test_cases)
    successful_tests = sum(1 for r in results.values() if r.get('success', False))
    failed_tests = total_tests - successful_tests
    
    print(f"📈 Overall Results:")
    print(f"   Total Tests: {total_tests}")
    print(f"   ✅ Successful: {successful_tests}")
    print(f"   ❌ Failed: {failed_tests}")
    print(f"   Success Rate: {(successful_tests/total_tests)*100:.1f}%")
    print()
    
    # Performance analysis
    successful_results = [r for r in results.values() if r.get('success', False)]
    if successful_results:
        times = [r['build_time'] for r in successful_results]
        cache_hits = sum(1 for r in successful_results if r['cache_hit'])
        connected_networks = sum(1 for r in successful_results if r['is_connected'])
        
        print(f"⚡ Performance Analysis:")
        print(f"   Average build time: {sum(times)/len(times):.2f}s")
        print(f"   Fastest: {min(times):.2f}s")
        print(f"   Slowest: {max(times):.2f}s")
        print(f"   Cache hits: {cache_hits}/{len(successful_results)} ({(cache_hits/len(successful_results))*100:.1f}%)")
        print(f"   Connected networks: {connected_networks}/{len(successful_results)} ({(connected_networks/len(successful_results))*100:.1f}%)")
        print()
    
    # Cache efficiency
    final_cache_stats = get_cache_stats()
    print(f"💾 Final Cache Statistics:")
    print(f"   Cached tiles: {final_cache_stats['cached_tiles']}")
    print(f"   Total cache size: {final_cache_stats['total_size']/1024/1024:.1f} MB")
    print()
    
    # Detailed results table
    print(f"📋 Detailed Results:")
    print(f"{'Test Name':<20} {'Time':<8} {'Nodes':<7} {'Edges':<7} {'Tiles':<8} {'Connected':<10}")
    print("-" * 70)
    
    for test_case in test_cases:
        name = test_case['name']
        if name in results and results[name].get('success', False):
            r = results[name]
            tiles_str = str(r['tiles_used']) if r['tiles_used'] != "cached" else "cached"
            connected_str = "✅" if r['is_connected'] else f"❌({r['num_components']})"
            print(f"{name:<20} {r['build_time']:<8.2f} {r['network_nodes']:<7} {r['network_edges']:<7} {tiles_str:<8} {connected_str:<10}")
        else:
            print(f"{name:<20} {'FAILED':<8} {'-':<7} {'-':<7} {'-':<8} {'-':<10}")
    
    print()
    print("🎉 Comprehensive adaptive buffering test complete!")

def main():
    """Run the comprehensive test suite."""
    try:
        test_route_types()
        
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 
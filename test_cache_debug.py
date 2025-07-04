#!/usr/bin/env python3
"""
Debug script to test grid caching behavior
"""

from crime_aware_routing_2.mapping.network.cached_network_builder import CachedNetworkBuilder
from crime_aware_routing_2.mapping.cache.grid_cache import GridCache

def test_cache_behavior():
    """Test the cache loading behavior step by step."""
    
    # Same coordinates as our API test
    start_coords = (43.6426, -79.3871)
    end_coords = (43.6452, -79.3806)
    
    print("=== CACHE DEBUG TEST ===")
    print(f"Testing route: {start_coords} -> {end_coords}")
    
    # Check current cache state
    print("\n1. Current cache state:")
    cache = GridCache()
    cache.print_cache_stats()
    
    # Test cache loading
    print("\n2. Testing cache loading...")
    covering_geohashes = cache.find_covering_geohashes(start_coords, end_coords)
    print(f"Covering geohashes: {covering_geohashes}")
    
    if covering_geohashes:
        print("\n3. Attempting to load cached network...")
        cached_network = cache.load_networks_for_route(start_coords, end_coords)
        
        if cached_network:
            print(f"✓ Cached network loaded: {len(cached_network.nodes)} nodes, {len(cached_network.edges)} edges")
            
            # Test connectivity
            import networkx as nx
            if cached_network.is_directed():
                is_connected = nx.is_weakly_connected(cached_network)
                num_components = nx.number_weakly_connected_components(cached_network)
            else:
                is_connected = nx.is_connected(cached_network)
                num_components = nx.number_connected_components(cached_network)
            
            print(f"Connected: {is_connected}, Components: {num_components}")
            
            # Test coverage
            print("\n4. Testing coverage validation...")
            builder = CachedNetworkBuilder()
            coverage_ok = builder._validate_network_coverage(cached_network, start_coords, end_coords)
            print(f"Coverage validation: {coverage_ok}")
            
        else:
            print("✗ No cached network returned")
    else:
        print("No covering geohashes found")
    
    # Test full network building process
    print("\n5. Testing full network building...")
    builder = CachedNetworkBuilder()
    network = builder.build_network(start_coords, end_coords, prefer_cache=True)
    print(f"Final network: {len(network.nodes)} nodes, {len(network.edges)} edges")

if __name__ == "__main__":
    test_cache_behavior() 
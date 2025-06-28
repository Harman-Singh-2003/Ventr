#!/usr/bin/env python3
"""
Crime-Aware Routing System - Main Entry Point

A clean, efficient implementation based on lessons learned.
"""

from core.data_loader import load_crime_data
from core.network_builder import build_network, find_nearest_nodes
from core.distance_utils import calculate_route_distance

def main():
    """
    Demonstrate the clean crime-aware routing system.
    """
    print("Crime-Aware Routing System v2.0")
    print("=" * 40)
    
    # Load crime data
    print("\n📊 Loading crime data...")
    try:
        crimes = load_crime_data()
        print(f"✓ Loaded {len(crimes)} crime incidents")
    except Exception as e:
        print(f"✗ Error loading crime data: {e}")
        return
    
    # Define test route (CN Tower to Union Station)
    start_coords = (43.6426, -79.3871)  # CN Tower
    end_coords = (43.6452, -79.3806)    # Union Station
    
    print(f"\n🗺️ Building network for route:")
    print(f"   Start: CN Tower {start_coords}")
    print(f"   End: Union Station {end_coords}")
    
    # Build network
    try:
        graph = build_network(start_coords, end_coords)
    except Exception as e:
        print(f"✗ Error building network: {e}")
        return
    
    # Find route endpoints
    try:
        start_node, end_node = find_nearest_nodes(graph, start_coords, end_coords)
        print(f"✓ Found nearest nodes: {start_node} -> {end_node}")
    except Exception as e:
        print(f"✗ Error finding nodes: {e}")
        return
    
    # Calculate baseline shortest path
    try:
        import networkx as nx
        shortest_route = nx.shortest_path(graph, start_node, end_node, weight='length')
        shortest_distance = calculate_route_distance(shortest_route, graph)
        
        print(f"\n📏 Baseline shortest path:")
        print(f"   Distance: {shortest_distance:.0f}m")
        print(f"   Nodes: {len(shortest_route)}")
        
    except Exception as e:
        print(f"✗ Error calculating shortest path: {e}")
        return
    
    print("\n✅ System initialized successfully!")
    print("\nNext steps:")
    print("- Implement exponential decay algorithm")
    print("- Add distance constraint optimization")
    print("- Create route visualization")
    print("- Add performance benchmarks")

if __name__ == "__main__":
    main() 
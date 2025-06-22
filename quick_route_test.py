#!/usr/bin/env python3
"""
Quick Toronto Route Test
A super simple script to test basic routing between two hardcoded locations.
"""

import osmnx as ox
import networkx as nx
import folium

def quick_route_test():
    """Test routing between two nearby locations in downtown Toronto."""
    
    print("Quick Toronto Route Test")
    print("=" * 40)
    
    # Small area around downtown Toronto
    north, south, east, west = 43.655, 43.640, -79.375, -79.395
    
    print("Loading small Toronto street network...")
    
    try:
        # Load walking network for small area
        G = ox.graph_from_bbox(
            (north, south, east, west),
            network_type='walk',
            simplify=True
        )
        print(f"✓ Loaded network: {len(G.nodes)} nodes, {len(G.edges)} edges")
        
    except Exception as e:
        print(f"✗ Error loading network: {e}")
        return
    
    # Test coordinates (downtown Toronto)
    start_coords = (43.6502, -79.3832)  # Near King & Bay
    end_coords = (43.6481, -79.3815)    # Near Union Station
    
    print(f"\nFinding route from {start_coords} to {end_coords}")
    
    try:
        # Find nearest nodes
        start_node = ox.nearest_nodes(G, start_coords[1], start_coords[0])
        end_node = ox.nearest_nodes(G, end_coords[1], end_coords[0])
        
        print(f"Start node: {start_node}, End node: {end_node}")
        
        # Calculate shortest path
        route_nodes = nx.shortest_path(G, start_node, end_node, weight='length')
        
        print(f"✓ Route found with {len(route_nodes)} nodes")
        
        # Convert to coordinates
        route_coords = []
        total_distance = 0
        
        for i, node in enumerate(route_nodes):
            node_data = G.nodes[node]
            route_coords.append([node_data['y'], node_data['x']])
            
            # Calculate distance
            if i > 0:
                prev_node = route_nodes[i-1]
                if G.has_edge(prev_node, node):
                    edge_data = G.edges[prev_node, node, 0]
                    total_distance += edge_data.get('length', 0)
        
        distance_km = total_distance / 1000
        print(f"Distance: {distance_km:.2f} km")
        print(f"Walking time: ~{distance_km * 12:.0f} minutes")
        
        # Create map
        center_lat = (start_coords[0] + end_coords[0]) / 2
        center_lon = (start_coords[1] + end_coords[1]) / 2
        
        route_map = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=16,
            tiles='OpenStreetMap'
        )
        
        # Add route line
        folium.PolyLine(
            locations=route_coords,
            color='blue',
            weight=4,
            opacity=0.8,
            popup=f"Distance: {distance_km:.2f} km"
        ).add_to(route_map)
        
        # Add start marker
        folium.Marker(
            location=list(start_coords),
            popup="Start: King & Bay",
            icon=folium.Icon(color='green', icon='play')
        ).add_to(route_map)
        
        # Add end marker
        folium.Marker(
            location=list(end_coords),
            popup="End: Union Station",
            icon=folium.Icon(color='red', icon='stop')
        ).add_to(route_map)
        
        # Save map
        map_filename = "quick_route_test.html"
        route_map.save(map_filename)
        print(f"✓ Map saved as: {map_filename}")
        
        print("\n✓ Quick route test completed successfully!")
        
    except Exception as e:
        print(f"✗ Error finding route: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    quick_route_test() 
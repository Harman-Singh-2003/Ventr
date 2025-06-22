#!/usr/bin/env python3
"""
Simple Toronto Walking Route Generator
A barebones script to test basic routing capabilities between two locations in Toronto.
"""

import osmnx as ox
import networkx as nx
import folium
from geopy.geocoders import Nominatim

class SimpleTorontoRouter:
    def __init__(self):
        """Initialize the router with Toronto's street network."""
        self.graph = None
        self.geocoder = Nominatim(user_agent="toronto_router")
        
    def load_toronto_network(self):
        """Load Toronto's walking network from OpenStreetMap."""
        print("Loading Toronto street network...")
        
        # Define Toronto downtown area bounds
        north, south, east, west = 43.7, 43.6, -79.3, -79.5
        
        try:
            # Get walking network
            self.graph = ox.graph_from_bbox(
                (north, south, east, west),
                network_type='walk',
                simplify=True
            )
            print(f"Loaded network with {len(self.graph.nodes)} nodes and {len(self.graph.edges)} edges")
            
        except Exception as e:
            print(f"Error loading network: {e}")
            return False
            
        return True
    
    def geocode_address(self, address):
        """Convert address to coordinates."""
        try:
            # Add Toronto to address if not specified
            if "toronto" not in address.lower():
                address += ", Toronto, ON, Canada"
                
            location = self.geocoder.geocode(address)
            if location:
                return (float(location.latitude), float(location.longitude))
            else:
                print(f"Could not geocode address: {address}")
                return None
                
        except Exception as e:
            print(f"Geocoding error: {e}")
            return None
    
    def find_route(self, start_coords, end_coords):
        """Find the shortest walking route between two coordinate points."""
        if not self.graph:
            print("Network not loaded. Call load_toronto_network() first.")
            return None
            
        try:
            # Find nearest nodes
            start_node = ox.nearest_nodes(self.graph, start_coords[1], start_coords[0])
            end_node = ox.nearest_nodes(self.graph, end_coords[1], end_coords[0])
            
            # Calculate shortest path
            route_nodes = nx.shortest_path(self.graph, start_node, end_node, weight='length')
            
            # Convert to coordinates
            route_coords = []
            total_distance = 0
            
            for i, node in enumerate(route_nodes):
                node_data = self.graph.nodes[node]
                route_coords.append([node_data['y'], node_data['x']])
                
                # Calculate distance
                if i > 0:
                    prev_node = route_nodes[i-1]
                    if self.graph.has_edge(prev_node, node):
                        edge_data = self.graph.edges[prev_node, node, 0]
                        total_distance += edge_data.get('length', 0)
            
            return {
                'coordinates': route_coords,
                'distance_meters': total_distance,
                'distance_km': total_distance / 1000,
                'nodes': route_nodes
            }
            
        except Exception as e:
            print(f"Error finding route: {e}")
            return None
    
    def create_route_map(self, route_info, start_coords, end_coords, start_name="Start", end_name="End"):
        """Create a Folium map showing the route."""
        if not route_info:
            return None
            
        # Create map centered on route
        center_lat = (start_coords[0] + end_coords[0]) / 2
        center_lon = (start_coords[1] + end_coords[1]) / 2
        
        route_map = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=14,
            tiles='OpenStreetMap'
        )
        
        # Add route line
        folium.PolyLine(
            locations=route_info['coordinates'],
            color='blue',
            weight=4,
            opacity=0.8,
            popup=f"Distance: {route_info['distance_km']:.2f} km"
        ).add_to(route_map)
        
        # Add start marker
        folium.Marker(
            location=[start_coords[0], start_coords[1]],
            popup=f"Start: {start_name}",
            icon=folium.Icon(color='green', icon='play')
        ).add_to(route_map)
        
        # Add end marker
        folium.Marker(
            location=[end_coords[0], end_coords[1]],
            popup=f"End: {end_name}",
            icon=folium.Icon(color='red', icon='stop')
        ).add_to(route_map)
        
        return route_map

def test_simple_routing():
    """Test the simple routing with some Toronto locations."""
    router = SimpleTorontoRouter()
    
    # Load the network
    if not router.load_toronto_network():
        print("Failed to load network")
        return
    
    print("\n" + "="*50)
    print("TORONTO WALKING ROUTE TEST")
    print("="*50)
    
    # Test locations
    test_routes = [
        {
            'start': 'CN Tower, Toronto',
            'end': 'Union Station, Toronto',
            'start_coords': (43.6426, -79.3871),  # CN Tower
            'end_coords': (43.6452, -79.3806)     # Union Station
        },
        {
            'start': 'Toronto City Hall',
            'end': 'Distillery District, Toronto',
            'start_coords': (43.6534, -79.3839),  # City Hall
            'end_coords': (43.6503, -79.3592)     # Distillery District
        }
    ]
    
    for i, test in enumerate(test_routes, 1):
        print(f"\nRoute {i}: {test['start']} → {test['end']}")
        print("-" * 40)
        
        # Find route
        route_info = router.find_route(test['start_coords'], test['end_coords'])
        
        if route_info:
            print(f"✓ Route found!")
            print(f"  Distance: {route_info['distance_km']:.2f} km")
            print(f"  Walking time: ~{route_info['distance_km'] * 12:.0f} minutes")
            
            # Create map
            route_map = router.create_route_map(
                route_info, 
                test['start_coords'], 
                test['end_coords'],
                test['start'],
                test['end']
            )
            
            # Save map
            if route_map:
                map_filename = f"route_test_{i}.html"
                route_map.save(map_filename)
                print(f"  Map saved as: {map_filename}")
            else:
                print("  Could not create map")
            
        else:
            print("✗ Route not found")

def interactive_routing():
    """Interactive routing function for custom locations."""
    router = SimpleTorontoRouter()
    
    print("Loading Toronto street network...")
    if not router.load_toronto_network():
        print("Failed to load network")
        return
    
    print("\n" + "="*50)
    print("INTERACTIVE TORONTO ROUTING")
    print("="*50)
    print("Enter two locations in Toronto to get walking directions.")
    print("You can use addresses or landmarks.")
    print("Type 'quit' to exit.\n")
    
    while True:
        try:
            start_input = input("Start location: ").strip()
            if start_input.lower() == 'quit':
                break
                
            end_input = input("End location: ").strip()
            if end_input.lower() == 'quit':
                break
            
            print("\nGeocoding locations...")
            
            # Geocode addresses
            start_coords = router.geocode_address(start_input)
            end_coords = router.geocode_address(end_input)
            
            if not start_coords or not end_coords:
                print("Could not find one or both locations. Please try again.\n")
                continue
            
            print(f"Start: {start_coords}")
            print(f"End: {end_coords}")
            
            # Find route
            print("Finding route...")
            route_info = router.find_route(start_coords, end_coords)
            
            if route_info:
                print(f"\n✓ Route found!")
                print(f"  Distance: {route_info['distance_km']:.2f} km")
                print(f"  Estimated walking time: {route_info['distance_km'] * 12:.0f} minutes")
                
                # Create and save map
                route_map = router.create_route_map(
                    route_info, start_coords, end_coords, 
                    start_input, end_input
                )
                
                if route_map:
                    map_filename = "custom_route.html"
                    route_map.save(map_filename)
                    print(f"  Interactive map saved as: {map_filename}")
                else:
                    print("  Could not create map")
                
            else:
                print("✗ Could not find a route between these locations.")
            
            print("\n" + "-"*50 + "\n")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    print("Toronto Simple Routing Test")
    print("1. Run predefined test routes")
    print("2. Interactive custom routing")
    
    choice = input("\nChoose option (1 or 2): ").strip()
    
    if choice == "1":
        test_simple_routing()
    elif choice == "2":
        interactive_routing()
    else:
        print("Running default test...")
        test_simple_routing() 
#!/usr/bin/env python3
"""
Minimal Toronto Route Test with Crime Avoidance
Super basic routing test using a tiny area with crime data integration.
"""

import osmnx as ox
import networkx as nx
import folium
import json
import math
from collections import defaultdict

def load_crime_data(geojson_file):
    """Load crime data from GeoJSON file."""
    print("Loading crime data...")
    try:
        with open(geojson_file, 'r') as f:
            crime_data = json.load(f)
        
        crimes = []
        for feature in crime_data['features']:
            if feature['geometry']['type'] == 'Point':
                coords = feature['geometry']['coordinates']
                # GeoJSON uses [longitude, latitude] format
                lon, lat = coords[0], coords[1]
                
                # Filter for valid Toronto coordinates
                if 43.5 <= lat <= 44.0 and -80.0 <= lon <= -79.0:
                    crimes.append({
                        'lat': lat,
                        'lon': lon,
                        'coords': (lat, lon)
                    })
        
        print(f"✓ Loaded {len(crimes)} valid crime incidents")
        return crimes
        
    except Exception as e:
        print(f"✗ Error loading crime data: {e}")
        return []

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points using Haversine formula."""
    R = 6371000  # Earth's radius in meters
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_lat/2) * math.sin(delta_lat/2) + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * 
         math.sin(delta_lon/2) * math.sin(delta_lon/2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

def add_crime_weights_to_graph(G, crimes, influence_radius=100):
    """Add crime-based weights to graph edges."""
    print(f"Adding crime weights to {len(G.edges)} edges...")
    
    # Method 1: Distance-based penalty
    for u, v, key in G.edges(keys=True):
        edge_data = G.edges[u, v, key]
        
        # Get edge coordinates (midpoint)
        node_u = G.nodes[u]
        node_v = G.nodes[v]
        edge_lat = (node_u['y'] + node_v['y']) / 2
        edge_lon = (node_u['x'] + node_v['x']) / 2
        
        # Calculate crime risk for this edge
        crime_penalty = 0
        nearby_crimes = 0
        
        for crime in crimes:
            distance = calculate_distance(edge_lat, edge_lon, crime['lat'], crime['lon'])
            
            if distance <= influence_radius:
                # Exponential decay penalty based on distance
                penalty = math.exp(-distance / (influence_radius / 3))
                crime_penalty += penalty
                nearby_crimes += 1
        
        # Store original length
        original_length = edge_data.get('length', 50)  # Default 50m if no length
        
        # Calculate safety multiplier (1.0 = safe, higher = more dangerous)
        safety_multiplier = 1.0 + (crime_penalty * 2.0)  # Max 3x penalty
        
        # Store crime-aware weights
        edge_data['crime_penalty'] = crime_penalty
        edge_data['nearby_crimes'] = nearby_crimes
        edge_data['safety_multiplier'] = safety_multiplier
        edge_data['safe_length'] = original_length * safety_multiplier
    
    print(f"✓ Crime weights added (influence radius: {influence_radius}m)")

def create_crime_density_map(crimes, bounds):
    """Create a simple crime density grid for visualization."""
    # Create a simple grid-based density map
    grid_size = 20  # 20x20 grid
    lat_min, lat_max = bounds['lat_min'], bounds['lat_max']
    lon_min, lon_max = bounds['lon_min'], bounds['lon_max']
    
    lat_step = (lat_max - lat_min) / grid_size
    lon_step = (lon_max - lon_min) / grid_size
    
    density_grid = []
    
    for i in range(grid_size):
        for j in range(grid_size):
            grid_lat = lat_min + i * lat_step + lat_step/2
            grid_lon = lon_min + j * lon_step + lon_step/2
            
            # Count crimes within this grid cell
            crime_count = 0
            for crime in crimes:
                if (grid_lat - lat_step/2 <= crime['lat'] <= grid_lat + lat_step/2 and
                    grid_lon - lon_step/2 <= crime['lon'] <= grid_lon + lon_step/2):
                    crime_count += 1
            
            if crime_count > 0:
                density_grid.append({
                    'lat': grid_lat,
                    'lon': grid_lon,
                    'count': crime_count
                })
    
    return density_grid

def minimal_route_test_with_crimes():
    """Test basic routing with crime avoidance in a very small area."""
    
    print("Minimal Toronto Route Test with Crime Avoidance")
    print("=" * 50)
    
    # Load crime data
    crimes = load_crime_data('Assault_Open_Data_-331273077107818534.geojson')
    if not crimes:
        print("No crime data available, running basic routing...")
        return minimal_route_test()
    
    # Very small area - just a few blocks
    center_lat, center_lon = 43.6505, -79.3810
    distance = 500  # Increased to 500 meters for more interesting routes
    
    print(f"\nLoading street network around {center_lat}, {center_lon}...")
    
    try:
        # Load network
        G = ox.graph_from_point(
            (center_lat, center_lon),
            dist=distance,
            network_type='walk',
            simplify=True
        )
        print(f"✓ Loaded network: {len(G.nodes)} nodes, {len(G.edges)} edges")
        
        if len(G.nodes) < 2:
            print("✗ Network too small, try a larger area")
            return
            
    except Exception as e:
        print(f"✗ Error loading network: {e}")
        return
    
    # Filter crimes to network area
    network_bounds = {
        'lat_min': min(G.nodes[node]['y'] for node in G.nodes()),
        'lat_max': max(G.nodes[node]['y'] for node in G.nodes()),
        'lon_min': min(G.nodes[node]['x'] for node in G.nodes()),
        'lon_max': max(G.nodes[node]['x'] for node in G.nodes())
    }
    
    local_crimes = [
        crime for crime in crimes
        if (network_bounds['lat_min'] <= crime['lat'] <= network_bounds['lat_max'] and
            network_bounds['lon_min'] <= crime['lon'] <= network_bounds['lon_max'])
    ]
    
    print(f"Found {len(local_crimes)} crimes in network area")
    
    # Add crime weights to graph
    if local_crimes:
        add_crime_weights_to_graph(G, local_crimes, influence_radius=150)
    
    # Get nodes for routing
    nodes = list(G.nodes())
    if len(nodes) < 2:
        print("✗ Not enough nodes for routing")
        return
    
    # Use nodes that are reasonably far apart
    start_node = nodes[0]
    end_node = nodes[len(nodes)//2]  # Middle node for better distance
    
    start_coords = (G.nodes[start_node]['y'], G.nodes[start_node]['x'])
    end_coords = (G.nodes[end_node]['y'], G.nodes[end_node]['x'])
    
    print(f"\nRouting from node {start_node} to node {end_node}")
    print(f"Start: {start_coords}")
    print(f"End: {end_coords}")
    
    try:
        # Check if path exists
        if not nx.has_path(G, start_node, end_node):
            print("✗ No path exists between these nodes")
            return
        
        # Calculate routes using different methods
        routes = {}
        
        # Method 1: Shortest path (distance only)
        route_shortest = nx.shortest_path(G, start_node, end_node, weight='length')
        routes['shortest'] = {
            'nodes': route_shortest,
            'color': 'red',
            'name': 'Shortest Route'
        }
        
        # Method 2: Safest path (crime-weighted)
        if local_crimes:
            route_safest = nx.shortest_path(G, start_node, end_node, weight='safe_length')
            routes['safest'] = {
                'nodes': route_safest,
                'color': 'green',
                'name': 'Safest Route'
            }
        
        # Calculate route statistics
        for route_type, route_info in routes.items():
            route_nodes = route_info['nodes']
            route_coords = []
            total_distance = 0
            total_crime_penalty = 0
            
            for i, node in enumerate(route_nodes):
                node_data = G.nodes[node]
                route_coords.append([node_data['y'], node_data['x']])
                
                if i > 0:
                    prev_node = route_nodes[i-1]
                    if G.has_edge(prev_node, node):
                        edge_data = G.edges[prev_node, node, 0]
                        total_distance += edge_data.get('length', 0)
                        total_crime_penalty += edge_data.get('crime_penalty', 0)
            
            route_info['coordinates'] = route_coords
            route_info['distance'] = total_distance
            route_info['crime_penalty'] = total_crime_penalty
            
            print(f"\n{route_info['name']}:")
            print(f"  Distance: {total_distance:.0f} meters")
            print(f"  Crime penalty: {total_crime_penalty:.2f}")
            print(f"  Walking time: ~{total_distance / 80:.1f} minutes")
        
        # Create comparison map
        route_map = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=17,
            tiles='OpenStreetMap'
        )
        
        # Add routes
        for route_type, route_info in routes.items():
            folium.PolyLine(
                locations=route_info['coordinates'],
                color=route_info['color'],
                weight=4,
                opacity=0.8,
                popup=f"{route_info['name']}: {route_info['distance']:.0f}m"
            ).add_to(route_map)
        
        # Add start/end markers
        folium.Marker(
            location=list(start_coords),
            popup=f"Start (Node {start_node})",
            icon=folium.Icon(color='blue', icon='play')
        ).add_to(route_map)
        
        folium.Marker(
            location=list(end_coords),
            popup=f"End (Node {end_node})",
            icon=folium.Icon(color='blue', icon='stop')
        ).add_to(route_map)
        
        # Add crime locations
        if local_crimes:
            for i, crime in enumerate(local_crimes):
                folium.CircleMarker(
                    location=[crime['lat'], crime['lon']],
                    radius=5,
                    color='darkred',
                    fillColor='red',
                    fillOpacity=0.6,
                    popup=f"Crime incident {i+1}"
                ).add_to(route_map)
        
        # Add crime density heatmap
        if local_crimes:
            density_grid = create_crime_density_map(local_crimes, network_bounds)
            for cell in density_grid:
                folium.CircleMarker(
                    location=[cell['lat'], cell['lon']],
                    radius=cell['count'] * 3,
                    color='orange',
                    fillColor='orange',
                    fillOpacity=0.3,
                    popup=f"Crime density: {cell['count']}"
                ).add_to(route_map)
        
        # Note: Legend colors are explained in the popup text and terminal output
        
        # Save map
        map_filename = "crime_aware_route_test.html"
        route_map.save(map_filename)
        print(f"\n✓ Crime-aware map saved as: {map_filename}")
        
        # Show route comparison
        if len(routes) > 1:
            shortest_dist = routes['shortest']['distance']
            safest_dist = routes['safest']['distance']
            shortest_penalty = routes['shortest']['crime_penalty']
            safest_penalty = routes['safest']['crime_penalty']
            
            print(f"\n📊 Route Comparison:")
            print(f"  Distance difference: {safest_dist - shortest_dist:.0f}m ({((safest_dist/shortest_dist-1)*100):+.1f}%)")
            print(f"  Crime penalty reduction: {shortest_penalty - safest_penalty:.2f} ({((1-safest_penalty/shortest_penalty)*100 if shortest_penalty > 0 else 0):.1f}%)")
        
        print(f"\n✓ Crime-aware routing test completed successfully!")
        print(f"Open {map_filename} in your browser to see the route comparison")
        
    except Exception as e:
        print(f"✗ Error finding route: {e}")
        import traceback
        traceback.print_exc()

def minimal_route_test():
    """Original test basic routing in a very small area."""
    
    print("Minimal Toronto Route Test")
    print("=" * 30)
    
    # Very small area - just a few blocks
    center_lat, center_lon = 43.6505, -79.3810
    distance = 300  # 300 meters radius
    
    print(f"Loading tiny network around {center_lat}, {center_lon}...")
    
    try:
        # Load very small network
        G = ox.graph_from_point(
            (center_lat, center_lon),
            dist=distance,
            network_type='walk',
            simplify=True
        )
        print(f"✓ Loaded network: {len(G.nodes)} nodes, {len(G.edges)} edges")
        
        if len(G.nodes) < 2:
            print("✗ Network too small, try a larger area")
            return
            
    except Exception as e:
        print(f"✗ Error loading network: {e}")
        return
    
    # Get some nodes from the network for testing
    nodes = list(G.nodes())
    if len(nodes) < 2:
        print("✗ Not enough nodes for routing")
        return
    
    # Use first and last nodes for simplicity
    start_node = nodes[0]
    end_node = nodes[-1]
    
    start_coords = (G.nodes[start_node]['y'], G.nodes[start_node]['x'])
    end_coords = (G.nodes[end_node]['y'], G.nodes[end_node]['x'])
    
    print(f"\nRouting from node {start_node} to node {end_node}")
    print(f"Start: {start_coords}")
    print(f"End: {end_coords}")
    
    try:
        # Check if path exists
        if not nx.has_path(G, start_node, end_node):
            print("✗ No path exists between these nodes")
            return
            
        # Calculate shortest path
        route_nodes = nx.shortest_path(G, start_node, end_node, weight='length')
        
        print(f"✓ Route found with {len(route_nodes)} nodes")
        
        # Convert to coordinates and calculate distance
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
        
        distance_m = total_distance
        print(f"Distance: {distance_m:.0f} meters")
        print(f"Walking time: ~{distance_m / 80:.1f} minutes")  # ~5 km/h walking speed
        
        # Create simple map
        route_map = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=18,
            tiles='OpenStreetMap'
        )
        
        # Add route line
        folium.PolyLine(
            locations=route_coords,
            color='blue',
            weight=5,
            opacity=0.8,
            popup=f"Route: {distance_m:.0f}m"
        ).add_to(route_map)
        
        # Add start marker
        folium.Marker(
            location=list(start_coords),
            popup=f"Start (Node {start_node})",
            icon=folium.Icon(color='green', icon='play')
        ).add_to(route_map)
        
        # Add end marker
        folium.Marker(
            location=list(end_coords),
            popup=f"End (Node {end_node})",
            icon=folium.Icon(color='red', icon='stop')
        ).add_to(route_map)
        
        # Add all network nodes as small markers
        for node in G.nodes():
            node_data = G.nodes[node]
            folium.CircleMarker(
                location=[node_data['y'], node_data['x']],
                radius=2,
                color='gray',
                popup=f"Node {node}"
            ).add_to(route_map)
        
        # Save map
        map_filename = "minimal_route_test.html"
        route_map.save(map_filename)
        print(f"✓ Map saved as: {map_filename}")
        
        print("\n✓ Minimal route test completed successfully!")
        print(f"Open {map_filename} in your browser to see the route")
        
    except Exception as e:
        print(f"✗ Error finding route: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Toronto Route Test Options:")
    print("1. Basic routing test")
    print("2. Crime-aware routing test")
    
    choice = input("\nChoose option (1 or 2, default=2): ").strip()
    
    if choice == "1":
        minimal_route_test()
    else:
        minimal_route_test_with_crimes() 
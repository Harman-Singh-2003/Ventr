#!/usr/bin/env python3
"""
Crime-Aware Routing Methods Demonstration
Shows different approaches to avoid crime areas when routing.
"""

import osmnx as ox
import networkx as nx
import folium
import json
import math

def load_crime_data():
    """Load and filter crime data."""
    try:
        with open('Assault_Open_Data_-331273077107818534.geojson', 'r') as f:
            crime_data = json.load(f)
        
        crimes = []
        for feature in crime_data['features']:
            if feature['geometry']['type'] == 'Point':
                coords = feature['geometry']['coordinates']
                lon, lat = coords[0], coords[1]
                
                if 43.5 <= lat <= 44.0 and -80.0 <= lon <= -79.0:
                    crimes.append({'lat': lat, 'lon': lon})
        
        return crimes
    except Exception as e:
        print(f"Error loading crime data: {e}")
        return []

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points."""
    R = 6371000  # Earth's radius in meters
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat, delta_lon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    
    a = (math.sin(delta_lat/2)**2 + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

def method_1_exponential_decay(G, crimes, influence_radius=100):
    """Method 1: Exponential decay penalty based on distance to crimes."""
    print("Applying Method 1: Exponential Decay Penalty")
    
    for u, v, key in G.edges(keys=True):
        edge_data = G.edges[u, v, key]
        
        # Edge midpoint
        node_u, node_v = G.nodes[u], G.nodes[v]
        edge_lat = (node_u['y'] + node_v['y']) / 2
        edge_lon = (node_u['x'] + node_v['x']) / 2
        
        # Calculate penalty
        penalty = 0
        for crime in crimes:
            distance = haversine_distance(edge_lat, edge_lon, crime['lat'], crime['lon'])
            if distance <= influence_radius:
                penalty += math.exp(-distance / (influence_radius / 3))
        
        original_length = edge_data.get('length', 50)
        edge_data['method1_weight'] = original_length * (1.0 + penalty * 2.0)

def method_2_linear_penalty(G, crimes, influence_radius=100):
    """Method 2: Linear penalty that decreases with distance."""
    print("Applying Method 2: Linear Distance Penalty")
    
    for u, v, key in G.edges(keys=True):
        edge_data = G.edges[u, v, key]
        
        node_u, node_v = G.nodes[u], G.nodes[v]
        edge_lat = (node_u['y'] + node_v['y']) / 2
        edge_lon = (node_u['x'] + node_v['x']) / 2
        
        penalty = 0
        for crime in crimes:
            distance = haversine_distance(edge_lat, edge_lon, crime['lat'], crime['lon'])
            if distance <= influence_radius:
                penalty += (influence_radius - distance) / influence_radius
        
        original_length = edge_data.get('length', 50)
        edge_data['method2_weight'] = original_length * (1.0 + penalty * 1.5)

def method_3_crime_density(G, crimes, grid_size=50):
    """Method 3: Grid-based crime density penalty."""
    print("Applying Method 3: Crime Density Grid")
    
    # Create density grid
    bounds = {
        'lat_min': min(G.nodes[node]['y'] for node in G.nodes()),
        'lat_max': max(G.nodes[node]['y'] for node in G.nodes()),
        'lon_min': min(G.nodes[node]['x'] for node in G.nodes()),
        'lon_max': max(G.nodes[node]['x'] for node in G.nodes())
    }
    
    lat_step = (bounds['lat_max'] - bounds['lat_min']) / grid_size
    lon_step = (bounds['lon_max'] - bounds['lon_min']) / grid_size
    
    # Build density map
    density_map = {}
    for i in range(grid_size):
        for j in range(grid_size):
            grid_lat = bounds['lat_min'] + i * lat_step
            grid_lon = bounds['lon_min'] + j * lon_step
            
            count = sum(1 for crime in crimes 
                       if grid_lat <= crime['lat'] < grid_lat + lat_step and
                          grid_lon <= crime['lon'] < grid_lon + lon_step)
            
            if count > 0:
                density_map[(i, j)] = count
    
    # Apply density penalty to edges
    for u, v, key in G.edges(keys=True):
        edge_data = G.edges[u, v, key]
        
        node_u, node_v = G.nodes[u], G.nodes[v]
        edge_lat = (node_u['y'] + node_v['y']) / 2
        edge_lon = (node_u['x'] + node_v['x']) / 2
        
        # Find grid cell
        i = int((edge_lat - bounds['lat_min']) / lat_step)
        j = int((edge_lon - bounds['lon_min']) / lon_step)
        i = max(0, min(grid_size-1, i))
        j = max(0, min(grid_size-1, j))
        
        density = density_map.get((i, j), 0)
        penalty_multiplier = 1.0 + (density * 0.3)  # 30% penalty per crime in cell
        
        original_length = edge_data.get('length', 50)
        edge_data['method3_weight'] = original_length * penalty_multiplier

def method_4_threshold_avoidance(G, crimes, danger_radius=75):
    """Method 4: Binary avoidance - high penalty within danger radius."""
    print("Applying Method 4: Threshold-based Avoidance")
    
    for u, v, key in G.edges(keys=True):
        edge_data = G.edges[u, v, key]
        
        node_u, node_v = G.nodes[u], G.nodes[v]
        edge_lat = (node_u['y'] + node_v['y']) / 2
        edge_lon = (node_u['x'] + node_v['x']) / 2
        
        is_dangerous = False
        for crime in crimes:
            distance = haversine_distance(edge_lat, edge_lon, crime['lat'], crime['lon'])
            if distance <= danger_radius:
                is_dangerous = True
                break
        
        original_length = edge_data.get('length', 50)
        if is_dangerous:
            edge_data['method4_weight'] = original_length * 5.0  # 5x penalty
        else:
            edge_data['method4_weight'] = original_length

def method_5_raw_data_weighted(G, crimes, max_influence=200):
    """Method 5: Raw data approach - direct weighting by all crime distances."""
    print("Applying Method 5: Raw Data Weighted (No Clustering)")
    
    for u, v, key in G.edges(keys=True):
        edge_data = G.edges[u, v, key]
        
        node_u, node_v = G.nodes[u], G.nodes[v]
        edge_lat = (node_u['y'] + node_v['y']) / 2
        edge_lon = (node_u['x'] + node_v['x']) / 2
        
        # Calculate cumulative risk from ALL crimes (no clustering)
        total_risk = 0
        crime_count = 0
        
        for crime in crimes:
            distance = haversine_distance(edge_lat, edge_lon, crime['lat'], crime['lon'])
            
            if distance <= max_influence:
                # Inverse distance weighting - closer crimes have more influence
                risk_contribution = 1.0 / (1.0 + distance / 50)  # 50m normalization
                total_risk += risk_contribution
                crime_count += 1
        
        original_length = edge_data.get('length', 50)
        
        # Scale penalty based on cumulative risk
        # More crimes nearby = higher penalty
        risk_multiplier = 1.0 + (total_risk * 0.5)  # 50% penalty per risk unit
        
        edge_data['method5_weight'] = original_length * risk_multiplier
        edge_data['crime_count'] = crime_count
        edge_data['total_risk'] = total_risk

def compare_routing_methods():
    """Compare different crime avoidance routing methods."""
    print("Crime-Aware Routing Methods Comparison")
    print("=" * 45)
    
    # Load data
    crimes = load_crime_data()
    if not crimes:
        print("No crime data available")
        return
    
    print(f"Loaded {len(crimes)} crime incidents")
    
    # Load network
    center_lat, center_lon = 43.6505, -79.3810
    distance = 400
    
    print(f"Loading network around {center_lat}, {center_lon}...")
    
    try:
        G = ox.graph_from_point(
            (center_lat, center_lon),
            dist=distance,
            network_type='walk',
            simplify=True
        )
        print(f"✓ Network: {len(G.nodes)} nodes, {len(G.edges)} edges")
    except Exception as e:
        print(f"Error loading network: {e}")
        return
    
    # Filter crimes to network area
    bounds = {
        'lat_min': min(G.nodes[node]['y'] for node in G.nodes()),
        'lat_max': max(G.nodes[node]['y'] for node in G.nodes()),
        'lon_min': min(G.nodes[node]['x'] for node in G.nodes()),
        'lon_max': max(G.nodes[node]['x'] for node in G.nodes())
    }
    
    local_crimes = [
        crime for crime in crimes
        if (bounds['lat_min'] <= crime['lat'] <= bounds['lat_max'] and
            bounds['lon_min'] <= crime['lon'] <= bounds['lon_max'])
    ]
    
    print(f"Found {len(local_crimes)} crimes in network area")
    
    if not local_crimes:
        print("No crimes in network area - using basic routing")
        return
    
    # Apply different methods
    method_1_exponential_decay(G, local_crimes)
    method_2_linear_penalty(G, local_crimes)
    method_3_crime_density(G, local_crimes)
    method_4_threshold_avoidance(G, local_crimes)
    method_5_raw_data_weighted(G, local_crimes)
    
    # Select start and end nodes
    nodes = list(G.nodes())
    start_node = nodes[0]
    end_node = nodes[len(nodes)//3]  # Use 1/3 through the list
    
    start_coords = (G.nodes[start_node]['y'], G.nodes[start_node]['x'])
    end_coords = (G.nodes[end_node]['y'], G.nodes[end_node]['x'])
    
    print(f"\nRouting from {start_coords} to {end_coords}")
    
    # Calculate routes using different methods
    methods = {
        'shortest': {'weight': 'length', 'color': 'blue', 'name': 'Shortest Path'},
        'method1': {'weight': 'method1_weight', 'color': 'red', 'name': 'Exponential Decay'},
        'method2': {'weight': 'method2_weight', 'color': 'green', 'name': 'Linear Penalty'},
        'method3': {'weight': 'method3_weight', 'color': 'purple', 'name': 'Density Grid'},
        'method4': {'weight': 'method4_weight', 'color': 'orange', 'name': 'Threshold Avoidance'},
        'method5': {'weight': 'method5_weight', 'color': 'darkgreen', 'name': 'Raw Data Weighted'}
    }
    
    routes = {}
    
    for method_name, method_info in methods.items():
        try:
            route_nodes = nx.shortest_path(G, start_node, end_node, weight=method_info['weight'])
            
            # Calculate route stats
            route_coords = []
            total_distance = 0
            crimes_nearby = 0
            total_crime_exposure = 0
            total_risk_score = 0
            
            for i, node in enumerate(route_nodes):
                node_data = G.nodes[node]
                route_coords.append([node_data['y'], node_data['x']])
                
                if i > 0:
                    prev_node = route_nodes[i-1]
                    if G.has_edge(prev_node, node):
                        edge_data = G.edges[prev_node, node, 0]
                        total_distance += edge_data.get('length', 0)
                        
                        # Count nearby crimes for this edge
                        edge_lat = (G.nodes[prev_node]['y'] + node_data['y']) / 2
                        edge_lon = (G.nodes[prev_node]['x'] + node_data['x']) / 2
                        
                        for crime in local_crimes:
                            if haversine_distance(edge_lat, edge_lon, crime['lat'], crime['lon']) <= 100:
                                crimes_nearby += 1
                                break
                        
                        # Additional stats for raw data method
                        if method_name == 'method5':
                            total_crime_exposure += edge_data.get('crime_count', 0)
                            total_risk_score += edge_data.get('total_risk', 0)
            
            routes[method_name] = {
                'nodes': route_nodes,
                'coordinates': route_coords,
                'distance': total_distance,
                'crimes_nearby': crimes_nearby,
                'crime_exposure': total_crime_exposure,
                'risk_score': total_risk_score,
                'color': method_info['color'],
                'name': method_info['name']
            }
            
            print(f"\n{method_info['name']}:")
            print(f"  Distance: {total_distance:.0f}m")
            print(f"  Edges near crimes: {crimes_nearby}")
            if method_name == 'method5':
                print(f"  Total crime exposure: {total_crime_exposure:.0f}")
                print(f"  Risk score: {total_risk_score:.2f}")
            
        except Exception as e:
            print(f"Error calculating {method_name}: {e}")
    
    # Create comparison map
    comparison_map = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=17,
        tiles='OpenStreetMap'
    )
    
    # Add routes
    for method_name, route_info in routes.items():
        folium.PolyLine(
            locations=route_info['coordinates'],
            color=route_info['color'],
            weight=3,
            opacity=0.7,
            popup=f"{route_info['name']}: {route_info['distance']:.0f}m"
        ).add_to(comparison_map)
    
    # Add markers
    folium.Marker(
        location=list(start_coords),
        popup="Start",
        icon=folium.Icon(color='darkblue', icon='play')
    ).add_to(comparison_map)
    
    folium.Marker(
        location=list(end_coords),
        popup="End",
        icon=folium.Icon(color='darkblue', icon='stop')
    ).add_to(comparison_map)
    
    # Add crime locations
    for i, crime in enumerate(local_crimes):
        folium.CircleMarker(
            location=[crime['lat'], crime['lon']],
            radius=3,
            color='darkred',
            fillColor='red',
            fillOpacity=0.6,
            popup=f"Crime {i+1}"
        ).add_to(comparison_map)
    
    # Save map
    map_filename = "routing_methods_comparison.html"
    comparison_map.save(map_filename)
    print(f"\n✓ Comparison map saved as: {map_filename}")
    
    # Print summary
    if len(routes) > 1:
        print(f"\n📊 Methods Comparison Summary:")
        shortest_dist = routes['shortest']['distance']
        
        for method_name, route_info in routes.items():
            if method_name != 'shortest':
                dist_diff = route_info['distance'] - shortest_dist
                dist_pct = (dist_diff / shortest_dist) * 100
                print(f"  {route_info['name']}: +{dist_diff:.0f}m ({dist_pct:+.1f}%), {route_info['crimes_nearby']} danger edges")
    
    print(f"\n✓ All methods tested successfully!")

if __name__ == "__main__":
    compare_routing_methods() 
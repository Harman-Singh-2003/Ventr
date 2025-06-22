#!/usr/bin/env python3
"""
Comprehensive Routing Algorithm Tests
Tests all crime-aware routing methods between multiple Toronto locations
with detailed path annotations showing method, crime exposure, and distance.
"""

import osmnx as ox
import networkx as nx
import folium
import json
import math
from datetime import datetime

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

def apply_all_routing_methods(G, crimes):
    """Apply all routing methods to the graph."""
    print(f"Applying all routing methods to {len(G.edges)} edges...")
    
    # Method 1: Exponential Decay
    for u, v, key in G.edges(keys=True):
        edge_data = G.edges[u, v, key]
        node_u, node_v = G.nodes[u], G.nodes[v]
        edge_lat = (node_u['y'] + node_v['y']) / 2
        edge_lon = (node_u['x'] + node_v['x']) / 2
        
        penalty = 0
        crimes_nearby = 0
        closest_distance = float('inf')
        
        for crime in crimes:
            distance = haversine_distance(edge_lat, edge_lon, crime['lat'], crime['lon'])
            if distance <= 150:  # 150m influence radius
                penalty += math.exp(-distance / 50)
                crimes_nearby += 1
                closest_distance = min(closest_distance, distance)
        
        original_length = edge_data.get('length', 50)
        edge_data['method1_weight'] = original_length * (1.0 + penalty * 2.0)
        edge_data['method1_crimes'] = crimes_nearby
        edge_data['method1_closest'] = closest_distance if closest_distance != float('inf') else None
    
    # Method 2: Linear Penalty
    for u, v, key in G.edges(keys=True):
        edge_data = G.edges[u, v, key]
        node_u, node_v = G.nodes[u], G.nodes[v]
        edge_lat = (node_u['y'] + node_v['y']) / 2
        edge_lon = (node_u['x'] + node_v['x']) / 2
        
        penalty = 0
        crimes_nearby = 0
        closest_distance = float('inf')
        
        for crime in crimes:
            distance = haversine_distance(edge_lat, edge_lon, crime['lat'], crime['lon'])
            if distance <= 150:
                penalty += (150 - distance) / 150
                crimes_nearby += 1
                closest_distance = min(closest_distance, distance)
        
        original_length = edge_data.get('length', 50)
        edge_data['method2_weight'] = original_length * (1.0 + penalty * 1.5)
        edge_data['method2_crimes'] = crimes_nearby
        edge_data['method2_closest'] = closest_distance if closest_distance != float('inf') else None
    
    # Method 3: Threshold Avoidance
    for u, v, key in G.edges(keys=True):
        edge_data = G.edges[u, v, key]
        node_u, node_v = G.nodes[u], G.nodes[v]
        edge_lat = (node_u['y'] + node_v['y']) / 2
        edge_lon = (node_u['x'] + node_v['x']) / 2
        
        is_dangerous = False
        crimes_nearby = 0
        closest_distance = float('inf')
        
        for crime in crimes:
            distance = haversine_distance(edge_lat, edge_lon, crime['lat'], crime['lon'])
            if distance <= 75:  # 75m danger radius
                crimes_nearby += 1
                closest_distance = min(closest_distance, distance)
                is_dangerous = True
        
        original_length = edge_data.get('length', 50)
        edge_data['method3_weight'] = original_length * (5.0 if is_dangerous else 1.0)
        edge_data['method3_crimes'] = crimes_nearby
        edge_data['method3_closest'] = closest_distance if closest_distance != float('inf') else None
    
    # Method 4: Raw Data Weighted
    for u, v, key in G.edges(keys=True):
        edge_data = G.edges[u, v, key]
        node_u, node_v = G.nodes[u], G.nodes[v]
        edge_lat = (node_u['y'] + node_v['y']) / 2
        edge_lon = (node_u['x'] + node_v['x']) / 2
        
        total_risk = 0
        crime_count = 0
        
        for crime in crimes:
            distance = haversine_distance(edge_lat, edge_lon, crime['lat'], crime['lon'])
            if distance <= 200:  # 200m max influence
                risk_contribution = 1.0 / (1.0 + distance / 50)
                total_risk += risk_contribution
                crime_count += 1
        
        original_length = edge_data.get('length', 50)
        edge_data['method4_weight'] = original_length * (1.0 + total_risk * 0.5)
        edge_data['method4_crimes'] = crime_count
        edge_data['method4_risk'] = total_risk

def calculate_route_stats(G, route_nodes, method_prefix=''):
    """Calculate detailed statistics for a route."""
    total_distance = 0
    total_crimes = 0
    total_risk = 0
    dangerous_segments = 0
    route_coords = []
    
    for i, node in enumerate(route_nodes):
        node_data = G.nodes[node]
        route_coords.append([node_data['y'], node_data['x']])
        
        if i > 0:
            prev_node = route_nodes[i-1]
            if G.has_edge(prev_node, node):
                edge_data = G.edges[prev_node, node, 0]
                total_distance += edge_data.get('length', 0)
                
                if method_prefix:
                    total_crimes += edge_data.get(f'{method_prefix}_crimes', 0)
                    total_risk += edge_data.get(f'{method_prefix}_risk', 0)
                    if edge_data.get(f'{method_prefix}_crimes', 0) > 0:
                        dangerous_segments += 1
                else:
                    # For shortest path, count crimes within 100m
                    total_crimes += edge_data.get('method1_crimes', 0)
                    if edge_data.get('method1_crimes', 0) > 0:
                        dangerous_segments += 1
    
    return {
        'coordinates': route_coords,
        'distance': total_distance,
        'crime_exposure': total_crimes,
        'risk_score': total_risk,
        'dangerous_segments': dangerous_segments,
        'walking_time': total_distance / 80  # ~5 km/h walking speed
    }

def test_routing_between_locations():
    """Test routing algorithms between multiple Toronto locations."""
    print("Comprehensive Routing Algorithm Tests")
    print("=" * 45)
    
    # Load crime data
    crimes = load_crime_data()
    if not crimes:
        print("No crime data available")
        return
    
    print(f"Loaded {len(crimes)} crime incidents")
    
    # Define test locations (real Toronto landmarks with coordinates)
    test_locations = [
        {
            'name': 'CN Tower',
            'coords': (43.6426, -79.3871),
            'description': 'Downtown landmark'
        },
        {
            'name': 'Union Station',
            'coords': (43.6452, -79.3806),
            'description': 'Major transit hub'
        },
        {
            'name': 'Toronto City Hall',
            'coords': (43.6534, -79.3839),
            'description': 'Government center'
        },
        {
            'name': 'St. Lawrence Market',
            'coords': (43.6487, -79.3716),
            'description': 'Historic market'
        },
        {
            'name': 'Harbourfront Centre',
            'coords': (43.6387, -79.3816),
            'description': 'Waterfront cultural center'
        }
    ]
    
    # Define test route pairs
    test_routes = [
        (0, 1, 'CN Tower to Union Station'),
        (1, 2, 'Union Station to City Hall'),
        (2, 3, 'City Hall to St. Lawrence Market'),
        (3, 4, 'St. Lawrence Market to Harbourfront'),
        (0, 4, 'CN Tower to Harbourfront (longer route)')
    ]
    
    all_results = []
    
    for start_idx, end_idx, route_name in test_routes:
        print(f"\n{'='*60}")
        print(f"TESTING: {route_name.upper()}")
        print('='*60)
        
        start_location = test_locations[start_idx]
        end_location = test_locations[end_idx]
        
        start_coords = start_location['coords']
        end_coords = end_location['coords']
        
        # Calculate network bounds to include both locations with buffer
        center_lat = (start_coords[0] + end_coords[0]) / 2
        center_lon = (start_coords[1] + end_coords[1]) / 2
        
        # Calculate distance between points to determine network size
        route_distance = haversine_distance(start_coords[0], start_coords[1], 
                                          end_coords[0], end_coords[1])
        network_radius = max(800, route_distance * 0.8)  # At least 800m, or 80% of route distance
        
        print(f"Loading network around ({center_lat:.4f}, {center_lon:.4f})")
        print(f"Route distance: {route_distance:.0f}m, Network radius: {network_radius:.0f}m")
        
        try:
            # Load street network
            G = ox.graph_from_point(
                (center_lat, center_lon),
                dist=network_radius,
                network_type='walk',
                simplify=True
            )
            print(f"✓ Network: {len(G.nodes)} nodes, {len(G.edges)} edges")
            
        except Exception as e:
            print(f"✗ Error loading network: {e}")
            continue
        
        # Filter crimes to network area with buffer for edge effects
        buffer = 0.002  # ~200m buffer around network bounds
        bounds = {
            'lat_min': min(G.nodes[node]['y'] for node in G.nodes()) - buffer,
            'lat_max': max(G.nodes[node]['y'] for node in G.nodes()) + buffer,
            'lon_min': min(G.nodes[node]['x'] for node in G.nodes()) - buffer,
            'lon_max': max(G.nodes[node]['x'] for node in G.nodes()) + buffer
        }
        
        print(f"Network bounds: {bounds['lat_min']:.4f} to {bounds['lat_max']:.4f} lat, {bounds['lon_min']:.4f} to {bounds['lon_max']:.4f} lon")
        
        local_crimes = [
            crime for crime in crimes
            if (bounds['lat_min'] <= crime['lat'] <= bounds['lat_max'] and
                bounds['lon_min'] <= crime['lon'] <= bounds['lon_max'])
        ]
        
        # Debug: Check if any crimes are very close to network bounds but excluded
        nearby_excluded = [
            crime for crime in crimes
            if not (bounds['lat_min'] <= crime['lat'] <= bounds['lat_max'] and
                   bounds['lon_min'] <= crime['lon'] <= bounds['lon_max'])
            and (abs(crime['lat'] - bounds['lat_min']) < buffer * 2 or
                 abs(crime['lat'] - bounds['lat_max']) < buffer * 2 or
                 abs(crime['lon'] - bounds['lon_min']) < buffer * 2 or
                 abs(crime['lon'] - bounds['lon_max']) < buffer * 2)
        ]
        
        if nearby_excluded:
            print(f"Note: {len(nearby_excluded)} crimes are just outside the extended network area")
        
        print(f"Found {len(local_crimes)} crimes in network area")
        
        if not local_crimes:
            print("No crimes in area - skipping")
            continue
        
        # Apply all routing methods
        apply_all_routing_methods(G, local_crimes)
        
        # Find nearest nodes to start and end locations
        try:
            start_node = ox.nearest_nodes(G, start_coords[1], start_coords[0])
            end_node = ox.nearest_nodes(G, end_coords[1], end_coords[0])
        except Exception as e:
            print(f"✗ Error finding nearest nodes: {e}")
            continue
        
        # Calculate routes using all methods
        methods = {
            'shortest': {
                'weight': 'length', 
                'color': 'blue', 
                'name': 'Shortest Path',
                'prefix': ''
            },
            'exponential': {
                'weight': 'method1_weight', 
                'color': 'red', 
                'name': 'Exponential Decay',
                'prefix': 'method1'
            },
            'linear': {
                'weight': 'method2_weight', 
                'color': 'green', 
                'name': 'Linear Penalty',
                'prefix': 'method2'
            },
            'threshold': {
                'weight': 'method3_weight', 
                'color': 'orange', 
                'name': 'Threshold Avoidance',
                'prefix': 'method3'
            },
            'raw_data': {
                'weight': 'method4_weight', 
                'color': 'purple', 
                'name': 'Raw Data Weighted',
                'prefix': 'method4'
            }
        }
        
        route_results = {}
        
        for method_name, method_info in methods.items():
            try:
                route_nodes = nx.shortest_path(G, start_node, end_node, weight=method_info['weight'])
                stats = calculate_route_stats(G, route_nodes, method_info['prefix'])
                
                route_results[method_name] = {
                    'nodes': route_nodes,
                    'stats': stats,
                    'color': method_info['color'],
                    'name': method_info['name']
                }
                
                print(f"\n{method_info['name']}:")
                print(f"  Distance: {stats['distance']:.0f}m")
                print(f"  Crime exposure: {stats['crime_exposure']:.0f}")
                print(f"  Dangerous segments: {stats['dangerous_segments']}")
                print(f"  Walking time: {stats['walking_time']:.1f} min")
                
            except Exception as e:
                print(f"✗ Error calculating {method_name}: {e}")
        
        # Create detailed comparison map
        if route_results:
            route_map = folium.Map(
                location=[center_lat, center_lon],
                zoom_start=15,
                tiles='OpenStreetMap'
            )
            
            # Add routes with detailed annotations
            for method_name, route_info in route_results.items():
                stats = route_info['stats']
                
                # Create detailed popup text
                popup_text = f"""
                <b>{route_info['name']}</b><br>
                📏 Distance: {stats['distance']:.0f}m<br>
                🚨 Crime Exposure: {stats['crime_exposure']:.0f}<br>
                ⚠️ Dangerous Segments: {stats['dangerous_segments']}<br>
                🚶 Walking Time: {stats['walking_time']:.1f} min<br>
                📊 Safety Score: {((1 - stats['crime_exposure']/max(1, route_results['shortest']['stats']['crime_exposure'])) * 100):.1f}%
                """
                
                folium.PolyLine(
                    locations=stats['coordinates'],
                    color=route_info['color'],
                    weight=4,
                    opacity=0.8,
                    popup=folium.Popup(popup_text, max_width=300)
                ).add_to(route_map)
                
                # Add method label at route midpoint
                mid_idx = len(stats['coordinates']) // 2
                if mid_idx < len(stats['coordinates']):
                    mid_coord = stats['coordinates'][mid_idx]
                    folium.Marker(
                        location=mid_coord,
                        icon=folium.DivIcon(
                            html=f"""
                            <div style="background-color: {route_info['color']}; 
                                        color: white; padding: 2px 6px; border-radius: 3px; 
                                        font-size: 10px; font-weight: bold; text-align: center;">
                                {route_info['name']}<br>
                                {stats['distance']:.0f}m | {stats['crime_exposure']:.0f} crimes
                            </div>
                            """,
                            icon_size=(120, 30),
                            icon_anchor=(60, 15)
                        )
                    ).add_to(route_map)
            
            # Add start and end markers
            folium.Marker(
                location=list(start_coords),
                popup=f"<b>START</b><br>{start_location['name']}<br>{start_location['description']}",
                icon=folium.Icon(color='darkgreen', icon='play')
            ).add_to(route_map)
            
            folium.Marker(
                location=list(end_coords),
                popup=f"<b>END</b><br>{end_location['name']}<br>{end_location['description']}",
                icon=folium.Icon(color='darkred', icon='stop')
            ).add_to(route_map)
            
            # Add ALL crime incidents with high visibility
            print(f"Adding {len(local_crimes)} crime incidents to map...")
            for i, crime in enumerate(local_crimes):
                folium.CircleMarker(
                    location=[crime['lat'], crime['lon']],
                    radius=4,  # Larger radius for better visibility
                    color='darkred',
                    fillColor='red',
                    fillOpacity=0.8,  # Higher opacity for better visibility
                    weight=2,  # Border weight
                    popup=f"<b>Crime Incident #{i+1}</b><br>Location: {crime['lat']:.4f}, {crime['lon']:.4f}"
                ).add_to(route_map)
            
            # Add crime density heatmap overlay for better visualization
            from folium.plugins import HeatMap
            if len(local_crimes) > 0:
                heat_data = [[crime['lat'], crime['lon'], 1.0] for crime in local_crimes]
                HeatMap(
                    heat_data,
                    radius=25,
                    blur=15,
                    max_zoom=18,
                    gradient={0.2: 'blue', 0.4: 'cyan', 0.6: 'lime', 0.8: 'yellow', 1.0: 'red'}
                ).add_to(route_map)
            
            # Add map legend using marker with HTML content
            legend_text = f"""
            <b>Map Legend</b><br>
            🔴 Crime Incidents ({len(local_crimes)} total)<br>
            🔵 Shortest Path<br>
            🔴 Exponential Decay<br>
            🟢 Linear Penalty<br>
            🟠 Threshold Avoidance<br>
            🟣 Raw Data Weighted<br>
            🟩 Start Location<br>
            🟥 End Location<br>
            🌡️ Heatmap = Crime Density
            """
            
            # Add legend as a marker in the bottom-left corner of the map
            folium.Marker(
                location=[center_lat - 0.01, center_lon - 0.01],  # Bottom-left offset
                icon=folium.DivIcon(
                    html=f"""
                    <div style="background-color: white; border: 2px solid black; 
                                padding: 8px; border-radius: 5px; font-size: 11px; 
                                line-height: 1.3; white-space: nowrap;">
                        {legend_text}
                    </div>
                    """,
                    icon_size=(200, 140),
                    icon_anchor=(0, 140)
                )
            ).add_to(route_map)
            
            # Save individual route map
            safe_route_name = route_name.lower().replace(' ', '_').replace('(', '').replace(')', '')
            map_filename = f"test_{safe_route_name}.html"
            route_map.save(map_filename)
            print(f"\n✓ Route map saved as: {map_filename}")
            
            # Store results for summary
            all_results.append({
                'route_name': route_name,
                'results': route_results,
                'map_file': map_filename,
                'start_location': start_location,
                'end_location': end_location
            })
    
    # Create summary report
    if all_results:
        print(f"\n{'='*80}")
        print("COMPREHENSIVE ROUTING TEST SUMMARY")
        print('='*80)
        
        for test_result in all_results:
            print(f"\n📍 {test_result['route_name'].upper()}")
            print('-' * 60)
            
            results = test_result['results']
            if 'shortest' in results:
                baseline = results['shortest']['stats']
                
                print(f"{'Method':<20} {'Distance':<12} {'Crime Exp':<12} {'Danger Seg':<12} {'Time':<8} {'Trade-off'}")
                print('-' * 75)
                
                for method_name, route_info in results.items():
                    stats = route_info['stats']
                    dist_diff = stats['distance'] - baseline['distance']
                    exp_diff = baseline['crime_exposure'] - stats['crime_exposure']
                    
                    print(f"{route_info['name']:<20} "
                          f"{stats['distance']:.0f}m{f' (+{dist_diff:.0f})' if dist_diff > 0 else '':<11} "
                          f"{stats['crime_exposure']:.0f}{f' (-{exp_diff:.0f})' if exp_diff > 0 else '':<11} "
                          f"{stats['dangerous_segments']:<12} "
                          f"{stats['walking_time']:.1f}min{'':<3} "
                          f"{'✓ Safer' if exp_diff > 0 else '- Same'}")
        
        print(f"\n✅ All test maps generated successfully!")
        print(f"📁 Individual route maps: test_*.html")
        print(f"🗂️  Total routes tested: {len(all_results)}")

if __name__ == "__main__":
    test_routing_between_locations() 
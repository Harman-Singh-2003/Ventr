#!/usr/bin/env python3
"""
Raw Crime Data Routing
Direct approach using all individual crime incidents without clustering.
"""

import osmnx as ox
import networkx as nx
import folium
import json
import math

def load_raw_crime_data():
    """Load raw crime data without any clustering or preprocessing."""
    print("Loading raw crime data (no clustering)...")
    try:
        with open('Assault_Open_Data_-331273077107818534.geojson', 'r') as f:
            crime_data = json.load(f)
        
        crimes = []
        for feature in crime_data['features']:
            if feature['geometry']['type'] == 'Point':
                coords = feature['geometry']['coordinates']
                lon, lat = coords[0], coords[1]
                
                # Filter for valid Toronto coordinates
                if 43.5 <= lat <= 44.0 and -80.0 <= lon <= -79.0:
                    crimes.append({
                        'lat': lat,
                        'lon': lon,
                        'properties': feature.get('properties', {})
                    })
        
        print(f"✓ Loaded {len(crimes)} raw crime incidents")
        return crimes
        
    except Exception as e:
        print(f"✗ Error loading crime data: {e}")
        return []

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points using Haversine formula."""
    R = 6371000  # Earth's radius in meters
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat, delta_lon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    
    a = (math.sin(delta_lat/2)**2 + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

def apply_raw_crime_weighting(G, crimes, influence_radius=150):
    """Apply raw crime data weighting to graph edges."""
    print(f"Processing {len(G.edges)} edges against {len(crimes)} individual crimes...")
    
    edge_stats = []
    
    for u, v, key in G.edges(keys=True):
        edge_data = G.edges[u, v, key]
        
        # Calculate edge midpoint
        node_u, node_v = G.nodes[u], G.nodes[v]
        edge_lat = (node_u['y'] + node_v['y']) / 2
        edge_lon = (node_u['x'] + node_v['x']) / 2
        
        # Process each individual crime
        cumulative_risk = 0
        crimes_in_range = 0
        closest_crime_distance = float('inf')
        
        for crime in crimes:
            distance = haversine_distance(edge_lat, edge_lon, crime['lat'], crime['lon'])
            
            if distance <= influence_radius:
                crimes_in_range += 1
                closest_crime_distance = min(closest_crime_distance, distance)
                
                # Inverse square law for crime influence
                # Closer crimes have exponentially more impact
                if distance < 1:  # Avoid division by zero
                    distance = 1
                
                risk_contribution = 1.0 / (distance ** 0.5)  # Square root falloff
                cumulative_risk += risk_contribution
        
        # Calculate weighted length
        original_length = edge_data.get('length', 50)
        
        # Risk multiplier based on cumulative exposure
        risk_multiplier = 1.0 + (cumulative_risk * 0.3)  # 30% penalty per risk unit
        
        # Store all statistics
        edge_data['raw_weight'] = original_length * risk_multiplier
        edge_data['crimes_in_range'] = crimes_in_range
        edge_data['cumulative_risk'] = cumulative_risk
        edge_data['closest_crime'] = closest_crime_distance if closest_crime_distance != float('inf') else None
        edge_data['risk_multiplier'] = risk_multiplier
        
        edge_stats.append({
            'crimes_in_range': crimes_in_range,
            'cumulative_risk': cumulative_risk,
            'risk_multiplier': risk_multiplier
        })
    
    # Print statistics
    if edge_stats:
        avg_crimes = sum(s['crimes_in_range'] for s in edge_stats) / len(edge_stats)
        max_crimes = max(s['crimes_in_range'] for s in edge_stats)
        avg_risk = sum(s['cumulative_risk'] for s in edge_stats) / len(edge_stats)
        max_risk = max(s['cumulative_risk'] for s in edge_stats)
        
        print(f"✓ Raw crime weighting applied:")
        print(f"  Average crimes per edge: {avg_crimes:.1f}")
        print(f"  Maximum crimes per edge: {max_crimes}")
        print(f"  Average risk score: {avg_risk:.2f}")
        print(f"  Maximum risk score: {max_risk:.2f}")

def analyze_route_crime_exposure(G, route_nodes, crimes):
    """Analyze detailed crime exposure for a route."""
    exposure_data = []
    total_exposure = 0
    
    for i in range(len(route_nodes) - 1):
        u, v = route_nodes[i], route_nodes[i + 1]
        
        if G.has_edge(u, v):
            edge_data = G.edges[u, v, 0]
            
            crimes_count = edge_data.get('crimes_in_range', 0)
            risk_score = edge_data.get('cumulative_risk', 0)
            closest_crime = edge_data.get('closest_crime', None)
            
            exposure_data.append({
                'edge': f"{u}-{v}",
                'crimes_nearby': crimes_count,
                'risk_score': risk_score,
                'closest_crime_m': closest_crime,
                'length_m': edge_data.get('length', 0)
            })
            
            total_exposure += crimes_count
    
    return exposure_data, total_exposure

def raw_crime_routing_test():
    """Test routing using raw crime data without clustering."""
    print("Raw Crime Data Routing Test")
    print("=" * 35)
    
    # Load raw crime data
    crimes = load_raw_crime_data()
    if not crimes:
        print("No crime data available")
        return
    
    # Load street network
    center_lat, center_lon = 43.6505, -79.3810
    distance = 600  # Larger area for more interesting routes
    
    print(f"\nLoading street network (radius: {distance}m)...")
    
    try:
        G = ox.graph_from_point(
            (center_lat, center_lon),
            dist=distance,
            network_type='walk',
            simplify=True
        )
        print(f"✓ Network loaded: {len(G.nodes)} nodes, {len(G.edges)} edges")
        
    except Exception as e:
        print(f"✗ Error loading network: {e}")
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
        print("No crimes in network area")
        return
    
    # Apply raw crime weighting
    apply_raw_crime_weighting(G, local_crimes)
    
    # Select start and end nodes
    nodes = list(G.nodes())
    start_node = nodes[0]
    end_node = nodes[len(nodes)//4]  # Quarter way through for good distance
    
    start_coords = (G.nodes[start_node]['y'], G.nodes[start_node]['x'])
    end_coords = (G.nodes[end_node]['y'], G.nodes[end_node]['x'])
    
    print(f"\nRouting from {start_coords} to {end_coords}")
    
    try:
        # Calculate different routes
        routes = {}
        
        # Standard shortest path
        shortest_route = nx.shortest_path(G, start_node, end_node, weight='length')
        routes['shortest'] = {
            'nodes': shortest_route,
            'color': 'blue',
            'name': 'Shortest Path',
            'weight': 'length'
        }
        
        # Raw crime-weighted path
        safe_route = nx.shortest_path(G, start_node, end_node, weight='raw_weight')
        routes['raw_safe'] = {
            'nodes': safe_route,
            'color': 'green',
            'name': 'Raw Crime-Weighted',
            'weight': 'raw_weight'
        }
        
        # Analyze each route
        for route_name, route_info in routes.items():
            route_nodes = route_info['nodes']
            
            # Calculate basic stats
            total_distance = 0
            for i in range(len(route_nodes) - 1):
                u, v = route_nodes[i], route_nodes[i + 1]
                if G.has_edge(u, v):
                    edge_data = G.edges[u, v, 0]
                    total_distance += edge_data.get('length', 0)
            
            # Analyze crime exposure
            exposure_data, total_exposure = analyze_route_crime_exposure(G, route_nodes, local_crimes)
            
            # Calculate route coordinates for mapping
            route_coords = []
            for node in route_nodes:
                node_data = G.nodes[node]
                route_coords.append([node_data['y'], node_data['x']])
            
            route_info.update({
                'coordinates': route_coords,
                'distance': total_distance,
                'crime_exposure': total_exposure,
                'exposure_data': exposure_data
            })
            
            print(f"\n{route_info['name']}:")
            print(f"  Distance: {total_distance:.0f}m")
            print(f"  Total crime exposure: {total_exposure}")
            print(f"  Route segments: {len(route_nodes)-1}")
            
            # Show most dangerous segments
            dangerous_segments = [e for e in exposure_data if e['crimes_nearby'] > 0]
            if dangerous_segments:
                print(f"  Dangerous segments: {len(dangerous_segments)}")
                # Show top 3 most dangerous
                dangerous_segments.sort(key=lambda x: x['crimes_nearby'], reverse=True)
                for i, seg in enumerate(dangerous_segments[:3]):
                    print(f"    {i+1}. {seg['crimes_nearby']} crimes within 150m")
        
        # Create visualization map
        route_map = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=16,
            tiles='OpenStreetMap'
        )
        
        # Add routes
        for route_name, route_info in routes.items():
            folium.PolyLine(
                locations=route_info['coordinates'],
                color=route_info['color'],
                weight=4,
                opacity=0.8,
                popup=f"{route_info['name']}: {route_info['distance']:.0f}m, Exposure: {route_info['crime_exposure']}"
            ).add_to(route_map)
        
        # Add start/end markers
        folium.Marker(
            location=list(start_coords),
            popup="Start",
            icon=folium.Icon(color='darkblue', icon='play')
        ).add_to(route_map)
        
        folium.Marker(
            location=list(end_coords),
            popup="End",
            icon=folium.Icon(color='darkblue', icon='stop')
        ).add_to(route_map)
        
        # Add all individual crime incidents
        for i, crime in enumerate(local_crimes):
            folium.CircleMarker(
                location=[crime['lat'], crime['lon']],
                radius=2,
                color='red',
                fillColor='darkred',
                fillOpacity=0.7,
                popup=f"Crime incident {i+1}"
            ).add_to(route_map)
        
        # Save map
        map_filename = "raw_crime_routing.html"
        route_map.save(map_filename)
        print(f"\n✓ Raw crime routing map saved as: {map_filename}")
        
        # Route comparison
        if len(routes) > 1:
            shortest = routes['shortest']
            safe = routes['raw_safe']
            
            distance_diff = safe['distance'] - shortest['distance']
            exposure_diff = shortest['crime_exposure'] - safe['crime_exposure']
            
            print(f"\n📊 Raw Crime Routing Analysis:")
            print(f"  Distance trade-off: +{distance_diff:.0f}m ({(distance_diff/shortest['distance']*100):+.1f}%)")
            print(f"  Crime exposure reduction: {exposure_diff} fewer crime exposures")
            print(f"  Safety improvement: {(exposure_diff/shortest['crime_exposure']*100 if shortest['crime_exposure'] > 0 else 0):.1f}%")
        
        print(f"\n✓ Raw crime routing analysis completed!")
        
    except Exception as e:
        print(f"✗ Error in routing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    raw_crime_routing_test() 
#!/usr/bin/env python3
"""
Mapbox Crime Heatmap Generator
Creates a road network with crime density data formatted for Mapbox heatmap visualization.
Generates GeoJSON with crime density weights (0-1) for each road segment.
"""

import osmnx as ox
import networkx as nx
import json
import math
from shapely.geometry import Point, LineString

def load_crime_data():
    """Load and filter crime data from the assault geojson file."""
    try:
        with open('Assault_Open_Data_-331273077107818534.geojson', 'r') as f:
            crime_data = json.load(f)
        
        crimes = []
        for feature in crime_data['features']:
            if feature['geometry']['type'] == 'Point':
                coords = feature['geometry']['coordinates']
                lon, lat = coords[0], coords[1]
                
                # Filter for Toronto area
                if 43.5 <= lat <= 44.0 and -80.0 <= lon <= -79.0:
                    crimes.append({
                        'lat': lat, 
                        'lon': lon,
                        'point': Point(lon, lat)
                    })
        
        print(f"Loaded {len(crimes)} crime incidents")
        return crimes
    except Exception as e:
        print(f"Error loading crime data: {e}")
        return []

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in meters."""
    R = 6371000  # Earth's radius in meters
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat, delta_lon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    
    a = (math.sin(delta_lat/2)**2 + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

def calculate_crime_density_for_edge(edge_geometry, crimes, max_influence_distance=50):
    """
    Calculate crime density for a road edge.
    
    Args:
        edge_geometry: LineString geometry of the road edge
        crimes: List of crime incidents with point geometry
        max_influence_distance: Maximum distance for crime influence (meters)
    
    Returns:
        float: Crime density score (0-1 scale where 1.0 = 3 crimes)
    """
    total_crime_weight = 0.0
    
    for crime in crimes:
        # Calculate distance from crime to the road edge
        distance = edge_geometry.distance(crime['point'])
        distance_meters = distance * 111000  # Rough conversion from degrees to meters
        
        if distance_meters <= max_influence_distance:
            # Heavy bias for crimes directly on street (within 5m)
            if distance_meters <= 5:
                weight = 1.0
            # Medium weight for crimes very close (5-15m)
            elif distance_meters <= 15:
                weight = 0.8 * (1 - (distance_meters - 5) / 10)
            # Gradient weight for nearby crimes (15-50m)
            else:
                weight = 0.3 * (1 - (distance_meters - 15) / 35)
            
            total_crime_weight += weight
    
    # Normalize to 0-1 scale where 3 crimes = 1.0
    normalized_density = min(total_crime_weight / 3.0, 1.0)
    return normalized_density

def create_road_network_heatmap(center_lat=43.6426, center_lon=-79.3871, radius=100):
    """
    Create a road network with crime density data for Mapbox heatmap.
    
    Args:
        center_lat: Center latitude (default: CN Tower)
        center_lon: Center longitude
                 radius: Network radius in meters (100m = 200m diameter)
    
    Returns:
        dict: GeoJSON formatted data for Mapbox
    """
    print(f"Creating road network around ({center_lat}, {center_lon}) with {radius*2}m diameter")
    
    # Load crime data
    crimes = load_crime_data()
    if not crimes:
        print("No crime data available")
        return None
    
    # Create road network
    try:
        G = ox.graph_from_point(
            (center_lat, center_lon),
            dist=radius,
            network_type='all',  # Use all network types for better coverage
            simplify=True
        )
        print(f"Created network with {len(G.nodes)} nodes and {len(G.edges)} edges")
    except Exception as e:
        print(f"Error creating network: {e}")
        return None
    
    # Filter crimes to network area with buffer
    buffer = 0.001  # ~100m buffer
    bounds = {
        'lat_min': min(G.nodes[node]['y'] for node in G.nodes()) - buffer,
        'lat_max': max(G.nodes[node]['y'] for node in G.nodes()) + buffer,
        'lon_min': min(G.nodes[node]['x'] for node in G.nodes()) - buffer,
        'lon_max': max(G.nodes[node]['x'] for node in G.nodes()) + buffer
    }
    
    local_crimes = [
        crime for crime in crimes
        if (bounds['lat_min'] <= crime['lat'] <= bounds['lat_max'] and
            bounds['lon_min'] <= crime['lon'] <= bounds['lon_max'])
    ]
    
    print(f"Found {len(local_crimes)} crimes in network area")
    
    # Create GeoJSON features for each road edge
    features = []
    
    for u, v, key in G.edges(keys=True):
        # Get edge geometry
        edge_data = G.edges[u, v, key]
        node_u = G.nodes[u]
        node_v = G.nodes[v]
        
        # Create LineString geometry for the edge
        if 'geometry' in edge_data:
            # Use existing geometry if available
            coords = [(point[0], point[1]) for point in edge_data['geometry'].coords]
        else:
            # Create simple line between nodes
            coords = [(node_u['x'], node_u['y']), (node_v['x'], node_v['y'])]
        
        edge_line = LineString(coords)
        
        # Calculate crime density for this edge
        crime_density = calculate_crime_density_for_edge(edge_line, local_crimes)
        
        # Create GeoJSON feature
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coords
            },
            "properties": {
                "weight": crime_density,
                "edge_id": f"{u}_{v}_{key}",
                "length": edge_data.get('length', 0),
                "road_type": edge_data.get('highway', 'unknown'),
                "name": edge_data.get('name', 'Unnamed Road')
            }
        }
        
        features.append(feature)
    
    # Create GeoJSON FeatureCollection
    geojson_data = {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "description": "Road network with crime density heatmap data",
            "center": [center_lon, center_lat],
            "radius_meters": radius * 2,
            "total_roads": len(features),
            "total_crimes": len(local_crimes),
            "generated": "2024-01-01",
            "scale": "0-1 where 1.0 = 3 crimes per road segment"
        }
    }
    
    return geojson_data

def generate_multiple_locations():
    """Generate heatmap data for multiple Toronto locations."""
    locations = [
        {"name": "CN Tower", "lat": 43.6426, "lon": -79.3871},
        {"name": "Downtown Core", "lat": 43.6532, "lon": -79.3832},
        {"name": "Entertainment District", "lat": 43.6463, "lon": -79.3912},
        {"name": "Financial District", "lat": 43.6481, "lon": -79.3794},
        {"name": "King West", "lat": 43.6441, "lon": -79.3957}
    ]
    
    all_features = []
    
    for location in locations:
        print(f"\nProcessing {location['name']}...")
        geojson_data = create_road_network_heatmap(
            center_lat=location['lat'],
            center_lon=location['lon'],
            radius=100
        )
        
        if geojson_data and geojson_data['features']:
            # Add location info to each feature
            for feature in geojson_data['features']:
                feature['properties']['location'] = location['name']
            
            all_features.extend(geojson_data['features'])
            print(f"Added {len(geojson_data['features'])} road segments from {location['name']}")
    
    return {
        "type": "FeatureCollection",
        "features": all_features,
        "properties": {
            "description": "Multi-location road network crime heatmap for Toronto",
            "locations": [loc['name'] for loc in locations],
            "total_segments": len(all_features),
            "scale": "0-1 where 1.0 = 3 crimes per road segment"
        }
    }

def main():
    """Main function to generate the heatmap data."""
    print("Mapbox Crime Heatmap Generator")
    print("=" * 40)
    
    # Generate single location heatmap (CN Tower area)
    print("\n1. Generating single location heatmap (CN Tower area)...")
    single_location_data = create_road_network_heatmap()
    
    if single_location_data:
        # Save single location data
        with open('mapbox_crime_heatmap_single.geojson', 'w') as f:
            json.dump(single_location_data, f, indent=2)
        print("✓ Single location heatmap saved: mapbox_crime_heatmap_single.geojson")
        
        # Print statistics
        weights = [f['properties']['weight'] for f in single_location_data['features']]
        non_zero_weights = [w for w in weights if w > 0]
        
        print(f"\nStatistics for single location:")
        print(f"  Total road segments: {len(weights)}")
        print(f"  Segments with crime exposure: {len(non_zero_weights)}")
        print(f"  Max crime density: {max(weights):.3f}")
        print(f"  Average crime density: {sum(weights)/len(weights):.3f}")
        print(f"  High crime segments (>0.5): {len([w for w in weights if w > 0.5])}")
    
    # Generate multi-location heatmap
    print("\n2. Generating multi-location heatmap...")
    multi_location_data = generate_multiple_locations()
    
    if multi_location_data['features']:
        # Save multi-location data
        with open('mapbox_crime_heatmap_multi.geojson', 'w') as f:
            json.dump(multi_location_data, f, indent=2)
        print("✓ Multi-location heatmap saved: mapbox_crime_heatmap_multi.geojson")
        
        # Print statistics
        weights = [f['properties']['weight'] for f in multi_location_data['features']]
        non_zero_weights = [w for w in weights if w > 0]
        
        print(f"\nStatistics for multi-location:")
        print(f"  Total road segments: {len(weights)}")
        print(f"  Segments with crime exposure: {len(non_zero_weights)}")
        print(f"  Max crime density: {max(weights):.3f}")
        print(f"  Average crime density: {sum(weights)/len(weights):.3f}")
        print(f"  High crime segments (>0.5): {len([w for w in weights if w > 0.5])}")
    
    print(f"\n✅ Heatmap generation complete!")
    print(f"📁 Files generated:")
    print(f"   - mapbox_crime_heatmap_single.geojson (CN Tower area)")
    print(f"   - mapbox_crime_heatmap_multi.geojson (Multiple Toronto locations)")
    print(f"\n📋 Usage Instructions:")
    print(f"   1. Upload either GeoJSON file to Mapbox Studio")
    print(f"   2. Create a heatmap layer")
    print(f"   3. Use 'weight' property for heatmap intensity")
    print(f"   4. Set color ramp from 0 (cool) to 1 (hot)")

if __name__ == "__main__":
    main() 
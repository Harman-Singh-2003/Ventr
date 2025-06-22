#!/usr/bin/env python3
"""
Preview the Mapbox Crime Heatmap Data
Creates a simple Folium map to visualize the crime heatmap before uploading to Mapbox.
"""

import folium
import json
import numpy as np

def preview_heatmap(geojson_file='mapbox_crime_heatmap_multi.geojson'):
    """Create a preview map of the crime heatmap data."""
    
    # Load the GeoJSON data
    with open(geojson_file, 'r') as f:
        data = json.load(f)
    
    # Calculate center point for the map
    all_coords = []
    for feature in data['features']:
        coords = feature['geometry']['coordinates']
        for coord in coords:
            all_coords.append(coord)
    
    if not all_coords:
        print("No coordinates found in data")
        return
    
    center_lon = sum(coord[0] for coord in all_coords) / len(all_coords)
    center_lat = sum(coord[1] for coord in all_coords) / len(all_coords)
    
    # Create the map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=14,
        tiles='OpenStreetMap'
    )
    
    # Get weights for color mapping
    weights = [feature['properties']['weight'] for feature in data['features']]
    max_weight = max(weights) if weights else 1.0
    
    # Color mapping function
    def get_color(weight):
        if weight == 0:
            return 'gray'
        elif weight < 0.2:
            return 'blue'
        elif weight < 0.4:
            return 'green'
        elif weight < 0.6:
            return 'yellow'
        elif weight < 0.8:
            return 'orange'
        else:
            return 'red'
    
    def get_opacity(weight):
        return max(0.3, min(1.0, weight + 0.3))
    
    # Add each road segment
    high_crime_count = 0
    total_segments = len(data['features'])
    
    for feature in data['features']:
        weight = feature['properties']['weight']
        coordinates = feature['geometry']['coordinates']
        location = feature['properties'].get('location', 'Unknown')
        road_type = feature['properties'].get('road_type', 'Unknown')
        road_name = feature['properties'].get('name', 'Unnamed Road')
        
        if weight > 0.5:
            high_crime_count += 1
        
        # Convert coordinates for Folium (lat, lon format)
        folium_coords = [[coord[1], coord[0]] for coord in coordinates]
        
        popup_text = f"""
        <b>Road Segment</b><br>
        Crime Weight: {weight:.3f}<br>
        Location: {location}<br>
        Road Type: {road_type}<br>
        Name: {road_name}<br>
        Length: {feature['properties'].get('length', 0):.1f}m
        """
        
        folium.PolyLine(
            locations=folium_coords,
            color=get_color(weight),
            weight=3 if weight > 0 else 1,
            opacity=get_opacity(weight),
            popup=folium.Popup(popup_text, max_width=300)
        ).add_to(m)
    
    # Add legend as a text marker instead
    folium.Marker(
        location=[center_lat + 0.002, center_lon - 0.005],
        icon=folium.DivIcon(
            html="""
            <div style="background-color: white; border: 2px solid black; 
                        padding: 8px; border-radius: 5px; font-size: 12px; 
                        line-height: 1.3; white-space: nowrap;">
                <b>Crime Heat Legend</b><br>
                🔴 High (0.8-1.0)<br>
                🟠 Med-High (0.6-0.8)<br>
                🟡 Medium (0.4-0.6)<br>
                🟢 Low-Med (0.2-0.4)<br>
                🔵 Low (0.0-0.2)<br>
                ⭕ No Crime (0.0)
            </div>
            """,
            icon_size=(160, 120),
            icon_anchor=(0, 120)
        )
    ).add_to(m)
    
    # Save the map
    output_file = 'crime_heatmap_preview.html'
    m.save(output_file)
    
    # Print statistics
    print(f"Crime Heatmap Preview Statistics")
    print(f"=" * 40)
    print(f"Total road segments: {total_segments}")
    print(f"Segments with crime exposure: {sum(1 for w in weights if w > 0)}")
    print(f"High crime segments (>0.5): {high_crime_count}")
    print(f"Maximum crime weight: {max_weight:.3f}")
    print(f"Average crime weight: {np.mean(weights):.3f}")
    print(f"Median crime weight: {np.median(weights):.3f}")
    print(f"\nWeight distribution:")
    print(f"  0.0 (No crime): {sum(1 for w in weights if w == 0)}")
    print(f"  0.0-0.2 (Low): {sum(1 for w in weights if 0 < w <= 0.2)}")
    print(f"  0.2-0.4 (Low-Med): {sum(1 for w in weights if 0.2 < w <= 0.4)}")
    print(f"  0.4-0.6 (Medium): {sum(1 for w in weights if 0.4 < w <= 0.6)}")
    print(f"  0.6-0.8 (Med-High): {sum(1 for w in weights if 0.6 < w <= 0.8)}")
    print(f"  0.8-1.0 (High): {sum(1 for w in weights if 0.8 < w <= 1.0)}")
    
    print(f"\n✓ Preview map saved as: {output_file}")
    return output_file

if __name__ == "__main__":
    print("Generating Crime Heatmap Preview...")
    preview_heatmap() 
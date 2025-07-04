"""
Clean crime data loader with efficient filtering and validation.
"""

import json
import os
from typing import List, Dict, Tuple

def load_crime_data(data_path: str = None) -> List[Dict[str, float]]:
    """
    Load and filter crime data efficiently.
    
    Args:
        data_path: Path to the GeoJSON crime data file
        
    Returns:
        List of crime incidents with 'lat' and 'lon' keys
        
    Raises:
        FileNotFoundError: If crime data file not found
        ValueError: If data format is invalid
    """
    if data_path is None:
        # Default to the data directory relative to this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        data_path = os.path.join(current_dir, '..', 'data', 'crime_data.geojson')
    
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Crime data file not found: {data_path}")
    
    print(f"Loading crime data from: {data_path}")
    
    try:
        with open(data_path, 'r') as f:
            crime_data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format in crime data file: {e}")
    
    crimes = []
    
    # Process GeoJSON features
    if 'features' not in crime_data:
        raise ValueError("Crime data must be in GeoJSON format with 'features' key")
    
    for feature in crime_data['features']:
        if feature.get('geometry', {}).get('type') == 'Point':
            coords = feature['geometry']['coordinates']
            if len(coords) >= 2:
                lon, lat = coords[0], coords[1]
                
                # Filter to Toronto area (learned optimal bounds)
                if 43.5 <= lat <= 44.0 and -80.0 <= lon <= -79.0:
                    crimes.append({'lat': lat, 'lon': lon})
    
    print(f"Loaded {len(crimes)} crime incidents in Toronto area")
    return crimes

def filter_crimes_to_bounds(crimes: List[Dict[str, float]], 
                          lat_min: float, lat_max: float,
                          lon_min: float, lon_max: float,
                          buffer: float = 0.002) -> List[Dict[str, float]]:
    """
    Filter crimes to a specific geographic bounding box with buffer.
    
    Args:
        crimes: List of crime incidents
        lat_min, lat_max: Latitude bounds
        lon_min, lon_max: Longitude bounds
        buffer: Buffer distance in degrees (~200m)
        
    Returns:
        Filtered list of crimes within bounds
    """
    # Add buffer for edge effects (learned from experience)
    lat_min_buf = lat_min - buffer
    lat_max_buf = lat_max + buffer
    lon_min_buf = lon_min - buffer
    lon_max_buf = lon_max + buffer
    
    filtered_crimes = [
        crime for crime in crimes
        if (lat_min_buf <= crime['lat'] <= lat_max_buf and 
            lon_min_buf <= crime['lon'] <= lon_max_buf)
    ]
    
    print(f"Filtered to {len(filtered_crimes)} crimes within network bounds")
    return filtered_crimes 
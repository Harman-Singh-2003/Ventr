#!/usr/bin/env python3
"""
Standalone KDE Crime Surface Visualization

This script creates an interactive map showing the KDE crime density heatmap
that the routing algorithms use for decision making. You can see the exact
crime surface that influences route selection.
"""

import sys
import logging
from pathlib import Path
from typing import Tuple, Dict, Any
import folium
from folium.plugins import HeatMap
import numpy as np

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from crime_aware_routing_2.data.crime_processor import CrimeProcessor
from crime_aware_routing_2.algorithms.crime_weighting.kde_weighter import KDECrimeWeighter, CrimeSurface
from crime_aware_routing_2.config.routing_config import RoutingConfig
from crime_aware_routing_2.visualization.route_visualizer import RouteVisualizer

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_kde_visualization_map(crime_surface: CrimeSurface, 
                               crime_points: np.ndarray,
                               center_coords: Tuple[float, float],
                               config: RoutingConfig) -> folium.Map:
    """
    Create a detailed KDE visualization map with multiple layers.
    
    Args:
        crime_surface: KDE-generated crime surface
        crime_points: Raw crime incident points
        center_coords: Map center coordinates
        config: Routing configuration
        
    Returns:
        Folium map with crime visualization layers
    """
    # Initialize map
    m = folium.Map(
        location=center_coords,
        zoom_start=13,
        tiles='OpenStreetMap'
    )
    
    # Add raw crime points as markers
    logger.info("Adding crime incident markers...")
    if len(crime_points) > 0:
        # Limit to 1000 points for performance
        max_points = min(1000, len(crime_points))
        if len(crime_points) > max_points:
            indices = np.random.choice(len(crime_points), max_points, replace=False)
            sample_points = crime_points[indices]
        else:
            sample_points = crime_points
        
        # Add crime points as circle markers
        for point in sample_points:
            lat, lon = point[0], point[1]
            folium.CircleMarker(
                location=[lat, lon],
                radius=2,
                popup='Crime Incident',
                color='darkred',
                fill=True,
                fillOpacity=0.7,
                weight=1
            ).add_to(m)
    
    # Add KDE heatmap overlay
    logger.info("Adding KDE crime heatmap...")
    heat_data = []
    
    # Extract all points from the crime surface grid
    for i in range(len(crime_surface.lat_grid)):
        for j in range(len(crime_surface.lon_grid)):
            lat = crime_surface.lat_grid[i]
            lon = crime_surface.lon_grid[j]
            density = crime_surface.density_values[i, j]
            
            # Include all non-zero density values
            if density > 0.001:  # Very low threshold to show full surface
                heat_data.append([lat, lon, float(density)])
    
    if heat_data:
        HeatMap(
            heat_data,
            name='KDE Crime Density Surface',
            radius=20,           # Larger radius for smoother appearance
            blur=25,             # More blur for smooth gradients
            max_zoom=1,
            min_opacity=0.3,     # Minimum visibility
            gradient={
                0.0: 'blue',     # Lowest crime density
                0.2: 'cyan',
                0.4: 'lime',
                0.6: 'yellow',
                0.8: 'orange',
                1.0: 'red'       # Highest crime density
            }
        ).add_to(m)
        
        logger.info(f"Added KDE heatmap with {len(heat_data)} density points")
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Add configuration info as a popup marker
    config_info = f"""
    KDE Configuration:
    • Bandwidth: {config.kde_bandwidth}m
    • Resolution: {config.kde_resolution}m
    • Grid Size: {crime_surface.density_values.shape}
    
    Color Scale:
    • Blue = Low Crime Risk
    • Lime/Yellow = Medium Crime Risk  
    • Orange/Red = High Crime Risk
    """
    
    folium.Marker(
        location=[center_coords[0] + 0.008, center_coords[1] - 0.015],
        popup=folium.Popup(config_info, max_width=300),
        tooltip="Click for KDE Configuration Info",
        icon=folium.Icon(color='blue', icon='info-sign')
    ).add_to(m)
    
    return m


def main():
    """Generate KDE crime surface visualization for Toronto downtown area."""
    
    print("🗺️  Generating KDE Crime Surface Visualization")
    print("=" * 50)
    
    # Configuration
    crime_data_path = Path(__file__).parent.parent / "data" / "crime_data.geojson"
    
    # Define visualization area (Toronto downtown core)
    # This covers roughly from Harbourfront to Bloor, Bathurst to Parliament
    toronto_bounds = {
        'lat_min': 43.635,   # South (near waterfront)
        'lat_max': 43.670,   # North (near Bloor)
        'lon_min': -79.420,  # West (near Bathurst)
        'lon_max': -79.360   # East (near Parliament)
    }
    
    center_coords = (
        (toronto_bounds['lat_min'] + toronto_bounds['lat_max']) / 2,
        (toronto_bounds['lon_min'] + toronto_bounds['lon_max']) / 2
    )
    
    print(f"📍 Visualization area: {center_coords}")
    print(f"📂 Crime data: {crime_data_path}")
    
    try:
        # Test different KDE configurations to show variety
        configs = {
            'default': RoutingConfig(),
            'sharp_boundaries': RoutingConfig(kde_bandwidth=100.0, kde_resolution=25.0),
            'smooth_wide': RoutingConfig(kde_bandwidth=400.0, kde_resolution=75.0)
        }
        
        for config_name, config in configs.items():
            print(f"\n🔧 Creating visualization with {config_name} configuration...")
            print(f"   KDE Bandwidth: {config.kde_bandwidth}m")
            print(f"   KDE Resolution: {config.kde_resolution}m")
            
            # Initialize crime processor
            crime_processor = CrimeProcessor(str(crime_data_path), config)
            
            # Get crime data for the area
            crime_points = crime_processor.get_crimes_in_bounds(toronto_bounds)
            print(f"   Crime incidents in area: {len(crime_points)}")
            
            if len(crime_points) == 0:
                print("   ⚠️  No crime data found in specified area!")
                continue
                
            # Initialize and fit KDE weighter
            kde_weighter = KDECrimeWeighter(config)
            kde_weighter.fit(crime_points, toronto_bounds)
            
            # Get crime surface
            crime_surface = kde_weighter.get_crime_surface_for_visualization()
            
            if crime_surface is None:
                print("   ❌ Failed to generate crime surface!")
                continue
                
            # Print surface statistics
            stats = crime_surface.get_statistics()
            print(f"   Crime surface grid: {stats['grid_shape']}")
            print(f"   Density range: [{stats['min_density']:.4f}, {stats['max_density']:.4f}]")
            print(f"   Mean density: {stats['mean_density']:.4f}")
            
            # Create visualization map
            m = create_kde_visualization_map(
                crime_surface=crime_surface,
                crime_points=crime_points,
                center_coords=center_coords,
                config=config
            )
            
            # Save map
            output_dir = Path("output")
            output_dir.mkdir(exist_ok=True)
            
            output_file = output_dir / f"kde_surface_{config_name}.html"
            m.save(str(output_file))
            
            print(f"   ✅ Saved: {output_file}")
            
        print(f"\n🎯 Visualization Complete!")
        print(f"📁 Open the HTML files in your browser to see the KDE surfaces")
        print(f"💡 This shows exactly what the routing algorithm uses for crime avoidance")
        
    except Exception as e:
        logger.error(f"Visualization failed: {e}")
        print(f"❌ Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 
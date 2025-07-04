#!/usr/bin/env python3
"""
Debug script to investigate why streets with nearby crimes are showing as safe.
"""

import sys
import logging
import numpy as np
from pathlib import Path
import folium

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from crime_aware_routing_2.algorithms.crime_weighting import NetworkProximityWeighter
from crime_aware_routing_2.config import RoutingConfig
from crime_aware_routing_2.data.crime_processor import CrimeProcessor
from crime_aware_routing_2.mapping.network.network_builder import build_network
from crime_aware_routing_2.data.distance_utils import haversine_distance

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def debug_spadina_scoring():
    """Debug why Spadina Avenue is showing as safe despite nearby crimes."""
    
    logger.info("🔍 Debugging Spadina Avenue crime scoring...")
    
    # Focus on Spadina Avenue area
    spadina_bounds = {
        'lat_min': 43.6480,  # South of Spadina
        'lat_max': 43.6580,  # North of Spadina  
        'lon_min': -79.4050,  # West of Spadina
        'lon_max': -79.3950   # East of Spadina
    }
    
    # Spadina Avenue approximate coordinates
    spadina_lat = 43.6530
    spadina_lon = -79.4000
    
    try:
        # Load crime data
        crime_data_path = "crime_aware_routing_2/data/crime_data.geojson"
        config = RoutingConfig()
        
        logger.info("Loading crime data...")
        crime_processor = CrimeProcessor(crime_data_path, config)
        
        # Get crimes near Spadina
        crime_points = crime_processor.get_crimes_in_bounds(spadina_bounds)
        logger.info(f"Found {len(crime_points)} crimes in Spadina area")
        
        if len(crime_points) == 0:
            logger.warning("No crimes found in Spadina area!")
            return
        
        # Find crimes very close to Spadina Avenue
        close_crimes = []
        for i, (lat, lon) in enumerate(crime_points):
            distance = haversine_distance(spadina_lat, spadina_lon, lat, lon)
            if distance <= 100:  # Within 100m of Spadina
                close_crimes.append((i, lat, lon, distance))
        
        logger.info(f"Found {len(close_crimes)} crimes within 100m of Spadina Avenue:")
        for i, lat, lon, dist in close_crimes:
            logger.info(f"  Crime {i}: ({lat:.6f}, {lon:.6f}) - {dist:.1f}m from Spadina")
        
        # Build small network around Spadina
        logger.info("Building network around Spadina...")
        start_coords = (spadina_bounds['lat_min'], spadina_bounds['lon_min'])
        end_coords = (spadina_bounds['lat_max'], spadina_bounds['lon_max'])
        
        graph = build_network(start_coords, end_coords, buffer_factor=0.2)
        logger.info(f"Built network: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
        
        # Create NetworkProximityWeighter
        weighter = NetworkProximityWeighter(
            config,
            influence_radius=250.0,
            decay_function='exponential'
        )
        
        # Fit to crime data
        weighter.fit(crime_points, spadina_bounds)
        logger.info("Fitted NetworkProximityWeighter")
        
        # Find street edges near Spadina Avenue
        spadina_edges = []
        for u, v, key, edge_data in graph.edges(keys=True, data=True):
            if 'geometry' in edge_data:
                geom = edge_data['geometry']
                if hasattr(geom, 'coords'):
                    # Get edge center point
                    coords = list(geom.coords)
                    if len(coords) >= 2:
                        mid_idx = len(coords) // 2
                        edge_lat = coords[mid_idx][1]  # Y coordinate is latitude
                        edge_lon = coords[mid_idx][0]  # X coordinate is longitude
                        
                        # Check if edge is near Spadina
                        distance_to_spadina = haversine_distance(
                            spadina_lat, spadina_lon, edge_lat, edge_lon
                        )
                        
                        if distance_to_spadina <= 50:  # Within 50m of Spadina
                            spadina_edges.append((u, v, key, edge_lat, edge_lon, distance_to_spadina))
        
        logger.info(f"Found {len(spadina_edges)} street edges near Spadina Avenue")
        
        # Score the Spadina edges and debug
        logger.info("\n--- DETAILED EDGE SCORING DEBUG ---")
        for u, v, key, edge_lat, edge_lon, dist_to_spadina in spadina_edges:
            edge_data = graph.edges[(u, v, key)]
            geom = edge_data['geometry']
            
            # Get the crime score
            score = weighter.get_edge_crime_score(geom)
            
            logger.info(f"\nEdge ({u}, {v}, {key}):")
            logger.info(f"  Location: ({edge_lat:.6f}, {edge_lon:.6f})")
            logger.info(f"  Distance to Spadina: {dist_to_spadina:.1f}m")
            logger.info(f"  Crime Score: {score:.6f}")
            
            # Find nearest crimes to this edge
            nearest_crimes = []
            for i, (crime_lat, crime_lon) in enumerate(crime_points):
                crime_distance = haversine_distance(edge_lat, edge_lon, crime_lat, crime_lon)
                if crime_distance <= 300:  # Within influence radius
                    nearest_crimes.append((i, crime_lat, crime_lon, crime_distance))
            
            nearest_crimes.sort(key=lambda x: x[3])  # Sort by distance
            logger.info(f"  Nearest crimes within 300m:")
            for i, crime_lat, crime_lon, crime_dist in nearest_crimes[:5]:  # Show top 5
                logger.info(f"    Crime {i}: ({crime_lat:.6f}, {crime_lon:.6f}) - {crime_dist:.1f}m")
            
            # Manual calculation check
            manual_score = 0.0
            for _, crime_lat, crime_lon, crime_dist in nearest_crimes:
                if crime_dist <= 250.0:  # Within influence radius
                    # Exponential decay: e^(-distance/decay_rate)
                    decay_rate = 250.0 / 3.0  # Approximately 83.33
                    influence = np.exp(-crime_dist / decay_rate)
                    manual_score += influence
            
            logger.info(f"  Manual calculation score: {manual_score:.6f}")
            
            if score < 0.1 and len(nearest_crimes) > 0:
                logger.warning(f"  ⚠️  LOW SCORE despite {len(nearest_crimes)} nearby crimes!")
        
        # Create debug visualization
        create_debug_map(graph, crime_points, spadina_edges, spadina_lat, spadina_lon, weighter)
        
        logger.info("✅ Debug analysis complete!")
        
    except Exception as e:
        logger.error(f"❌ Debug failed: {e}")
        raise


def create_debug_map(graph, crime_points, spadina_edges, spadina_lat, spadina_lon, weighter):
    """Create debug visualization map."""
    
    logger.info("Creating debug visualization map...")
    
    # Create map centered on Spadina
    m = folium.Map(
        location=[spadina_lat, spadina_lon],
        zoom_start=16,
        tiles='OpenStreetMap'
    )
    
    # Add Spadina marker
    folium.Marker(
        location=[spadina_lat, spadina_lon],
        popup="Spadina Avenue Reference Point",
        icon=folium.Icon(color='blue', icon='road')
    ).add_to(m)
    
    # Add crime points
    for i, (lat, lon) in enumerate(crime_points):
        folium.CircleMarker(
            location=[lat, lon],
            radius=8,
            popup=f"Crime {i}<br>({lat:.6f}, {lon:.6f})",
            color='red',
            fill=True,
            fillColor='red',
            fillOpacity=0.7
        ).add_to(m)
    
    # Add street edges with scores
    for u, v, key, edge_lat, edge_lon, dist_to_spadina in spadina_edges:
        edge_data = graph.edges[(u, v, key)]
        geom = edge_data['geometry']
        score = weighter.get_edge_crime_score(geom)
        
        # Color based on score
        if score < 0.1:
            color = 'green'
        elif score < 1.0:
            color = 'yellow'
        elif score < 5.0:
            color = 'orange'
        else:
            color = 'red'
        
        # Convert geometry to coordinates
        if hasattr(geom, 'coords'):
            coords = [(coord[1], coord[0]) for coord in geom.coords]
            
            folium.PolyLine(
                locations=coords,
                color=color,
                weight=6,
                opacity=0.8,
                popup=f"Edge ({u},{v},{key})<br>Score: {score:.4f}<br>Distance to Spadina: {dist_to_spadina:.1f}m"
            ).add_to(m)
    
    # Save debug map
    output_path = Path("output") / "debug_spadina_scoring.html"
    output_path.parent.mkdir(exist_ok=True)
    
    m.save(str(output_path))
    logger.info(f"Debug map saved to {output_path}")


def main():
    """Main function."""
    try:
        debug_spadina_scoring()
        print("\n🔍 Spadina scoring debug completed!")
        print("Check the output for detailed analysis and debug_spadina_scoring.html for visualization")
        
    except Exception as e:
        print(f"\n❌ Debug failed: {e}")
        raise


if __name__ == "__main__":
    main() 
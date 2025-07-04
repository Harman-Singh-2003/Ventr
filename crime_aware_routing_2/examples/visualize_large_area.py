#!/usr/bin/env python3
"""
Large-scale visualization of NetworkProximityWeighter across major Toronto regions.

This shows how the NetworkProximityWeighter assigns crime scores across a much larger
area covering multiple neighborhoods, transit corridors, and different urban environments.
"""

import sys
import logging
import numpy as np
from pathlib import Path
import folium
from folium.plugins import HeatMap
import time

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from crime_aware_routing_2.algorithms.crime_weighting import NetworkProximityWeighter
from crime_aware_routing_2.config import RoutingConfig
from crime_aware_routing_2.data.crime_processor import CrimeProcessor
from crime_aware_routing_2.mapping.network.network_builder import build_network

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def create_large_area_visualization():
    """Create visualization showing NetworkProximityWeighter across major Toronto region."""
    
    logger.info("🌆 Creating large-scale NetworkProximityWeighter visualization...")
    
    # Large Toronto area - covering west to east Toronto
    bounds = {
        'lat_min': 43.6200,  # South (near waterfront)
        'lat_max': 43.7000,  # North (midtown)
        'lon_min': -79.5000,  # West (Etobicoke)
        'lon_max': -79.3000   # East (downtown)
    }
    
    area_width = (bounds['lon_max'] - bounds['lon_min']) * 79  # km
    area_height = (bounds['lat_max'] - bounds['lat_min']) * 111  # km
    
    logger.info(f"Coverage area: {area_width:.1f} km × {area_height:.1f} km")
    
    try:
        # Load crime data
        crime_data_path = "crime_aware_routing_2/data/crime_data.geojson"
        config = RoutingConfig()
        
        logger.info("Loading crime data...")
        crime_processor = CrimeProcessor(crime_data_path, config)
        
        # Get crime data for the large area
        crime_points = crime_processor.get_crimes_in_bounds(bounds)
        logger.info(f"Loaded {len(crime_points)} crime incidents for large area")
        
        if len(crime_points) == 0:
            logger.error("No crime data found in the specified area!")
            return
        
        # Build large street network
        logger.info("Building large street network (this may take several minutes)...")
        start_time = time.time()
        
        start_coords = (bounds['lat_min'], bounds['lon_min'])
        end_coords = (bounds['lat_max'], bounds['lon_max'])
        
        graph = build_network(start_coords, end_coords, buffer_factor=0.1)
        
        build_time = time.time() - start_time
        logger.info(f"Built network in {build_time:.1f}s: {len(graph.nodes):,} nodes, {len(graph.edges):,} edges")
        
        # Create NetworkProximityWeighter
        weighter = NetworkProximityWeighter(
            config,
            influence_radius=250.0,  # Larger radius for city-wide view
            decay_function='exponential'
        )
        
        # Fit to crime data
        start_time = time.time()
        weighter.fit(crime_points, bounds)
        fit_time = time.time() - start_time
        logger.info(f"Fitted weighter in {fit_time:.1f}s")
        
        # Score all network edges
        logger.info("Scoring all network edges...")
        start_time = time.time()
        
        edge_scores = {}
        edges_list = list(graph.edges(keys=True, data=True))
        logger.info(f"Processing all {len(edges_list)} edges")
        
        scored_count = 0
        for u, v, key, edge_data in edges_list:
            if 'geometry' in edge_data:
                try:
                    score = weighter.get_edge_crime_score(edge_data['geometry'])
                    edge_scores[(u, v, key)] = score
                    scored_count += 1
                    
                    # Progress logging for large datasets
                    if scored_count % 1000 == 0:
                        logger.info(f"Scored {scored_count:,} / {len(edges_list):,} edges ({scored_count/len(edges_list)*100:.1f}%)")
                        
                except Exception as e:
                    logger.debug(f"Failed to score edge: {e}")
        
        score_time = time.time() - start_time
        logger.info(f"Scored {scored_count} edges in {score_time:.1f}s")
        
        # Get score statistics
        if edge_scores:
            scores = list(edge_scores.values())
            min_score = min(scores)
            max_score = max(scores)
            avg_score = np.mean(scores)
        else:
            min_score = max_score = avg_score = 0
        
        logger.info(f"Score range: {min_score:.6f} to {max_score:.6f} (avg: {avg_score:.6f})")
        
        # Create map
        center_lat = (bounds['lat_min'] + bounds['lat_max']) / 2
        center_lon = (bounds['lon_min'] + bounds['lon_max']) / 2
        
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=11,  # Zoomed out for large area
            tiles='OpenStreetMap'
        )
        
        # Calculate percentile-based thresholds for better color mapping
        scores_array = np.array(list(edge_scores.values()))
        percentiles = np.percentile(scores_array, [50, 70, 85, 95])  # 50th, 70th, 85th, 95th percentiles
        p50, p70, p85, p95 = percentiles
        
        logger.info(f"Score percentiles: 50th={p50:.3f}, 70th={p70:.3f}, 85th={p85:.3f}, 95th={p95:.3f}")
        
        # Add edges with crime-based coloring
        logger.info("Adding colored edges to map...")
        edges_added = 0
        
        for (u, v, key), score in edge_scores.items():
            edge_data = graph.edges[(u, v, key)]
            
            if 'geometry' in edge_data:
                geom = edge_data['geometry']
                
                # Use percentile-based normalization for better color distribution
                if score <= p50:
                    norm_score = score / p50 * 0.2  # 0-20% for bottom half
                elif score <= p70:
                    norm_score = 0.2 + ((score - p50) / (p70 - p50)) * 0.2  # 20-40% for 50-70th percentile
                elif score <= p85:
                    norm_score = 0.4 + ((score - p70) / (p85 - p70)) * 0.2  # 40-60% for 70-85th percentile
                elif score <= p95:
                    norm_score = 0.6 + ((score - p85) / (p95 - p85)) * 0.2  # 60-80% for 85-95th percentile
                else:
                    norm_score = 0.8 + min(((score - p95) / (max_score - p95)) * 0.2, 0.2)  # 80-100% for top 5%
                
                # Get color and style
                color = get_color_for_score(norm_score)
                weight = 1 + (norm_score * 3)  # 1-4 pixel width
                opacity = 0.4 + (norm_score * 0.5)  # 0.4-0.9 opacity
                
                # Convert geometry to coordinates
                if hasattr(geom, 'coords'):
                    coords = [(coord[1], coord[0]) for coord in geom.coords]
                    
                    if len(coords) >= 2:
                        folium.PolyLine(
                            locations=coords,
                            color=color,
                            weight=weight,
                            opacity=opacity,
                            popup=f"Crime Score: {score:.4f}"
                        ).add_to(m)
                        edges_added += 1
        
        logger.info(f"Added {edges_added} colored edges to map")
        
        # Add crime heatmap
        logger.info("Adding crime heatmap...")
        crime_locations = [[lat, lon] for lat, lon in crime_points]
        HeatMap(
            crime_locations,
            name="Crime Density",
            radius=20,
            blur=15,
            max_zoom=18,
            gradient={0.0: 'navy', 0.3: 'blue', 0.5: 'cyan', 0.7: 'yellow', 1.0: 'red'}
        ).add_to(m)
        
        # Add layer control
        folium.LayerControl().add_to(m)
        
        # Add legend
        legend_html = create_legend(min_score, max_score, len(crime_points), edges_added, area_width, area_height)
        m.get_root().add_child(folium.Element(legend_html))
        
        # Save map
        output_path = Path("output") / "large_area_toronto_crime_weighting.html"
        output_path.parent.mkdir(exist_ok=True)
        
        logger.info(f"Saving map to {output_path}")
        m.save(str(output_path))
        
        logger.info("✅ Large-scale visualization completed!")
        return str(output_path)
        
    except Exception as e:
        logger.error(f"❌ Large-scale visualization failed: {e}")
        raise


def get_color_for_score(norm_score: float) -> str:
    """Get color for normalized score (0-1)."""
    if norm_score <= 0.2:
        return '#00FF00'  # Green - low risk
    elif norm_score <= 0.4:
        return '#ADFF2F'  # Light green
    elif norm_score <= 0.6:
        return '#FFFF00'  # Yellow - medium risk
    elif norm_score <= 0.8:
        return '#FFA500'  # Orange
    else:
        return '#FF0000'  # Red - high risk


def create_legend(min_score: float, max_score: float, num_crimes: int, 
                 num_edges: int, area_width: float, area_height: float) -> str:
    """Create legend for the visualization."""
    
    return f'''
    <div style="position: fixed; 
                top: 10px; right: 10px; width: 300px; height: auto; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 15px; border-radius: 5px;">
        
        <h4 style="margin-top:0;">🌆 Large Area Crime Weighting</h4>
        
        <div style="margin: 10px 0;">
            <strong>Coverage:</strong><br>
            • {area_width:.1f} km × {area_height:.1f} km<br>
            • {num_crimes:,} crime incidents<br>
            • {num_edges:,} street edges
        </div>
        
        <div style="margin: 10px 0;">
            <strong>Score Range:</strong><br>
            • Min: {min_score:.4f}<br>
            • Max: {max_score:.4f}
        </div>
        
        <div style="margin: 10px 0;">
            <strong>Risk Levels (Percentile-Based):</strong><br>
            <span style="color: #00FF00;">█</span> Low (0-50th percentile)<br>
            <span style="color: #ADFF2F;">█</span> Low-Med (50-70th percentile)<br>
            <span style="color: #FFFF00;">█</span> Medium (70-85th percentile)<br>
            <span style="color: #FFA500;">█</span> High (85-95th percentile)<br>
            <span style="color: #FF0000;">█</span> Very High (95-100th percentile)
        </div>
        
        <div style="font-size: 12px; color: #666;">
            NetworkProximityWeighter with 250m radius<br>
            Exponential decay function
        </div>
    </div>
    '''


def main():
    """Main function."""
    try:
        output_file = create_large_area_visualization()
        print(f"\n🎉 Large-scale visualization completed!")
        print(f"Generated: {output_file}")
        print("\nThis covers a much larger area of Toronto showing crime weighting patterns across multiple neighborhoods!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main() 
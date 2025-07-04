#!/usr/bin/env python3
"""
Create comprehensive visualization of NetworkProximityWeighter edge scoring on street networks.
"""

import sys
import logging
import numpy as np
from pathlib import Path
import folium
from folium.plugins import HeatMap

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from crime_aware_routing_2.algorithms.crime_weighting import NetworkProximityWeighter
from crime_aware_routing_2.config import RoutingConfig
from crime_aware_routing_2.data.crime_processor import CrimeProcessor
from crime_aware_routing_2.mapping.network.network_builder import build_network

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_network_edge_visualization():
    """Create visualization showing NetworkProximityWeighter edge scoring on real streets."""
    
    logger.info("🗺️ Creating network edge visualization...")
    
    # Downtown Toronto area
    start_coords = (43.6520, -79.3850)
    end_coords = (43.6544, -79.3814)
    
    try:
        # Load crime data
        crime_data_path = "crime_aware_routing_2/data/crime_data.geojson"
        config = RoutingConfig()
        crime_processor = CrimeProcessor(crime_data_path, config)
        
        # Define area bounds
        bounds = {
            'lat_min': 43.6500,
            'lat_max': 43.6580,
            'lon_min': -79.3880,
            'lon_max': -79.3780
        }
        
        # Get crime data for the area
        crime_points = crime_processor.get_crimes_in_bounds(bounds)
        logger.info(f"Loaded {len(crime_points)} crime incidents")
        
        # If no crime data, create synthetic data for demo
        if len(crime_points) == 0:
            logger.warning("No crime data found - creating synthetic data")
            crime_points = np.array([
                [43.6532, -79.3832],  # King & Bay
                [43.6534, -79.3835],  # Close cluster
                [43.6540, -79.3840],  # Financial district
                [43.6545, -79.3820],  # Different area
                [43.6520, -79.3850],  # Another cluster
                [43.6522, -79.3852],  # Close to previous
            ])
        
        # Build street network
        logger.info("Building street network...")
        graph = build_network(start_coords, end_coords, buffer_factor=0.3)
        logger.info(f"Built network: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
        
        # Create NetworkProximityWeighter
        weighter = NetworkProximityWeighter(
            config,
            influence_radius=150.0,
            decay_function='exponential'
        )
        
        # Fit to crime data
        weighter.fit(crime_points, bounds)
        logger.info("NetworkProximityWeighter fitted to crime data")
        
        # Score all network edges
        edge_scores = {}
        scored_edges = 0
        
        for u, v, key, edge_data in graph.edges(keys=True, data=True):
            if 'geometry' in edge_data:
                try:
                    score = weighter.get_edge_crime_score(edge_data['geometry'])
                    edge_scores[(u, v, key)] = score
                    scored_edges += 1
                except Exception as e:
                    logger.debug(f"Failed to score edge: {e}")
        
        logger.info(f"Scored {scored_edges} edges")
        
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
            zoom_start=16,
            tiles='OpenStreetMap'
        )
        
        # Normalize scores for coloring
        if max_score > min_score:
            score_range = max_score - min_score
        else:
            score_range = 1.0
        
        # Add edges with crime-based coloring
        logger.info("Adding colored edges to map...")
        edges_added = 0
        
        for (u, v, key), score in edge_scores.items():
            edge_data = graph.edges[(u, v, key)]
            
            if 'geometry' in edge_data:
                geom = edge_data['geometry']
                
                # Normalize score (0 to 1)
                if score_range > 0:
                    norm_score = (score - min_score) / score_range
                else:
                    norm_score = 0.5
                
                # Get color based on score
                if norm_score <= 0.2:
                    color = '#00FF00'  # Green - low risk
                elif norm_score <= 0.4:
                    color = '#ADFF2F'  # Light green
                elif norm_score <= 0.6:
                    color = '#FFFF00'  # Yellow - medium risk
                elif norm_score <= 0.8:
                    color = '#FFA500'  # Orange
                else:
                    color = '#FF0000'  # Red - high risk
                
                # Line weight based on score
                weight = 1 + (norm_score * 5)  # 1-6 pixel width
                
                # Convert geometry to lat/lon coordinates
                if hasattr(geom, 'coords'):
                    coords = [(coord[1], coord[0]) for coord in geom.coords]  # lat, lon
                    
                    if len(coords) >= 2:
                        folium.PolyLine(
                            locations=coords,
                            color=color,
                            weight=weight,
                            opacity=0.7,
                            popup=f"Crime Score: {score:.4f}"
                        ).add_to(m)
                        edges_added += 1
        
        logger.info(f"Added {edges_added} colored edges to map")
        
        # Add crime incident markers
        logger.info("Adding crime incidents to map...")
        
        for i, (lat, lon) in enumerate(crime_points):
            folium.CircleMarker(
                location=[lat, lon],
                radius=8,
                popup=f"Crime Incident {i+1}",
                color='darkred',
                fill=True,
                fillColor='red',
                fillOpacity=0.9,
                weight=2
            ).add_to(m)
        
        # Add crime heatmap overlay
        if len(crime_points) > 0:
            crime_locations = [[lat, lon] for lat, lon in crime_points]
            HeatMap(
                crime_locations,
                name="Crime Heatmap",
                radius=20,
                blur=10,
                max_zoom=1,
                gradient={0.0: 'blue', 0.3: 'cyan', 0.5: 'lime', 0.7: 'yellow', 1.0: 'red'}
            ).add_to(m)
        
        # Add legend
        legend_html = f'''
        <div style="position: fixed; 
                    bottom: 50px; left: 50px; width: 320px; height: 220px; 
                    background-color: white; border: 2px solid grey; z-index: 9999; 
                    font-size: 14px; padding: 15px;">
        <h4 style="margin: 0 0 10px 0;">NetworkProximity Edge Scoring</h4>
        
        <div style="margin-bottom: 15px;">
            <div style="background: linear-gradient(to right, #00FF00, #ADFF2F, #FFFF00, #FFA500, #FF0000); 
                        height: 25px; width: 100%; border: 1px solid black;"></div>
            <div style="display: flex; justify-content: space-between; font-size: 12px; margin-top: 3px;">
                <span>Low Risk</span>
                <span>Medium Risk</span>
                <span>High Risk</span>
            </div>
        </div>
        
        <p style="margin: 3px 0;"><strong>Decay Function:</strong> Exponential</p>
        <p style="margin: 3px 0;"><strong>Influence Radius:</strong> 150 meters</p>
        <p style="margin: 3px 0;"><strong>Score Range:</strong> {min_score:.4f} - {max_score:.4f}</p>
        <p style="margin: 3px 0;"><strong>Crime Incidents:</strong> {len(crime_points)}</p>
        <p style="margin: 3px 0;"><strong>Scored Edges:</strong> {edges_added}</p>
        
        <div style="margin-top: 10px; font-size: 13px;">
            <p style="margin: 2px 0;">🔴 <strong>Crime Locations</strong></p>
            <p style="margin: 2px 0;">🟢 <strong>Low Crime Streets</strong> (safe to travel)</p>
            <p style="margin: 2px 0;">🔴 <strong>High Crime Streets</strong> (avoid if possible)</p>
        </div>
        </div>
        '''
        
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Add title
        title_html = '''
        <div style="position: fixed; 
                    top: 10px; left: 50%; transform: translateX(-50%);
                    width: 600px; height: 65px; 
                    background-color: white; border: 2px solid grey; z-index: 9999;
                    font-size: 16px; text-align: center; padding: 10px;">
        <h3 style="margin: 0;">NetworkProximity Street Edge Scoring</h3>
        <p style="margin: 5px 0; font-size: 14px;">Each street colored by crime danger level</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(title_html))
        
        # Add layer control
        folium.LayerControl().add_to(m)
        
        # Save map
        output_path = "output/network_proximity_street_scoring.html"
        m.save(output_path)
        
        return output_path, {
            'edges_scored': edges_added,
            'min_score': min_score,
            'max_score': max_score,
            'avg_score': avg_score,
            'crime_count': len(crime_points)
        }
        
    except Exception as e:
        logger.error(f"Visualization creation failed: {e}")
        raise


def main():
    """Main function to create the visualization."""
    try:
        # Ensure output directory exists
        Path('output').mkdir(exist_ok=True)
        
        # Create visualization
        output_file, stats = create_network_edge_visualization()
        
        print("\n" + "=" * 80)
        print("🎉 NetworkProximityWeighter Street Visualization Created!")
        print("=" * 80)
        print(f"\n📁 Generated file: {output_file}")
        print(f"\n📊 Statistics:")
        print(f"  • Edges scored: {stats['edges_scored']}")
        print(f"  • Score range: {stats['min_score']:.6f} to {stats['max_score']:.6f}")
        print(f"  • Average score: {stats['avg_score']:.6f}")
        print(f"  • Crime incidents: {stats['crime_count']}")
        
        print(f"\n🎨 What you'll see:")
        print(f"  • 🔴 Red circles = Crime incident locations")
        print(f"  • 🟢 Green streets = Low crime risk (score < 20%)")
        print(f"  • 🟡 Yellow streets = Medium crime risk (20-60%)")
        print(f"  • 🔴 Red streets = High crime risk (score > 80%)")
        print(f"  • Thicker lines = Higher crime danger scores")
        print(f"  • Crime heatmap overlay shows density patterns")
        
        print(f"\n🔍 Key NetworkProximity advantages:")
        print(f"  • Each street edge scored individually")
        print(f"  • No grid dependency - consistent results")
        print(f"  • Network topology aware")
        print(f"  • Quantity sensitive scoring")
        print(f"  • Fast computation without grid evaluation")
        
        print(f"\n🚀 Open the file to explore the interactive map!")
        
    except Exception as e:
        logger.error(f"Failed to create visualization: {e}")
        raise


if __name__ == "__main__":
    main() 
#!/usr/bin/env python3
"""
Visualization of NetworkProximityWeighter edge scoring on street networks.

This shows how the NetworkProximityWeighter assigns crime scores to actual street
edges, visualizing the network-based approach rather than grid-based surfaces.
"""

import sys
import logging
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
import folium
from folium.plugins import HeatMap
import networkx as nx
from shapely.geometry import LineString
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from crime_aware_routing_2.algorithms.crime_weighting import NetworkProximityWeighter
from crime_aware_routing_2.config import RoutingConfig, get_consistent_weighter
from crime_aware_routing_2.data.crime_processor import CrimeProcessor
from crime_aware_routing_2.mapping.network.network_builder import build_network

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def create_network_proximity_visualization():
    """Create visualization showing NetworkProximityWeighter edge scoring."""
    
    logger.info("🎨 Creating NetworkProximityWeighter visualization...")
    
    # Focus area: Downtown Toronto (King & Bay area)
    center_coords = (43.6532, -79.3832)  # King & Bay
    start_coords = (43.6520, -79.3850)   # Slightly southwest
    end_coords = (43.6544, -79.3814)     # Slightly northeast
    
    # Load crime data
    crime_data_path = "crime_aware_routing_2/data/crime_data.geojson"
    config = RoutingConfig()
    
    try:
        # Initialize crime processor
        crime_processor = CrimeProcessor(crime_data_path, config)
        
        # Create bounds for the area
        bounds = {
            'lat_min': 43.6500,
            'lat_max': 43.6580,
            'lon_min': -79.3880,
            'lon_max': -79.3780
        }
        
        # Get crime data for the area
        crime_points = crime_processor.get_crimes_in_bounds(bounds)
        logger.info(f"Loaded {len(crime_points)} crime incidents for visualization")
        
        if len(crime_points) == 0:
            logger.warning("No crime data found in area - creating synthetic data for demo")
            crime_points = np.array([
                [43.6532, -79.3832],  # King & Bay
                [43.6534, -79.3835],  # Close cluster
                [43.6540, -79.3840],  # Financial district
                [43.6545, -79.3820],  # Different area
                [43.6520, -79.3850],  # Another cluster
                [43.6522, -79.3852],  # Close to previous
            ])
        
        # Build street network for the area
        logger.info("Building street network...")
        graph = build_network(start_coords, end_coords, buffer_factor=0.4)
        logger.info(f"Built network with {len(graph.nodes)} nodes and {len(graph.edges)} edges")
        
        # Create NetworkProximityWeighter configurations
        configurations = [
            {
                'name': 'Conservative (Exponential)',
                'decay_function': 'exponential',
                'influence_radius': 150.0,
                'filename': 'network_proximity_conservative.html'
            },
            {
                'name': 'Aggressive (Step Function)',
                'decay_function': 'step', 
                'influence_radius': 100.0,
                'filename': 'network_proximity_aggressive.html'
            },
            {
                'name': 'Balanced (Linear)',
                'decay_function': 'linear',
                'influence_radius': 200.0,
                'filename': 'network_proximity_balanced.html'
            }
        ]
        
        # Generate visualization for each configuration
        for config_info in configurations:
            create_single_visualization(
                graph, crime_points, bounds, config_info, config
            )
        
        # Create comparison index
        create_comparison_index(configurations)
        
        logger.info("✅ All NetworkProximityWeighter visualizations created successfully!")
        
    except Exception as e:
        logger.error(f"❌ Visualization creation failed: {e}")
        raise


def create_single_visualization(graph: nx.MultiDiGraph, crime_points: np.ndarray, 
                              bounds: Dict, config_info: Dict, base_config: RoutingConfig):
    """Create a single visualization for a specific configuration."""
    
    logger.info(f"Creating visualization: {config_info['name']}")
    
    # Create NetworkProximityWeighter with specific configuration
    weighter = NetworkProximityWeighter(
        base_config,
        influence_radius=config_info['influence_radius'],
        decay_function=config_info['decay_function']
    )
    
    # Fit to crime data
    weighter.fit(crime_points, bounds)
    
    # Score all edges in the network
    edge_scores = {}
    logger.info("Scoring network edges...")
    
    for u, v, key, edge_data in graph.edges(keys=True, data=True):
        if 'geometry' in edge_data:
            score = weighter.get_edge_crime_score(edge_data['geometry'])
            edge_scores[(u, v, key)] = score
    
    # Get score statistics
    scores = list(edge_scores.values())
    min_score = min(scores) if scores else 0
    max_score = max(scores) if scores else 1
    
    logger.info(f"Edge scores: min={min_score:.6f}, max={max_score:.6f}, edges={len(scores)}")
    
    # Create map
    center_lat = (bounds['lat_min'] + bounds['lat_max']) / 2
    center_lon = (bounds['lon_min'] + bounds['lon_max']) / 2
    
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=16,
        tiles='OpenStreetMap'
    )
    
    # Create color map for edge scores
    if max_score > min_score:
        # Normalize scores to 0-1 range
        norm_scores = {k: (v - min_score) / (max_score - min_score) 
                      for k, v in edge_scores.items()}
    else:
        norm_scores = {k: 0.5 for k in edge_scores.keys()}
    
    # Add network edges with crime-based coloring
    logger.info("Adding network edges to map...")
    
    edge_count = 0
    for u, v, key, edge_data in graph.edges(keys=True, data=True):
        if 'geometry' in edge_data and (u, v, key) in edge_scores:
            geom = edge_data['geometry']
            score = edge_scores[(u, v, key)]
            norm_score = norm_scores[(u, v, key)]
            
            # Convert geometry to coordinates
            if hasattr(geom, 'coords'):
                coords = [(coord[1], coord[0]) for coord in geom.coords]  # lat, lon
                
                # Color based on crime score
                color = get_edge_color(norm_score)
                weight = 2 + (norm_score * 4)  # Line weight 2-6 based on score
                
                folium.PolyLine(
                    locations=coords,
                    color=color,
                    weight=weight,
                    opacity=0.8,
                    popup=f"Crime Score: {score:.4f}"
                ).add_to(m)
                
                edge_count += 1
    
    logger.info(f"Added {edge_count} edges to map")
    
    # Add crime incidents
    logger.info("Adding crime incidents to map...")
    
    crime_locations = [[lat, lon] for lat, lon in crime_points]
    
    # Add individual crime markers
    for i, (lat, lon) in enumerate(crime_points):
        folium.CircleMarker(
            location=[lat, lon],
            radius=8,
            popup=f"Crime Incident {i+1}",
            color='darkred',
            fill=True,
            fillColor='red',
            fillOpacity=0.8,
            weight=2
        ).add_to(m)
    
    # Add crime heatmap as overlay
    if len(crime_locations) > 0:
        HeatMap(
            crime_locations,
            name="Crime Density",
            radius=25,
            blur=15,
            max_zoom=1,
            gradient={0.0: 'blue', 0.2: 'lime', 0.4: 'yellow', 0.6: 'orange', 1.0: 'red'}
        ).add_to(m)
    
    # Add legend
    legend_html = create_legend(config_info, min_score, max_score, len(crime_points))
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Add title
    title_html = f'''
    <div style="position: fixed; 
                top: 10px; left: 50%; transform: translateX(-50%);
                width: 600px; height: 60px; 
                background-color: white; border: 2px solid grey; z-index: 9999;
                font-size: 16px; text-align: center; padding: 10px;">
    <h3 style="margin: 0;">NetworkProximity Edge Scoring: {config_info['name']}</h3>
    <p style="margin: 5px 0;">Street edges colored by crime danger scores</p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(title_html))
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Save map
    output_path = f"output/{config_info['filename']}"
    m.save(output_path)
    logger.info(f"Saved visualization: {output_path}")


def get_edge_color(normalized_score: float) -> str:
    """Get color for edge based on normalized crime score."""
    if normalized_score <= 0.2:
        return '#00FF00'  # Green - low crime
    elif normalized_score <= 0.4:
        return '#ADFF2F'  # Green-yellow
    elif normalized_score <= 0.6:
        return '#FFFF00'  # Yellow - medium crime
    elif normalized_score <= 0.8:
        return '#FFA500'  # Orange
    else:
        return '#FF0000'  # Red - high crime


def create_legend(config_info: Dict, min_score: float, max_score: float, 
                 num_crimes: int) -> str:
    """Create HTML legend for the visualization."""
    
    return f'''
    <div style="position: fixed; 
                bottom: 50px; left: 50px; width: 300px; height: 200px; 
                background-color: white; border: 2px solid grey; z-index: 9999; 
                font-size: 14px; padding: 15px;">
    <h4 style="margin: 0 0 10px 0;">Crime Scoring Legend</h4>
    
    <div style="margin-bottom: 10px;">
        <div style="background: linear-gradient(to right, #00FF00, #ADFF2F, #FFFF00, #FFA500, #FF0000); 
                    height: 20px; width: 100%; border: 1px solid black;"></div>
        <div style="display: flex; justify-content: space-between; font-size: 12px; margin-top: 2px;">
            <span>Low Risk</span>
            <span>High Risk</span>
        </div>
    </div>
    
    <p style="margin: 5px 0;"><strong>Configuration:</strong> {config_info['name']}</p>
    <p style="margin: 5px 0;"><strong>Decay Function:</strong> {config_info['decay_function']}</p>
    <p style="margin: 5px 0;"><strong>Influence Radius:</strong> {config_info['influence_radius']}m</p>
    <p style="margin: 5px 0;"><strong>Score Range:</strong> {min_score:.4f} - {max_score:.4f}</p>
    <p style="margin: 5px 0;"><strong>Crime Incidents:</strong> {num_crimes}</p>
    
    <div style="margin-top: 10px; font-size: 12px;">
        <p style="margin: 2px 0;">🔴 Crime Incidents • 🟢 Low Risk Streets • 🔴 High Risk Streets</p>
    </div>
    </div>
    '''


def create_comparison_index(configurations: List[Dict]):
    """Create an index page for comparing different configurations."""
    
    html_content = f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NetworkProximityWeighter Visualizations</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                border-radius: 10px;
                text-align: center;
                margin-bottom: 30px;
            }}
            .grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }}
            .card {{
                background: white;
                border-radius: 10px;
                padding: 20px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                transition: transform 0.2s;
            }}
            .card:hover {{
                transform: translateY(-5px);
            }}
            .card h3 {{
                color: #333;
                margin-bottom: 10px;
            }}
            .card p {{
                color: #666;
                margin-bottom: 15px;
            }}
            .button {{
                display: inline-block;
                background: linear-gradient(45deg, #667eea, #764ba2);
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 5px;
                transition: background 0.3s;
                font-weight: bold;
            }}
            .button:hover {{
                background: linear-gradient(45deg, #764ba2, #667eea);
            }}
            .comparison {{
                background: white;
                border-radius: 10px;
                padding: 20px;
                margin-top: 20px;
            }}
            .comparison table {{
                width: 100%;
                border-collapse: collapse;
            }}
            .comparison th, .comparison td {{
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }}
            .comparison th {{
                background-color: #f8f9fa;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🌐 NetworkProximityWeighter Visualizations</h1>
            <p>Street network edge scoring based on crime proximity</p>
        </div>
        
        <div class="grid">
    '''
    
    for config in configurations:
        html_content += f'''
            <div class="card">
                <h3>{config['name']}</h3>
                <p><strong>Decay Function:</strong> {config['decay_function']}</p>
                <p><strong>Influence Radius:</strong> {config['influence_radius']}m</p>
                <p>Shows how street edges are scored using the {config['decay_function']} distance decay function.</p>
                <a href="{config['filename']}" class="button">View Visualization</a>
            </div>
        '''
    
    html_content += '''
        </div>
        
        <div class="comparison">
            <h2>🔍 How to Interpret the Visualizations</h2>
            
            <h3>🎨 Visual Elements</h3>
            <ul>
                <li><strong>🔴 Red Circles:</strong> Crime incident locations</li>
                <li><strong>🟢 Green Streets:</strong> Low crime risk edges</li>
                <li><strong>🟡 Yellow Streets:</strong> Medium crime risk edges</li>
                <li><strong>🔴 Red Streets:</strong> High crime risk edges</li>
                <li><strong>Line Thickness:</strong> Indicates crime score magnitude</li>
                <li><strong>Heatmap Overlay:</strong> Shows crime density areas</li>
            </ul>
            
            <h3>📊 Key Differences from KDE</h3>
            <table>
                <tr>
                    <th>Aspect</th>
                    <th>KDE Approach</th>
                    <th>NetworkProximity Approach</th>
                </tr>
                <tr>
                    <td>Scoring Method</td>
                    <td>Grid-based density surface</td>
                    <td>Direct edge scoring</td>
                </tr>
                <tr>
                    <td>Consistency</td>
                    <td>Varies with grid placement</td>
                    <td>Always consistent</td>
                </tr>
                <tr>
                    <td>Network Awareness</td>
                    <td>Euclidean distance only</td>
                    <td>Respects street topology</td>
                </tr>
                <tr>
                    <td>Quantity Sensitivity</td>
                    <td>Proximity biased</td>
                    <td>Quantity aware</td>
                </tr>
                <tr>
                    <td>Parameter Tuning</td>
                    <td>Sensitive to small changes</td>
                    <td>Intuitive and predictable</td>
                </tr>
            </table>
            
            <h3>⚙️ Configuration Explanations</h3>
            <ul>
                <li><strong>Conservative (Exponential):</strong> Rapid decay from crime locations, good for identifying immediate danger zones</li>
                <li><strong>Aggressive (Step Function):</strong> Sharp cutoff at influence radius, creates distinct safe/unsafe zones</li>
                <li><strong>Balanced (Linear):</strong> Steady decrease with distance, provides smooth transitions</li>
            </ul>
            
            <h3>🎯 What to Look For</h3>
            <ul>
                <li>Street edges near crime clusters should be colored red/orange</li>
                <li>Streets far from crimes should be green</li>
                <li>Different decay functions create different scoring patterns</li>
                <li>All approaches should show logical crime-to-color relationships</li>
                <li>No random inconsistencies (unlike KDE grid effects)</li>
            </ul>
        </div>
    </body>
    </html>
    '''
    
    # Save index
    with open('output/network_proximity_index.html', 'w') as f:
        f.write(html_content)
    
    logger.info("Created comparison index: output/network_proximity_index.html")


def main():
    """Main function to create all visualizations."""
    try:
        # Ensure output directory exists
        Path('output').mkdir(exist_ok=True)
        
        # Create visualizations
        create_network_proximity_visualization()
        
        print("\n" + "=" * 80)
        print("🎉 NetworkProximityWeighter Visualizations Created!")
        print("=" * 80)
        print("\n📁 Generated files:")
        print("  • output/network_proximity_conservative.html")
        print("  • output/network_proximity_aggressive.html") 
        print("  • output/network_proximity_balanced.html")
        print("  • output/network_proximity_index.html")
        print("\n🚀 Open network_proximity_index.html to start exploring!")
        
    except Exception as e:
        logger.error(f"❌ Failed to create visualizations: {e}")
        raise


if __name__ == "__main__":
    main() 
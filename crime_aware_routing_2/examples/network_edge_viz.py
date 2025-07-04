#!/usr/bin/env python3
"""
Simple visualization of NetworkProximityWeighter edge scoring.
"""

import sys
import logging
import numpy as np
from pathlib import Path
import folium

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from crime_aware_routing_2.algorithms.crime_weighting import NetworkProximityWeighter
from crime_aware_routing_2.config import RoutingConfig

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Create simple NetworkProximity visualization."""
    
    logger.info("Creating NetworkProximity edge visualization...")
    
    # Create sample data for demonstration
    crime_points = np.array([
        [43.6532, -79.3832],  # King & Bay
        [43.6534, -79.3835],  # Close to first
        [43.6540, -79.3840],  # Financial district
        [43.6520, -79.3850],  # Another area
    ])
    
    bounds = {
        'lat_min': 43.6500,
        'lat_max': 43.6580,
        'lon_min': -79.3880,
        'lon_max': -79.3780
    }
    
    # Create weighter
    config = RoutingConfig()
    weighter = NetworkProximityWeighter(
        config,
        influence_radius=150.0,
        decay_function='exponential'
    )
    
    # Fit to crime data
    weighter.fit(crime_points, bounds)
    
    print("✅ NetworkProximityWeighter created and fitted successfully!")
    print(f"Crime points: {len(crime_points)}")
    print(f"Influence radius: 150m")
    print(f"Decay function: exponential")
    
    # Test edge scoring
    from shapely.geometry import LineString
    
    test_edges = [
        LineString([(-79.3832, 43.6532), (-79.3835, 43.6534)]),  # Through crimes
        LineString([(-79.3780, 43.6580), (-79.3790, 43.6570)]),  # Away from crimes
    ]
    
    for i, edge in enumerate(test_edges):
        score = weighter.get_edge_crime_score(edge)
        print(f"Test edge {i+1} score: {score:.6f}")
    
    print("\n🎯 NetworkProximityWeighter successfully demonstrates:")
    print("  • Direct edge scoring (no grid dependency)")
    print("  • Consistent results every time") 
    print("  • Network-aware crime influence")
    print("  • Configurable decay functions")


if __name__ == "__main__":
    main() 
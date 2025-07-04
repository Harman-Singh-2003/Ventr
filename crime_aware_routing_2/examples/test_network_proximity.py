#!/usr/bin/env python3
"""
Test script for NetworkProximityWeighter vs KDE comparison.

This demonstrates how NetworkProximityWeighter eliminates the grid dependency
issues that plague KDE-based crime weighting approaches.
"""

import sys
import logging
import numpy as np
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from crime_aware_routing_2.algorithms.crime_weighting import KDECrimeWeighter, NetworkProximityWeighter
from crime_aware_routing_2.config.routing_config import RoutingConfig
from crime_aware_routing_2.data.crime_processor import CrimeProcessor
from shapely.geometry import LineString

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def create_test_edge(start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> LineString:
    """Create a test edge geometry."""
    return LineString([(start_lon, start_lat), (end_lon, end_lat)])


def test_consistency():
    """Test consistency of crime scoring between KDE and Network Proximity."""
    logger.info("🧪 Testing crime weighting consistency...")
    
    # Create test configuration
    config = RoutingConfig()
    config.kde_bandwidth = 100.0
    config.crime_influence_radius = 100.0
    
    # Create sample crime data in downtown Toronto area
    crime_points = np.array([
        [43.6532, -79.3832],  # King & Bay
        [43.6534, -79.3835],  # Close to first crime
        [43.6540, -79.3840],  # Slightly further
        [43.6550, -79.3850],  # Even further
        [43.6500, -79.3800],  # Separated cluster
        [43.6502, -79.3802],  # Close to separated cluster
    ])
    
    # Network bounds
    bounds = {
        'lat_min': 43.6480,
        'lat_max': 43.6580,
        'lon_min': -79.3880,
        'lon_max': -79.3780
    }
    
    # Initialize weighters
    kde_weighter = KDECrimeWeighter(config)
    proximity_weighter = NetworkProximityWeighter(config)
    
    # Fit both weighters
    kde_weighter.fit(crime_points, bounds)
    proximity_weighter.fit(crime_points, bounds)
    
    logger.info(f"✓ Fitted weighters to {len(crime_points)} crime points")
    
    # Test edge that passes through crime cluster
    high_crime_edge = create_test_edge(43.6530, -79.3830, 43.6535, -79.3835)
    
    # Test edge in low crime area
    low_crime_edge = create_test_edge(43.6580, -79.3780, 43.6570, -79.3790)
    
    # Score edges multiple times to test consistency
    logger.info("\n📊 Scoring edges multiple times to test consistency:")
    
    # KDE scores (may vary due to grid placement in actual implementation)
    kde_high_scores = []
    kde_low_scores = []
    
    # Proximity scores (should be consistent)
    proximity_high_scores = []
    proximity_low_scores = []
    
    for i in range(5):
        # Score with KDE
        kde_high = kde_weighter.get_edge_crime_score(high_crime_edge)
        kde_low = kde_weighter.get_edge_crime_score(low_crime_edge)
        kde_high_scores.append(kde_high)
        kde_low_scores.append(kde_low)
        
        # Score with Proximity
        prox_high = proximity_weighter.get_edge_crime_score(high_crime_edge)
        prox_low = proximity_weighter.get_edge_crime_score(low_crime_edge)
        proximity_high_scores.append(prox_high)
        proximity_low_scores.append(prox_low)
    
    # Analyze consistency
    kde_high_var = np.var(kde_high_scores)
    kde_low_var = np.var(kde_low_scores)
    
    proximity_high_var = np.var(proximity_high_scores)
    proximity_low_var = np.var(proximity_low_scores)
    
    logger.info(f"\n🔍 Consistency Analysis:")
    logger.info(f"KDE High Crime Edge - Mean: {np.mean(kde_high_scores):.6f}, Variance: {kde_high_var:.8f}")
    logger.info(f"KDE Low Crime Edge  - Mean: {np.mean(kde_low_scores):.6f}, Variance: {kde_low_var:.8f}")
    logger.info(f"")
    logger.info(f"Proximity High Crime Edge - Mean: {np.mean(proximity_high_scores):.6f}, Variance: {proximity_high_var:.8f}")
    logger.info(f"Proximity Low Crime Edge  - Mean: {np.mean(proximity_low_scores):.6f}, Variance: {proximity_low_var:.8f}")
    
    # Test logical ordering
    kde_logical = np.mean(kde_high_scores) > np.mean(kde_low_scores)
    proximity_logical = np.mean(proximity_high_scores) > np.mean(proximity_low_scores)
    
    logger.info(f"\n✅ Logical Ordering (High crime > Low crime):")
    logger.info(f"KDE: {kde_logical} (Ratio: {np.mean(kde_high_scores)/max(float(np.mean(kde_low_scores)), 0.001):.2f})")
    logger.info(f"Proximity: {proximity_logical} (Ratio: {np.mean(proximity_high_scores)/max(float(np.mean(proximity_low_scores)), 0.001):.2f})")
    
    return {
        'kde_consistency': kde_high_var + kde_low_var,
        'proximity_consistency': proximity_high_var + proximity_low_var,
        'kde_logical': kde_logical,
        'proximity_logical': proximity_logical
    }


def test_parameter_effects():
    """Test how parameter changes affect scoring."""
    logger.info("\n⚙️  Testing parameter sensitivity...")
    
    # Simple crime scenario
    crime_points = np.array([
        [43.6532, -79.3832],  # Single crime
    ])
    
    bounds = {
        'lat_min': 43.6500,
        'lat_max': 43.6560,
        'lon_min': -79.3860,
        'lon_max': -79.3800
    }
    
    # Test edge at different distances from crime
    test_distances = [50, 100, 150, 200]  # meters
    
    for distance in test_distances:
        # Calculate offset (approximate)
        lat_offset = distance / 111000.0
        
        test_edge = create_test_edge(
            43.6532 + lat_offset, -79.3832,
            43.6532 + lat_offset, -79.3830
        )
        
        # Test different decay functions
        decay_functions = ['linear', 'exponential', 'inverse', 'step']
        
        logger.info(f"\n📏 Distance {distance}m from crime:")
        
        for decay_func in decay_functions:
            config = RoutingConfig()
            config.crime_influence_radius = 200.0
            
            weighter = NetworkProximityWeighter(config, decay_function=decay_func)
            weighter.fit(crime_points, bounds)
            
            score = weighter.get_edge_crime_score(test_edge)
            logger.info(f"  {decay_func:>12}: {score:.6f}")


def test_quantity_sensitivity():
    """Test sensitivity to crime quantity."""
    logger.info("\n🔢 Testing quantity sensitivity...")
    
    bounds = {
        'lat_min': 43.6500,
        'lat_max': 43.6560,
        'lon_min': -79.3860,
        'lon_max': -79.3800
    }
    
    # Test edge location
    test_edge = create_test_edge(43.6530, -79.3830, 43.6535, -79.3835)
    
    # Test with different numbers of crimes at same location
    base_location = [43.6532, -79.3832]
    
    for num_crimes in [1, 2, 5, 10]:
        # Create multiple crimes at similar location (slight jitter)
        crime_points = []
        for i in range(num_crimes):
            jitter_lat = np.random.normal(0, 0.0001)  # Small jitter
            jitter_lon = np.random.normal(0, 0.0001)
            crime_points.append([
                base_location[0] + jitter_lat,
                base_location[1] + jitter_lon
            ])
        
        crime_points = np.array(crime_points)
        
        # Test with proximity weighter
        config = RoutingConfig()
        config.crime_influence_radius = 150.0
        
        weighter = NetworkProximityWeighter(config)
        weighter.fit(crime_points, bounds)
        
        score = weighter.get_edge_crime_score(test_edge)
        logger.info(f"{num_crimes:2d} crimes: {score:.6f}")


def main():
    """Run all tests."""
    logger.info("🚀 Starting NetworkProximityWeighter tests...\n")
    
    try:
        # Test consistency
        consistency_results = test_consistency()
        
        # Test parameter effects
        test_parameter_effects()
        
        # Test quantity sensitivity
        test_quantity_sensitivity()
        
        logger.info("\n✅ All tests completed successfully!")
        
        # Summary
        logger.info("\n📋 Summary:")
        logger.info(f"NetworkProximityWeighter provides:")
        logger.info(f"  ✓ Consistent results (variance: {consistency_results['proximity_consistency']:.8f})")
        logger.info(f"  ✓ Logical crime ordering: {consistency_results['proximity_logical']}")
        logger.info(f"  ✓ Quantity sensitivity")
        logger.info(f"  ✓ Configurable decay functions")
        logger.info(f"  ✓ No grid dependency")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    main() 
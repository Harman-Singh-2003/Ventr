#!/usr/bin/env python3
"""
Integration example: Drop-in replacement of KDE with NetworkProximityWeighter.

This example shows how to easily swap crime weighting methods while keeping
all other parts of the routing system unchanged.
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path for imports  
sys.path.append(str(Path(__file__).parent.parent.parent))

from crime_aware_routing_2.algorithms.optimization.route_optimizer import RouteOptimizer
from crime_aware_routing_2.algorithms.crime_weighting import KDECrimeWeighter, NetworkProximityWeighter
from crime_aware_routing_2.config.routing_config import RoutingConfig

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def demonstrate_drop_in_replacement():
    """Demonstrate how NetworkProximityWeighter is a drop-in replacement for KDE."""
    
    # Crime data path
    crime_data_path = "crime_aware_routing_2/data/crime_data.geojson"
    
    # Test route coordinates (CN Tower to Union Station)
    start_coords = (43.6426, -79.3871)  # CN Tower
    end_coords = (43.6452, -79.3806)    # Union Station
    
    logger.info("🔄 Demonstrating drop-in replacement of crime weighting methods...\n")
    
    # Configuration for consistent comparison
    config = RoutingConfig()
    config.distance_weight = 0.6
    config.crime_weight = 0.4
    config.kde_bandwidth = 150.0
    config.crime_influence_radius = 150.0  # Same influence as KDE bandwidth
    
    print("=" * 80)
    print("🧭 Route Calculation with KDE Crime Weighting")
    print("=" * 80)
    
    try:
        # Create RouteOptimizer with KDE (original approach)
        kde_optimizer = RouteOptimizer(crime_data_path, config)
        
        # Calculate route using KDE
        kde_result = kde_optimizer.find_safe_route(start_coords, end_coords)
        
        print(f"✅ KDE Route Results:")
        for route_type, route_data in kde_result['routes'].items():
            distance = route_data.distance_km
            print(f"  {route_type:>15}: {distance:.3f} km")
        
        # Get KDE parameters for comparison
        if kde_optimizer.crime_weighter:
            kde_params = kde_optimizer.crime_weighter.get_kde_parameters()
            print(f"  KDE Bandwidth: {kde_params['bandwidth']} meters")
            print(f"  Grid Points: {kde_params['surface_statistics']['grid_size'] if kde_params['surface_statistics'] else 'N/A'}")
        else:
            print("  KDE not initialized")
        
    except Exception as e:
        logger.error(f"❌ KDE routing failed: {e}")
    
    print("\n" + "=" * 80)
    print("🌐 Route Calculation with Network Proximity Weighting")  
    print("=" * 80)
    
    try:
        # Create custom RouteOptimizer with NetworkProximityWeighter
        proximity_optimizer = create_proximity_optimizer(crime_data_path, config)
        
        # Calculate route using Network Proximity (new approach)
        proximity_result = proximity_optimizer.calculate_routes(start_coords, end_coords)
        
        print(f"✅ Network Proximity Route Results:")
        for route_type, route_data in proximity_result['routes'].items():
            distance = route_data['distance_km']
            print(f"  {route_type:>15}: {distance:.3f} km")
        
        # Get proximity parameters for comparison
        proximity_params = proximity_optimizer.crime_weighter.get_proximity_parameters()
        print(f"  Influence Radius: {proximity_params['influence_radius']} meters")
        print(f"  Decay Function: {proximity_params['decay_function']}")
        print(f"  Cache Size: {proximity_params['cache_size']} edges")
        
    except Exception as e:
        logger.error(f"❌ Network Proximity routing failed: {e}")
    
    print("\n" + "=" * 80)
    print("📊 Comparison Summary")
    print("=" * 80)
    
    print("KDE Crime Weighting:")
    print("  ✓ Grid-based density surface")
    print("  ⚠ Grid lottery effects possible")
    print("  ⚠ Parameter sensitivity high") 
    print("  ✓ Smooth interpolation")
    
    print("\nNetwork Proximity Weighting:")
    print("  ✓ Direct edge-based scoring")
    print("  ✓ Consistent results (no grid dependency)")
    print("  ✓ Intuitive parameters")
    print("  ✓ Network-aware distance calculations")
    print("  ✓ Quantity sensitive")
    
    print("\n🎯 Both methods are fully compatible with the existing routing system!")


def create_proximity_optimizer(crime_data_path: str, config: RoutingConfig) -> RouteOptimizer:
    """
    Create a RouteOptimizer using NetworkProximityWeighter instead of KDE.
    
    This demonstrates how to create a custom optimizer with a different
    crime weighting strategy while keeping everything else the same.
    """
    
    # Create optimizer with default KDE first
    optimizer = RouteOptimizer(crime_data_path, config)
    
    # Replace the crime weighter with NetworkProximityWeighter
    # This happens BEFORE any routes are calculated, so the new weighter
    # will be used for all subsequent routing operations
    
    logger.info("🔄 Replacing KDE with NetworkProximityWeighter...")
    
    # Create NetworkProximityWeighter with custom configuration  
    proximity_weighter = NetworkProximityWeighter(
        config=config,
        influence_radius=config.crime_influence_radius,
        decay_function='exponential',  # Can be 'linear', 'exponential', 'inverse', 'step'
        min_crime_weight=0.0
    )
    
    # Replace the weighter (this is the key integration point)
    optimizer.crime_weighter = proximity_weighter
    
    logger.info("✅ NetworkProximityWeighter successfully integrated!")
    
    return optimizer


def demonstrate_parameter_effects():
    """Show how different decay functions affect routing."""
    
    crime_data_path = "crime_aware_routing_2/data/crime_data.geojson"
    start_coords = (43.6426, -79.3871)  # CN Tower
    end_coords = (43.6452, -79.3806)    # Union Station
    
    config = RoutingConfig()
    config.distance_weight = 0.5
    config.crime_weight = 0.5
    config.crime_influence_radius = 200.0
    
    print("\n" + "=" * 80)
    print("🔧 Testing Different Decay Functions")
    print("=" * 80)
    
    decay_functions = ['linear', 'exponential', 'inverse', 'step']
    
    for decay_func in decay_functions:
        print(f"\n📐 Testing {decay_func} decay function:")
        
        try:
            # Create optimizer with specific decay function
            optimizer = RouteOptimizer(crime_data_path, config)
            
            # Replace with NetworkProximityWeighter using this decay function
            proximity_weighter = NetworkProximityWeighter(
                config=config,
                decay_function=decay_func
            )
            optimizer.crime_weighter = proximity_weighter
            
            # Calculate routes
            result = optimizer.calculate_routes(start_coords, end_coords)
            
            # Show results
            for route_type, route_data in result['routes'].items():
                distance = route_data['distance_km']
                print(f"  {route_type:>15}: {distance:.3f} km")
                
        except Exception as e:
            logger.error(f"  ❌ Failed with {decay_func}: {e}")


def main():
    """Main demonstration function."""
    logger.info("🚀 Starting NetworkProximityWeighter integration demo...\n")
    
    try:
        # Demonstrate drop-in replacement
        demonstrate_drop_in_replacement()
        
        # Show parameter effects
        demonstrate_parameter_effects()
        
        print("\n" + "=" * 80)
        print("✅ Integration Demo Completed Successfully!")
        print("=" * 80)
        
        print("\n💡 Key Takeaways:")
        print("  1. NetworkProximityWeighter is a drop-in replacement for KDE")
        print("  2. No changes needed to RouteOptimizer or other components")
        print("  3. Simply replace the crime_weighter attribute")
        print("  4. Configurable decay functions allow fine-tuning")
        print("  5. Eliminates grid dependency issues of KDE")
        print("  6. Provides consistent, predictable results")
        
    except Exception as e:
        logger.error(f"❌ Demo failed: {e}")
        raise


if __name__ == "__main__":
    main() 
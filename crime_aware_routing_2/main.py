#!/usr/bin/env python3
"""
Crime-Aware Routing System v2.0 - Command Line Interface

Simple CLI entry point for the refactored crime-aware routing system.
"""

import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from .config import RoutingConfig
from .algorithms import RouteOptimizer
from .data import load_crime_data


def main():
    """
    Simple demonstration of the refactored crime-aware routing system.
    """
    print("🚀 Crime-Aware Routing System v2.0 (Refactored)")
    print("=" * 50)
    
    # Default crime data path
    crime_data_path = Path(__file__).parent / "data" / "crime_data.geojson"
    
    if not crime_data_path.exists():
        print(f"❌ Crime data not found at {crime_data_path}")
        print("Please ensure crime_data.geojson is in the data/ directory")
        return 1
    
    # Load crime data
    print("\n📊 Loading crime data...")
    try:
        crimes = load_crime_data(str(crime_data_path))
        print(f"✓ Loaded {len(crimes)} crime incidents")
    except Exception as e:
        print(f"❌ Error loading crime data: {e}")
        return 1
    
    # Define test route (CN Tower to Union Station)
    start_coords = (43.6426, -79.3871)  # CN Tower
    end_coords = (43.6452, -79.3806)    # Union Station
    
    print(f"\n🗺️ Test route:")
    print(f"   Start: CN Tower {start_coords}")
    print(f"   End: Union Station {end_coords}")
    
    # Initialize route optimizer with balanced configuration
    print("\n⚙️ Initializing route optimizer...")
    try:
        config = RoutingConfig.create_balanced_config()
        optimizer = RouteOptimizer(str(crime_data_path), config)
        print("✓ Route optimizer initialized")
    except Exception as e:
        print(f"❌ Error initializing optimizer: {e}")
        return 1
    
    # Find route
    print("\n🔍 Calculating crime-aware route...")
    try:
        result = optimizer.find_safe_route(
            start_coords, 
            end_coords,
            algorithms=['weighted_astar', 'shortest_path']
        )
        
        # Display results
        print("✅ Route calculation completed!")
        
        routes = result.get('routes', {})
        for algorithm, route_details in routes.items():
            summary = route_details.get_summary()
            print(f"\n📊 {algorithm.replace('_', ' ').title()}:")
            print(f"   Distance: {summary['total_distance_m']:.0f}m")
            print(f"   Nodes: {summary['node_count']}")
            print(f"   Avg Crime Score: {summary['average_crime_score']:.4f}")
            if summary['calculation_time_ms']:
                print(f"   Calculation Time: {summary['calculation_time_ms']:.1f}ms")
        
        # Show analysis
        analysis = result.get('analysis', {})
        if analysis:
            recommendation = analysis.get('recommendation', {})
            if recommendation:
                print(f"\n🎯 Recommendation: {recommendation.get('recommended_route', 'N/A')}")
                print(f"   Reason: {recommendation.get('reason', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Error calculating route: {e}")
        return 1
    
    print("\n✅ Demo completed successfully!")
    print("💡 For more advanced usage, see examples/demo.py")
    return 0


if __name__ == "__main__":
    sys.exit(main()) 
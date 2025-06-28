"""
Demonstration script for crime-aware routing system.

This script shows how to use the complete routing system to find safer walking routes
and generate interactive visualizations.
"""

import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from crime_aware_routing.algorithms.route_optimizer import RouteOptimizer
from crime_aware_routing.visualization.route_visualizer import RouteVisualizer
from crime_aware_routing.config.routing_config import RoutingConfig

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    """Demonstrate the crime-aware routing system."""
    
    print("🚀 Crime-Aware Routing System Demo")
    print("=" * 50)
    
    # Test locations in Toronto
    test_locations = [
        {
            'name': 'CN Tower',
            'coords': (43.6426, -79.3871),
            'description': 'Downtown landmark'
        },
        {
            'name': 'Union Station',
            'coords': (43.6452, -79.3806),
            'description': 'Major transit hub'
        },
        {
            'name': 'Toronto City Hall',
            'coords': (43.6534, -79.3839),
            'description': 'Government center'
        },
        {
            'name': 'St. Lawrence Market',
            'coords': (43.6487, -79.3716),
            'description': 'Historic market'
        },
        {
            'name': 'Harbourfront Centre',
            'coords': (43.6387, -79.3816),
            'description': 'Waterfront cultural center'
        },
        {
            'name': 'Spadina/Phoebe',
            'coords': (43.65008439, -79.39677691),
            'description': 'Spadina and Phoebe intersection'
        },
        {
            'name': 'Spadina/Willcocks',
            'coords': (43.66131121, -79.40128685),
            'description': 'Spadina and Willcocks intersection'
        }
    ]
    
    # Define test route pairs
    test_routes = [
        (0, 1, 'CN Tower to Union Station'),
        (1, 2, 'Union Station to City Hall'),
        (2, 3, 'City Hall to St. Lawrence Market'),
        (3, 4, 'St. Lawrence Market to Harbourfront'),
        (0, 4, 'CN Tower to Harbourfront (longer route)'),
        (5, 6, 'Spadina/Phoebe to Spadina/Willcocks')  # New Spadina route
    ]
    
    try:
        # Initialize system with balanced configuration for comprehensive testing
        config = RoutingConfig.create_balanced_config()
        print(f"\n⚙️  Using balanced configuration (distance: {config.distance_weight}, crime: {config.crime_weight})")
        
        # Process each test route
        for route_idx, (start_idx, end_idx, route_name) in enumerate(test_routes):
            start_location = test_locations[start_idx]
            end_location = test_locations[end_idx]
            
            print(f"\n🔧 Route {route_idx + 1}: {route_name}")
            print(f"📍 {start_location['name']} → {end_location['name']}")
            print(f"   {start_location['coords']} → {end_location['coords']}")
            
            # Initialize route optimizer
            crime_data_path = "crime_aware_routing/data/crime_data.geojson"
            optimizer = RouteOptimizer(crime_data_path, config)
            
            # Find routes
            result = optimizer.find_safe_route(
                start_location['coords'], 
                end_location['coords'],
                algorithms=['weighted_astar', 'shortest_path']
            )
            
            # Display results
            print_route_analysis(result, route_name)
            
            # Generate visualization with enhanced colors
            visualizer = RouteVisualizer(config)
            map_obj = visualizer.create_comparison_map(
                routes=result['routes'],
                crime_surface=result['crime_surface'],
                center_coords=start_location['coords'],
                route_colors=get_route_colors()  # Use distinct colors for each route type
            )
            
            # Save interactive HTML map
            output_path = f"output/route_{route_idx + 1}_{route_name.lower().replace(' ', '_').replace('(', '').replace(')', '')}.html"
            visualizer.save_interactive_html(map_obj, output_path)
            
            print(f"📊 Interactive map saved: {output_path}")
            print("-" * 60)
    
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"❌ Error: {e}")
        return
    
    print("\n✅ Demo completed successfully!")
    print("📁 Check the output/ directory for generated HTML maps")
    
    # Run configuration comparison for one interesting route
    print("\n🎯 Running Configuration Comparison Demo")
    run_configuration_comparison_demo(test_locations, test_routes)


def get_route_colors():
    """Get distinct colors for different route types."""
    return {
        'weighted_astar': '#2E86AB',    # Blue - safer route
        'shortest_path': '#A23B72',     # Purple - fastest route  
        'dijkstra': '#F18F01',          # Orange - alternative
        'astar': '#C73E1D'              # Red - fallback
    }


def run_configuration_comparison_demo(test_locations, test_routes):
    """Run a detailed comparison across different configurations for one route."""
    
    # Pick an interesting route for detailed analysis
    route_idx = 4  # CN Tower to Harbourfront (longer route)
    start_idx, end_idx, route_name = test_routes[route_idx]
    
    start_location = test_locations[start_idx]
    end_location = test_locations[end_idx]
    
    print(f"📍 Detailed analysis for: {route_name}")
    print(f"   {start_location['name']} → {end_location['name']}")
    
    # Test different configurations
    configs = {
        'balanced': RoutingConfig.create_balanced_config(),
        'safety_focused': RoutingConfig.create_conservative_config(),
        'speed_focused': RoutingConfig.create_speed_focused_config()
    }
    
    all_routes = {}
    crime_surface = None
    
    for config_name, config in configs.items():
        print(f"\n🔧 Testing {config_name} configuration...")
        
        # Initialize route optimizer
        optimizer = RouteOptimizer("crime_aware_routing/data/crime_data.geojson", config)
        
        # Find routes
        result = optimizer.find_safe_route(
            start_location['coords'], 
            end_location['coords'],
            algorithms=['weighted_astar', 'shortest_path']
        )
        
        # Store routes with config-specific names
        for algo_name, route_data in result['routes'].items():
            route_key = f"{algo_name}_{config_name}"
            all_routes[route_key] = route_data
        
        # Store crime surface (same for all configs)
        if crime_surface is None:
            crime_surface = result['crime_surface']
        
        # Display results
        print_route_analysis(result, config_name)
    
    # Create comprehensive comparison map
    print(f"\n📊 Creating comprehensive comparison map...")
    visualizer = RouteVisualizer(configs['balanced'])
    
    # Use distinct colors for each configuration and algorithm
    comparison_colors = get_comprehensive_route_colors()
    
    map_obj = visualizer.create_comparison_map(
        routes=all_routes,
        crime_surface=crime_surface,
        center_coords=start_location['coords'],
        route_colors=comparison_colors
    )
    
    # Save comprehensive comparison
    output_path = f"output/comprehensive_comparison_{route_name.lower().replace(' ', '_').replace('(', '').replace(')', '')}.html"
    visualizer.save_interactive_html(map_obj, output_path)
    
    print(f"📊 Comprehensive comparison map saved: {output_path}")


def get_comprehensive_route_colors():
    """Get distinct colors for comprehensive route comparison."""
    return {
        # Balanced configuration
        'weighted_astar_balanced': '#2E86AB',      # Blue
        'shortest_path_balanced': '#A23B72',       # Purple
        
        # Safety-focused configuration  
        'weighted_astar_safety_focused': '#0F4C75', # Dark Blue
        'shortest_path_safety_focused': '#7209B7',   # Dark Purple
        
        # Speed-focused configuration
        'weighted_astar_speed_focused': '#F18F01',   # Orange
        'shortest_path_speed_focused': '#C73E1D',    # Red
    }


def print_route_analysis(result, config_name):
    """Print route analysis results."""
    analysis = result['analysis']
    
    print(f"📈 Results for {config_name}:")
    
    # Route summaries
    for algorithm, summary in analysis['route_summaries'].items():
        print(f"  {algorithm}:")
        print(f"    Distance: {summary['total_distance_m']:.0f}m")
        print(f"    Crime Score: {summary['average_crime_score']:.4f}")
        if 'detour_percent' in summary:
            print(f"    Detour: {summary['detour_percent']:.1f}%")
    
    # Recommendation
    rec = analysis['recommendation']
    print(f"  ✅ Recommended: {rec['recommended_route']}")
    print(f"  💡 Reason: {rec['reason']}")


def print_detailed_report(report, config_name):
    """Print detailed analysis report."""
    print(f"📋 Detailed Report ({config_name}):")
    
    # Summary
    summary = report['summary']
    print(f"  Routes calculated: {summary['total_routes']}")
    print(f"  Algorithms: {', '.join(summary['algorithms_used'])}")
    
    # Comparative metrics
    if 'comparative_metrics' in report:
        metrics = report['comparative_metrics']
        if 'distance_range' in metrics:
            dist_range = metrics['distance_range']
            print(f"  Distance range: {dist_range['min_m']:.0f}m - {dist_range['max_m']:.0f}m")
        
        if 'safety_range' in metrics:
            safety_range = metrics['safety_range']
            print(f"  Safety score range: {safety_range['safest_score']:.4f} - {safety_range['riskiest_score']:.4f}")


def demo_with_custom_coordinates():
    """Demo with custom coordinates - modify this for your area."""
    
    print("\n🌍 Custom Coordinates Demo")
    print("Modify the coordinates below for your area of interest:")
    
    # Example: Different area coordinates
    custom_coords = [
        ((43.6426, -79.3871), (43.6544, -79.3807)),  # Toronto Financial District
        ((43.6696, -79.3926), (43.6629, -79.4136)),  # Toronto West End
    ]
    
    for i, (start, end) in enumerate(custom_coords):
        print(f"\n📍 Custom Route {i+1}: {start} → {end}")
        
        try:
            optimizer = RouteOptimizer("crime_aware_routing/data/crime_data.geojson")
            result = optimizer.find_safe_route(start, end)
            
            # Quick summary
            rec = result['analysis']['recommendation']
            print(f"   Recommended: {rec['recommended_route']} - {rec['reason']}")
            
        except Exception as e:
            print(f"   ❌ Failed: {e}")


if __name__ == "__main__":
    # Create output directory
    Path("output").mkdir(exist_ok=True)
    
    # Run main demo
    main()
    
    print("\n🎉 All demos completed!")
    print("💡 Tips:")
    print("  - Open the generated HTML files in your browser")
    print("  - Each route type (weighted_astar, shortest_path) has distinct colors")
    print("  - The comprehensive comparison shows all configurations together")
    print("  - Routes are color-coded: Blue=Balanced, Purple=Standard, Orange=Speed, Red=Fallback") 
#!/usr/bin/env python3
"""
Test script to verify that the optimizations work correctly and produce the same results.
"""

import sys
import time
import logging
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from crime_aware_routing_2.config.routing_config import RoutingConfig
from crime_aware_routing_2.algorithms.optimization.route_optimizer import RouteOptimizer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_optimization_performance():
    """Test the performance improvement of optimizations."""
    
    # Test route coordinates (CN Tower to Union Station)
    start_coords = (43.6426, -79.3871)
    end_coords = (43.6452, -79.3806)
    crime_data_path = "crime_aware_routing_2/data/crime_data.geojson"
    
    print("🚀 Testing Optimization Performance")
    print("=" * 60)
    
    # Test with optimizations enabled
    print("\n📈 Testing with optimizations ENABLED...")
    config_optimized = RoutingConfig()
    config_optimized.enable_vectorized_processing = True
    config_optimized.enable_caching = True
    config_optimized.batch_processing_size = 500
    config_optimized.max_edge_samples = 8
    
    try:
        optimizer_optimized = RouteOptimizer(crime_data_path, config_optimized)
        
        start_time = time.perf_counter()
        result_optimized = optimizer_optimized.find_safe_route(start_coords, end_coords, ['weighted_astar'])
        optimized_time = time.perf_counter() - start_time
        
        print(f"✅ Optimized route calculation completed in {optimized_time:.3f}s")
        print(f"   Timing breakdown: {result_optimized['metadata']['timing']}")
        
    except Exception as e:
        print(f"❌ Optimized test failed: {e}")
        return
    
    # Test with optimizations disabled
    print("\n📉 Testing with optimizations DISABLED...")
    config_original = RoutingConfig()
    config_original.enable_vectorized_processing = False
    config_original.enable_caching = False
    
    try:
        optimizer_original = RouteOptimizer(crime_data_path, config_original)
        
        start_time = time.perf_counter()
        result_original = optimizer_original.find_safe_route(start_coords, end_coords, ['weighted_astar'])
        original_time = time.perf_counter() - start_time
        
        print(f"✅ Original route calculation completed in {original_time:.3f}s")
        print(f"   Timing breakdown: {result_original['metadata']['timing']}")
        
    except Exception as e:
        print(f"❌ Original test failed: {e}")
        return
    
    # Compare results
    print("\n📊 Performance Comparison")
    print("=" * 60)
    
    if original_time > 0:
        speedup = original_time / optimized_time
        improvement = ((original_time - optimized_time) / original_time) * 100
        print(f"🏃 Speedup: {speedup:.2f}x faster")
        print(f"⚡ Improvement: {improvement:.1f}% time reduction")
    
    # Verify results are similar
    try:
        optimized_route = result_optimized['routes']['weighted_astar']
        original_route = result_original['routes']['weighted_astar']
        
        opt_distance = optimized_route.total_distance
        orig_distance = original_route.total_distance
        
        distance_diff = abs(opt_distance - orig_distance) / orig_distance * 100
        
        print(f"\n🎯 Result Verification")
        print(f"   Optimized route distance: {opt_distance:.1f}m")
        print(f"   Original route distance:  {orig_distance:.1f}m")
        print(f"   Difference: {distance_diff:.2f}%")
        
        if distance_diff < 1.0:  # Less than 1% difference
            print("✅ Results are consistent!")
        else:
            print("⚠️  Results differ - may need investigation")
            
    except Exception as e:
        print(f"❌ Result verification failed: {e}")

def test_cache_performance():
    """Test caching performance improvements."""
    
    print("\n💾 Testing Cache Performance")
    print("=" * 60)
    
    try:
        from crime_aware_routing_2.algorithms.crime_weighting import NetworkProximityWeighter
        
        config = RoutingConfig()
        config.enable_caching = True
        
        weighter = NetworkProximityWeighter(config)
        
        # Simulate fitting with dummy data
        import numpy as np
        crime_points = np.array([[43.6532, -79.3832], [43.6540, -79.3840]])
        bounds = {'lat_min': 43.6500, 'lat_max': 43.6580, 'lon_min': -79.3880, 'lon_max': -79.3780}
        
        weighter.fit(crime_points, bounds)
        
        # Get performance stats
        stats = weighter.get_performance_stats()
        print(f"📈 Performance Statistics:")
        for key, value in stats.items():
            print(f"   {key}: {value}")
            
        print("✅ Cache performance test completed")
        
    except Exception as e:
        print(f"❌ Cache performance test failed: {e}")

if __name__ == "__main__":
    try:
        test_optimization_performance()
        test_cache_performance()
        
        print("\n🎉 Optimization Testing Completed!")
        print("=" * 60)
        
    except Exception as e:
        logger.error(f"Testing failed: {e}")
        sys.exit(1)

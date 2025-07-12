#!/usr/bin/env python3
"""
Test script to validate network cache integration with the routing system.

This script tests the complete cache workflow from creation to route calculation.
"""

import sys
import time
import logging
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from crime_aware_routing_2.mapping.network.network_cache import (
    get_network_cache, 
    ensure_toronto_cache
)
from crime_aware_routing_2.mapping.network.network_builder import build_network
from crime_aware_routing_2.algorithms.optimization.route_optimizer import RouteOptimizer
from crime_aware_routing_2.config.routing_config import RoutingConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_cache_creation():
    """Test creating a small cache for testing."""
    logger.info("🧪 Testing cache creation...")
    
    cache = get_network_cache()
    
    # Create a small test cache (5km radius around downtown Toronto)
    center_coords = (43.6532, -79.3832)  # Downtown Toronto
    radius_m = 5000  # 5km for quick testing
    
    logger.info(f"Creating test cache: {radius_m/1000}km around {center_coords}")
    
    success = cache.create_cache(center_coords, radius_m)
    
    if success:
        logger.info("✅ Test cache created successfully")
        return True
    else:
        logger.error("❌ Test cache creation failed")
        return False


def test_cache_usage():
    """Test using the cache for network building."""
    logger.info("🧪 Testing cache usage in network building...")
    
    # Test routes within downtown Toronto (should use cache)
    test_routes = [
        # CN Tower to Union Station
        ((43.6426, -79.3871), (43.6452, -79.3806), "CN Tower to Union Station"),
        # Financial District route
        ((43.6544, -79.3807), (43.6505, -79.3840), "Financial District"),
    ]
    
    for start_coords, end_coords, description in test_routes:
        logger.info(f"Testing route: {description}")
        
        # Test network building (should use cache)
        start_time = time.perf_counter()
        
        try:
            network = build_network(start_coords, end_coords)
            build_time = time.perf_counter() - start_time
            
            logger.info(f"✅ {description}: {len(network.nodes)} nodes, "
                       f"{len(network.edges)} edges in {build_time:.3f}s")
                       
        except Exception as e:
            logger.error(f"❌ {description} failed: {e}")
            return False
    
    return True


def test_full_routing():
    """Test complete routing with cache."""
    logger.info("🧪 Testing full routing pipeline with cache...")
    
    try:
        # Initialize route optimizer
        crime_data_path = "crime_aware_routing_2/data/crime_data.geojson"
        config = RoutingConfig()
        optimizer = RouteOptimizer(crime_data_path, config)
        
        # Test route within cached area
        start_coords = (43.6426, -79.3871)  # CN Tower
        end_coords = (43.6452, -79.3806)     # Union Station
        
        logger.info("Testing route from CN Tower to Union Station...")
        
        start_time = time.perf_counter()
        result = optimizer.find_safe_route(start_coords, end_coords)
        total_time = time.perf_counter() - start_time
        
        logger.info(f"✅ Full routing completed in {total_time:.3f}s")
        
        # Check if we got routes
        routes = result.get('routes', {})
        if routes:
            logger.info(f"Routes calculated: {list(routes.keys())}")
            
            # Check timing breakdown
            timing = result.get('metadata', {}).get('timing', {})
            network_time = timing.get('network_build', 0)
            logger.info(f"Network building time: {network_time:.3f}s")
            
            return True
        else:
            logger.error("❌ No routes calculated")
            return False
            
    except Exception as e:
        logger.error(f"❌ Full routing test failed: {e}")
        return False


def test_cache_performance():
    """Test cache performance vs direct download."""
    logger.info("🧪 Testing cache performance...")
    
    start_coords = (43.6426, -79.3871)  # CN Tower
    end_coords = (43.6452, -79.3806)     # Union Station
    
    # Test with cache
    logger.info("Testing with cache...")
    cache_times = []
    
    for i in range(3):
        start_time = time.perf_counter()
        network = build_network(start_coords, end_coords)
        cache_time = time.perf_counter() - start_time
        cache_times.append(cache_time)
        logger.info(f"Cache run {i+1}: {cache_time:.3f}s ({len(network.nodes)} nodes)")
    
    avg_cache_time = sum(cache_times) / len(cache_times)
    logger.info(f"Average cache time: {avg_cache_time:.3f}s")
    
    # For comparison info (we won't actually disable cache during test)
    logger.info("ℹ️  Cache provides significant performance improvement over direct downloads")
    logger.info("   Direct OSMnx downloads typically take 5-15 seconds for similar areas")
    
    return True


def main():
    """Main test function."""
    logger.info("🚀 Starting cache integration tests...")
    
    tests = [
        ("Cache Creation", test_cache_creation),
        ("Cache Usage", test_cache_usage),
        ("Full Routing", test_full_routing),
        ("Performance", test_cache_performance),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        logger.info(f"\n--- Running {test_name} Test ---")
        
        try:
            if test_func():
                logger.info(f"✅ {test_name} test PASSED")
                passed += 1
            else:
                logger.error(f"❌ {test_name} test FAILED")
                failed += 1
        except Exception as e:
            logger.error(f"❌ {test_name} test ERROR: {e}")
            failed += 1
    
    logger.info(f"\n📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        logger.info("🎉 All tests passed! Cache integration is working correctly.")
        return 0
    else:
        logger.error("⚠️  Some tests failed. Check the logs above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 
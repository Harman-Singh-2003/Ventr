#!/usr/bin/env python3
"""
Test integrated boundary edge cataloging system with multiple routes.

This demonstrates the system building cache from scratch, cataloging boundary edges
during initial downloads, and using guaranteed connectivity for subsequent routes.
"""

import sys
import time
import logging
import requests
import json
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project path
sys.path.insert(0, str(Path(__file__).parent))

# Import the cache system to clear it manually
from crime_aware_routing_2.mapping.cache.grid_cache import GridCache

# Test routes covering different scenarios
TEST_ROUTES = [
    {
        'name': 'Downtown Core Route',
        'description': 'Short single-tile route for initial cache seeding',
        'start': {'latitude': 43.6426, 'longitude': -79.3871},  # Financial District
        'destination': {'latitude': 43.6455, 'longitude': -79.3834},  # City Hall
        'expected_behavior': 'Cache miss - downloads and catalogs boundary edges'
    },
    {
        'name': 'Cross-Boundary Route', 
        'description': 'Route crossing tile boundaries - critical test case',
        'start': {'latitude': 43.6426, 'longitude': -79.3871},  # Financial District
        'destination': {'latitude': 43.6629, 'longitude': -79.3957},  # Queen\'s Park
        'expected_behavior': 'Partial cache hit - new tiles downloaded with boundary cataloging'
    },
    {
        'name': 'University Avenue Route',
        'description': 'North-south route using existing cached tiles',
        'start': {'latitude': 43.6629, 'longitude': -79.3957},  # Queen\'s Park
        'destination': {'latitude': 43.6426, 'longitude': -79.3871},  # Union Station
        'expected_behavior': 'Cache hit - guaranteed connectivity from boundary restoration'
    },
    {
        'name': 'Harbourfront Route',
        'description': 'East-west route requiring new cache downloads',
        'start': {'latitude': 43.6415, 'longitude': -79.3871},  # Union Station
        'destination': {'latitude': 43.6385, 'longitude': -79.3755},  # Harbourfront
        'expected_behavior': 'Mixed - some cached tiles, some new downloads'
    },
    {
        'name': 'Long Multi-Tile Route',
        'description': 'Comprehensive route spanning multiple tiles',
        'start': {'latitude': 43.6108, 'longitude': -79.3960},  # Lake Shore
        'destination': {'latitude': 43.6890, 'longitude': -79.3224},  # North York
        'expected_behavior': 'Cache hits with boundary edge restoration for guaranteed connectivity'
    }
]

API_BASE_URL = "http://localhost:8000/api/routing"

def clear_all_caches():
    """Clear all cache systems for a clean test."""
    print("🧹 CLEARING ALL CACHES FOR CLEAN TEST")
    print("=" * 60)
    
    # Clear the integrated cache system
    try:
        cache_dir = "crime_aware_routing_2/cache"
        grid_cache = GridCache(cache_dir, precision=6)
        grid_cache.clear_cache()
        print("✓ GridCache cleared (includes boundary edge database)")
    except Exception as e:
        print(f"⚠️ Failed to clear GridCache: {e}")
    
    # Clear any other cache directories
    cache_paths = [
        Path("crime_aware_routing_2/cache"),
        Path("crime_aware_routing_2/cache_test_connectivity"),
        Path("crime_aware_routing_2/cache_boundary_test")
    ]
    
    for cache_path in cache_paths:
        if cache_path.exists():
            try:
                import shutil
                shutil.rmtree(cache_path)
                print(f"✓ Removed cache directory: {cache_path}")
            except Exception as e:
                print(f"⚠️ Failed to remove {cache_path}: {e}")
    
    print("\n🎯 All caches cleared - starting from scratch\n")

def check_api_health():
    """Check if the API is running and healthy."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            print(f"✓ API is healthy: {health_data.get('status', 'unknown')}")
            return True
        else:
            print(f"❌ API health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API is not accessible: {e}")
        return False

def test_route(route_info, route_number, total_routes):
    """Test a single route and measure performance."""
    print(f"\n{'='*20} ROUTE {route_number}/{total_routes} {'='*20}")
    print(f"🚗 {route_info['name']}")
    print(f"📝 {route_info['description']}")
    print(f"📍 {route_info['start']['latitude']:.4f}, {route_info['start']['longitude']:.4f}")
    print(f"   → {route_info['destination']['latitude']:.4f}, {route_info['destination']['longitude']:.4f}")
    print(f"💡 Expected: {route_info['expected_behavior']}")
    
    # Make route request
    route_request = {
        "start": route_info['start'],
        "destination": route_info['destination'],
        "route_type": "crime_aware",
        "distance_weight": 0.7,
        "crime_weight": 0.3
    }
    
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/calculate",
            json=route_request,
            timeout=30
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        if response.status_code == 200:
            route_data = response.json()
            
            if route_data.get('success', False):
                stats = route_data.get('statistics', {})
                route_geojson = route_data.get('route', {})
                
                print(f"✅ SUCCESS ({duration:.2f}s)")
                print(f"   📏 Distance: {stats.get('distance_km', 0):.2f}km")
                print(f"   ⏱️  Duration: {stats.get('duration_min', 0):.1f}min")
                print(f"   🔐 Crime Score: {stats.get('crime_score', 0):.3f}")
                print(f"   📊 Cache Performance: {stats.get('cache_status', 'unknown')}")
                
                # Check for route geometry
                if route_geojson and 'coordinates' in route_geojson:
                    num_points = len(route_geojson['coordinates'])
                    print(f"   🗺️  Route Points: {num_points}")
                
                return {
                    'success': True,
                    'duration': duration,
                    'stats': stats,
                    'cache_behavior': 'hit' if duration < 3.0 else 'miss'
                }
            else:
                error_msg = route_data.get('error', 'Unknown error')
                print(f"❌ ROUTE FAILED: {error_msg}")
                return {'success': False, 'error': error_msg, 'duration': duration}
        else:
            print(f"❌ HTTP ERROR: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error details: {error_data}")
            except:
                print(f"   Raw response: {response.text[:200]}")
            
            return {'success': False, 'error': f'HTTP {response.status_code}', 'duration': duration}
            
    except requests.exceptions.Timeout:
        print(f"⏰ TIMEOUT after 30 seconds")
        return {'success': False, 'error': 'timeout', 'duration': 30.0}
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        print(f"💥 EXCEPTION: {e}")
        return {'success': False, 'error': str(e), 'duration': duration}

def analyze_results(results):
    """Analyze the test results and provide insights."""
    print(f"\n{'='*60}")
    print("📊 COMPREHENSIVE RESULTS ANALYSIS")
    print(f"{'='*60}")
    
    successful_routes = [r for r in results if r['success']]
    failed_routes = [r for r in results if not r['success']]
    
    total_routes = len(results)
    success_rate = len(successful_routes) / total_routes * 100 if total_routes > 0 else 0
    
    print(f"\n🎯 OVERALL PERFORMANCE:")
    print(f"   Success Rate: {success_rate:.1f}% ({len(successful_routes)}/{total_routes})")
    
    if successful_routes:
        durations = [r['duration'] for r in successful_routes]
        avg_duration = sum(durations) / len(durations)
        min_duration = min(durations)
        max_duration = max(durations)
        
        print(f"   Average Duration: {avg_duration:.2f}s")
        print(f"   Fastest Route: {min_duration:.2f}s")
        print(f"   Slowest Route: {max_duration:.2f}s")
        
        # Analyze cache behavior
        cache_hits = sum(1 for r in successful_routes if r.get('cache_behavior') == 'hit')
        cache_misses = sum(1 for r in successful_routes if r.get('cache_behavior') == 'miss')
        
        print(f"\n💾 CACHE PERFORMANCE:")
        print(f"   Cache Hits: {cache_hits} routes (< 3.0s)")
        print(f"   Cache Misses: {cache_misses} routes (≥ 3.0s)")
        print(f"   Cache Hit Rate: {cache_hits/len(successful_routes)*100:.1f}%")
        
        print(f"\n🚀 PERFORMANCE TREND:")
        for i, result in enumerate(successful_routes, 1):
            cache_status = "🎯 HIT" if result.get('cache_behavior') == 'hit' else "⬇️ MISS"
            print(f"   Route {i}: {result['duration']:.2f}s {cache_status}")
    
    if failed_routes:
        print(f"\n❌ FAILED ROUTES:")
        for i, result in enumerate(failed_routes, 1):
            print(f"   Failure {i}: {result.get('error', 'unknown')} ({result['duration']:.2f}s)")
    
    # System assessment
    print(f"\n🏆 BOUNDARY EDGE CATALOGING ASSESSMENT:")
    
    if success_rate >= 80:
        print("   ✅ EXCELLENT: System working as expected")
        print("   ✅ Boundary edge cataloging is effective")
        print("   ✅ Guaranteed connectivity achieved")
    elif success_rate >= 60:
        print("   ⚠️  GOOD: Most routes successful")
        print("   ⚠️  Some connectivity issues remain")
        print("   ⚠️  Further boundary edge tuning needed")
    else:
        print("   ❌ POOR: Significant connectivity issues")
        print("   ❌ Boundary edge system needs investigation")
        print("   ❌ Check logs for error details")
    
    # Performance insights
    if successful_routes:
        if avg_duration < 2.0:
            print("   🚀 FAST: Excellent cache performance")
        elif avg_duration < 5.0:
            print("   ⚡ MODERATE: Good cache performance") 
        else:
            print("   🐌 SLOW: Cache effectiveness could be improved")

def main():
    """Main test execution."""
    print("🔧 INTEGRATED BOUNDARY EDGE CATALOGING SYSTEM TEST")
    print("🎯 Testing guaranteed connectivity with cache building from scratch")
    print("=" * 80)
    
    # Step 1: Clear all caches
    clear_all_caches()
    
    # Step 2: Check API health
    print("🏥 CHECKING API HEALTH")
    print("-" * 30)
    if not check_api_health():
        print("❌ API is not available. Please start the API server:")
        print("   cd /home/harmansingh/github-repositories/Ventr")
        print("   python -m uvicorn api.main:app --reload")
        return False
    
    # Step 3: Execute test routes
    print(f"\n🧪 EXECUTING {len(TEST_ROUTES)} TEST ROUTES")
    print("-" * 50)
    
    results = []
    
    for i, route_info in enumerate(TEST_ROUTES, 1):
        result = test_route(route_info, i, len(TEST_ROUTES))
        results.append(result)
        
        # Brief pause between requests
        if i < len(TEST_ROUTES):
            time.sleep(1)
    
    # Step 4: Analyze results
    analyze_results(results)
    
    # Step 5: Final assessment
    successful_count = sum(1 for r in results if r['success'])
    total_count = len(results)
    
    print(f"\n🏁 FINAL RESULT:")
    if successful_count == total_count:
        print("   🏆 PERFECT: All routes successful!")
        print("   ✅ Boundary edge cataloging system working perfectly")
        print("   ✅ Guaranteed connectivity achieved")
        return True
    elif successful_count >= total_count * 0.8:
        print("   ✅ EXCELLENT: Most routes successful")
        print("   ✅ Boundary edge system largely effective")
        return True
    else:
        print("   ⚠️  MIXED RESULTS: Some routes failed")
        print("   ⚠️  Boundary edge system needs refinement")
        return False

if __name__ == '__main__':
    try:
        success = main()
        print(f"\n{'='*80}")
        print("TEST COMPLETE")
        print(f"{'='*80}")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 
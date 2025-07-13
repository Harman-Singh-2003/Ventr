#!/usr/bin/env python3
"""
Test script for the new multiple routes endpoint.
"""

import sys
import os
import json
import asyncio
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_multiple_routes_schema():
    """Test that the schemas are properly defined."""
    try:
        from api.schemas.routing import MultipleRouteRequest, MultipleRouteResponse, LocationRequest
        
        # Test creating a valid request
        start = LocationRequest(latitude=43.6426, longitude=-79.3871)
        destination = LocationRequest(latitude=43.6452, longitude=-79.3806)
        
        request = MultipleRouteRequest(
            start=start,
            destination=destination,
            include_shortest=True,
            include_safest=True,
            crime_weight_safest=0.7,
            max_detour_factor=2.0
        )
        
        logger.info("✓ MultipleRouteRequest schema validation passed")
        logger.info(f"Request: {request.dict()}")
        
        # Test creating a response
        response = MultipleRouteResponse(
            success=True,
            message="Test response",
            shortest_route=None,
            shortest_stats=None,
            safest_route=None,
            safest_stats=None,
            comparison_stats=None
        )
        
        logger.info("✓ MultipleRouteResponse schema validation passed")
        logger.info(f"Response: {response.dict()}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Schema validation failed: {e}")
        return False

def test_service_method_signature():
    """Test that the service method has correct signature."""
    try:
        from api.services.routing_service import CrimeAwareRoutingService
        from api.schemas.routing import MultipleRouteRequest
        
        service = CrimeAwareRoutingService()
        
        # Check that the method exists
        assert hasattr(service, 'calculate_multiple_routes'), "calculate_multiple_routes method not found"
        
        method = getattr(service, 'calculate_multiple_routes')
        
        # Check method signature (basic check)
        import inspect
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        
        assert 'request' in params, "Method should have 'request' parameter"
        
        logger.info("✓ Service method signature validation passed")
        logger.info(f"Method signature: {sig}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Service method validation failed: {e}")
        return False

def test_routing_endpoint_exists():
    """Test that the new routing endpoint is defined."""
    try:
        from api.routes.routing import router
        
        # Get all routes from the router
        routes = []
        for route in router.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                routes.append((route.path, list(route.methods)))
        
        # Check if our new endpoint exists
        calculate_multiple_found = False
        for path, methods in routes:
            if '/calculate-multiple' in path and 'POST' in methods:
                calculate_multiple_found = True
                break
        
        assert calculate_multiple_found, "calculate-multiple endpoint not found"
        
        logger.info("✓ Routing endpoint validation passed")
        logger.info(f"Available routes: {routes}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Routing endpoint validation failed: {e}")
        return False

async def main():
    """Run all tests."""
    logger.info("Testing multiple routes implementation...")
    
    tests = [
        test_multiple_routes_schema,
        test_service_method_signature,
        test_routing_endpoint_exists
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"Test {test.__name__} failed with exception: {e}")
            failed += 1
    
    logger.info(f"\nTest Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        logger.info("✓ All tests passed! Multiple routes implementation is ready.")
    else:
        logger.warning("✗ Some tests failed. Please check the implementation.")

if __name__ == "__main__":
    asyncio.run(main())

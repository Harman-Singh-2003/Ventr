"""
FastAPI routes for crime-aware routing endpoints.
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
import logging

from api.schemas.routing import (
    RouteRequest, 
    RouteResponse, 
    HealthResponse,
    LocationRequest,
    ErrorResponse
)
from api.services.routing_service import routing_service

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/routing", tags=["routing"])


@router.get("/health", response_model=HealthResponse, summary="Health Check")
async def health_check():
    """
    Check the health status of the routing service.
    
    Returns:
        HealthResponse: Service health information
    """
    try:
        health_status = routing_service.get_health_status()
        return health_status
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Health check failed"
        )


@router.post("/calculate", response_model=RouteResponse, summary="Calculate Crime-Aware Route")
async def calculate_route(request: RouteRequest):
    """
    Calculate a crime-aware route between two locations.
    
    This endpoint calculates routes that take into account crime data to provide
    safer navigation options. You can specify the balance between route distance
    and crime avoidance.
    
    Args:
        request: RouteRequest containing start/end locations and preferences
        
    Returns:
        RouteResponse: Route data in GeoJSON format with statistics
        
    Example:
        ```json
        {
            "start": {
                "latitude": 43.6426,
                "longitude": -79.3871
            },
            "destination": {
                "latitude": 43.6452,
                "longitude": -79.3806
            },
            "route_type": "crime_aware",
            "distance_weight": 0.7,
            "crime_weight": 0.3
        }
        ```
    """
    try:
        logger.info(f"Route calculation request: {request.route_type} from "
                   f"({request.start.latitude}, {request.start.longitude}) to "
                   f"({request.destination.latitude}, {request.destination.longitude})")
        
        # Calculate the route
        response = routing_service.calculate_route(request)
        
        # Return appropriate HTTP status based on success
        if response.success:
            return response
        else:
            # Return 200 with error details for business logic failures
            # Use 4xx/5xx only for actual HTTP-level errors
            return response
            
    except ValueError as e:
        # Validation errors
        logger.warning(f"Route calculation validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Unexpected errors
        logger.error(f"Route calculation failed with unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during route calculation"
        )


@router.post("/shortest", response_model=RouteResponse, summary="Calculate Shortest Route")
async def calculate_shortest_route(start: LocationRequest, destination: LocationRequest):
    """
    Calculate the shortest route between two locations (ignoring crime data).
    
    This is a convenience endpoint that calculates only the shortest path
    without considering crime factors.
    
    Args:
        start: Starting location
        destination: Destination location
        
    Returns:
        RouteResponse: Shortest route in GeoJSON format
    """
    try:
        # Create a request with shortest route type
        request = RouteRequest(
            start=start,
            destination=destination,
            route_type="shortest",
            distance_weight=1.0,
            crime_weight=0.0
        )
        
        return await calculate_route(request)
        
    except Exception as e:
        logger.error(f"Shortest route calculation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate shortest route"
        )


@router.post("/safest", response_model=RouteResponse, summary="Calculate Safest Route")
async def calculate_safest_route(start: LocationRequest, destination: LocationRequest):
    """
    Calculate the safest route between two locations (prioritizing crime avoidance).
    
    This endpoint prioritizes safety over distance, finding routes that avoid
    high-crime areas even if they are longer.
    
    Args:
        start: Starting location  
        destination: Destination location
        
    Returns:
        RouteResponse: Safest route in GeoJSON format
    """
    try:
        # Create a request with safest route type
        request = RouteRequest(
            start=start,
            destination=destination,
            route_type="safest",
            distance_weight=0.3,
            crime_weight=0.7,
            max_detour_factor=2.0  # Allow longer detours for safety
        )
        
        return await calculate_route(request)
        
    except Exception as e:
        logger.error(f"Safest route calculation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate safest route"
        )


@router.get("/", summary="API Information")
async def get_api_info():
    """
    Get information about the Crime-Aware Routing API.
    
    Returns:
        dict: API information and available endpoints
    """
    return {
        "api": "Crime-Aware Routing API",
        "version": "2.0.0",
        "description": "Calculate safer routes using Toronto crime data",
        "endpoints": {
            "POST /api/routing/calculate": "Calculate crime-aware route with custom parameters",
            "POST /api/routing/shortest": "Calculate shortest route only",
            "POST /api/routing/safest": "Calculate safest route (prioritizes crime avoidance)",
            "GET /api/routing/health": "Check service health status",
            "GET /api/routing/": "This information endpoint"
        },
        "supported_areas": [
            "Toronto, Ontario, Canada"
        ],
        "coordinate_bounds": {
            "latitude": {"min": 43.0, "max": 44.5},
            "longitude": {"min": -80.5, "max": -78.5}
        }
    } 
"""
Service layer for crime-aware routing API.
"""

import logging
import os
from typing import Dict, Any, List, Tuple, Optional
import networkx as nx
import geojson
from shapely.geometry import LineString

# Import from the existing crime_aware_routing system
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from crime_aware_routing.algorithms.route_optimizer import RouteOptimizer
from crime_aware_routing.core.data_loader import load_crime_data
from crime_aware_routing.config.routing_config import RoutingConfig
from api.schemas.routing import RouteRequest, RouteResponse, RouteStats, HealthResponse, ErrorResponse

logger = logging.getLogger(__name__)


class CrimeAwareRoutingService:
    """
    Service class that provides crime-aware routing functionality for the API.
    """
    
    def __init__(self):
        """Initialize the routing service."""
        self.crime_data: Optional[List[Dict[str, float]]] = None
        self.crime_data_path = self._get_crime_data_path()
        self.is_initialized = False
        
        # Initialize the service
        self._initialize()
    
    def _get_crime_data_path(self) -> str:
        """Get the path to the crime data file."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        crime_data_path = os.path.join(current_dir, '../../crime_aware_routing/data/crime_data.geojson')
        return crime_data_path
    
    def _initialize(self) -> None:
        """Initialize the routing service by loading crime data."""
        try:
            logger.info("Initializing crime-aware routing service...")
            
            # Load crime data
            if os.path.exists(self.crime_data_path):
                self.crime_data = load_crime_data(self.crime_data_path)
                self.is_initialized = True
                logger.info(f"Service initialized with {len(self.crime_data)} crime incidents")
            else:
                logger.warning(f"Crime data file not found at {self.crime_data_path}")
                self.crime_data = []
                self.is_initialized = False
                
        except Exception as e:
            logger.error(f"Failed to initialize routing service: {e}")
            self.crime_data = []
            self.is_initialized = False
    
    def get_health_status(self) -> HealthResponse:
        """Get the health status of the routing service."""
        return HealthResponse(
            status="healthy" if self.is_initialized else "degraded",
            version="1.0.0",
            crime_data_loaded=self.is_initialized,
            crime_incidents_count=len(self.crime_data) if self.crime_data else 0
        )
    
    def calculate_route(self, request: RouteRequest) -> RouteResponse:
        """
        Calculate a crime-aware route between two points.
        
        Args:
            request: Route calculation request
            
        Returns:
            RouteResponse with route GeoJSON and statistics
        """
        try:
            if not self.is_initialized:
                return RouteResponse(
                    success=False,
                    message="Service not properly initialized - crime data not available"
                )
            
            logger.info(f"Calculating route from {request.start.dict()} to {request.destination.dict()}")
            
            # Convert request to coordinates
            start_coords = (request.start.latitude, request.start.longitude)
            end_coords = (request.destination.latitude, request.destination.longitude)
            
            # Create routing configuration
            config = RoutingConfig()
            config.distance_weight = request.distance_weight
            config.crime_weight = request.crime_weight
            config.max_detour_ratio = request.max_detour_factor
            
            # Initialize route optimizer
            optimizer = RouteOptimizer(self.crime_data_path, config)
            
            # Determine algorithms to use based on route type
            algorithms = self._get_algorithms_for_route_type(request.route_type)
            
            # Calculate routes
            result = optimizer.find_safe_route(start_coords, end_coords, algorithms)
            
            # Convert result to API response format
            return self._convert_to_response(result, request)
            
        except Exception as e:
            logger.error(f"Route calculation failed: {e}")
            return RouteResponse(
                success=False,
                message=f"Route calculation failed: {str(e)}"
            )
    
    def _get_algorithms_for_route_type(self, route_type: str) -> List[str]:
        """Get the appropriate algorithms for the requested route type."""
        if route_type == "shortest":
            return ["shortest_path"]
        elif route_type == "safest":
            return ["weighted_astar"]  # With high crime weight
        else:  # crime_aware (default)
            return ["weighted_astar", "shortest_path"]
    
    def _convert_to_response(self, result: Dict[str, Any], request: RouteRequest) -> RouteResponse:
        """
        Convert optimizer result to API response format.
        
        Args:
            result: Result from RouteOptimizer
            request: Original request
            
        Returns:
            Formatted RouteResponse
        """
        try:
            routes = result.get('routes', {})
            
            # Get the primary route based on request type
            primary_route = None
            if request.route_type == "shortest":
                primary_route = routes.get('shortest_path')
            else:
                primary_route = routes.get('weighted_astar', routes.get('shortest_path'))
            
            if not primary_route:
                return RouteResponse(
                    success=False,
                    message="No valid route found"
                )
            
            # Convert route to GeoJSON
            route_geojson = self._route_to_geojson(primary_route)
            
            # Calculate route statistics
            route_stats = self._calculate_route_stats(primary_route)
            
            # Calculate shortest path stats for comparison if available
            shortest_path_stats = None
            shortest_route = routes.get('shortest_path')
            if shortest_route and shortest_route != primary_route:
                shortest_path_stats = self._calculate_route_stats(shortest_route)
            
            return RouteResponse(
                success=True,
                message="Route calculated successfully",
                route_geojson=route_geojson,
                route_stats=route_stats,
                shortest_path_stats=shortest_path_stats
            )
            
        except Exception as e:
            logger.error(f"Failed to convert result to response: {e}")
            return RouteResponse(
                success=False,
                message=f"Failed to process route result: {str(e)}"
            )
    
    def _route_to_geojson(self, route_details) -> Dict[str, Any]:
        """
        Convert route details to GeoJSON format.
        
        Args:
            route_details: RouteDetails object
            
        Returns:
            GeoJSON FeatureCollection
        """
        try:
            # Extract coordinates (lat, lon pairs)
            coordinates = route_details.coordinates
            
            # Convert to GeoJSON LineString format (lon, lat)
            geojson_coords = [[coord[1], coord[0]] for coord in coordinates]
            
            # Create LineString feature
            line_feature = geojson.Feature(
                geometry=geojson.LineString(geojson_coords),
                properties={
                    "algorithm": route_details.algorithm,
                    "total_distance_m": route_details.total_distance,
                    "node_count": len(route_details.nodes),
                    "calculation_time_ms": route_details.calculation_time * 1000 if route_details.calculation_time else None
                }
            )
            
            # Create point features for start and end
            start_feature = geojson.Feature(
                geometry=geojson.Point([geojson_coords[0][0], geojson_coords[0][1]]),
                properties={"type": "start", "name": "Start Point"}
            )
            
            end_feature = geojson.Feature(
                geometry=geojson.Point([geojson_coords[-1][0], geojson_coords[-1][1]]),
                properties={"type": "end", "name": "End Point"}
            )
            
            # Create FeatureCollection
            feature_collection = geojson.FeatureCollection([
                line_feature,
                start_feature,
                end_feature
            ])
            
            return feature_collection
            
        except Exception as e:
            logger.error(f"Failed to convert route to GeoJSON: {e}")
            raise
    
    def _calculate_route_stats(self, route_details) -> RouteStats:
        """
        Calculate statistics for a route.
        
        Args:
            route_details: RouteDetails object
            
        Returns:
            RouteStats object
        """
        try:
            # Calculate basic metrics
            distance_m = route_details.total_distance
            
            # Estimate travel time (assuming 5 km/h walking speed)
            walking_speed_mps = 5000 / 3600  # 5 km/h in m/s
            time_s = distance_m / walking_speed_mps
            
            # Calculate safety score (inverse of average crime score)
            avg_crime_score = sum(route_details.crime_scores) / len(route_details.crime_scores) if route_details.crime_scores else 0
            safety_score = max(0.0, min(1.0, 1.0 - avg_crime_score))
            
            # Count nearby crime incidents (approximate)
            crime_incidents_nearby = len(route_details.crime_scores)
            
            # Calculate detour factor (will be set by caller if shortest path is available)
            detour_factor = 1.0
            
            return RouteStats(
                total_distance_m=round(distance_m, 1),
                total_time_s=round(time_s, 0),
                crime_incidents_nearby=crime_incidents_nearby,
                safety_score=round(safety_score, 3),
                detour_factor=detour_factor
            )
            
        except Exception as e:
            logger.error(f"Failed to calculate route stats: {e}")
            # Return default stats
            return RouteStats(
                total_distance_m=0.0,
                total_time_s=0.0,
                crime_incidents_nearby=0,
                safety_score=0.5,
                detour_factor=1.0
            )


# Global service instance
routing_service = CrimeAwareRoutingService() 
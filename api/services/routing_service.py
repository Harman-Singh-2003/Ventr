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

from crime_aware_routing_2.algorithms.optimization.cached_route_optimizer import CachedRouteOptimizer
from crime_aware_routing_2.data.data_loader import load_crime_data
from crime_aware_routing_2.config.routing_config import RoutingConfig
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
        crime_data_path = os.path.join(current_dir, '../../crime_aware_routing_2/data/crime_data.geojson')
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
            version="2.0.0",  # Updated to reflect refactored codebase
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
            
            # Create routing configuration based on route type
            if request.route_type == "shortest":
                # For shortest routes, use streamlined optimizer without crime weighting
                config = RoutingConfig()
                config.distance_weight = 1.0
                config.crime_weight = 0.0
                logger.info("Using shortest path configuration (no crime weighting)")
            else:
                # For crime-aware routes, apply gradual weight interpolation
                config = RoutingConfig()
                config.crime_weighting_method = 'network_proximity'  # Use the new NetworkProximityWeighter
                
                # Apply gradual weight interpolation based on crime_weight parameter
                config.distance_weight = 1.0 - request.crime_weight
                config.crime_weight = request.crime_weight
                
                # Scale crime penalty gradually - key fix for binary behavior
                # Use lower base penalty that scales smoothly with crime_weight
                base_penalty = 500.0  # Reduced from 1000.0 for smoother transitions
                config.crime_penalty_scale = base_penalty * (1.0 + request.crime_weight * 3.0)  # 500-2000 range
                
                # Adjust influence radius based on crime sensitivity
                config.crime_influence_radius = 100.0 + (request.crime_weight * 150.0)  # 100-250m range
                
                logger.info(f"Using crime-aware configuration (distance: {config.distance_weight:.2f}, crime: {config.crime_weight:.2f})")
            
            # Override with other request parameters if provided
            if hasattr(request, 'max_detour_factor') and request.max_detour_factor is not None:
                config.max_detour_ratio = request.max_detour_factor
            
            # Initialize route optimizer based on route type
            if request.route_type == "shortest":
                # For shortest routes, use streamlined optimizer without crime weighting
                optimizer = CachedRouteOptimizer(self.crime_data_path, config)
                # Skip crime weighting by using algorithms that don't require it
                algorithms = ["shortest_path"]
            else:
                # For crime-aware routes, use full crime-aware optimizer
                optimizer = CachedRouteOptimizer(self.crime_data_path, config)
                algorithms = self._get_algorithms_for_route_type(request.route_type)
            
            # Calculate routes
            result = optimizer.find_safe_route(start_coords, end_coords, algorithms)
            
            logger.info(f"Route calculation completed using {request.route_type} configuration with algorithms: {algorithms}")
            
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
        else:  # crime_aware (default) and safest - use weighted algorithm with gradual scaling
            return ["weighted_astar"]
    
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
            
            # Get the primary route - no more binary selection, use gradual weighting
            primary_route = None
            if request.route_type == "shortest":
                primary_route = routes.get('shortest_path')
            else:  # crime_aware (default) and safest - use the weighted route
                primary_route = routes.get('weighted_astar')
                
            # Fallback to any available route if primary not found
            if not primary_route:
                available_routes = list(routes.values())
                primary_route = available_routes[0] if available_routes else None
            
            if not primary_route:
                return RouteResponse(
                    success=False,
                    message="No valid route found"
                )
            
            # Convert route to GeoJSON
            route_geojson = self._route_to_geojson(primary_route)
            
            # Calculate route statistics
            route_stats = self._calculate_route_stats(primary_route)
            
            # For comparison, always calculate shortest path stats when using weighted route
            shortest_path_stats = None
            if request.route_type != "shortest" and primary_route.algorithm != "shortest_path":
                # Calculate shortest path for comparison
                try:
                    start_coords = (request.start.latitude, request.start.longitude)
                    end_coords = (request.destination.latitude, request.destination.longitude)
                    comparison_optimizer = CachedRouteOptimizer(self.crime_data_path, RoutingConfig())
                    comparison_result = comparison_optimizer.find_safe_route(
                        start_coords, end_coords, ["shortest_path"]
                    )
                    shortest_route = comparison_result.get('routes', {}).get('shortest_path')
                    if shortest_route:
                        shortest_path_stats = self._calculate_route_stats(shortest_route)
                except Exception as e:
                    logger.debug(f"Could not calculate shortest path for comparison: {e}")
            
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
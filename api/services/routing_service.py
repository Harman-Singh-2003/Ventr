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

from crime_aware_routing_2.algorithms.optimization.route_optimizer import RouteOptimizer
from crime_aware_routing_2.data.data_loader import load_crime_data
from crime_aware_routing_2.config.routing_config import RoutingConfig
from crime_aware_routing_2.mapping.network.network_cache import get_network_cache
from api.schemas.routing import RouteRequest, RouteResponse, RouteStats, HealthResponse, ErrorResponse, MultipleRouteRequest, MultipleRouteResponse

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
        # Check network cache status
        cache = get_network_cache()
        cache_info = cache.get_cache_info()
        
        return HealthResponse(
            status="healthy" if self.is_initialized else "degraded",
            version="2.0.0",  # Updated to reflect refactored codebase
            crime_data_loaded=self.is_initialized,
            crime_incidents_count=len(self.crime_data) if self.crime_data else 0,
            network_cache_available=cache_info.get('available', False),
            cache_coverage_km=cache_info.get('radius_km', 0) if cache_info.get('available') else 0
        )
    
    def calculate_route(self, request: RouteRequest) -> RouteResponse:
        """
        Calculate a crime-aware route between two points.
        
        Args:
            request: Route calculation request
            
        Returns:
            RouteResponse with route GeoJSON and statistics
        """
        import time
        
        try:
            service_start_time = time.perf_counter()
            
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
            config_start_time = time.perf_counter()
            
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
                
                # Scale crime penalty directly proportional to crime weight
                # This ensures crime_weight=0 gives no penalty, crime_weight=1 gives full penalty
                base_penalty = 2000.0  # Higher base since we're multiplying by crime_weight directly
                config.crime_penalty_scale = base_penalty * request.crime_weight
                
                # Adjust influence radius based on crime sensitivity
                if request.crime_weight > 0:
                    config.crime_influence_radius = 100.0 + (request.crime_weight * 150.0)  # 100-250m range
                else:
                    config.crime_influence_radius = 0.0  # No influence when crime weight is 0
                
                logger.info(f"Using crime-aware configuration (distance: {config.distance_weight:.2f}, crime: {config.crime_weight:.2f})")
            
            # Override with other request parameters if provided
            if hasattr(request, 'max_detour_factor') and request.max_detour_factor is not None:
                config.max_detour_ratio = request.max_detour_factor
            
            config_time = time.perf_counter() - config_start_time
            logger.info(f"Configuration setup completed in {config_time:.3f}s")
            
            # Initialize route optimizer based on route type
            optimizer_start_time = time.perf_counter()
            
            if request.route_type == "shortest":
                # For shortest routes, use streamlined optimizer without crime weighting
                optimizer = RouteOptimizer(self.crime_data_path, config)
                # Skip crime weighting by using algorithms that don't require it
                algorithms = ["shortest_path"]
            else:
                # For crime-aware routes, use full crime-aware optimizer
                optimizer = RouteOptimizer(self.crime_data_path, config)
                algorithms = self._get_algorithms_for_route_type(request.route_type)
            
            optimizer_time = time.perf_counter() - optimizer_start_time
            logger.info(f"Optimizer initialization completed in {optimizer_time:.3f}s")
            
            # Calculate routes
            route_calc_start_time = time.perf_counter()
            result = optimizer.find_safe_route(start_coords, end_coords, algorithms)
            route_calc_time = time.perf_counter() - route_calc_start_time
            
            logger.info(f"Route calculation completed using {request.route_type} configuration with algorithms: {algorithms} in {route_calc_time:.3f}s")
            
            # Convert result to API response format
            response_start_time = time.perf_counter()
            response = self._convert_to_response(result, request)
            response_time = time.perf_counter() - response_start_time
            
            total_service_time = time.perf_counter() - service_start_time
            logger.info(f"Response conversion completed in {response_time:.3f}s")
            logger.info(f"Total service calculation time: {total_service_time:.3f}s")
            
            return response
            
        except Exception as e:
            logger.error(f"Route calculation failed: {e}")
            return RouteResponse(
                success=False,
                message=f"Route calculation failed: {str(e)}"
            )
    
    def calculate_multiple_routes(self, request: MultipleRouteRequest) -> MultipleRouteResponse:
        """
        Calculate both shortest and safest routes in a single optimized operation.
        
        Args:
            request: MultipleRouteRequest containing start/end locations and preferences
            
        Returns:
            MultipleRouteResponse with both route types and comparison data
        """
        import time
        
        try:
            service_start_time = time.perf_counter()
            
            if not self.is_initialized:
                return MultipleRouteResponse(
                    success=False,
                    message="Service not properly initialized - crime data not available"
                )
            
            logger.info(f"Calculating multiple routes from {request.start.dict()} to {request.destination.dict()}")
            
            # Convert request to coordinates
            start_coords = (request.start.latitude, request.start.longitude)
            end_coords = (request.destination.latitude, request.destination.longitude)
            
            # Determine which algorithms to run
            algorithms = []
            if request.include_shortest:
                algorithms.append("shortest_path")
            if request.include_safest:
                algorithms.append("weighted_astar")
            
            if not algorithms:
                return MultipleRouteResponse(
                    success=False,
                    message="No route types specified"
                )
            
            # Create routing configuration for safest route (if requested)
            config = RoutingConfig()
            if request.include_safest:
                config.crime_weighting_method = 'network_proximity'
                config.distance_weight = 1.0 - request.crime_weight_safest
                config.crime_weight = request.crime_weight_safest
                config.max_detour_ratio = request.max_detour_factor
                
                # Scale crime penalty directly proportional to crime weight
                # This ensures crime_weight=0 gives no penalty, crime_weight=1 gives full penalty
                base_penalty = 2000.0  # Higher base since we're multiplying by crime_weight directly
                config.crime_penalty_scale = base_penalty * request.crime_weight_safest
                
                # Only apply influence radius when crime weight > 0
                if request.crime_weight_safest > 0:
                    config.crime_influence_radius = 100.0 + (request.crime_weight_safest * 150.0)
                else:
                    config.crime_influence_radius = 0.0  # No influence when crime weight is 0
                
                logger.info(f"Using safest route config (distance: {config.distance_weight:.2f}, crime: {config.crime_weight:.2f})")
            
            # Initialize route optimizer - single instance for both routes
            optimizer_start_time = time.perf_counter()
            optimizer = RouteOptimizer(self.crime_data_path, config)
            optimizer_time = time.perf_counter() - optimizer_start_time
            logger.info(f"Optimizer initialization completed in {optimizer_time:.3f}s")
            
            # Calculate all routes in one operation
            route_calc_start_time = time.perf_counter()
            result = optimizer.find_safe_route(start_coords, end_coords, algorithms)
            route_calc_time = time.perf_counter() - route_calc_start_time
            
            logger.info(f"Multiple route calculation completed with algorithms: {algorithms} in {route_calc_time:.3f}s")
            
            # Process results
            response_start_time = time.perf_counter()
            response = self._convert_to_multiple_response(result, request)
            response_time = time.perf_counter() - response_start_time
            
            total_service_time = time.perf_counter() - service_start_time
            logger.info(f"Response conversion completed in {response_time:.3f}s")
            logger.info(f"Total multiple route service time: {total_service_time:.3f}s")
            
            return response
            
        except Exception as e:
            logger.error(f"Multiple route calculation failed: {e}")
            return MultipleRouteResponse(
                success=False,
                message=f"Multiple route calculation failed: {str(e)}"
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
            
            return RouteResponse(
                success=True,
                message="Route calculated successfully",
                route_geojson=route_geojson,
                route_stats=route_stats,
                shortest_path_stats=None
            )
            
        except Exception as e:
            logger.error(f"Failed to convert result to response: {e}")
            return RouteResponse(
                success=False,
                message=f"Failed to process route result: {str(e)}"
            )
    
    def _convert_to_multiple_response(self, result: Dict[str, Any], request: MultipleRouteRequest) -> MultipleRouteResponse:
        """
        Convert optimizer result to MultipleRouteResponse format.
        
        Args:
            result: Result from RouteOptimizer
            request: Original MultipleRouteRequest
            
        Returns:
            Formatted MultipleRouteResponse
        """
        try:
            routes = result.get('routes', {})
            
            # Extract individual routes
            shortest_route = routes.get('shortest_path') if request.include_shortest else None
            safest_route = routes.get('weighted_astar') if request.include_safest else None
            
            # Convert routes to GeoJSON and calculate stats
            shortest_geojson = None
            shortest_stats = None
            if shortest_route:
                shortest_geojson = self._route_to_geojson(shortest_route)
                shortest_stats = self._calculate_route_stats(shortest_route)
            
            safest_geojson = None
            safest_stats = None
            if safest_route:
                safest_geojson = self._route_to_geojson(safest_route)
                safest_stats = self._calculate_route_stats(safest_route)
            
            # Calculate comparison statistics
            comparison_stats = None
            if shortest_stats and safest_stats:
                comparison_stats = {
                    'distance_difference_m': safest_stats.total_distance_m - shortest_stats.total_distance_m,
                    'distance_difference_percent': ((safest_stats.total_distance_m - shortest_stats.total_distance_m) / shortest_stats.total_distance_m) * 100 if shortest_stats.total_distance_m > 0 else 0,
                    'time_difference_s': safest_stats.total_time_s - shortest_stats.total_time_s,
                    'safety_improvement': safest_stats.safety_score - shortest_stats.safety_score,
                    'crime_incidents_avoided': max(0, shortest_stats.crime_incidents_nearby - safest_stats.crime_incidents_nearby)
                }
                
                # Update detour factor for safest route
                if shortest_stats.total_distance_m > 0:
                    safest_stats.detour_factor = safest_stats.total_distance_m / shortest_stats.total_distance_m
            
            return MultipleRouteResponse(
                success=True,
                message="Multiple routes calculated successfully",
                shortest_route=shortest_geojson,
                shortest_stats=shortest_stats,
                safest_route=safest_geojson,
                safest_stats=safest_stats,
                comparison_stats=comparison_stats
            )
            
        except Exception as e:
            logger.error(f"Failed to convert multiple route result to response: {e}")
            return MultipleRouteResponse(
                success=False,
                message=f"Failed to process multiple route result: {str(e)}"
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
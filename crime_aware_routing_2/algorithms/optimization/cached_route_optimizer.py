"""
Cached route optimizer that uses grid-based caching for improved performance.
"""

import logging
from typing import Dict, Tuple, Optional, Any, List
import networkx as nx
import numpy as np
from ...data.crime_processor import CrimeProcessor
from ...mapping.network.graph_enhancer import GraphEnhancer
from ...mapping.network.cached_network_builder import CachedNetworkBuilder
from ...mapping.network.network_builder import find_nearest_nodes
from ..crime_weighting import BaseCrimeWeighter
from ..routing.astar_weighted import WeightedAStarRouter, RouteDetails
from ...config.routing_config import RoutingConfig
from ...config.crime_weighting_factory import create_weighter_from_string

logger = logging.getLogger(__name__)


class CachedRouteOptimizer:
    """
    Route optimizer that uses grid-based caching for improved performance.
    
    This is a drop-in replacement for RouteOptimizer that uses cached network data
    when available, falling back to live downloads when necessary.
    """
    
    def __init__(self, crime_data_path: str, config: Optional[RoutingConfig] = None,
                 cache_dir: str = "crime_aware_routing_2/cache", 
                 cache_precision: int = 6,
                 enable_cache: bool = True):
        """
        Initialize cached route optimizer.
        
        Args:
            crime_data_path: Path to crime data GeoJSON file
            config: Routing configuration parameters
            cache_dir: Directory for cache storage
            cache_precision: Geohash precision level for caching
            enable_cache: Whether to use caching (can disable for testing)
        """
        self.config = config or RoutingConfig()
        self.config.validate()
        
        # Initialize components
        self.crime_processor = CrimeProcessor(crime_data_path, self.config)
        self.crime_weighter: Optional[BaseCrimeWeighter] = None
        self.graph_enhancer: Optional[GraphEnhancer] = None
        self.router: Optional[WeightedAStarRouter] = None
        
        # Initialize cached network builder
        self.network_builder = CachedNetworkBuilder(
            cache_dir=cache_dir,
            precision=cache_precision,
            enable_cache=enable_cache
        )
        
        # State tracking
        self.current_graph: Optional[nx.MultiDiGraph] = None
        self.current_bounds: Optional[Dict[str, float]] = None
        
        logger.info(f"CachedRouteOptimizer initialized (cache: {'enabled' if enable_cache else 'disabled'})")
    
    def find_safe_route(self, start_coords: Tuple[float, float], 
                       end_coords: Tuple[float, float],
                       algorithms: Optional[List[str]] = None,
                       prefer_cache: bool = True) -> Dict[str, Any]:
        """
        Find crime-aware routes between two points using cached data when possible.
        
        Args:
            start_coords: (lat, lon) of route start
            end_coords: (lat, lon) of route end
            algorithms: List of algorithms to use for comparison
            prefer_cache: Whether to prefer cached data over live downloads
            
        Returns:
            Dictionary with routes, crime surface, and metrics
        """
        if algorithms is None:
            algorithms = ['weighted_astar', 'shortest_path']
        
        logger.info(f"Finding safe route from {start_coords} to {end_coords} (cache: {prefer_cache})")
        
        try:
            # Step 1: Build street network (using cache when possible)
            graph = self._build_network(start_coords, end_coords, prefer_cache)
            
            # Step 2: Process crime data for the area
            self._prepare_crime_weighting(start_coords, end_coords)
            
            # Step 3: Enhance graph with crime weights
            enhanced_graph = self._enhance_graph(graph)
            
            # Step 4: Find nearest nodes to coordinates
            start_node, end_node = find_nearest_nodes(enhanced_graph, start_coords, end_coords)
            
            # Step 5: Calculate routes using different algorithms
            routes = self._calculate_routes(enhanced_graph, start_node, end_node, algorithms)
            
            # Step 6: Generate analysis and metrics
            analysis = self._analyze_routes(routes, start_coords, end_coords)
            
            result = {
                'routes': routes,
                'crime_surface': getattr(self.crime_weighter, 'get_crime_surface_for_visualization', lambda: None)() if self.crime_weighter else None,
                'analysis': analysis,
                'metadata': {
                    'start_coords': start_coords,
                    'end_coords': end_coords,
                    'start_node': start_node,
                    'end_node': end_node,
                    'graph_stats': {
                        'nodes': len(enhanced_graph.nodes),
                        'edges': len(enhanced_graph.edges)
                    },
                    'config': self.config.__dict__,
                    'used_cache': prefer_cache
                }
            }
            
            logger.info(f"Route optimization completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Route optimization failed: {e}")
            raise
    
    def _build_network(self, start_coords: Tuple[float, float], 
                      end_coords: Tuple[float, float],
                      prefer_cache: bool = True) -> nx.MultiDiGraph:
        """Build street network for the route area using cache when possible."""
        logger.info("Building street network...")
        
        # Use cached network builder
        graph = self.network_builder.build_network(
            start_coords, 
            end_coords,
            buffer_factor=self.config.max_network_radius / 1000.0,  # Convert to km approximation
            prefer_cache=prefer_cache
        )
        
        self.current_graph = graph
        return graph
    
    def _prepare_crime_weighting(self, start_coords: Tuple[float, float], 
                                end_coords: Tuple[float, float]) -> None:
        """Prepare crime weighting for the route area."""
        logger.info("Preparing crime weighting...")
        
        # Get geographic bounds for the route area
        bounds = self.crime_processor.create_bounds_from_route(
            start_coords, end_coords, self.config.crime_data_buffer
        )
        self.current_bounds = bounds
        
        # Get crime data for the area
        crime_points = self.crime_processor.get_crimes_in_bounds(bounds)
        
        if len(crime_points) == 0:
            logger.warning("No crime data found in route area - using uniform weighting")
            # Create dummy crime weighter for areas with no crime data
            self.crime_weighter = create_weighter_from_string(
                self.config.crime_weighting_method, self.config
            )
            # Create a single dummy point to avoid fitting issues
            dummy_point = np.array([[
                (start_coords[0] + end_coords[0]) / 2,
                (start_coords[1] + end_coords[1]) / 2
            ]])
            self.crime_weighter.fit(dummy_point, bounds)
        else:
            # Initialize and fit crime weighter using factory
            self.crime_weighter = create_weighter_from_string(
                self.config.crime_weighting_method, self.config
            )
            self.crime_weighter.fit(crime_points, bounds)
            
            logger.info(f"Crime weighter fitted with {len(crime_points)} crime incidents")
    
    def _enhance_graph(self, graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
        """Enhance graph with crime-based edge weights."""
        logger.info("Enhancing graph with crime weights...")
        
        if self.crime_weighter is None:
            raise RuntimeError("Crime weighter must be initialized before enhancing graph")
        
        # Initialize graph enhancer
        self.graph_enhancer = GraphEnhancer(self.crime_weighter, self.config)
        
        # Add crime weights to edges
        enhanced_graph = self.graph_enhancer.add_crime_weights(graph)
        
        # Validate enhancement
        if not self.graph_enhancer.validate_enhanced_graph(enhanced_graph):
            logger.warning("Graph enhancement validation failed")
        
        # Log enhancement statistics
        stats = self.graph_enhancer.get_enhancement_statistics(enhanced_graph)
        logger.info(f"Graph enhancement completed: {stats['enhancement_rate']:.1%} edges enhanced")
        
        return enhanced_graph
    
    def _calculate_routes(self, graph: nx.MultiDiGraph, start_node: int, end_node: int,
                         algorithms: List[str]) -> Dict[str, RouteDetails]:
        """Calculate routes using specified algorithms."""
        logger.info(f"Calculating routes using algorithms: {algorithms}")
        
        # Initialize router
        self.router = WeightedAStarRouter(graph, self.config)
        
        # Calculate routes
        routes = self.router.find_multiple_routes(start_node, end_node, algorithms)
        
        # Validate routes
        for algorithm, route in routes.items():
            if not self.router.validate_route(route):
                logger.warning(f"Route validation failed for {algorithm}")
        
        return routes
    
    def _analyze_routes(self, routes: Dict[str, RouteDetails], 
                       start_coords: Tuple[float, float],
                       end_coords: Tuple[float, float]) -> Dict[str, Any]:
        """Analyze routes and generate comparison metrics."""
        logger.info("Analyzing routes...")
        
        # Calculate summary statistics for each route
        summaries = {}
        for algorithm, route in routes.items():
            summaries[algorithm] = self._summarize_route(route, algorithm)
        
        # Generate recommendation
        recommendation = self._generate_recommendation(summaries)
        
        return {
            'route_summaries': summaries,
            'recommendation': recommendation,
            'comparison': self._compare_routes(summaries)
        }
    
    def _summarize_route(self, route: RouteDetails, algorithm: str) -> Dict[str, Any]:
        """Generate summary statistics for a route."""
        # Calculate total crime exposure from crime scores
        total_crime_exposure = sum(route.crime_scores) if route.crime_scores else 0
        
        return {
            'algorithm': algorithm,
            'distance_m': route.total_distance,
            'time_estimate_s': route.total_distance / 1.389,  # 5 km/h walking speed
            'crime_exposure': total_crime_exposure,
            'safety_score': self._calculate_safety_score(route),
            'node_count': len(route.nodes),
            'coordinates_count': len(route.coordinates)
        }
    
    def _calculate_safety_score(self, route: RouteDetails) -> float:
        """Calculate normalized safety score (0-1, higher is safer)."""
        if route.total_distance == 0:
            return 1.0
        
        # Calculate total crime exposure from crime scores
        total_crime_exposure = sum(route.crime_scores) if route.crime_scores else 0
        
        # Normalize crime exposure by distance
        crime_per_meter = total_crime_exposure / route.total_distance
        
        # Convert to safety score (inverse relationship)
        # Use sigmoid-like function to map to 0-1 range
        max_expected_crime_per_meter = 0.01  # Calibrated threshold
        safety_score = 1.0 / (1.0 + crime_per_meter / max_expected_crime_per_meter)
        
        return min(max(safety_score, 0.0), 1.0)
    
    def _generate_recommendation(self, summaries: Dict[str, Dict]) -> Dict[str, Any]:
        """Generate route recommendation based on analysis."""
        if not summaries:
            return {
                'recommended_route': None,
                'reason': 'No routes found',
                'confidence': 0.0
            }
        
        # Simple recommendation logic
        # Prefer balanced approach: not too long, not too unsafe
        best_route = None
        best_score = -1
        
        for algorithm, summary in summaries.items():
            # Weighted score combining safety and efficiency
            safety_weight = self.config.crime_weight
            efficiency_weight = self.config.distance_weight
            
            # Normalize distance (shorter is better)
            distances = [s['distance_m'] for s in summaries.values()]
            min_distance = min(distances)
            distance_score = min_distance / summary['distance_m']
            
            # Combined score
            combined_score = (safety_weight * summary['safety_score'] + 
                            efficiency_weight * distance_score)
            
            if combined_score > best_score:
                best_score = combined_score
                best_route = algorithm
        
        if best_route is None:
            return {
                'recommended_route': None,
                'reason': 'No valid routes found',
                'confidence': 0.0
            }
            
        return {
            'recommended_route': best_route,
            'reason': f'Best balance of safety ({summaries[best_route]["safety_score"]:.2f}) and efficiency',
            'confidence': best_score
        }
    
    def _compare_routes(self, summaries: Dict[str, Dict]) -> Dict[str, Any]:
        """Generate route comparison metrics."""
        if len(summaries) < 2:
            return {}
        
        algorithms = list(summaries.keys())
        route1, route2 = algorithms[0], algorithms[1]
        
        distance_diff = summaries[route2]['distance_m'] - summaries[route1]['distance_m']
        safety_diff = summaries[route2]['safety_score'] - summaries[route1]['safety_score']
        time_diff = summaries[route2]['time_estimate_s'] - summaries[route1]['time_estimate_s']
        
        return {
            'distance_difference_m': distance_diff,
            'safety_difference': safety_diff,
            'time_difference_s': time_diff,
            'detour_factor': summaries[route2]['distance_m'] / summaries[route1]['distance_m']
        }
    
    # Cache management methods
    def predownload_cache(self, force_refresh: bool = False) -> None:
        """Predownload cache for Toronto area."""
        self.network_builder.predownload_cache(force_refresh)
    
    def get_cache_stats(self) -> None:
        """Print cache statistics."""
        self.network_builder.get_cache_stats()
    
    def clear_cache(self, older_than_days: Optional[int] = None) -> None:
        """Clear cache entries."""
        self.network_builder.clear_cache(older_than_days)
    
    # Original methods for compatibility
    def update_config(self, new_config: RoutingConfig) -> None:
        """Update routing configuration."""
        self.config = new_config
        self.config.validate()
        logger.info("Configuration updated")
    
    def get_crime_statistics(self) -> Dict[str, Any]:
        """Get crime data statistics for the current area."""
        if self.crime_processor is None:
            return {}
        
        # Return basic statistics (method compatibility)
        return {
            'processor_initialized': True,
            'bounds': self.current_bounds
        } 
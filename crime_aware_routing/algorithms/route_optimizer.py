"""
Main route optimizer that coordinates crime data, graph enhancement, and routing algorithms.
"""

import logging
from typing import Dict, Tuple, Optional, Any, List
import networkx as nx
import numpy as np
from ..core.crime_processor import CrimeProcessor
from ..core.graph_enhancer import GraphEnhancer
from ..core.network_builder import build_network, find_nearest_nodes
from ..algorithms.crime_weighting.kde_weighter import KDECrimeWeighter
from ..algorithms.astar_weighted import WeightedAStarRouter, RouteDetails
from ..config.routing_config import RoutingConfig

logger = logging.getLogger(__name__)


class RouteOptimizer:
    """
    Main coordinator for crime-aware route optimization.
    
    This class brings together all components: crime data processing, KDE weighting,
    graph enhancement, and routing algorithms.
    """
    
    def __init__(self, crime_data_path: str, config: Optional[RoutingConfig] = None):
        """
        Initialize route optimizer.
        
        Args:
            crime_data_path: Path to crime data GeoJSON file
            config: Routing configuration parameters
        """
        self.config = config or RoutingConfig()
        self.config.validate()
        
        # Initialize components
        self.crime_processor = CrimeProcessor(crime_data_path, self.config)
        self.crime_weighter: Optional[KDECrimeWeighter] = None
        self.graph_enhancer: Optional[GraphEnhancer] = None
        self.router: Optional[WeightedAStarRouter] = None
        
        # State tracking
        self.current_graph: Optional[nx.MultiDiGraph] = None
        self.current_bounds: Optional[Dict[str, float]] = None
        
        logger.info("RouteOptimizer initialized successfully")
    
    def find_safe_route(self, start_coords: Tuple[float, float], 
                       end_coords: Tuple[float, float],
                       algorithms: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Find crime-aware routes between two points.
        
        Args:
            start_coords: (lat, lon) of route start
            end_coords: (lat, lon) of route end
            algorithms: List of algorithms to use for comparison
            
        Returns:
            Dictionary with routes, crime surface, and metrics
        """
        if algorithms is None:
            algorithms = ['weighted_astar', 'shortest_path']
        
        logger.info(f"Finding safe route from {start_coords} to {end_coords}")
        
        try:
            # Step 1: Build street network
            graph = self._build_network(start_coords, end_coords)
            
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
                'crime_surface': self.crime_weighter.get_crime_surface_for_visualization() if self.crime_weighter else None,
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
                    'config': self.config.__dict__
                }
            }
            
            logger.info(f"Route optimization completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Route optimization failed: {e}")
            raise
    
    def _build_network(self, start_coords: Tuple[float, float], 
                      end_coords: Tuple[float, float]) -> nx.MultiDiGraph:
        """Build street network for the route area."""
        logger.info("Building street network...")
        
        # Use existing network builder with optimized parameters
        graph = build_network(
            start_coords, 
            end_coords,
            buffer_factor=self.config.max_network_radius / 1000.0  # Convert to km approximation
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
            self.crime_weighter = KDECrimeWeighter(self.config)
            # Create a single dummy point to avoid KDE fitting issues
            dummy_point = np.array([[
                (start_coords[0] + end_coords[0]) / 2,
                (start_coords[1] + end_coords[1]) / 2
            ]])
            self.crime_weighter.fit(dummy_point, bounds)
        else:
            # Initialize and fit KDE crime weighter
            self.crime_weighter = KDECrimeWeighter(self.config)
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
        """Analyze and compare routes."""
        if not routes:
            return {}
        
        # Get route summaries
        summaries = {name: route.get_summary() for name, route in routes.items()}
        
        # Calculate comparative metrics
        baseline_distance = None
        if 'shortest_path' in summaries:
            baseline_distance = summaries['shortest_path']['total_distance_m']
        elif summaries:
            baseline_distance = min(s['total_distance_m'] for s in summaries.values())
        
        # Add detour analysis
        if baseline_distance and baseline_distance > 0:
            for name, summary in summaries.items():
                detour_meters = summary['total_distance_m'] - baseline_distance
                detour_percent = (detour_meters / baseline_distance) * 100
                summary['detour_meters'] = round(detour_meters, 1)
                summary['detour_percent'] = round(detour_percent, 1)
        
        # Safety comparison
        safety_scores = [s.get('average_crime_score', 0) for s in summaries.values()]
        if safety_scores:
            safest_score = min(safety_scores)
            for name, summary in summaries.items():
                score = summary.get('average_crime_score', 0)
                if safest_score > 0:
                    safety_improvement = ((score - safest_score) / safest_score) * 100
                    summary['safety_relative_to_safest'] = round(safety_improvement, 1)
        
        return {
            'route_summaries': summaries,
            'comparison_baseline': baseline_distance,
            'recommendation': self._generate_recommendation(summaries)
        }
    
    def _generate_recommendation(self, summaries: Dict[str, Dict]) -> Dict[str, Any]:
        """Generate route recommendation based on analysis."""
        if not summaries:
            return {'recommended_route': None, 'reason': 'No routes available'}
        
        # Simple recommendation logic
        # Priority: safety first, then reasonable detour
        
        scored_routes = []
        for name, summary in summaries.items():
            # Safety score (lower is better)
            safety_score = summary.get('average_crime_score', 1.0)
            
            # Distance penalty (higher is worse)
            detour_percent = abs(summary.get('detour_percent', 0))
            distance_penalty = min(detour_percent / 20.0, 1.0)  # Cap at 100%
            
            # Combined score (lower is better)
            combined_score = safety_score + distance_penalty
            
            scored_routes.append({
                'algorithm': name,
                'score': combined_score,
                'safety_score': safety_score,
                'distance_penalty': distance_penalty,
                'summary': summary
            })
        
        # Sort by combined score (lower is better)
        scored_routes.sort(key=lambda x: x['score'])
        
        best_route = scored_routes[0]
        
        # Generate explanation
        if best_route['algorithm'] == 'shortest_path':
            reason = "Shortest path recommended: minimal crime risk detected"
        elif best_route['summary'].get('detour_percent', 0) < 10:
            reason = f"Crime-aware route recommended: {best_route['summary']['detour_percent']:.1f}% longer but safer"
        else:
            reason = f"Safety-optimized route: {best_route['summary']['detour_percent']:.1f}% detour for improved safety"
        
        return {
            'recommended_route': best_route['algorithm'],
            'reason': reason,
            'confidence': 'high' if len(scored_routes) > 1 else 'medium',
            'alternatives': [r['algorithm'] for r in scored_routes[1:]]
        }
    
    def update_config(self, new_config: RoutingConfig) -> None:
        """
        Update configuration and reinitialize components if needed.
        
        Args:
            new_config: New routing configuration
        """
        new_config.validate()
        old_kde_bandwidth = self.config.kde_bandwidth
        
        self.config = new_config
        
        # Update crime processor config
        self.crime_processor.config = new_config
        
        # Update KDE bandwidth if changed
        if (self.crime_weighter and 
            abs(old_kde_bandwidth - new_config.kde_bandwidth) > 1e-6):
            logger.info("Updating KDE bandwidth due to config change")
            self.crime_weighter.update_bandwidth(new_config.kde_bandwidth)
        
        logger.info("Configuration updated successfully")
    
    def get_crime_statistics(self) -> Dict[str, Any]:
        """Get statistics about the loaded crime data."""
        stats = self.crime_processor.get_crime_statistics()
        
        if self.crime_weighter:
            kde_params = self.crime_weighter.get_kde_parameters()
            stats['kde_parameters'] = kde_params
        
        if self.current_bounds:
            area_crimes = self.crime_processor.get_crimes_in_bounds(self.current_bounds)
            stats['current_area'] = {
                'bounds': self.current_bounds,
                'crime_count': len(area_crimes)
            }
        
        return stats 
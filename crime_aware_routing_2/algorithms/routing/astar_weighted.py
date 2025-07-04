"""
Weighted A* routing algorithm for crime-aware pathfinding.
"""

import logging
import time
from typing import List, Optional, Dict, Any, Tuple
import networkx as nx
import numpy as np
from ...config.routing_config import RoutingConfig
from ...data.distance_utils import haversine_distance

logger = logging.getLogger(__name__)


class RouteDetails:
    """Container for detailed route information."""
    
    def __init__(self, nodes: List[int], graph: nx.MultiDiGraph, 
                 algorithm: str = "weighted_astar"):
        """
        Initialize route details.
        
        Args:
            nodes: List of node IDs in route order
            graph: Graph used for routing
            algorithm: Algorithm name used
        """
        self.nodes = nodes
        self.algorithm = algorithm
        self.calculation_time: Optional[float] = None
        
        # Calculate route metrics
        self._calculate_metrics(graph)
    
    def _calculate_metrics(self, graph: nx.MultiDiGraph) -> None:
        """Calculate route distance and safety metrics."""
        self.total_distance = 0.0
        self.total_weighted_distance = 0.0
        self.crime_scores = []
        self.coordinates = []
        
        # Extract coordinates and calculate metrics
        for i, node in enumerate(self.nodes):
            # Get node coordinates
            node_data = graph.nodes[node]
            coord = (node_data.get('y', 0), node_data.get('x', 0))  # (lat, lon)
            self.coordinates.append(coord)
            
            # Calculate edge metrics for non-final nodes
            if i < len(self.nodes) - 1:
                next_node = self.nodes[i + 1]
                
                # Find edge data
                edge_data = None
                if graph.has_edge(node, next_node):
                    edge_data = graph.edges[node, next_node, 0]
                
                if edge_data:
                    # Distance metrics
                    distance = edge_data.get('length', 0)
                    weighted_distance = edge_data.get('weighted_length', distance)
                    crime_score = edge_data.get('crime_score', 0)
                    
                    self.total_distance += distance
                    self.total_weighted_distance += weighted_distance
                    self.crime_scores.append(crime_score)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics for the route."""
        return {
            'algorithm': self.algorithm,
            'node_count': len(self.nodes),
            'total_distance_m': round(self.total_distance, 1),
            'total_weighted_distance': round(self.total_weighted_distance, 1),
            'average_crime_score': round(np.mean(self.crime_scores), 4) if self.crime_scores else 0,
            'max_crime_score': round(np.max(self.crime_scores), 4) if self.crime_scores else 0,
            'calculation_time_ms': round(self.calculation_time * 1000, 1) if self.calculation_time else None
        }


class WeightedAStarRouter:
    """
    A* routing algorithm with customizable edge weights for crime-aware pathfinding.
    """
    
    def __init__(self, graph: nx.MultiDiGraph, config: Optional[RoutingConfig] = None):
        """
        Initialize weighted A* router.
        
        Args:
            graph: Enhanced street network graph with weighted edges
            config: Routing configuration parameters
        """
        self.graph = graph
        self.config = config or RoutingConfig()
        
        # Validate graph has weighted edges
        self._validate_graph()
        
    def _validate_graph(self) -> None:
        """Validate that graph has required attributes for weighted routing."""
        if not self.graph.edges:
            raise ValueError("Graph has no edges")
        
        # Check for weighted_length attribute
        sample_edges = list(self.graph.edges(data=True))[:min(10, len(self.graph.edges))]
        weighted_edges = sum(1 for _, _, data in sample_edges if 'weighted_length' in data)
        
        if weighted_edges == 0:
            logger.warning("No weighted edges found - falling back to length attribute")
        else:
            logger.info(f"Graph validation passed: {weighted_edges}/{len(sample_edges)} sample edges have weights")
    
    def find_route(self, start_node: int, end_node: int, 
                  weight_attr: str = 'weighted_length') -> RouteDetails:
        """
        Find optimal route using weighted A* algorithm.
        
        Args:
            start_node: Starting node ID
            end_node: Ending node ID
            weight_attr: Edge attribute to use for weights
            
        Returns:
            RouteDetails object with path and metrics
        """
        start_time = time.time()
        
        try:
            logger.debug(f"Finding route from {start_node} to {end_node} using {weight_attr}")
            
            # Use NetworkX A* with custom weight and heuristic
            path = nx.astar_path(
                self.graph,
                start_node,
                end_node,
                heuristic=self._heuristic_function,
                weight=weight_attr
            )
            
            calculation_time = time.time() - start_time
            
            # Create route details
            route = RouteDetails(path, self.graph, "weighted_astar")
            route.calculation_time = calculation_time
            
            logger.info(f"Route found: {len(path)} nodes, "
                       f"{route.total_distance:.0f}m, "
                       f"calculated in {calculation_time*1000:.1f}ms")
            
            return route
            
        except nx.NetworkXNoPath:
            logger.error(f"No path found from {start_node} to {end_node}")
            
            # Fallback to shortest path if configured
            if self.config.fallback_to_shortest:
                logger.info("Attempting fallback to shortest path")
                return self._find_shortest_path_fallback(start_node, end_node, start_time)
            else:
                raise RuntimeError(f"No path found from {start_node} to {end_node}")
                
        except Exception as e:
            logger.error(f"Route calculation failed: {e}")
            
            # Fallback to shortest path if configured
            if self.config.fallback_to_shortest:
                logger.info("Attempting fallback to shortest path due to error")
                return self._find_shortest_path_fallback(start_node, end_node, start_time)
            else:
                raise
    
    def _find_shortest_path_fallback(self, start_node: int, end_node: int, 
                                   start_time: float) -> RouteDetails:
        """
        Fallback to shortest path when weighted routing fails.
        
        Args:
            start_node: Starting node ID
            end_node: Ending node ID
            start_time: Original calculation start time
            
        Returns:
            RouteDetails for shortest path
        """
        try:
            path = nx.shortest_path(
                self.graph,
                start_node,
                end_node,
                weight='length'
            )
            
            calculation_time = time.time() - start_time
            
            route = RouteDetails(path, self.graph, "shortest_path_fallback")
            route.calculation_time = calculation_time
            
            logger.warning(f"Using fallback shortest path: {len(path)} nodes, "
                          f"{route.total_distance:.0f}m")
            
            return route
            
        except Exception as e:
            raise RuntimeError(f"Both weighted and fallback routing failed: {e}")
    
    def _heuristic_function(self, node1: int, node2: int) -> float:
        """
        Heuristic function for A* algorithm using haversine distance.
        
        Args:
            node1: First node ID
            node2: Second node ID
            
        Returns:
            Estimated distance between nodes
        """
        try:
            # Get node coordinates
            node1_data = self.graph.nodes[node1]
            node2_data = self.graph.nodes[node2]
            
            lat1, lon1 = node1_data['y'], node1_data['x']
            lat2, lon2 = node2_data['y'], node2_data['x']
            
            # Calculate haversine distance
            return haversine_distance(lat1, lon1, lat2, lon2)
            
        except KeyError:
            # Fallback if coordinates missing
            return 0.0
    
    def find_multiple_routes(self, start_node: int, end_node: int, 
                           algorithms: Optional[List[str]] = None) -> Dict[str, RouteDetails]:
        """
        Find multiple routes using different algorithms for comparison.
        
        Args:
            start_node: Starting node ID
            end_node: Ending node ID
            algorithms: List of algorithm names to use
            
        Returns:
            Dictionary mapping algorithm names to RouteDetails
        """
        if algorithms is None:
            algorithms = ['weighted_astar', 'shortest_path']
        
        routes = {}
        
        for algorithm in algorithms:
            try:
                if algorithm == 'weighted_astar':
                    route = self.find_route(start_node, end_node, 'weighted_length')
                elif algorithm == 'shortest_path':
                    route = self.find_route_shortest(start_node, end_node)
                elif algorithm == 'fastest_path':
                    # Could implement time-based routing here
                    route = self.find_route_shortest(start_node, end_node)
                else:
                    logger.warning(f"Unknown algorithm: {algorithm}")
                    continue
                
                routes[algorithm] = route
                
            except Exception as e:
                logger.error(f"Failed to calculate {algorithm} route: {e}")
        
        return routes
    
    def find_route_shortest(self, start_node: int, end_node: int) -> RouteDetails:
        """
        Find shortest path route (baseline comparison).
        
        Args:
            start_node: Starting node ID
            end_node: Ending node ID
            
        Returns:
            RouteDetails for shortest path
        """
        start_time = time.time()
        
        try:
            path = nx.shortest_path(
                self.graph,
                start_node,
                end_node,
                weight='length'
            )
            
            calculation_time = time.time() - start_time
            
            route = RouteDetails(path, self.graph, "shortest_path")
            route.calculation_time = calculation_time
            
            return route
            
        except Exception as e:
            raise RuntimeError(f"Shortest path calculation failed: {e}")
    
    def validate_route(self, route: RouteDetails) -> bool:
        """
        Validate that a route is feasible and meets constraints.
        
        Args:
            route: Route to validate
            
        Returns:
            True if route is valid
        """
        if not route.nodes or len(route.nodes) < 2:
            return False
        
        # Check if route exceeds maximum detour ratio
        if hasattr(route, 'total_distance'):
            # Calculate baseline shortest path for comparison
            try:
                shortest_path = nx.shortest_path_length(
                    self.graph,
                    route.nodes[0],
                    route.nodes[-1],
                    weight='length'
                )
                
                detour_ratio = route.total_distance / shortest_path
                if detour_ratio > self.config.max_detour_ratio:
                    logger.warning(f"Route exceeds max detour ratio: {detour_ratio:.2f}")
                    return False
                    
            except Exception:
                # Can't calculate baseline - assume valid
                pass
        
        # Check path continuity
        for i in range(len(route.nodes) - 1):
            if not self.graph.has_edge(route.nodes[i], route.nodes[i + 1]):
                logger.error(f"Discontinuous path at nodes {route.nodes[i]} -> {route.nodes[i + 1]}")
                return False
        
        return True 
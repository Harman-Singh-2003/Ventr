"""
Graph enhancement module for adding crime-based weights to street network edges.
"""

import logging
import numpy as np
from typing import Dict, Optional, Any, Tuple
import networkx as nx
from shapely.geometry import LineString, Point
from ...algorithms.crime_weighting.base_weighter import BaseCrimeWeighter
from ...config.routing_config import RoutingConfig
from ...data.distance_utils import haversine_distance

logger = logging.getLogger(__name__)


class GraphEnhancer:
    """
    Enhance street network graphs with crime-based edge weights for safer routing.
    """
    
    def __init__(self, crime_weighter: BaseCrimeWeighter, config: Optional[RoutingConfig] = None):
        """
        Initialize graph enhancer.
        
        Args:
            crime_weighter: Fitted crime weighting strategy
            config: Routing configuration parameters
        """
        self.crime_weighter = crime_weighter
        self.config = config or RoutingConfig()
        self.edge_cache: Dict[Tuple[int, int], float] = {}
        
    def add_crime_weights(self, graph: nx.MultiDiGraph, 
                         distance_weight: Optional[float] = None,
                         crime_weight: Optional[float] = None) -> nx.MultiDiGraph:
        """
        Add crime-based weights to graph edges.
        
        Args:
            graph: OSMnx street network graph
            distance_weight: Weight for distance component (0-1)
            crime_weight: Weight for crime component (0-1)
            
        Returns:
            Enhanced graph with 'weighted_length' edge attributes
        """
        import time
        
        enhancement_start_time = time.perf_counter()
        
        if distance_weight is None:
            distance_weight = self.config.distance_weight
        if crime_weight is None:
            crime_weight = self.config.crime_weight
            
        # Validate weights
        if abs(distance_weight + crime_weight - 1.0) > 1e-6:
            raise ValueError(f"Weights must sum to 1.0, got {distance_weight + crime_weight}")
        
        logger.info(f"Adding crime weights to {len(graph.edges)} edges "
                   f"(distance_weight={distance_weight:.2f}, crime_weight={crime_weight:.2f})")
        
        # Ensure crime weighter is fitted
        weighter_validation_start = time.perf_counter()
        self.crime_weighter.validate_fitted()
        weighter_validation_time = time.perf_counter() - weighter_validation_start
        logger.info(f"Weighter validation completed in {weighter_validation_time:.3f}s")
        
        # Get distance statistics for normalization
        normalization_start = time.perf_counter()
        distances = [data.get('length', 0) for _, _, data in graph.edges(data=True)]
        max_distance = max(distances) if distances else 1.0
        normalization_time = time.perf_counter() - normalization_start
        logger.info(f"Distance normalization completed in {normalization_time:.3f}s")
        
        # Process each edge
        processing_start = time.perf_counter()
        edges_processed = 0
        for u, v, key, data in graph.edges(keys=True, data=True):
            try:
                # Get edge geometry
                edge_geometry = self._get_edge_geometry(graph, u, v, data)
                
                if edge_geometry is None:
                    # Fallback: use original length
                    data['weighted_length'] = data.get('length', 1.0)
                    continue
                
                # Calculate crime score for this edge
                crime_score = self._get_edge_crime_score(u, v, edge_geometry)
                
                # Get distance component
                edge_distance = data.get('length', 1.0)
                normalized_distance = edge_distance / max_distance
                
                # Apply adaptive weighting if enabled
                if self.config.adaptive_weighting:
                    adaptive_distance_weight, adaptive_crime_weight = self._calculate_adaptive_weights(
                        edge_distance, crime_score, distance_weight, crime_weight
                    )
                else:
                    adaptive_distance_weight = distance_weight
                    adaptive_crime_weight = crime_weight
                
                # Calculate composite weight
                crime_penalty = crime_score * self.config.crime_penalty_scale
                weighted_length = (
                    adaptive_distance_weight * edge_distance +
                    adaptive_crime_weight * crime_penalty
                )
                
                # Store enhanced weight
                data['weighted_length'] = max(weighted_length, 0.1)  # Prevent zero weights
                data['crime_score'] = crime_score
                data['original_length'] = edge_distance
                
                edges_processed += 1
                
                if edges_processed % 1000 == 0:
                    logger.debug(f"Processed {edges_processed}/{len(graph.edges)} edges")
                    
            except Exception as e:
                logger.warning(f"Failed to process edge ({u}, {v}): {e}")
                # Fallback to original length
                data['weighted_length'] = data.get('length', 1.0)
        
        processing_time = time.perf_counter() - processing_start
        total_enhancement_time = time.perf_counter() - enhancement_start_time
        
        logger.info(f"Successfully enhanced {edges_processed} edges with crime weights")
        logger.info(f"Edge processing completed in {processing_time:.3f}s")
        logger.info(f"Total graph enhancement completed in {total_enhancement_time:.3f}s")
        return graph
    
    def _get_edge_geometry(self, graph: nx.MultiDiGraph, u: int, v: int, 
                          edge_data: Dict[str, Any]) -> Optional[LineString]:
        """
        Extract geometry for a graph edge.
        
        Args:
            graph: NetworkX graph
            u, v: Edge node IDs
            edge_data: Edge data dictionary
            
        Returns:
            Shapely LineString geometry or None if unavailable
        """
        try:
            # Try to get geometry from edge data
            if 'geometry' in edge_data:
                return edge_data['geometry']
            
            # Fallback: create LineString from node coordinates
            u_data = graph.nodes[u]
            v_data = graph.nodes[v]
            
            if 'x' in u_data and 'y' in u_data and 'x' in v_data and 'y' in v_data:
                return LineString([
                    (u_data['x'], u_data['y']),
                    (v_data['x'], v_data['y'])
                ])
            
            return None
            
        except Exception as e:
            logger.debug(f"Failed to extract geometry for edge ({u}, {v}): {e}")
            return None
    
    def _get_edge_crime_score(self, u: int, v: int, edge_geometry: LineString) -> float:
        """
        Get crime score for an edge with caching.
        
        Args:
            u, v: Edge node IDs
            edge_geometry: Edge geometry
            
        Returns:
            Crime score for the edge
        """
        # Check cache first
        edge_key = (min(u, v), max(u, v))
        if self.config.enable_caching and edge_key in self.edge_cache:
            return self.edge_cache[edge_key]
        
        # Calculate crime score
        crime_score = self.crime_weighter.get_edge_crime_score(edge_geometry)
        
        # Cache result
        if self.config.enable_caching:
            self.edge_cache[edge_key] = crime_score
        
        return crime_score
    
    def _calculate_adaptive_weights(self, edge_distance: float, crime_score: float,
                                  base_distance_weight: float, base_crime_weight: float) -> Tuple[float, float]:
        """
        Calculate adaptive weights based on edge characteristics using smooth transitions.
        
        Args:
            edge_distance: Length of edge in meters
            crime_score: Crime score for edge
            base_distance_weight: Base distance weight
            base_crime_weight: Base crime weight
            
        Returns:
            Tuple of (adaptive_distance_weight, adaptive_crime_weight)
        """
        # Very short edges: gradually prioritize distance over crime (smooth transition)
        if edge_distance < self.config.min_detour_threshold:
            # Smooth scaling based on edge length (0 to min_detour_threshold)
            length_factor = edge_distance / self.config.min_detour_threshold
            distance_boost = 0.1 * (1.0 - length_factor)  # Max 0.1 boost for very short edges
            
            adaptive_distance_weight = min(base_distance_weight + distance_boost, 1.0)
            adaptive_crime_weight = max(base_crime_weight - distance_boost, 0.0)
            return adaptive_distance_weight, adaptive_crime_weight
        
        # Smooth crime-based adjustment (replaces hard thresholds)
        # Use sigmoid-like smooth transitions instead of hard jumps
        
        # For low crime areas (0.0 to 0.2): gradually favor distance
        if crime_score <= 0.2:
            # Smooth transition from 0.1 boost at score=0 to 0 boost at score=0.2
            distance_boost = 0.1 * (0.2 - crime_score) / 0.2
        # For high crime areas (0.6 to 1.0): gradually favor safety  
        elif crime_score >= 0.6:
            # Smooth transition from 0 boost at score=0.6 to 0.1 boost at score=1.0
            distance_boost = -0.1 * (crime_score - 0.6) / 0.4  # Negative = reduce distance weight
        else:
            # Normal range (0.2 to 0.6): no adjustment
            distance_boost = 0.0
        
        adaptive_distance_weight = max(0.0, min(1.0, base_distance_weight + distance_boost))
        adaptive_crime_weight = max(0.0, min(1.0, base_crime_weight - distance_boost))
        
        return adaptive_distance_weight, adaptive_crime_weight
    
    def get_enhancement_statistics(self, graph: nx.MultiDiGraph) -> Dict[str, Any]:
        """
        Get statistics about the graph enhancement process.
        
        Args:
            graph: Enhanced graph
            
        Returns:
            Dictionary with enhancement statistics
        """
        edges_with_weights = 0
        crime_scores = []
        weight_ratios = []
        
        for _, _, data in graph.edges(data=True):
            if 'weighted_length' in data and 'crime_score' in data:
                edges_with_weights += 1
                crime_scores.append(data['crime_score'])
                
                original_length = data.get('original_length', data.get('length', 1.0))
                if original_length > 0:
                    ratio = data['weighted_length'] / original_length
                    weight_ratios.append(ratio)
        
        return {
            'total_edges': len(graph.edges),
            'edges_with_crime_weights': edges_with_weights,
            'enhancement_rate': edges_with_weights / len(graph.edges) if graph.edges else 0,
            'crime_score_stats': {
                'mean': np.mean(crime_scores) if crime_scores else 0,
                'std': np.std(crime_scores) if crime_scores else 0,
                'min': np.min(crime_scores) if crime_scores else 0,
                'max': np.max(crime_scores) if crime_scores else 0
            },
            'weight_ratio_stats': {
                'mean': np.mean(weight_ratios) if weight_ratios else 1.0,
                'std': np.std(weight_ratios) if weight_ratios else 0,
                'min': np.min(weight_ratios) if weight_ratios else 1.0,
                'max': np.max(weight_ratios) if weight_ratios else 1.0
            },
            'cache_size': len(self.edge_cache)
        }
    
    def clear_cache(self) -> None:
        """Clear the edge crime score cache."""
        self.edge_cache.clear()
        logger.debug("Edge cache cleared")
    
    def validate_enhanced_graph(self, graph: nx.MultiDiGraph) -> bool:
        """
        Validate that the graph has been properly enhanced.
        
        Args:
            graph: Graph to validate
            
        Returns:
            True if graph is valid, False otherwise
        """
        if not graph.edges:
            return False
        
        # Check that most edges have weighted_length
        weighted_edges = sum(1 for _, _, data in graph.edges(data=True) 
                           if 'weighted_length' in data)
        
        enhancement_rate = weighted_edges / len(graph.edges)
        
        if enhancement_rate < 0.8:  # At least 80% of edges should be enhanced
            logger.warning(f"Low enhancement rate: {enhancement_rate:.2%}")
            return False
        
        # Check for invalid weights
        for _, _, data in graph.edges(data=True):
            weight = data.get('weighted_length', 0)
            if weight <= 0 or not np.isfinite(weight):
                logger.warning(f"Invalid weight found: {weight}")
                return False
        
        return True 
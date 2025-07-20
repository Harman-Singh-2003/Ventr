"""
Enhanced network builder that uses pre-enhanced graphs for optimal performance.

This module provides a network builder that can use pre-computed enhanced graphs
to eliminate runtime graph enhancement overhead while maintaining exact compatibility
with the current implementation.
"""

import logging
import time
from typing import Tuple
import networkx as nx
from .enhanced_graph_cache import get_enhanced_cache
from .network_cache import get_network_cache
from .network_builder import build_network  # Reuse existing function

logger = logging.getLogger(__name__)

def build_enhanced_network(start_coords: Tuple[float, float], 
                          end_coords: Tuple[float, float],
                          crime_weight: float = 0.1) -> nx.MultiDiGraph:
    """
    Build enhanced network with crime weights pre-applied.
    
    Uses enhanced cache when available for optimal performance,
    falls back to standard network building for other crime weights.
    
    Args:
        start_coords: (lat, lon) of start point
        end_coords: (lat, lon) of end point
        crime_weight: Crime weighting parameter (only 0.1 is cached)
        
    Returns:
        NetworkX MultiDiGraph with crime weights applied
    """
    import time
    
    network_start_time = time.perf_counter()
    
    # Calculate center point and network radius
    center_lat = (start_coords[0] + end_coords[0]) / 2
    center_lon = (start_coords[1] + end_coords[1]) / 2
    center_coords = (center_lat, center_lon)
    
    from crime_aware_routing_2.data.distance_utils import haversine_distance
    route_distance = haversine_distance(
        start_coords[0], start_coords[1], 
        end_coords[0], end_coords[1]
    )
    
    # Network radius: at least 800m, or 80% of route distance
    network_radius = max(800, route_distance * 0.8)
    
    logger.info(f"Building enhanced network around ({center_lat:.4f}, {center_lon:.4f})")
    logger.info(f"Route distance: {route_distance:.0f}m, Network radius: {network_radius:.0f}m")
    
    try:
        # MEMORY OPTIMIZATION: Use enhanced cache when available (regardless of crime_weight)
        enhanced_cache = get_enhanced_cache()
        
        # Check if enhanced cache is loaded (memory-optimized scenario)
        if enhanced_cache.enhanced_graph is not None:
            logger.info("Enhanced cache is primary cache - checking route coverage")
            
            # Check if route is within enhanced cache coverage
            if enhanced_cache.is_route_in_cache(start_coords, end_coords, buffer_m=0):
                logger.info("Route is within enhanced cache area - using pre-enhanced graph")
                
                # Extract pre-enhanced subgraph
                extraction_start = time.perf_counter()
                extraction_radius = network_radius + 500  # Add safety buffer
                enhanced_subgraph = enhanced_cache.extract_subgraph(center_coords, extraction_radius)
                extraction_time = time.perf_counter() - extraction_start
                
                if enhanced_subgraph is not None:
                    total_time = time.perf_counter() - network_start_time
                    enhanced_edges = sum(1 for _, _, data in enhanced_subgraph.edges(data=True) 
                                       if 'crime_score' in data)
                    
                    logger.info(f"✓ Enhanced network extracted from cache: {len(enhanced_subgraph.nodes)} nodes, "
                               f"{len(enhanced_subgraph.edges)} edges ({enhanced_edges} enhanced)")
                    logger.info(f"Extraction time: {extraction_time:.3f}s, Total enhanced network building: {total_time:.3f}s")
                    return enhanced_subgraph
                else:
                    logger.warning("Enhanced cache extraction failed, checking network cache fallback")
            else:
                logger.info("Route is outside enhanced cache area - checking network cache fallback")
        
        # Fallback to network cache if available
        from .network_builder import build_network
        network_cache = get_network_cache()
        if network_cache.large_graph is not None:
            logger.info("Using network cache for standard network building")
            standard_start = time.perf_counter()
            standard_graph = build_network(start_coords, end_coords)
            standard_time = time.perf_counter() - standard_start
            
            total_time = time.perf_counter() - network_start_time
            logger.info(f"✓ Standard network built: {len(standard_graph.nodes)} nodes, "
                       f"{len(standard_graph.edges)} edges in {standard_time:.3f}s")
            logger.info(f"Total enhanced network building (network cache): {total_time:.3f}s")
            
            return standard_graph
        
        # Last resort: extract larger area from enhanced cache if available
        if enhanced_cache.enhanced_graph is not None:
            logger.warning("Network cache unavailable - attempting larger extraction from enhanced cache")
            larger_radius = network_radius * 1.5  # 50% larger radius
            enhanced_subgraph = enhanced_cache.extract_subgraph(center_coords, larger_radius)
            
            if enhanced_subgraph is not None:
                logger.info(f"✓ Larger enhanced subgraph extracted: {len(enhanced_subgraph.nodes)} nodes")
                return enhanced_subgraph
            
            # Check if route is within enhanced cache coverage
            if enhanced_cache.is_route_in_cache(start_coords, end_coords, buffer_m=0):
                logger.info("Route is within enhanced cache area - using pre-enhanced graph")
                
                # Extract pre-enhanced subgraph
                extraction_start = time.perf_counter()
                extraction_radius = network_radius + 500  # Add safety buffer
                enhanced_subgraph = enhanced_cache.extract_subgraph(center_coords, extraction_radius)
                extraction_time = time.perf_counter() - extraction_start
                
                if enhanced_subgraph is not None:
                    total_time = time.perf_counter() - network_start_time
                    enhanced_edges = sum(1 for _, _, data in enhanced_subgraph.edges(data=True) 
                                       if 'crime_score' in data)
                    
                    logger.info(f"✓ Enhanced network extracted from cache: {len(enhanced_subgraph.nodes)} nodes, "
                               f"{len(enhanced_subgraph.edges)} edges ({enhanced_edges} enhanced)")
                    logger.info(f"Extraction time: {extraction_time:.3f}s, Total enhanced network building: {total_time:.3f}s")
                    return enhanced_subgraph
                else:
                    logger.warning("Enhanced cache extraction failed, falling back to standard method")
            else:
                logger.info("Route is outside enhanced cache area - using standard method")
        else:
            logger.info(f"Crime weight {crime_weight} not cached - using standard method")
        
        # Fall back to standard network building
        logger.info("Using standard network building with runtime enhancement")
        standard_start = time.perf_counter()
        standard_graph = build_network(start_coords, end_coords)
        standard_time = time.perf_counter() - standard_start
        
        total_time = time.perf_counter() - network_start_time
        logger.info(f"✓ Standard network built: {len(standard_graph.nodes)} nodes, "
                   f"{len(standard_graph.edges)} edges in {standard_time:.3f}s")
        logger.info(f"Total enhanced network building (standard fallback): {total_time:.3f}s")
        
        return standard_graph
        
    except Exception as e:
        logger.error(f"Failed to build enhanced network: {e}")
        raise RuntimeError(f"Failed to build enhanced network: {e}") 
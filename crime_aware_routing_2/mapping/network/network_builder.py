"""
Clean network builder for obtaining street networks efficiently.
"""

import osmnx as ox
import networkx as nx
import logging
from typing import Tuple
from ...data.distance_utils import haversine_distance
from .network_cache import get_network_cache

logger = logging.getLogger(__name__)

def build_network(start_coords: Tuple[float, float], 
                 end_coords: Tuple[float, float],
                 buffer_factor: float = 0.8) -> 'nx.MultiDiGraph':
    """
    Build a street network that encompasses the route with intelligent sizing.
    
    Uses cached network when available for better performance, falls back to
    direct OSMnx download when route is outside cached area.
    
    Args:
        start_coords: (lat, lon) of start point
        end_coords: (lat, lon) of end point  
        buffer_factor: Factor to determine network size (0.8 = 80% of route distance)
        
    Returns:
        NetworkX MultiDiGraph with street network
    """
    import time
    
    network_start_time = time.perf_counter()
    
    # Calculate center point and network radius
    calc_start = time.perf_counter()
    center_lat = (start_coords[0] + end_coords[0]) / 2
    center_lon = (start_coords[1] + end_coords[1]) / 2
    center_coords = (center_lat, center_lon)
    
    # Calculate route distance to determine appropriate network size
    route_distance = haversine_distance(
        start_coords[0], start_coords[1], 
        end_coords[0], end_coords[1]
    )
    
    # Network radius: at least 800m, or 80% of route distance (learned optimal)
    network_radius = max(800, route_distance * buffer_factor)
    calc_time = time.perf_counter() - calc_start
    
    logger.info(f"Building network around ({center_lat:.4f}, {center_lon:.4f})")
    logger.info(f"Route distance: {route_distance:.0f}m, Network radius: {network_radius:.0f}m")
    logger.info(f"Network parameters calculated in {calc_time:.3f}s")
    
    try:
        # Try to use cached network first
        cache = get_network_cache()
        
        # Load cache if not already loaded
        if not cache.large_graph:
            cache.load_cache()
        
        if cache.is_route_in_cache(start_coords, end_coords, buffer_m=0):
            logger.info("Route is within cached area - using full cached graph (no extraction)")
            
            # Extract from cache with buffer for the route
            extraction_radius = network_radius + 500  # Add safety buffer
            
            G = cache.extract_subgraph(center_coords, extraction_radius)
            
            if G is not None:
                total_time = time.perf_counter() - network_start_time
                logger.info(f"✓ Network extracted from cache: {len(G.nodes)} nodes, {len(G.edges)} edges")
                logger.info(f"Total cached network building completed in {total_time:.3f}s")
                return G
            else:
                logger.warning("Cache extraction failed, falling back to direct download")
        else:
            logger.info("Route is outside cached area - using direct OSMnx download")
        
        # Fall back to direct OSMnx download
        download_start = time.perf_counter()
        G = ox.graph_from_point(
            center_coords,
            dist=network_radius,
            network_type='walk',  # Optimized for pedestrian routing
            simplify=True         # Simplify for better performance
        )
        download_time = time.perf_counter() - download_start
        total_time = time.perf_counter() - network_start_time
        
        logger.info(f"✓ Network downloaded: {len(G.nodes)} nodes, {len(G.edges)} edges")
        logger.info(f"Network download completed in {download_time:.3f}s")
        logger.info(f"Total network building completed in {total_time:.3f}s")
        return G
        
    except Exception as e:
        raise RuntimeError(f"Failed to load street network: {e}")

def find_nearest_nodes(graph, start_coords: Tuple[float, float], 
                      end_coords: Tuple[float, float]) -> Tuple[int, int]:
    """
    Find nearest nodes in the graph for start and end coordinates.
    
    Args:
        graph: NetworkX graph
        start_coords: (lat, lon) of start point
        end_coords: (lat, lon) of end point
        
    Returns:
        Tuple of (start_node_id, end_node_id)
    """
    import time
    
    try:
        # Use OSMnx to find nearest nodes (reverted to original reliable method)
        nearest_start = time.perf_counter()
        start_node = ox.nearest_nodes(graph, start_coords[1], start_coords[0])
        end_node = ox.nearest_nodes(graph, end_coords[1], end_coords[0])
        nearest_time = time.perf_counter() - nearest_start
        
        logger.info(f"Nearest nodes found in {nearest_time:.3f}s (start: {start_node}, end: {end_node})")
        return start_node, end_node
        
    except Exception as e:
        raise RuntimeError(f"Failed to find nearest nodes: {e}")

# Virtual node functionality temporarily removed due to connectivity issues
# Will be re-implemented with proper testing in future versions 
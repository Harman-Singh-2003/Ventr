"""
Clean network builder for obtaining street networks efficiently.
"""

import osmnx as ox
import networkx as nx
from typing import Tuple
from ...data.distance_utils import haversine_distance

def build_network(start_coords: Tuple[float, float], 
                 end_coords: Tuple[float, float],
                 buffer_factor: float = 0.8) -> 'nx.MultiDiGraph':
    """
    Build a street network that encompasses the route with intelligent sizing.
    
    Args:
        start_coords: (lat, lon) of start point
        end_coords: (lat, lon) of end point  
        buffer_factor: Factor to determine network size (0.8 = 80% of route distance)
        
    Returns:
        NetworkX MultiDiGraph with street network
    """
    # Calculate center point and network radius
    center_lat = (start_coords[0] + end_coords[0]) / 2
    center_lon = (start_coords[1] + end_coords[1]) / 2
    
    # Calculate route distance to determine appropriate network size
    route_distance = haversine_distance(
        start_coords[0], start_coords[1], 
        end_coords[0], end_coords[1]
    )
    
    # Network radius: at least 800m, or 80% of route distance (learned optimal)
    network_radius = max(800, route_distance * buffer_factor)
    
    print(f"Building network around ({center_lat:.4f}, {center_lon:.4f})")
    print(f"Route distance: {route_distance:.0f}m, Network radius: {network_radius:.0f}m")
    
    try:
        # Load street network with walking configuration
        G = ox.graph_from_point(
            (center_lat, center_lon),
            dist=network_radius,
            network_type='walk',  # Optimized for pedestrian routing
            simplify=True         # Simplify for better performance
        )
        
        print(f"✓ Network loaded: {len(G.nodes)} nodes, {len(G.edges)} edges")
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
    try:
        # Use OSMnx to find nearest nodes (reverted to original reliable method)
        start_node = ox.nearest_nodes(graph, start_coords[1], start_coords[0])
        end_node = ox.nearest_nodes(graph, end_coords[1], end_coords[0])
        return start_node, end_node
        
    except Exception as e:
        raise RuntimeError(f"Failed to find nearest nodes: {e}")

# Virtual node functionality temporarily removed due to connectivity issues
# Will be re-implemented with proper testing in future versions 
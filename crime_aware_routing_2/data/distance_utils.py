"""
Distance calculation utilities optimized for performance.
"""

import math
from typing import List, Dict

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on Earth.
    
    Args:
        lat1, lon1: First point coordinates
        lat2, lon2: Second point coordinates
        
    Returns:
        Distance in meters
    """
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    # Haversine formula
    a = (math.sin(delta_lat / 2) ** 2 + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    # Earth's radius in meters
    R = 6371000
    return R * c

def calculate_route_distance(route_nodes: List, graph) -> float:
    """
    Calculate the total geometric distance of a route.
    
    Args:
        route_nodes: List of node IDs in the route
        graph: NetworkX graph with 'length' edge attributes
        
    Returns:
        Total distance in meters
    """
    total_distance = 0.0
    
    for i in range(len(route_nodes) - 1):
        current_node = route_nodes[i]
        next_node = route_nodes[i + 1]
        
        if graph.has_edge(current_node, next_node):
            edge_data = graph.edges[current_node, next_node, 0]
            total_distance += edge_data.get('length', 0)
    
    return total_distance

def get_network_bounds(graph) -> Dict[str, float]:
    """
    Get the geographic bounds of a network.
    
    Args:
        graph: NetworkX graph with node coordinates
        
    Returns:
        Dictionary with lat_min, lat_max, lon_min, lon_max
    """
    lats = [graph.nodes[node]['y'] for node in graph.nodes()]
    lons = [graph.nodes[node]['x'] for node in graph.nodes()]
    
    return {
        'lat_min': min(lats),
        'lat_max': max(lats),
        'lon_min': min(lons),
        'lon_max': max(lons)
    } 
"""
Network caching system for OSMnx street networks.

This module implements efficient caching of large street networks to avoid
repeated downloads for routing requests within the cached area.
"""

import os
import time
import pickle
import logging
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import numpy as np
import osmnx as ox
import networkx as nx
from osmnx.truncate import truncate_graph_dist
from ...data.distance_utils import haversine_distance

logger = logging.getLogger(__name__)


class NetworkCache:
    """
    Manages caching of OSMnx street networks for efficient reuse.
    
    Downloads a large area once and extracts smaller subgraphs as needed,
    significantly reducing API calls and improving performance.
    """
    
    def __init__(self, cache_dir: str = "osmnx_cache", cache_file: str = "toronto_network.pkl"):
        """
        Initialize network cache.
        
        Args:
            cache_dir: Directory for cache files
            cache_file: Filename for the cached network
        """
        self.cache_dir = Path(cache_dir)
        self.cache_file = self.cache_dir / cache_file
        self.large_graph: Optional[nx.MultiDiGraph] = None
        self.cache_center: Optional[Tuple[float, float]] = None
        self.cache_radius: Optional[float] = None
        
        # Ensure cache directory exists
        self.cache_dir.mkdir(exist_ok=True)
        
    def is_cache_available(self) -> bool:
        """Check if cached network file exists."""
        return self.cache_file.exists()
    
    def load_cache(self) -> bool:
        """
        Load cached network from disk.
        
        Returns:
            True if cache loaded successfully, False otherwise
        """
        if not self.is_cache_available():
            logger.info(f"No cache file found at {self.cache_file}")
            return False
            
        try:
            logger.info(f"Loading cached network from {self.cache_file}")
            start_time = time.perf_counter()
            
            with open(self.cache_file, 'rb') as f:
                cache_data = pickle.load(f)
            
            self.large_graph = cache_data['graph']
            self.cache_center = cache_data['center']
            self.cache_radius = cache_data['radius']
            
            load_time = time.perf_counter() - start_time
            logger.info(f"✓ Cached network loaded: {len(self.large_graph.nodes)} nodes, "
                       f"{len(self.large_graph.edges)} edges in {load_time:.3f}s")
            logger.info(f"Cache covers {self.cache_radius/1000:.1f}km radius around "
                       f"({self.cache_center[0]:.4f}, {self.cache_center[1]:.4f})")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load cache: {e}")
            self.large_graph = None
            self.cache_center = None
            self.cache_radius = None
            return False
    
    def create_cache(self, center_coords: Tuple[float, float], radius_m: float) -> bool:
        """
        Create cache by downloading large area from OSMnx.
        
        Args:
            center_coords: (lat, lon) center of area to cache
            radius_m: Radius in meters for cached area
            
        Returns:
            True if cache created successfully, False otherwise
        """
        try:
            logger.info(f"Creating network cache for {radius_m/1000:.1f}km radius around "
                       f"({center_coords[0]:.4f}, {center_coords[1]:.4f})")
            
            start_time = time.perf_counter()
            
            # Download large area from OSMnx
            large_graph = ox.graph_from_point(
                center_coords,
                dist=radius_m,
                network_type='walk',
                simplify=True
            )
            
            download_time = time.perf_counter() - start_time
            logger.info(f"✓ Downloaded {len(large_graph.nodes)} nodes, "
                       f"{len(large_graph.edges)} edges in {download_time:.3f}s")
            
            # Prepare cache data
            cache_data = {
                'graph': large_graph,
                'center': center_coords,
                'radius': radius_m,
                'created_at': time.time(),
                'osmnx_version': ox.__version__
            }
            
            # Save to cache file
            logger.info(f"Saving cache to {self.cache_file}")
            save_start = time.perf_counter()
            
            with open(self.cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
            
            save_time = time.perf_counter() - save_start
            total_time = time.perf_counter() - start_time
            
            logger.info(f"✓ Cache saved in {save_time:.3f}s (total: {total_time:.3f}s)")
            
            # Store in memory
            self.large_graph = large_graph
            self.cache_center = center_coords
            self.cache_radius = radius_m
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create cache: {e}")
            return False
    
    def is_point_in_cache(self, coords: Tuple[float, float], buffer_m: float = 1000) -> bool:
        """
        Check if a point is within the cached area with buffer.
        
        Args:
            coords: (lat, lon) to check
            buffer_m: Safety buffer in meters
            
        Returns:
            True if point is in cached area with buffer
        """
        if not self.large_graph or not self.cache_center or not self.cache_radius:
            return False
            
        distance = haversine_distance(
            self.cache_center[0], self.cache_center[1],
            coords[0], coords[1]
        )
        
        return distance <= (self.cache_radius - buffer_m)
    
    def is_route_in_cache(self, start_coords: Tuple[float, float], 
                         end_coords: Tuple[float, float], buffer_m: float = 1000) -> bool:
        """
        Check if a route is entirely within the cached area.
        
        Args:
            start_coords: (lat, lon) of start point
            end_coords: (lat, lon) of end point
            buffer_m: Safety buffer in meters
            
        Returns:
            True if both points are in cached area with buffer
        """
        return (self.is_point_in_cache(start_coords, buffer_m) and 
                self.is_point_in_cache(end_coords, buffer_m))
    
    def extract_subgraph(self, center_coords: Tuple[float, float], 
                        radius_m: float) -> Optional[nx.MultiDiGraph]:
        """
        Extract a subgraph from the cached network using optimized algorithms.
        
        Args:
            center_coords: (lat, lon) center of area to extract
            radius_m: Radius in meters for extraction
            
        Returns:
            Extracted subgraph or None if cache not available
        """
        if not self.large_graph:
            logger.warning("No cached graph available for extraction")
            return None
            
        try:
            logger.info(f"Extracting subgraph: {radius_m}m radius around "
                       f"({center_coords[0]:.4f}, {center_coords[1]:.4f})")
            
            start_time = time.perf_counter()
            
            # Optimized nearest node finding using vectorized operations
            center_node = self._find_nearest_node_optimized(center_coords)
            
            # Extract subgraph using optimized distance-based truncation
            # Use slightly larger radius to ensure coverage
            extraction_radius = radius_m * 1.2
            subgraph = self._truncate_graph_optimized(center_node, extraction_radius)
            
            extract_time = time.perf_counter() - start_time
            
            logger.info(f"✓ Extracted subgraph: {len(subgraph.nodes)} nodes, "
                       f"{len(subgraph.edges)} edges in {extract_time:.3f}s")
            
            return subgraph
            
        except Exception as e:
            logger.error(f"Failed to extract subgraph: {e}")
            return None
    
    def _find_nearest_node_optimized(self, center_coords: Tuple[float, float]) -> int:
        """
        Optimized nearest node finding using vectorized operations.
        
        Args:
            center_coords: (lat, lon) center coordinates
            
        Returns:
            Nearest node ID
        """
        if not self.large_graph:
            raise ValueError("No large graph available for node finding")
        
        # Extract all node coordinates as numpy arrays
        nodes = list(self.large_graph.nodes())
        node_coords = np.array([
            (self.large_graph.nodes[node]['y'], self.large_graph.nodes[node]['x']) 
            for node in nodes
        ])
        
        # Vectorized distance calculation
        center_lat, center_lon = center_coords
        distances = np.sqrt(
            (node_coords[:, 0] - center_lat) ** 2 + 
            (node_coords[:, 1] - center_lon) ** 2
        )
        
        # Find nearest node
        nearest_idx = np.argmin(distances)
        return nodes[nearest_idx]
    
    def _truncate_graph_optimized(self, center_node: int, radius_m: float) -> nx.MultiDiGraph:
        """
        Optimized graph truncation using breadth-first search with distance tracking.
        
        Args:
            center_node: Starting node ID
            radius_m: Maximum distance in meters
            
        Returns:
            Truncated subgraph
        """
        if not self.large_graph:
            raise ValueError("No large graph available for truncation")
        
        from collections import deque
        
        # Convert radius to approximate degrees for faster filtering
        # At Toronto's latitude (~43.7°N): 1° lat ≈ 111320m, 1° lon ≈ 79700m
        lat_radius_deg = radius_m / 111320.0
        lon_radius_deg = radius_m / 79700.0
        
        # Get center node coordinates for filtering
        center_lat = self.large_graph.nodes[center_node]['y']
        center_lon = self.large_graph.nodes[center_node]['x']
        
        # Pre-filter nodes by bounding box for efficiency
        bbox_nodes = set()
        for node, data in self.large_graph.nodes(data=True):
            node_lat, node_lon = data['y'], data['x']
            
            # Quick bounding box check
            if (abs(node_lat - center_lat) <= lat_radius_deg and 
                abs(node_lon - center_lon) <= lon_radius_deg):
                bbox_nodes.add(node)
        
        # BFS with distance tracking
        visited = {center_node: 0.0}  # node: distance
        queue = deque([(center_node, 0.0)])
        nodes_to_keep = set()
        
        while queue:
            current_node, current_dist = queue.popleft()
            
            if current_dist > radius_m:
                continue
                
            nodes_to_keep.add(current_node)
            
            # Explore neighbors
            for neighbor in self.large_graph.neighbors(current_node):
                if neighbor not in visited:
                    # Calculate distance to neighbor
                    neighbor_data = self.large_graph.nodes[neighbor]
                    edge_data = self.large_graph.edges[current_node, neighbor, 0]
                    
                    # Use edge length for accurate distance
                    edge_length = edge_data.get('length', 0)
                    new_dist = current_dist + edge_length
                    
                    if new_dist <= radius_m:
                        visited[neighbor] = new_dist
                        queue.append((neighbor, new_dist))
        
        # Create subgraph with only the nodes within radius
        subgraph = self.large_graph.subgraph(nodes_to_keep).copy()
        
        # Ensure we return a MultiDiGraph
        if not isinstance(subgraph, nx.MultiDiGraph):
            subgraph = nx.MultiDiGraph(subgraph)
        
        return subgraph
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get information about the current cache.
        
        Returns:
            Dictionary with cache information
        """
        if not self.large_graph:
            return {
                'available': False,
                'cache_file': str(self.cache_file)
            }
            
        return {
            'available': True,
            'cache_file': str(self.cache_file),
            'center': self.cache_center,
            'radius_km': self.cache_radius / 1000.0 if self.cache_radius else None,
            'nodes': len(self.large_graph.nodes),
            'edges': len(self.large_graph.edges),
            'file_size_mb': self.cache_file.stat().st_size / (1024 * 1024) if self.cache_file.exists() else None
        }


# Global cache instance
_network_cache = NetworkCache()


def get_network_cache() -> NetworkCache:
    """Get the global network cache instance."""
    return _network_cache


def ensure_toronto_cache(center_coords: Tuple[float, float] = (43.6532, -79.3832), 
                        radius_km: float = 30.0) -> bool:
    """
    Ensure Toronto network cache is available, creating if necessary.
    
    Args:
        center_coords: Center of Toronto area (default: downtown)
        radius_km: Radius in kilometers for cached area
        
    Returns:
        True if cache is ready, False if failed
    """
    cache = get_network_cache()
    
    # Try to load existing cache
    if cache.load_cache():
        logger.info("Toronto network cache loaded successfully")
        return True
    
    # Create new cache
    logger.info(f"Creating Toronto network cache ({radius_km}km radius)...")
    radius_m = radius_km * 1000.0
    
    if cache.create_cache(center_coords, radius_m):
        logger.info("Toronto network cache created successfully")
        return True
    else:
        logger.error("Failed to create Toronto network cache")
        return False 
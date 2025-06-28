"""
Cached network builder that uses grid-based caching with fallback to original method.
"""

import osmnx as ox
from typing import Tuple, Optional
from .distance_utils import haversine_distance
from .grid_cache import GridCache
from .network_builder import build_network as build_network_original
import networkx as nx
import geohash
from datetime import datetime


class CachedNetworkBuilder:
    """
    Network builder that uses grid-based caching for improved performance.
    Falls back to original method if cache miss or errors occur.
    """
    
    def __init__(self, cache_dir: str = "crime_aware_routing/cache", 
                 precision: int = 6, enable_cache: bool = True,
                 enable_opportunistic_caching: bool = True):
        """
        Initialize the cached network builder.
        
        Args:
            cache_dir: Directory for cache storage
            precision: Geohash precision level
            enable_cache: Whether to use caching (can disable for testing)
            enable_opportunistic_caching: Cache tiles when falling back to live download
        """
        self.enable_cache = enable_cache
        self.enable_opportunistic_caching = enable_opportunistic_caching
        self.grid_cache = GridCache(cache_dir, precision) if enable_cache else None
    
    def build_network(self, start_coords: Tuple[float, float], 
                     end_coords: Tuple[float, float],
                     buffer_factor: float = 0.8,
                     prefer_cache: bool = True) -> 'nx.MultiDiGraph':
        """
        Build a street network using cache when possible, fallback to original method.
        
        Args:
            start_coords: (lat, lon) of start point
            end_coords: (lat, lon) of end point  
            buffer_factor: Factor to determine network size for fallback method
            prefer_cache: Whether to prefer cache over original method
            
        Returns:
            NetworkX MultiDiGraph with street network
        """
        if not self.enable_cache or not prefer_cache:
            print("Cache disabled or not preferred, using original method")
            return build_network_original(start_coords, end_coords, buffer_factor)
        
        try:
            # Try to load from cache first
            print("Attempting to load network from cache...")
            if self.grid_cache is None:
                raise ValueError("Grid cache not initialized")
            cached_network = self.grid_cache.load_networks_for_route(start_coords, end_coords)
            
            if cached_network is not None:
                # Validate that the network covers our points
                if self._validate_network_coverage(cached_network, start_coords, end_coords):
                    print("✓ Using cached network data")
                    return cached_network
                else:
                    print("⚠ Cached network doesn't cover route endpoints, falling back to original method")
            
        except Exception as e:
            print(f"⚠ Cache failed: {e}, falling back to original method")
        
        # Fallback to original method
        print("Using original network download method")
        network = build_network_original(start_coords, end_coords, buffer_factor)
        
        # Opportunistic caching: Cache tiles that cover this network for future use
        if self.enable_cache and self.enable_opportunistic_caching and self.grid_cache is not None:
            self._opportunistic_cache(network, start_coords, end_coords)
        
        return network
    
    def _validate_network_coverage(self, graph: nx.MultiDiGraph, 
                                  start_coords: Tuple[float, float], 
                                  end_coords: Tuple[float, float],
                                  max_distance: float = 1000) -> bool:
        """
        Validate that the network adequately covers the route endpoints.
        
        Args:
            graph: Network graph to validate
            start_coords: (lat, lon) of start point
            end_coords: (lat, lon) of end point
            max_distance: Maximum acceptable distance to nearest node (meters)
            
        Returns:
            True if network coverage is adequate
        """
        try:
            # Find nearest nodes to start and end points
            start_node = ox.nearest_nodes(graph, start_coords[1], start_coords[0])
            end_node = ox.nearest_nodes(graph, end_coords[1], end_coords[0])
            
            # Get coordinates of nearest nodes
            start_node_coords = (graph.nodes[start_node]['y'], graph.nodes[start_node]['x'])
            end_node_coords = (graph.nodes[end_node]['y'], graph.nodes[end_node]['x'])
            
            # Calculate distances
            start_distance = haversine_distance(
                start_coords[0], start_coords[1],
                start_node_coords[0], start_node_coords[1]
            )
            
            end_distance = haversine_distance(
                end_coords[0], end_coords[1],
                end_node_coords[0], end_node_coords[1]
            )
            
            # Check if distances are acceptable
            coverage_ok = start_distance <= max_distance and end_distance <= max_distance
            
            if not coverage_ok:
                print(f"  Coverage check failed: start_dist={start_distance:.0f}m, end_dist={end_distance:.0f}m")
            else:
                print(f"  Coverage check passed: start_dist={start_distance:.0f}m, end_dist={end_distance:.0f}m")
            
            return coverage_ok
            
        except Exception as e:
            print(f"  Coverage validation failed: {e}")
            return False
    
    def _opportunistic_cache(self, network: nx.MultiDiGraph, start_coords: Tuple[float, float], 
                           end_coords: Tuple[float, float]) -> None:
        """
        Opportunistically cache geohash tiles that cover the downloaded network.
        
        Args:
            network: The network that was just downloaded
            start_coords: Route start coordinates
            end_coords: Route end coordinates
        """
        try:
            if self.grid_cache is None:
                return
                
            # Calculate network bounds
            lats = [data['y'] for _, data in network.nodes(data=True)]
            lons = [data['x'] for _, data in network.nodes(data=True)]
            
            if not lats or not lons:
                return
            
            network_bounds = {
                'lat_min': min(lats), 'lat_max': max(lats),
                'lon_min': min(lons), 'lon_max': max(lons)
            }
            
            print(f"🔄 Opportunistic caching: Network covers {network_bounds['lat_min']:.3f}-{network_bounds['lat_max']:.3f}°N, {network_bounds['lon_min']:.3f}-{network_bounds['lon_max']:.3f}°W")
            
            # Find geohash tiles that would cover this area
            cache_tiles = set()
            
            # Sample points across the network bounds to find covering tiles
            lat_step = (network_bounds['lat_max'] - network_bounds['lat_min']) / 10
            lon_step = (network_bounds['lon_max'] - network_bounds['lon_min']) / 10
            
            lat = network_bounds['lat_min']
            while lat <= network_bounds['lat_max']:
                lon = network_bounds['lon_min'] 
                while lon <= network_bounds['lon_max']:
                    gh = geohash.encode(lat, lon, self.grid_cache.precision)
                    cache_tiles.add(gh)
                    lon += lon_step
                lat += lat_step
            
            cached_count = 0
            for gh in cache_tiles:
                try:
                    # Extract subnetwork for this tile and cache it
                    if self._cache_network_tile(network, gh):
                        cached_count += 1
                except Exception as e:
                    print(f"    Warning: Failed to cache tile {gh}: {e}")
            
            print(f"✓ Opportunistically cached {cached_count}/{len(cache_tiles)} tiles for future use")
            
        except Exception as e:
            print(f"⚠ Opportunistic caching failed: {e}")
    
    def _cache_network_tile(self, full_network: nx.MultiDiGraph, gh: str) -> bool:
        """
        Extract and cache a network tile from the full downloaded network.
        
        Args:
            full_network: The complete downloaded network
            gh: Geohash of the tile to extract
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.grid_cache is None:
                return False
                
            # Get tile bounds
            bounds = self.grid_cache.get_geohash_bounds(gh)
            
            # Find nodes within this tile
            tile_nodes = []
            for node, data in full_network.nodes(data=True):
                lat, lon = data.get('y', 0), data.get('x', 0)
                if (bounds['south'] <= lat <= bounds['north'] and 
                    bounds['west'] <= lon <= bounds['east']):
                    tile_nodes.append(node)
            
            if len(tile_nodes) < 2:  # Not enough nodes for a meaningful tile
                return False
            
            # Extract subgraph for this tile with some buffer
            buffer_nodes = set(tile_nodes)
            for node in tile_nodes:
                # Add immediate neighbors to ensure connectivity
                buffer_nodes.update(full_network.neighbors(node))
            
            # Create MultiDiGraph from subgraph
            tile_network = nx.MultiDiGraph(full_network.subgraph(buffer_nodes))
            
            # Save to cache
            file_path = self.grid_cache.networks_dir / f"{gh}.graphml"
            ox.save_graphml(tile_network, file_path)
            
            # Update database
            center_lat, center_lon = geohash.decode(gh)[:2]
            now = datetime.now().isoformat()
            file_size = file_path.stat().st_size
            
            with self.grid_cache._get_db_connection() as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO grid_cache 
                    (geohash, center_lat, center_lon, bounds_north, bounds_south, 
                     bounds_east, bounds_west, last_updated, node_count, edge_count, 
                     file_path, download_radius, created_at, file_size_bytes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    gh, center_lat, center_lon,
                    bounds['north'], bounds['south'], bounds['east'], bounds['west'],
                    now, len(tile_network.nodes), len(tile_network.edges), 
                    str(file_path), 700, now, file_size  # Use default radius for opportunistic cache
                ))
                conn.commit()
            
            return True
            
        except Exception as e:
            return False
    
    def predownload_cache(self, force_refresh: bool = False) -> None:
        """
        Predownload cache for Toronto area.
        
        Args:
            force_refresh: Whether to force re-download existing cache
        """
        if not self.enable_cache:
            print("Cache is disabled")
            return
        
        print("Starting cache predownload...")
        if self.grid_cache is not None:
            self.grid_cache.predownload_toronto(force_refresh)
    
    def get_cache_stats(self) -> None:
        """Print cache statistics."""
        if not self.enable_cache:
            print("Cache is disabled")
            return
        
        if self.grid_cache is not None:
            self.grid_cache.print_cache_stats()
    
    def clear_cache(self, older_than_days: Optional[int] = None) -> None:
        """
        Clear cache entries.
        
        Args:
            older_than_days: If specified, only clear entries older than this many days
        """
        if not self.enable_cache:
            print("Cache is disabled")
            return
        
        if self.grid_cache is not None:
            self.grid_cache.clear_cache(older_than_days)


# Global instance for backward compatibility
_cached_builder = CachedNetworkBuilder()

def build_network_cached(start_coords: Tuple[float, float], 
                        end_coords: Tuple[float, float],
                        buffer_factor: float = 0.8,
                        prefer_cache: bool = True) -> 'nx.MultiDiGraph':
    """
    Convenience function to build network with caching.
    
    Args:
        start_coords: (lat, lon) of start point
        end_coords: (lat, lon) of end point  
        buffer_factor: Factor to determine network size for fallback method
        prefer_cache: Whether to prefer cache over original method
        
    Returns:
        NetworkX MultiDiGraph with street network
    """
    return _cached_builder.build_network(start_coords, end_coords, buffer_factor, prefer_cache) 
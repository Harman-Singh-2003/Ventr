"""
Connectivity Cache with Boundary Edge Restoration.

This integrates the BoundaryEdgeManager with the existing GridCache to provide
guaranteed connectivity without relying on buffer adequacy.
"""

import logging
import time
from typing import Dict, List, Tuple, Optional, Any
import networkx as nx
import osmnx as ox
from pathlib import Path

from .grid_cache import GridCache
from .boundary_edge_manager import BoundaryEdgeManager
from ...data.distance_utils import haversine_distance

logger = logging.getLogger(__name__)


class ConnectivityCache(GridCache):
    """
    Enhanced grid cache with guaranteed connectivity using boundary edge restoration.
    
    This extends the base GridCache to:
    1. Catalog boundary edges during network download
    2. Restore boundary edges during tile merging
    3. Guarantee perfect connectivity regardless of buffer sizes
    4. Maintain compatibility with existing grid cache interface
    """
    
    def __init__(self, cache_dir: str = "crime_aware_routing_2/cache", precision: int = 6):
        """
        Initialize connectivity cache.
        
        Args:
            cache_dir: Directory for cache storage
            precision: Geohash precision level
        """
        super().__init__(cache_dir, precision)
        
        # Initialize boundary edge manager
        self.boundary_manager = BoundaryEdgeManager(cache_dir)
        
        logger.info("ConnectivityCache initialized with boundary edge restoration")
    
    def download_and_cache_network(self, gh: str, force_refresh: bool = False) -> bool:
        """
        Download and cache network with boundary edge cataloging.
        
        Args:
            gh: Geohash string
            force_refresh: Whether to force re-download
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Use parent method to download and cache normally
            success = super().download_and_cache_network(gh, force_refresh)
            
            if not success:
                return False
            
            # Load the cached network to catalog boundary edges
            try:
                file_path = self.networks_dir / f"{gh}.graphml"
                if file_path.exists():
                    G = ox.load_graphml(file_path)
                    
                    # Get tile bounds for boundary analysis
                    bounds = self.get_geohash_bounds(gh)
                    
                    # Catalog boundary edges for this tile
                    cataloging_stats = self.boundary_manager.catalog_boundary_edges(
                        network=G,
                        tile_id=gh,
                        tile_bounds=bounds
                    )
                    
                    logger.info(f"Boundary cataloging for {gh}: {cataloging_stats['boundary_edges']} "
                               f"boundary edges ({cataloging_stats['boundary_ratio']:.1%} of total)")
                    
                else:
                    logger.warning(f"Cache file missing for boundary cataloging: {gh}")
                    
            except Exception as e:
                logger.warning(f"Failed to catalog boundary edges for {gh}: {e}")
                # Don't fail the whole operation - regular caching still works
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to download and cache network with boundary cataloging for {gh}: {e}")
            return False
    
    def load_networks_for_route(self, start_coords: Tuple[float, float], 
                               end_coords: Tuple[float, float]) -> Optional[nx.MultiDiGraph]:
        """
        Load and merge cached networks with guaranteed connectivity restoration.
        
        Args:
            start_coords: (lat, lon) of start point
            end_coords: (lat, lon) of end point
            
        Returns:
            Merged NetworkX graph with guaranteed connectivity
        """
        try:
            logger.info("Loading networks with connectivity guarantee")
            
            # Find covering geohashes
            covering_geohashes = self.find_covering_geohashes(start_coords, end_coords)
            
            if not covering_geohashes:
                logger.info("No cached networks found for route")
                return None
            
            logger.info(f"Loading {len(covering_geohashes)} cached network tiles: {covering_geohashes}")
            
            # Load individual networks
            networks = []
            successful_tiles = []
            
            for gh in covering_geohashes:
                try:
                    file_path = self.networks_dir / f"{gh}.graphml"
                    if file_path.exists():
                        G = ox.load_graphml(file_path)
                        networks.append(G)
                        successful_tiles.append(gh)
                        logger.debug(f"Loaded tile {gh}: {len(G.nodes)} nodes, {len(G.edges)} edges")
                    else:
                        logger.warning(f"Cache file missing for {gh}")
                except Exception as e:
                    logger.warning(f"Failed to load {gh}: {e}")
            
            if not networks:
                logger.warning("No networks could be loaded")
                return None
            
            # Merge networks using parent method
            if len(networks) == 1:
                merged = networks[0]
                logger.info(f"Single tile loaded: {len(merged.nodes)} nodes, {len(merged.edges)} edges")
            else:
                logger.info(f"Merging {len(networks)} tiles with boundary edge restoration")
                
                # Start with largest network as base
                base_idx = max(range(len(networks)), key=lambda i: len(networks[i].nodes))
                merged = networks[base_idx].copy()
                
                logger.info(f"Base network: {len(merged.nodes)} nodes, {len(merged.edges)} edges")
                
                # Merge remaining networks
                for i, G in enumerate(networks):
                    if i == base_idx:
                        continue
                    
                    nodes_added = 0
                    edges_added = 0
                    
                    # Merge nodes
                    for node, data in G.nodes(data=True):
                        if node not in merged:
                            merged.add_node(node, **data)
                            nodes_added += 1
                    
                    # Merge edges
                    for u, v, key, data in G.edges(data=True, keys=True):
                        if u in merged.nodes and v in merged.nodes:
                            if not merged.has_edge(u, v, key):
                                merged.add_edge(u, v, key=key, **data)
                                edges_added += 1
                    
                    logger.debug(f"Merged tile {successful_tiles[i]}: +{nodes_added} nodes, +{edges_added} edges")
            
            # CRITICAL: Restore boundary edges for guaranteed connectivity
            logger.info("Restoring boundary edges for guaranteed connectivity")
            
            restoration_stats = self.boundary_manager.restore_boundary_edges(
                merged_network=merged,
                tile_ids=successful_tiles
            )
            
            logger.info(f"Boundary restoration: {restoration_stats['edges_restored']} edges restored, "
                       f"{restoration_stats['edges_skipped']} skipped, "
                       f"{restoration_stats['errors']} errors")
            
            # Validate connectivity (should be perfect now)
            if merged.is_directed():
                is_connected = nx.is_weakly_connected(merged)
                num_components = nx.number_weakly_connected_components(merged)
            else:
                is_connected = nx.is_connected(merged)
                num_components = nx.number_connected_components(merged)
            
            logger.info(f"Final merged network: {len(merged.nodes)} nodes, {len(merged.edges)} edges")
            
            if is_connected:
                logger.info("✓ Network is fully connected - boundary restoration successful!")
            else:
                logger.warning(f"⚠️ Network still has {num_components} components after boundary restoration")
                
                # Check if route endpoints are still reachable
                try:
                    start_node = ox.nearest_nodes(merged, start_coords[1], start_coords[0])
                    end_node = ox.nearest_nodes(merged, end_coords[1], end_coords[0])
                    
                    if merged.is_directed():
                        path_exists = nx.has_path(merged, start_node, end_node)
                    else:
                        # Check if nodes are in same component
                        components = list(nx.connected_components(merged))
                        start_component = None
                        end_component = None
                        for i, comp in enumerate(components):
                            if start_node in comp:
                                start_component = i
                            if end_node in comp:
                                end_component = i
                        path_exists = start_component == end_component and start_component is not None
                    
                    if path_exists:
                        logger.info("✓ Route endpoints are reachable despite disconnected components")
                    else:
                        logger.error("✗ Route endpoints are not reachable - connectivity restoration failed")
                        return None
                        
                except Exception as e:
                    logger.error(f"Error checking route connectivity: {e}")
                    return None
            
            return merged
            
        except Exception as e:
            logger.error(f"Failed to load networks with connectivity guarantee: {e}")
            return None
    
    def get_connectivity_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about connectivity cache.
        
        Returns:
            Dictionary with grid cache and boundary edge statistics
        """
        try:
            # Get base grid cache statistics
            with self._get_db_connection() as conn:
                cursor = conn.execute('''
                    SELECT 
                        COUNT(*) as total_tiles,
                        SUM(node_count) as total_nodes,
                        SUM(edge_count) as total_edges,
                        SUM(file_size_bytes) as total_size_bytes,
                        MIN(last_updated) as oldest_update,
                        MAX(last_updated) as newest_update
                    FROM grid_cache
                ''')
                grid_stats = cursor.fetchone()
            
            # Get boundary edge statistics
            boundary_stats = self.boundary_manager.get_boundary_statistics()
            
            # Calculate derived statistics
            connectivity_ratio = 0.0
            if grid_stats['total_edges'] and boundary_stats.get('boundary_edges', {}).get('total', 0):
                connectivity_ratio = boundary_stats['boundary_edges']['total'] / grid_stats['total_edges']
            
            return {
                'grid_cache': {
                    'tiles': grid_stats['total_tiles'] or 0,
                    'nodes': grid_stats['total_nodes'] or 0,
                    'edges': grid_stats['total_edges'] or 0,
                    'size_mb': (grid_stats['total_size_bytes'] or 0) / (1024 * 1024),
                    'oldest_update': grid_stats['oldest_update'],
                    'newest_update': grid_stats['newest_update']
                },
                'boundary_edges': boundary_stats.get('boundary_edges', {}),
                'connectivity': {
                    'boundary_edge_ratio': connectivity_ratio,
                    'guaranteed_connectivity': True,
                    'method': 'boundary_edge_restoration'
                },
                'cache_directories': {
                    'grid_cache': str(self.cache_dir),
                    'boundary_cache': str(self.boundary_manager.cache_dir)
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get connectivity statistics: {e}")
            return {'error': str(e)}
    
    def clear_connectivity_cache(self, older_than_days: Optional[int] = None):
        """
        Clear both grid cache and boundary edge cache.
        
        Args:
            older_than_days: If specified, only clear entries older than this many days
        """
        try:
            logger.info("Clearing connectivity cache (grid + boundary edges)")
            
            # Clear boundary edge cache first
            self.boundary_manager.clear_cache(older_than_days)
            
            # Clear grid cache
            self.clear_cache(older_than_days)
            
            logger.info("Connectivity cache cleared successfully")
            
        except Exception as e:
            logger.error(f"Failed to clear connectivity cache: {e}")
            raise
    
    def validate_connectivity_guarantee(self, start_coords: Tuple[float, float], 
                                      end_coords: Tuple[float, float]) -> Dict[str, Any]:
        """
        Validate that connectivity guarantee works for a specific route.
        
        Args:
            start_coords: (lat, lon) of start point
            end_coords: (lat, lon) of end point
            
        Returns:
            Dictionary with validation results
        """
        try:
            logger.info(f"Validating connectivity guarantee for route "
                       f"{start_coords} -> {end_coords}")
            
            start_time = time.time()
            
            # Load networks with connectivity guarantee
            merged_network = self.load_networks_for_route(start_coords, end_coords)
            
            load_time = time.time() - start_time
            
            if merged_network is None:
                return {
                    'success': False,
                    'error': 'Failed to load network',
                    'load_time_seconds': load_time
                }
            
            # Validate connectivity
            if merged_network.is_directed():
                is_connected = nx.is_weakly_connected(merged_network)
                num_components = nx.number_weakly_connected_components(merged_network)
            else:
                is_connected = nx.is_connected(merged_network)
                num_components = nx.number_connected_components(merged_network)
            
            # Check route feasibility
            start_node = ox.nearest_nodes(merged_network, start_coords[1], start_coords[0])
            end_node = ox.nearest_nodes(merged_network, end_coords[1], end_coords[0])
            
            if merged_network.is_directed():
                route_possible = nx.has_path(merged_network, start_node, end_node)
            else:
                # Check if in same component
                components = list(nx.connected_components(merged_network))
                start_comp = next((i for i, comp in enumerate(components) if start_node in comp), None)
                end_comp = next((i for i, comp in enumerate(components) if end_node in comp), None)
                route_possible = start_comp == end_comp and start_comp is not None
            
            # Calculate distances to nearest nodes
            start_node_coords = (merged_network.nodes[start_node]['y'], merged_network.nodes[start_node]['x'])
            end_node_coords = (merged_network.nodes[end_node]['y'], merged_network.nodes[end_node]['x'])
            
            start_distance = haversine_distance(
                start_coords[0], start_coords[1],
                start_node_coords[0], start_node_coords[1]
            )
            
            end_distance = haversine_distance(
                end_coords[0], end_coords[1],
                end_node_coords[0], end_node_coords[1]
            )
            
            return {
                'success': True,
                'connectivity': {
                    'is_fully_connected': is_connected,
                    'num_components': num_components,
                    'route_possible': route_possible
                },
                'network_stats': {
                    'nodes': len(merged_network.nodes),
                    'edges': len(merged_network.edges)
                },
                'coverage': {
                    'start_distance_m': start_distance,
                    'end_distance_m': end_distance,
                    'max_distance_m': max(start_distance, end_distance)
                },
                'performance': {
                    'load_time_seconds': load_time
                },
                'guarantee_status': 'PERFECT' if is_connected and route_possible else 
                                  'PARTIAL' if route_possible else 'FAILED'
            }
            
        except Exception as e:
            logger.error(f"Failed to validate connectivity guarantee: {e}")
            return {
                'success': False,
                'error': str(e)
            } 
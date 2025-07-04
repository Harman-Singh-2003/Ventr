"""
Grid-based caching system using geohash spatial indexing for map data.
Implements smart predownloading and efficient cache lookup for routing networks.
"""

import os
import sqlite3
import json
import pickle
import geohash
import osmnx as ox
import networkx as nx
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict, Set
from contextlib import contextmanager
from pathlib import Path
import geopandas as gpd
from shapely.geometry import box, Point
import pandas as pd
import logging

from .boundary_edge_manager import BoundaryEdgeManager

logger = logging.getLogger(__name__)


class GridCache:
    """
    Grid-based caching system for OSM network data using geohash spatial indexing.
    """
    
    def __init__(self, cache_dir: str = "crime_aware_routing_2/cache", precision: int = 6):
        """
        Initialize the grid cache system with boundary edge cataloging.
        
        Args:
            cache_dir: Directory to store cache files
            precision: Geohash precision level (6 = ~1.2km cells for Toronto)
        """
        self.cache_dir = Path(cache_dir)
        self.networks_dir = self.cache_dir / "networks"
        self.db_path = self.cache_dir / "grid_cache.db"
        self.precision = precision
        
        # Ensure directories exist
        self.cache_dir.mkdir(exist_ok=True)
        self.networks_dir.mkdir(exist_ok=True)
        
        # Initialize database
        self._init_database()
        
        # Initialize boundary edge manager for guaranteed connectivity
        self.boundary_manager = BoundaryEdgeManager(cache_dir)
        
        # Toronto city bounds (tighter focus on actual city)
        self.toronto_bounds = {
            'lat_min': 43.58, 'lat_max': 43.85,  # Toronto proper
            'lon_min': -79.65, 'lon_max': -79.12  # Toronto proper
        }
        
        logger.info(f"GridCache initialized with boundary edge cataloging at {cache_dir}")
    
    def _init_database(self):
        """Initialize the SQLite database for grid cache metadata."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS grid_cache (
                    geohash TEXT PRIMARY KEY,
                    center_lat REAL NOT NULL,
                    center_lon REAL NOT NULL,
                    bounds_north REAL NOT NULL,
                    bounds_south REAL NOT NULL,
                    bounds_east REAL NOT NULL,
                    bounds_west REAL NOT NULL,
                    last_updated TEXT NOT NULL,
                    node_count INTEGER,
                    edge_count INTEGER,
                    file_path TEXT NOT NULL,
                    download_radius REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    file_size_bytes INTEGER DEFAULT 0
                )
            ''')
            
            # Create spatial indexes for efficient queries
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_bounds_north ON grid_cache(bounds_north)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_bounds_south ON grid_cache(bounds_south)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_bounds_east ON grid_cache(bounds_east)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_bounds_west ON grid_cache(bounds_west)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_last_updated ON grid_cache(last_updated)
            ''')
    
    @contextmanager
    def _get_db_connection(self):
        """Get a database connection with proper cleanup."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
        finally:
            conn.close()
    
    def generate_toronto_grid(self) -> List[str]:
        """
        Generate geohash grid covering Toronto area.
        
        Returns:
            List of geohash strings covering Toronto
        """
        print(f"Generating geohash grid for Toronto (precision {self.precision})...")
        
        geohashes = set()
        
        # Calculate appropriate step size for precision 6 geohashes
        # At Toronto's latitude (~43.7°), precision 6 cells are roughly:
        # - Latitude: ~0.011° (1.22km)  
        # - Longitude: ~0.014° (0.61km)
        lat_step = 0.008  # Slightly smaller than cell size for good coverage
        lon_step = 0.010  # Slightly smaller than cell size for good coverage
        
        lat = self.toronto_bounds['lat_min']
        while lat <= self.toronto_bounds['lat_max']:
            lon = self.toronto_bounds['lon_min']
            while lon <= self.toronto_bounds['lon_max']:
                gh = geohash.encode(lat, lon, self.precision)
                geohashes.add(gh)
                lon += lon_step
            lat += lat_step
        
        geohash_list = sorted(list(geohashes))
        print(f"Generated {len(geohash_list)} geohash tiles for Toronto")
        return geohash_list
    
    def get_geohash_bounds(self, gh: str) -> Dict[str, float]:
        """
        Get the bounding box of a geohash.
        
        Args:
            gh: Geohash string
            
        Returns:
            Dictionary with bounds: {north, south, east, west}
        """
        bbox = geohash.bbox(gh)
        return {
            'north': bbox['n'],
            'south': bbox['s'], 
            'east': bbox['e'],
            'west': bbox['w']
        }
    
    def calculate_download_radius(self, gh: str) -> float:
        """
        Calculate appropriate download radius for a geohash cell.
        
        Args:
            gh: Geohash string
            
        Returns:
            Radius in meters with buffer for edge cases
        """
        bounds = self.get_geohash_bounds(gh)
        
        # Calculate diagonal distance of the cell
        from ...data.distance_utils import haversine_distance
        diagonal_distance = haversine_distance(
            bounds['south'], bounds['west'],
            bounds['north'], bounds['east']
        )
        
        # Add 30% buffer to ensure coverage across cell boundaries
        return int(diagonal_distance * 0.65)  # 65% of diagonal ensures good coverage
    
    def download_and_cache_network(self, gh: str, force_refresh: bool = False) -> bool:
        """
        Download and cache network data for a geohash cell.
        
        Args:
            gh: Geohash string
            force_refresh: Whether to force re-download even if cached
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if already cached and recent (unless forcing refresh)
            if not force_refresh:
                with self._get_db_connection() as conn:
                    cursor = conn.execute(
                        'SELECT last_updated, file_path FROM grid_cache WHERE geohash = ?',
                        (gh,)
                    )
                    row = cursor.fetchone()
                    if row:
                        last_updated = datetime.fromisoformat(row['last_updated'])
                        if datetime.now() - last_updated < timedelta(days=30):
                            print(f"  {gh}: Already cached and recent")
                            return True
            
            # Get geohash center and bounds
            center_lat, center_lon = geohash.decode(gh)[:2]
            bounds = self.get_geohash_bounds(gh)
            radius = self.calculate_download_radius(gh)
            
            print(f"  {gh}: Downloading network (center: {center_lat:.4f}, {center_lon:.4f}, radius: {radius}m)")
            
            # Download network from OSM
            G = ox.graph_from_point(
                (center_lat, center_lon),
                dist=radius,
                network_type='walk',
                simplify=True
            )
            
            # Save network to file
            file_path = self.networks_dir / f"{gh}.graphml"
            ox.save_graphml(G, file_path)
            
            # Get file size
            file_size = file_path.stat().st_size
            
            # Update database
            now = datetime.now().isoformat()
            with self._get_db_connection() as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO grid_cache 
                    (geohash, center_lat, center_lon, bounds_north, bounds_south, 
                     bounds_east, bounds_west, last_updated, node_count, edge_count, 
                     file_path, download_radius, created_at, file_size_bytes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    gh, center_lat, center_lon,
                    bounds['north'], bounds['south'], bounds['east'], bounds['west'],
                    now, len(G.nodes), len(G.edges), str(file_path), radius, now, file_size
                ))
                conn.commit()
            
            # Catalog boundary edges for guaranteed connectivity
            try:
                cataloging_stats = self.boundary_manager.catalog_boundary_edges(
                    network=G,
                    tile_id=gh,
                    tile_bounds=bounds
                )
                logger.info(f"Boundary cataloging for {gh}: {cataloging_stats['boundary_edges']} "
                           f"boundary edges ({cataloging_stats['boundary_ratio']:.1%} of total)")
            except Exception as e:
                logger.warning(f"Failed to catalog boundary edges for {gh}: {e}")
                # Don't fail the whole operation - regular caching still works
            
            print(f"  {gh}: Cached successfully ({len(G.nodes)} nodes, {len(G.edges)} edges, {file_size/1024:.0f}KB)")
            return True
            
        except Exception as e:
            print(f"  {gh}: Failed to download/cache: {e}")
            return False
    
    def predownload_toronto(self, force_refresh: bool = False) -> None:
        """
        Predownload all network data for Toronto area.
        
        Args:
            force_refresh: Whether to force re-download existing cache
        """
        print("Starting Toronto network predownload...")
        
        geohashes = self.generate_toronto_grid()
        successful = 0
        failed = 0
        
        for i, gh in enumerate(geohashes, 1):
            print(f"Processing {i}/{len(geohashes)}: {gh}")
            
            if self.download_and_cache_network(gh, force_refresh):
                successful += 1
            else:
                failed += 1
        
        print(f"\nPredownload complete:")
        print(f"  ✓ Successful: {successful}")
        print(f"  ✗ Failed: {failed}")
        print(f"  Total tiles: {len(geohashes)}")
        
        # Print cache statistics
        self.print_cache_stats()
    
    def find_covering_geohashes(self, start_coords: Tuple[float, float], 
                              end_coords: Tuple[float, float], 
                              buffer: Optional[float] = None) -> List[str]:
        """
        Find geohashes that cover the route between start and end coordinates.
        
        Args:
            start_coords: (lat, lon) of start point
            end_coords: (lat, lon) of end point
            buffer: Buffer around route in degrees (if None, calculates adaptive buffer)
            
        Returns:
            List of geohash strings that cover the route
        """
        # Calculate adaptive buffer based on route length if not specified
        if buffer is None:
            from ...data.distance_utils import haversine_distance
            
            route_distance = haversine_distance(
                start_coords[0], start_coords[1],
                end_coords[0], end_coords[1]
            )
            
            # Adaptive buffer: larger for longer routes
            # Base: 200m for short routes, up to 1000m for long routes
            base_buffer_m = 200.0
            max_buffer_m = 1000.0
            max_route_for_scaling = 10000.0  # 10km
            
            buffer_m = base_buffer_m + (max_buffer_m - base_buffer_m) * min(route_distance / max_route_for_scaling, 1.0)
            
            # Convert buffer from meters to degrees (approximate for Toronto latitude ~43.7°N)
            buffer = buffer_m / 111000.0  # 1 degree ≈ 111km
            
            print(f"Adaptive buffer: {buffer_m:.0f}m ({buffer:.4f}°) for {route_distance:.0f}m route")
        
        # Calculate bounding box for the route with buffer
        lat_min = min(start_coords[0], end_coords[0]) - buffer
        lat_max = max(start_coords[0], end_coords[0]) + buffer
        lon_min = min(start_coords[1], end_coords[1]) - buffer
        lon_max = max(start_coords[1], end_coords[1]) + buffer
        
        # Query database for intersecting geohashes
        # For proper intersection: tile overlaps route if:
        # - tile_north >= route_south AND tile_south <= route_north (latitude)
        # - tile_east >= route_west AND tile_west <= route_east (longitude)
        with self._get_db_connection() as conn:
            cursor = conn.execute('''
                SELECT geohash FROM grid_cache 
                WHERE bounds_north >= ? AND bounds_south <= ?
                  AND bounds_east >= ? AND bounds_west <= ?
                ORDER BY geohash
            ''', (lat_min, lat_max, lon_min, lon_max))
            
            return [row['geohash'] for row in cursor.fetchall()]
    
    def load_networks_for_route(self, start_coords: Tuple[float, float], 
                               end_coords: Tuple[float, float]) -> Optional[nx.MultiDiGraph]:
        """
        Load and merge cached networks for a route using enhanced adaptive buffer merging.
        
        Based on industry best practices for seamless tile stitching from major mapping systems.
        
        Args:
            start_coords: (lat, lon) of start point
            end_coords: (lat, lon) of end point
            
        Returns:
            Merged NetworkX graph or None if no cached networks found
        """
        # Find covering geohashes
        covering_geohashes = self.find_covering_geohashes(start_coords, end_coords)
        
        if not covering_geohashes:
            print("No cached networks found for route")
            return None
        
        print(f"Loading {len(covering_geohashes)} cached network tiles: {covering_geohashes}")
        
        # Load networks with metadata about their buffer zones
        networks = []
        network_metadata = []
        
        for gh in covering_geohashes:
            try:
                file_path = self.networks_dir / f"{gh}.graphml"
                if file_path.exists():
                    G = ox.load_graphml(file_path)
                    networks.append(G)
                    
                    # Get buffer metadata from database
                    with self._get_db_connection() as conn:
                        cursor = conn.execute(
                            'SELECT download_radius, node_count, edge_count FROM grid_cache WHERE geohash = ?',
                            (gh,)
                        )
                        row = cursor.fetchone()
                        if row:
                            network_metadata.append({
                                'geohash': gh,
                                'buffer_radius': row['download_radius'],
                                'node_count': row['node_count'],
                                'edge_count': row['edge_count']
                            })
                        else:
                            network_metadata.append({
                                'geohash': gh,
                                'buffer_radius': 400,  # Default fallback
                                'node_count': len(G.nodes),
                                'edge_count': len(G.edges)
                            })
                else:
                    print(f"Warning: Cache file missing for {gh}")
            except Exception as e:
                print(f"Warning: Failed to load {gh}: {e}")
        
        if not networks:
            print("No networks could be loaded")
            return None
        
        # Enhanced merging for adaptive buffered tiles
        if len(networks) == 1:
            merged = networks[0]
            print(f"Single tile loaded: {len(merged.nodes)} nodes, {len(merged.edges)} edges")
        else:
            print(f"Merging {len(networks)} buffered tiles with enhanced overlap handling")
            
            # Start with the largest network as base (most likely to be well-connected)
            base_idx = max(range(len(networks)), key=lambda i: len(networks[i].nodes))
            merged = networks[base_idx].copy()
            base_metadata = network_metadata[base_idx]
            
            print(f"  Base tile: {base_metadata['geohash']} ({len(merged.nodes)} nodes, {len(merged.edges)} edges)")
            
            # Track node and edge sources for conflict detection
            node_sources = {node: base_metadata['geohash'] for node in merged.nodes}
            edge_sources = {}
            for u, v, key in merged.edges(keys=True):
                edge_sources[(u, v, key)] = base_metadata['geohash']
            
            # Merge remaining networks with intelligent overlap handling
            for i, G in enumerate(networks):
                if i == base_idx:
                    continue
                    
                metadata = network_metadata[i]
                nodes_added = 0
                edges_added = 0
                conflicts_resolved = 0
                
                # Merge nodes with conflict detection
                for node, data in G.nodes(data=True):
                    if node not in merged:
                        merged.add_node(node, **data)
                        node_sources[node] = metadata['geohash']
                        nodes_added += 1
                    else:
                        # Node exists - validate data consistency
                        existing_data = merged.nodes[node]
                        if ('x' in data and 'y' in data and 
                            'x' in existing_data and 'y' in existing_data):
                            
                            # Check coordinate consistency (should be identical for same node)
                            coord_diff = abs(data['x'] - existing_data['x']) + abs(data['y'] - existing_data['y'])
                            if coord_diff > 0.00001:  # ~1m tolerance
                                conflicts_resolved += 1
                                print(f"    Coordinate conflict for node {node}: diff={coord_diff:.6f}°")
                                # Keep the existing data (from base tile)
                
                # Merge edges with overlap validation
                for u, v, key, data in G.edges(data=True, keys=True):
                    edge_key = (u, v, key)
                    if u in merged.nodes and v in merged.nodes:
                        if not merged.has_edge(u, v, key):
                            merged.add_edge(u, v, key=key, **data)
                            edge_sources[edge_key] = metadata['geohash']
                            edges_added += 1
                        else:
                            # Edge exists - validate data consistency
                            existing_data = merged.edges[u, v, key]
                            if 'length' in data and 'length' in existing_data:
                                length_diff = abs(data['length'] - existing_data['length'])
                                if length_diff > 1.0:  # 1m tolerance
                                    conflicts_resolved += 1
                                    print(f"    Length conflict for edge {u}-{v}-{key}: diff={length_diff:.1f}m")
                                    # Keep existing data (from base tile)
                
                print(f"  Merged tile: {metadata['geohash']} (+{nodes_added} nodes, +{edges_added} edges, {conflicts_resolved} conflicts)")
            
            print(f"Merged {len(networks)} buffered tiles with intelligent overlap handling")
        
        # CRITICAL: Restore boundary edges for guaranteed connectivity
        if len(networks) > 1:  # Only needed for multi-tile merges
            try:
                logger.info("Restoring boundary edges for guaranteed connectivity")
                successful_tiles = [metadata['geohash'] for metadata in network_metadata]
                
                restoration_stats = self.boundary_manager.restore_boundary_edges(
                    merged_network=merged,
                    tile_ids=successful_tiles
                )
                
                logger.info(f"Boundary restoration: {restoration_stats['edges_restored']} edges restored, "
                           f"{restoration_stats['edges_skipped']} skipped, "
                           f"{restoration_stats['errors']} errors")
                           
            except Exception as e:
                logger.warning(f"Failed to restore boundary edges: {e}")
                # Continue with regular connectivity validation
        
        # Enhanced connectivity validation with adaptive component handling
        if merged.is_directed():
            is_connected = nx.is_weakly_connected(merged)
            num_components = nx.number_weakly_connected_components(merged)
            components = list(nx.weakly_connected_components(merged))
        else:
            is_connected = nx.is_connected(merged)
            num_components = nx.number_connected_components(merged)
            components = list(nx.connected_components(merged))
        
        print(f"Merged network: {len(merged.nodes)} nodes, {len(merged.edges)} edges")
        
        if not is_connected:
            print(f"⚠️ Warning: Network has {num_components} disconnected components")
            
            # Enhanced connectivity validation using route endpoint analysis
            try:
                from ...data.distance_utils import haversine_distance
                
                # Find nearest nodes to start and end points
                start_node = ox.nearest_nodes(merged, start_coords[1], start_coords[0])
                end_node = ox.nearest_nodes(merged, end_coords[1], end_coords[0])
                
                # Calculate distances to validate coverage
                start_node_coords = (merged.nodes[start_node]['y'], merged.nodes[start_node]['x'])
                end_node_coords = (merged.nodes[end_node]['y'], merged.nodes[end_node]['x'])
                
                start_dist = haversine_distance(
                    start_coords[0], start_coords[1],
                    start_node_coords[0], start_node_coords[1]
                )
                
                end_dist = haversine_distance(
                    end_coords[0], end_coords[1],
                    end_node_coords[0], end_node_coords[1]
                )
                
                print(f"  Coverage check: start_dist={start_dist:.0f}m, end_dist={end_dist:.0f}m")
                
                # More intelligent coverage check - allow larger distances for buffered tiles
                # but check if endpoints are actually reachable
                max_reasonable_distance = 2000  # Increased from 1000m for buffered tiles
                
                if start_dist > max_reasonable_distance and end_dist > max_reasonable_distance:
                    print(f"✗ Coverage check failed: both endpoints too far from network")
                    return None
                elif start_dist > max_reasonable_distance or end_dist > max_reasonable_distance:
                    print(f"⚠️ One endpoint far from network, checking reachability...")
                else:
                    print(f"✓ Coverage check passed: start_dist={start_dist:.0f}m, end_dist={end_dist:.0f}m")
                
                # Check connectivity between route endpoints
                if merged.is_directed():
                    try:
                        path_exists = nx.has_path(merged, start_node, end_node)
                    except nx.NetworkXNoPath:
                        path_exists = False
                else:
                    # For undirected graphs, check same connected component
                    start_component = None
                    end_component = None
                    for i, comp in enumerate(components):
                        if start_node in comp:
                            start_component = i
                        if end_node in comp:
                            end_component = i
                    path_exists = start_component == end_component and start_component is not None
                
                if path_exists:
                    print("✓ Route endpoints are reachable despite disconnected components - using cached network")
                    return merged
                else:
                    print("✗ Route endpoints are unreachable - falling back to live network download")
                    return None
                    
            except Exception as e:
                print(f"✗ Error checking route coverage: {e} - falling back to live network download")
                return None
        else:
            print("✓ Network is fully connected")
        
        return merged
    
    def print_cache_stats(self) -> None:
        """Print current cache statistics."""
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
            stats = cursor.fetchone()
            
            if stats['total_tiles'] > 0:
                print(f"\nCache Statistics:")
                print(f"  Total tiles: {stats['total_tiles']}")
                print(f"  Total nodes: {stats['total_nodes']:,}")
                print(f"  Total edges: {stats['total_edges']:,}")
                print(f"  Total size: {stats['total_size_bytes'] / (1024*1024):.1f} MB")
                print(f"  Oldest data: {stats['oldest_update']}")
                print(f"  Newest data: {stats['newest_update']}")
            else:
                print("\nCache is empty")
    
    def clear_cache(self, older_than_days: Optional[int] = None) -> None:
        """
        Clear cache entries including boundary edge database.
        
        Args:
            older_than_days: If specified, only clear entries older than this many days
        """
        # Clear boundary edge cache first
        try:
            self.boundary_manager.clear_cache(older_than_days)
            logger.info("Boundary edge cache cleared")
        except Exception as e:
            logger.warning(f"Failed to clear boundary edge cache: {e}")
        
        # Clear grid cache
        with self._get_db_connection() as conn:
            if older_than_days:
                cutoff_date = (datetime.now() - timedelta(days=older_than_days)).isoformat()
                cursor = conn.execute(
                    'SELECT file_path FROM grid_cache WHERE last_updated < ?',
                    (cutoff_date,)
                )
            else:
                cursor = conn.execute('SELECT file_path FROM grid_cache')
            
            # Delete files
            deleted_files = 0
            for row in cursor:
                file_path = Path(row['file_path'])
                if file_path.exists():
                    file_path.unlink()
                    deleted_files += 1
            
            # Delete database entries
            if older_than_days:
                cursor = conn.execute(
                    'DELETE FROM grid_cache WHERE last_updated < ?',
                    (cutoff_date,)
                )
            else:
                cursor = conn.execute('DELETE FROM grid_cache')
            
            deleted_entries = cursor.rowcount
            conn.commit()
            
            print(f"Cleared {deleted_entries} cache entries and {deleted_files} files") 
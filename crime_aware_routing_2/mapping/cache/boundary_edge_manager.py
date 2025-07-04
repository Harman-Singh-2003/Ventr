"""
Boundary Edge Manager for guaranteed tile connectivity.

This system catalogs edges that cross tile boundaries during initial network download
and restores them during tile merging to ensure perfect connectivity without 
relying on potentially inadequate buffers.
"""

import json
import pickle
import sqlite3
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional, Any
from contextlib import contextmanager
import networkx as nx
import osmnx as ox
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import split, unary_union
import geopandas as gpd
from datetime import datetime

logger = logging.getLogger(__name__)


class BoundaryEdgeManager:
    """
    Manages boundary edges that cross tile boundaries to guarantee connectivity.
    
    Core approach:
    1. During network download, identify ALL edges crossing tile boundaries
    2. Store complete edge geometries and metadata in a boundary database
    3. During tile merging, restore boundary edges to guarantee connectivity
    4. Eliminate dependency on buffer sizes for connectivity
    """
    
    def __init__(self, cache_dir: str = "crime_aware_routing_2/cache"):
        """
        Initialize boundary edge manager.
        
        Args:
            cache_dir: Directory for cache storage
        """
        self.cache_dir = Path(cache_dir)
        self.boundary_dir = self.cache_dir / "boundary_edges"
        self.db_path = self.boundary_dir / "boundary_edges.db"
        
        # Ensure directories exist
        self.cache_dir.mkdir(exist_ok=True)
        self.boundary_dir.mkdir(exist_ok=True)
        
        # Initialize database
        self._init_database()
        
        # Cache for performance
        self._tile_edge_cache = {}
        self._edge_geometry_cache = {}
        
        logger.info(f"BoundaryEdgeManager initialized with cache at {self.cache_dir}")
    
    def _init_database(self):
        """Initialize SQLite database for boundary edge storage."""
        with self._get_db_connection() as conn:
            # Main boundary edges table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS boundary_edges (
                    edge_id TEXT PRIMARY KEY,
                    start_node TEXT NOT NULL,
                    end_node TEXT NOT NULL,
                    geometry_wkt TEXT NOT NULL,
                    edge_data_json TEXT NOT NULL,
                    edge_length REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    last_accessed TEXT NOT NULL
                )
            ''')
            
            # Tile-edge mapping table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS tile_edge_mapping (
                    tile_id TEXT NOT NULL,
                    edge_id TEXT NOT NULL,
                    crossing_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tile_id, edge_id),
                    FOREIGN KEY (edge_id) REFERENCES boundary_edges (edge_id)
                )
            ''')
            
            # Tile boundaries table for spatial queries
            conn.execute('''
                CREATE TABLE IF NOT EXISTS tile_boundaries (
                    tile_id TEXT PRIMARY KEY,
                    bounds_wkt TEXT NOT NULL,
                    center_lat REAL NOT NULL,
                    center_lon REAL NOT NULL,
                    precision_level INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
            ''')
            
            # Create indexes for performance
            conn.execute('CREATE INDEX IF NOT EXISTS idx_edge_length ON boundary_edges(edge_length)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_tile_mapping ON tile_edge_mapping(tile_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_edge_mapping ON tile_edge_mapping(edge_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_tile_center ON tile_boundaries(center_lat, center_lon)')
            
            logger.debug("Boundary edge database initialized")
    
    @contextmanager
    def _get_db_connection(self):
        """Get database connection with proper cleanup."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def catalog_boundary_edges(self, network: nx.MultiDiGraph, tile_id: str, 
                             tile_bounds: Dict[str, float], 
                             neighboring_tiles: List[str] = None) -> Dict[str, Any]:
        """
        Identify and catalog edges that cross tile boundaries.
        
        Args:
            network: NetworkX graph with edge geometries
            tile_id: Unique identifier for this tile
            tile_bounds: Dictionary with 'north', 'south', 'east', 'west' bounds
            neighboring_tiles: List of neighboring tile IDs
            
        Returns:
            Dictionary with cataloging statistics
        """
        try:
            logger.info(f"Cataloging boundary edges for tile {tile_id}")
            
            # Create tile boundary polygon
            tile_polygon = box(
                tile_bounds['west'], tile_bounds['south'],
                tile_bounds['east'], tile_bounds['north']
            )
            
            # Store tile boundary in database
            self._store_tile_boundary(tile_id, tile_polygon, tile_bounds)
            
            boundary_edges = []
            internal_edges = []
            
            # Analyze each edge for boundary crossings
            for u, v, key, edge_data in network.edges(data=True, keys=True):
                edge_id = f"{u}_{v}_{key}"
                
                # Get edge geometry
                if 'geometry' in edge_data:
                    edge_geom = edge_data['geometry']
                else:
                    # Create geometry from node positions
                    start_point = Point(network.nodes[u]['x'], network.nodes[u]['y'])
                    end_point = Point(network.nodes[v]['x'], network.nodes[v]['y'])
                    edge_geom = LineString([start_point.coords[0], end_point.coords[0]])
                
                # Check if edge crosses tile boundary
                crossing_type = self._analyze_edge_crossing(edge_geom, tile_polygon)
                
                if crossing_type != 'internal':
                    # This is a boundary edge - catalog it
                    boundary_edge_info = {
                        'edge_id': edge_id,
                        'start_node': str(u),
                        'end_node': str(v),
                        'key': key,
                        'geometry': edge_geom,
                        'edge_data': edge_data,
                        'crossing_type': crossing_type,
                        'tile_id': tile_id
                    }
                    
                    boundary_edges.append(boundary_edge_info)
                    self._store_boundary_edge(boundary_edge_info)
                else:
                    internal_edges.append(edge_id)
            
            # Store tile-edge mappings
            self._store_tile_mappings(tile_id, boundary_edges)
            
            stats = {
                'tile_id': tile_id,
                'total_edges': len(list(network.edges())),
                'boundary_edges': len(boundary_edges),
                'internal_edges': len(internal_edges),
                'boundary_ratio': len(boundary_edges) / len(list(network.edges())) if network.edges() else 0.0
            }
            
            logger.info(f"Cataloged {len(boundary_edges)} boundary edges for tile {tile_id} "
                       f"({stats['boundary_ratio']:.1%} of total)")
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to catalog boundary edges for tile {tile_id}: {e}")
            raise
    
    def _analyze_edge_crossing(self, edge_geom: LineString, tile_polygon: Polygon) -> str:
        """
        Analyze how an edge crosses the tile boundary.
        
        Args:
            edge_geom: Edge geometry
            tile_polygon: Tile boundary polygon
            
        Returns:
            Crossing type: 'internal', 'crossing', 'touching', 'external'
        """
        try:
            # Check relationship between edge and tile
            if tile_polygon.contains(edge_geom):
                return 'internal'
            elif edge_geom.intersects(tile_polygon):
                # Check if it's just touching vs actually crossing
                intersection = edge_geom.intersection(tile_polygon)
                if hasattr(intersection, 'length') and intersection.length > 0:
                    return 'crossing'
                else:
                    return 'touching'
            else:
                return 'external'
                
        except Exception as e:
            logger.debug(f"Error analyzing edge crossing: {e}")
            return 'unknown'
    
    def _store_tile_boundary(self, tile_id: str, tile_polygon: Polygon, 
                           tile_bounds: Dict[str, float]):
        """Store tile boundary information."""
        try:
            center_lat = (tile_bounds['north'] + tile_bounds['south']) / 2
            center_lon = (tile_bounds['east'] + tile_bounds['west']) / 2
            
            with self._get_db_connection() as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO tile_boundaries 
                    (tile_id, bounds_wkt, center_lat, center_lon, precision_level, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    tile_id,
                    tile_polygon.wkt,
                    center_lat,
                    center_lon,
                    6,  # Default precision level
                    datetime.now().isoformat()
                ))
                conn.commit()
                
        except Exception as e:
            logger.warning(f"Failed to store tile boundary for {tile_id}: {e}")
    
    def _store_boundary_edge(self, edge_info: Dict[str, Any]):
        """Store boundary edge in database."""
        try:
            with self._get_db_connection() as conn:
                # Serialize edge data
                edge_data_json = json.dumps(edge_info['edge_data'], default=str)
                
                # Calculate edge length
                edge_length = edge_info['geometry'].length
                
                now = datetime.now().isoformat()
                
                conn.execute('''
                    INSERT OR REPLACE INTO boundary_edges 
                    (edge_id, start_node, end_node, geometry_wkt, edge_data_json, 
                     edge_length, created_at, last_accessed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    edge_info['edge_id'],
                    edge_info['start_node'],
                    edge_info['end_node'],
                    edge_info['geometry'].wkt,
                    edge_data_json,
                    edge_length,
                    now,
                    now
                ))
                conn.commit()
                
        except Exception as e:
            logger.warning(f"Failed to store boundary edge {edge_info['edge_id']}: {e}")
    
    def _store_tile_mappings(self, tile_id: str, boundary_edges: List[Dict[str, Any]]):
        """Store tile-edge mappings."""
        try:
            with self._get_db_connection() as conn:
                now = datetime.now().isoformat()
                
                for edge_info in boundary_edges:
                    conn.execute('''
                        INSERT OR REPLACE INTO tile_edge_mapping 
                        (tile_id, edge_id, crossing_type, created_at)
                        VALUES (?, ?, ?, ?)
                    ''', (
                        tile_id,
                        edge_info['edge_id'],
                        edge_info['crossing_type'],
                        now
                    ))
                
                conn.commit()
                
        except Exception as e:
            logger.warning(f"Failed to store tile mappings for {tile_id}: {e}")
    
    def restore_boundary_edges(self, merged_network: nx.MultiDiGraph, 
                             tile_ids: List[str]) -> Dict[str, Any]:
        """
        Restore boundary edges for a set of tiles to guarantee connectivity.
        
        Args:
            merged_network: Merged network from tiles
            tile_ids: List of tile IDs being merged
            
        Returns:
            Dictionary with restoration statistics
        """
        try:
            logger.info(f"Restoring boundary edges for tiles: {tile_ids}")
            
            # Get all boundary edges for these tiles
            boundary_edges = self._get_boundary_edges_for_tiles(tile_ids)
            
            restored_count = 0
            skipped_count = 0
            error_count = 0
            
            for edge_info in boundary_edges:
                try:
                    # Check if edge already exists in merged network
                    if self._edge_exists_in_network(merged_network, edge_info):
                        skipped_count += 1
                        continue
                    
                    # Restore the complete boundary edge
                    self._restore_single_edge(merged_network, edge_info)
                    restored_count += 1
                    
                except Exception as e:
                    logger.debug(f"Failed to restore edge {edge_info['edge_id']}: {e}")
                    error_count += 1
            
            # Update last accessed time
            self._update_access_time(tile_ids)
            
            stats = {
                'tiles_processed': len(tile_ids),
                'boundary_edges_found': len(boundary_edges),
                'edges_restored': restored_count,
                'edges_skipped': skipped_count,
                'errors': error_count
            }
            
            logger.info(f"Boundary edge restoration complete: {restored_count} restored, "
                       f"{skipped_count} skipped, {error_count} errors")
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to restore boundary edges: {e}")
            raise
    
    def _get_boundary_edges_for_tiles(self, tile_ids: List[str]) -> List[Dict[str, Any]]:
        """Get all boundary edges for a set of tiles."""
        try:
            with self._get_db_connection() as conn:
                # Query boundary edges for these tiles
                placeholders = ','.join('?' * len(tile_ids))
                
                cursor = conn.execute(f'''
                    SELECT DISTINCT be.edge_id, be.start_node, be.end_node, 
                           be.geometry_wkt, be.edge_data_json, be.edge_length
                    FROM boundary_edges be
                    JOIN tile_edge_mapping tem ON be.edge_id = tem.edge_id
                    WHERE tem.tile_id IN ({placeholders})
                ''', tile_ids)
                
                boundary_edges = []
                
                for row in cursor.fetchall():
                    try:
                        # Deserialize edge data
                        edge_data = json.loads(row['edge_data_json'])
                        
                        # Reconstruct geometry
                        from shapely import wkt
                        geometry = wkt.loads(row['geometry_wkt'])
                        
                        edge_info = {
                            'edge_id': row['edge_id'],
                            'start_node': row['start_node'],
                            'end_node': row['end_node'],
                            'geometry': geometry,
                            'edge_data': edge_data,
                            'edge_length': row['edge_length']
                        }
                        
                        boundary_edges.append(edge_info)
                        
                    except Exception as e:
                        logger.debug(f"Failed to deserialize edge {row['edge_id']}: {e}")
                
                return boundary_edges
                
        except Exception as e:
            logger.warning(f"Failed to get boundary edges for tiles {tile_ids}: {e}")
            return []
    
    def _edge_exists_in_network(self, network: nx.MultiDiGraph, 
                               edge_info: Dict[str, Any]) -> bool:
        """Check if edge already exists in network."""
        try:
            start_node = edge_info['start_node']
            end_node = edge_info['end_node']
            
            # Check if both nodes exist
            if start_node not in network.nodes or end_node not in network.nodes:
                return False
            
            # Check if edge exists (any key)
            return network.has_edge(start_node, end_node)
            
        except Exception:
            return False
    
    def _restore_single_edge(self, network: nx.MultiDiGraph, edge_info: Dict[str, Any]):
        """Restore a single boundary edge to the network."""
        try:
            start_node = edge_info['start_node']
            end_node = edge_info['end_node']
            edge_data = edge_info['edge_data'].copy()
            
            # Ensure nodes exist in network
            if start_node not in network.nodes:
                # Extract node data from edge geometry
                start_point = Point(edge_info['geometry'].coords[0])
                network.add_node(start_node, 
                                x=start_point.x, 
                                y=start_point.y)
            
            if end_node not in network.nodes:
                end_point = Point(edge_info['geometry'].coords[-1])
                network.add_node(end_node, 
                                x=end_point.x, 
                                y=end_point.y)
            
            # Add the complete edge with original geometry
            edge_data['geometry'] = edge_info['geometry']
            edge_data['boundary_restored'] = True  # Mark as restored
            
            network.add_edge(start_node, end_node, **edge_data)
            
        except Exception as e:
            logger.debug(f"Failed to restore edge {edge_info['edge_id']}: {e}")
            raise
    
    def _update_access_time(self, tile_ids: List[str]):
        """Update last accessed time for boundary edges."""
        try:
            with self._get_db_connection() as conn:
                now = datetime.now().isoformat()
                placeholders = ','.join('?' * len(tile_ids))
                
                conn.execute(f'''
                    UPDATE boundary_edges 
                    SET last_accessed = ?
                    WHERE edge_id IN (
                        SELECT DISTINCT edge_id 
                        FROM tile_edge_mapping 
                        WHERE tile_id IN ({placeholders})
                    )
                ''', [now] + tile_ids)
                
                conn.commit()
                
        except Exception as e:
            logger.debug(f"Failed to update access time: {e}")
    
    def get_boundary_statistics(self) -> Dict[str, Any]:
        """Get statistics about boundary edge storage."""
        try:
            with self._get_db_connection() as conn:
                # Get edge statistics
                cursor = conn.execute('''
                    SELECT 
                        COUNT(*) as total_edges,
                        AVG(edge_length) as avg_length,
                        MAX(edge_length) as max_length,
                        MIN(edge_length) as min_length,
                        SUM(edge_length) as total_length
                    FROM boundary_edges
                ''')
                edge_stats = cursor.fetchone()
                
                # Get tile statistics
                cursor = conn.execute('''
                    SELECT 
                        COUNT(DISTINCT tile_id) as total_tiles,
                        COUNT(*) as total_mappings,
                        AVG(mappings_per_tile) as avg_mappings_per_tile
                    FROM (
                        SELECT tile_id, COUNT(*) as mappings_per_tile
                        FROM tile_edge_mapping
                        GROUP BY tile_id
                    )
                ''')
                tile_stats = cursor.fetchone()
                
                return {
                    'boundary_edges': {
                        'total': edge_stats['total_edges'] or 0,
                        'avg_length_m': edge_stats['avg_length'] or 0,
                        'max_length_m': edge_stats['max_length'] or 0,
                        'min_length_m': edge_stats['min_length'] or 0,
                        'total_length_km': (edge_stats['total_length'] or 0) / 1000
                    },
                    'tiles': {
                        'total': tile_stats['total_tiles'] or 0,
                        'total_mappings': tile_stats['total_mappings'] or 0,
                        'avg_boundary_edges_per_tile': tile_stats['avg_mappings_per_tile'] or 0
                    },
                    'database_path': str(self.db_path),
                    'cache_dir': str(self.cache_dir)
                }
                
        except Exception as e:
            logger.error(f"Failed to get boundary statistics: {e}")
            return {'error': str(e)}
    
    def clear_cache(self, older_than_days: Optional[int] = None):
        """Clear boundary edge cache."""
        try:
            with self._get_db_connection() as conn:
                if older_than_days:
                    from datetime import timedelta
                    cutoff_date = (datetime.now() - timedelta(days=older_than_days)).isoformat()
                    
                    # Delete old mappings
                    cursor = conn.execute(
                        'DELETE FROM tile_edge_mapping WHERE created_at < ?',
                        (cutoff_date,)
                    )
                    mappings_deleted = cursor.rowcount
                    
                    # Delete orphaned edges
                    cursor = conn.execute('''
                        DELETE FROM boundary_edges 
                        WHERE edge_id NOT IN (
                            SELECT DISTINCT edge_id FROM tile_edge_mapping
                        ) AND created_at < ?
                    ''', (cutoff_date,))
                    edges_deleted = cursor.rowcount
                    
                    # Delete old tile boundaries
                    cursor = conn.execute(
                        'DELETE FROM tile_boundaries WHERE created_at < ?',
                        (cutoff_date,)
                    )
                    tiles_deleted = cursor.rowcount
                    
                else:
                    # Clear everything
                    conn.execute('DELETE FROM tile_edge_mapping')
                    mappings_deleted = conn.execute('SELECT changes()').fetchone()[0]
                    
                    conn.execute('DELETE FROM boundary_edges')
                    edges_deleted = conn.execute('SELECT changes()').fetchone()[0]
                    
                    conn.execute('DELETE FROM tile_boundaries')
                    tiles_deleted = conn.execute('SELECT changes()').fetchone()[0]
                
                conn.commit()
                
                # Clear memory cache
                self._tile_edge_cache.clear()
                self._edge_geometry_cache.clear()
                
                logger.info(f"Boundary cache cleared: {edges_deleted} edges, "
                           f"{mappings_deleted} mappings, {tiles_deleted} tiles")
                
        except Exception as e:
            logger.error(f"Failed to clear boundary cache: {e}")
            raise 
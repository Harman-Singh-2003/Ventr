"""
Crime data processing and spatial indexing for efficient route analysis.
"""

import json
import numpy as np
import geopandas as gpd
from typing import List, Tuple, Dict, Optional, Union
from pathlib import Path
import logging
from scipy.spatial import KDTree
from shapely.geometry import Point, Polygon, box
from ..config.routing_config import RoutingConfig

logger = logging.getLogger(__name__)


class CrimeProcessor:
    """
    Process and spatially index crime data for efficient routing queries.
    """
    
    def __init__(self, crime_data_path: Union[str, Path], config: Optional[RoutingConfig] = None):
        """
        Initialize crime processor with data loading and spatial indexing.
        
        Args:
            crime_data_path: Path to crime data GeoJSON file
            config: Routing configuration parameters
        """
        self.config = config or RoutingConfig()
        self.crime_data_path = Path(crime_data_path)
        
        # Core data storage
        self.crime_points: Optional[np.ndarray] = None  # [N, 2] array of (lat, lon)
        self.crime_gdf: Optional[gpd.GeoDataFrame] = None  # Full GeoDataFrame
        self.spatial_index: Optional[KDTree] = None  # For fast spatial queries
        
        # Cached regions for performance
        self._bounds_cache: Dict[str, np.ndarray] = {}
        
        # Load and process data
        self._load_crime_data()
        self._create_spatial_index()
        
        logger.info(f"CrimeProcessor initialized with {len(self.crime_points)} crime incidents")
    
    def _load_crime_data(self) -> None:
        """Load crime data from GeoJSON file."""
        try:
            if not self.crime_data_path.exists():
                raise FileNotFoundError(f"Crime data file not found: {self.crime_data_path}")
            
            # Load GeoJSON data
            self.crime_gdf = gpd.read_file(self.crime_data_path)
            
            # Extract coordinates as numpy array for efficient processing
            geometries = self.crime_gdf.geometry
            coords = [(geom.y, geom.x) for geom in geometries if geom is not None]
            self.crime_points = np.array(coords)
            
            # Validate data
            if len(self.crime_points) == 0:
                raise ValueError("No valid crime coordinates found in data")
            
            logger.info(f"Loaded {len(self.crime_points)} crime incidents")
            logger.info(f"Coordinate bounds: lat ({self.crime_points[:, 0].min():.4f}, "
                       f"{self.crime_points[:, 0].max():.4f}), "
                       f"lon ({self.crime_points[:, 1].min():.4f}, "
                       f"{self.crime_points[:, 1].max():.4f})")
            
        except Exception as e:
            logger.error(f"Failed to load crime data: {e}")
            raise
    
    def _create_spatial_index(self) -> None:
        """Create spatial index for fast nearest neighbor queries."""
        try:
            # Create KDTree for efficient spatial queries
            # Note: KDTree expects (lon, lat) order for Euclidean distance
            tree_coords = self.crime_points[:, [1, 0]]  # Swap to (lon, lat)
            self.spatial_index = KDTree(tree_coords)
            logger.info("Spatial index created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create spatial index: {e}")
            raise
    
    def get_crimes_in_bounds(self, bounds: Dict[str, float], buffer_meters: float = 0) -> np.ndarray:
        """
        Get crime points within specified geographic bounds.
        
        Args:
            bounds: Dictionary with keys 'lat_min', 'lat_max', 'lon_min', 'lon_max'
            buffer_meters: Additional buffer around bounds in meters
            
        Returns:
            Array of crime coordinates [N, 2] as (lat, lon)
        """
        # Create cache key for bounds
        cache_key = f"{bounds['lat_min']:.6f}_{bounds['lat_max']:.6f}_{bounds['lon_min']:.6f}_{bounds['lon_max']:.6f}_{buffer_meters}"
        
        if cache_key in self._bounds_cache:
            return self._bounds_cache[cache_key]
        
        # Apply buffer if specified (approximate conversion: 1 degree ≈ 111km)
        if buffer_meters > 0:
            buffer_deg = buffer_meters / 111000.0  # Rough conversion to degrees
            bounds = {
                'lat_min': bounds['lat_min'] - buffer_deg,
                'lat_max': bounds['lat_max'] + buffer_deg, 
                'lon_min': bounds['lon_min'] - buffer_deg,
                'lon_max': bounds['lon_max'] + buffer_deg
            }
        
        # Filter points within bounds
        mask = (
            (self.crime_points[:, 0] >= bounds['lat_min']) &
            (self.crime_points[:, 0] <= bounds['lat_max']) &
            (self.crime_points[:, 1] >= bounds['lon_min']) &
            (self.crime_points[:, 1] <= bounds['lon_max'])
        )
        
        filtered_points = self.crime_points[mask]
        
        # Cache result
        if len(self._bounds_cache) < 100:  # Limit cache size
            self._bounds_cache[cache_key] = filtered_points
        
        logger.debug(f"Found {len(filtered_points)} crimes in bounds "
                    f"(original: {len(self.crime_points)})")
        
        return filtered_points
    
    def get_crimes_near_point(self, lat: float, lon: float, radius_meters: float) -> np.ndarray:
        """
        Get crime points within radius of a specific point.
        
        Args:
            lat: Latitude of center point
            lon: Longitude of center point
            radius_meters: Search radius in meters
            
        Returns:
            Array of crime coordinates [N, 2] as (lat, lon)
        """
        # Convert radius to approximate degrees (rough approximation)
        radius_deg = radius_meters / 111000.0
        
        # Query spatial index for nearby points
        query_point = [lon, lat]  # KDTree uses (lon, lat) order
        indices = self.spatial_index.query_ball_point(query_point, radius_deg)
        
        if not indices:
            return np.array([]).reshape(0, 2)
        
        return self.crime_points[indices]
    
    def get_all_crime_points(self) -> np.ndarray:
        """
        Get all crime points as (lat, lon) coordinates.
        
        Returns:
            Array of all crime coordinates [N, 2] as (lat, lon)
        """
        return self.crime_points.copy()
    
    def get_crime_statistics(self) -> Dict:
        """
        Get statistical summary of crime data.
        
        Returns:
            Dictionary with crime data statistics
        """
        if self.crime_points is None or len(self.crime_points) == 0:
            return {"total_crimes": 0}
        
        lats = self.crime_points[:, 0]
        lons = self.crime_points[:, 1]
        
        return {
            "total_crimes": len(self.crime_points),
            "bounds": {
                "lat_min": float(lats.min()),
                "lat_max": float(lats.max()),
                "lon_min": float(lons.min()),
                "lon_max": float(lons.max())
            },
            "center": {
                "lat": float(lats.mean()),
                "lon": float(lons.mean())
            },
            "std_dev": {
                "lat": float(lats.std()),
                "lon": float(lons.std())
            }
        }
    
    def filter_by_crime_type(self, crime_types: List[str]) -> 'CrimeProcessor':
        """
        Create new CrimeProcessor filtered by specific crime types.
        
        Args:
            crime_types: List of crime type strings to include
            
        Returns:
            New CrimeProcessor instance with filtered data
        """
        # This would require crime type information in the data
        # For now, return self as all crimes are weighted equally
        logger.warning("Crime type filtering not implemented - all crimes weighted equally")
        return self
    
    def create_bounds_from_route(self, start_coords: Tuple[float, float], 
                                end_coords: Tuple[float, float], 
                                buffer_meters: float = None) -> Dict[str, float]:
        """
        Create geographic bounds that encompass a route with buffer.
        
        Args:
            start_coords: (lat, lon) of route start
            end_coords: (lat, lon) of route end
            buffer_meters: Buffer around route in meters
            
        Returns:
            Dictionary with lat/lon bounds
        """
        if buffer_meters is None:
            buffer_meters = self.config.crime_data_buffer
        
        # Get route bounds
        lat_min = min(start_coords[0], end_coords[0])
        lat_max = max(start_coords[0], end_coords[0])
        lon_min = min(start_coords[1], end_coords[1])
        lon_max = max(start_coords[1], end_coords[1])
        
        # Apply buffer (approximate conversion to degrees)
        buffer_deg = buffer_meters / 111000.0
        
        return {
            'lat_min': lat_min - buffer_deg,
            'lat_max': lat_max + buffer_deg,
            'lon_min': lon_min - buffer_deg,
            'lon_max': lon_max + buffer_deg
        } 
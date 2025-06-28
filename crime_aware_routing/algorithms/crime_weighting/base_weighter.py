"""
Base abstract class for crime weighting strategies.
"""

from abc import ABC, abstractmethod
from typing import Dict, Tuple, Optional, List
import numpy as np
from shapely.geometry import LineString, Point
from ...config.routing_config import RoutingConfig


class BaseCrimeWeighter(ABC):
    """
    Abstract base class for crime weighting strategies.
    
    This defines the interface that all crime weighting implementations must follow.
    """
    
    def __init__(self, config: Optional[RoutingConfig] = None):
        """
        Initialize the crime weighter.
        
        Args:
            config: Routing configuration parameters
        """
        self.config = config or RoutingConfig()
        self.is_fitted = False
        self._crime_surface = None
        
    @abstractmethod
    def fit(self, crime_points: np.ndarray, network_bounds: Dict[str, float]) -> None:
        """
        Fit the crime weighting model to the data.
        
        Args:
            crime_points: Array of crime coordinates [N, 2] as (lat, lon)
            network_bounds: Geographic bounds with keys 'lat_min', 'lat_max', 'lon_min', 'lon_max'
        """
        pass
    
    @abstractmethod
    def get_edge_crime_score(self, edge_geometry: LineString) -> float:
        """
        Calculate crime score for a street edge.
        
        Args:
            edge_geometry: Shapely LineString representing the street segment
            
        Returns:
            Crime score (higher = more dangerous)
        """
        pass
    
    @abstractmethod
    def get_point_crime_score(self, lat: float, lon: float) -> float:
        """
        Calculate crime score at a specific point.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Crime score (higher = more dangerous)
        """
        pass
    
    def interpolate_points_along_edge(self, edge_geometry: LineString, 
                                    interval_meters: float = None) -> List[Tuple[float, float]]:
        """
        Generate sample points along an edge for crime scoring.
        
        Args:
            edge_geometry: Shapely LineString representing the street segment
            interval_meters: Distance between sample points in meters
            
        Returns:
            List of (lat, lon) coordinate tuples
        """
        if interval_meters is None:
            interval_meters = self.config.edge_sample_interval
        
        # Get edge coordinates
        coords = list(edge_geometry.coords)
        
        if len(coords) < 2:
            return []
        
        # For simple implementation, return start, middle, and end points
        # More sophisticated version would interpolate at regular intervals
        sample_points = []
        
        # Start point
        sample_points.append((coords[0][1], coords[0][0]))  # (lat, lon)
        
        # Middle point if edge is long enough
        if len(coords) > 2 or self._calculate_edge_length_rough(edge_geometry) > interval_meters:
            mid_point = edge_geometry.interpolate(0.5, normalized=True)
            sample_points.append((mid_point.y, mid_point.x))
        
        # End point
        sample_points.append((coords[-1][1], coords[-1][0]))  # (lat, lon)
        
        return sample_points
    
    def _calculate_edge_length_rough(self, edge_geometry: LineString) -> float:
        """
        Rough calculation of edge length in meters using coordinate differences.
        
        Args:
            edge_geometry: Shapely LineString
            
        Returns:
            Approximate length in meters
        """
        coords = list(edge_geometry.coords)
        if len(coords) < 2:
            return 0.0
        
        # Rough conversion: 1 degree ≈ 111km
        lat1, lon1 = coords[0][1], coords[0][0]
        lat2, lon2 = coords[-1][1], coords[-1][0]
        
        dlat = (lat2 - lat1) * 111000.0
        dlon = (lon2 - lon1) * 111000.0 * np.cos(np.radians((lat1 + lat2) / 2))
        
        return np.sqrt(dlat**2 + dlon**2)
    
    def normalize_score(self, score: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
        """
        Normalize a crime score to a specified range.
        
        Args:
            score: Raw crime score
            min_val: Minimum value of output range
            max_val: Maximum value of output range
            
        Returns:
            Normalized score
        """
        if not self.config.normalize_crime_scores:
            return score
        
        # Simple clipping for now - more sophisticated normalization could be added
        return np.clip(score, min_val, max_val)
    
    def validate_fitted(self) -> None:
        """Check if the weighter has been fitted to data."""
        if not self.is_fitted:
            raise RuntimeError("Crime weighter must be fitted to data before use")
    
    def get_crime_surface(self):
        """
        Get the computed crime surface for visualization.
        
        Returns:
            Crime surface data (implementation-specific)
        """
        self.validate_fitted()
        return self._crime_surface 
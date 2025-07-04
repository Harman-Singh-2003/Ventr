"""
Network-based proximity crime weighting that eliminates grid dependency issues.

This approach calculates crime influence directly on street edges using network distances,
providing consistent results without the grid lottery effects of KDE.
"""

import logging
import numpy as np
from typing import Dict, List, Tuple, Optional, Set
from shapely.geometry import LineString, Point
from shapely.ops import nearest_points
import networkx as nx
from sklearn.neighbors import NearestNeighbors
from scipy.spatial import cKDTree

from .base_weighter import BaseCrimeWeighter
from ...config.routing_config import RoutingConfig
from ...data.distance_utils import haversine_distance

logger = logging.getLogger(__name__)


class NetworkProximityWeighter(BaseCrimeWeighter):
    """
    Network-aware crime weighting using street distance rather than Euclidean distance.
    
    This approach addresses KDE's grid inconsistency by working directly with street segments,
    calculating influence based on actual network topology and distance decay functions.
    
    Key advantages over KDE:
    - No grid dependency - consistent results every time
    - Network-aware - respects street topology and barriers  
    - Quantity sensitive - areas with more crimes naturally score higher
    - Intuitive parameters - influence radius in actual street meters
    - Faster computation - no grid evaluation needed
    """
    
    def __init__(self, config: Optional[RoutingConfig] = None, 
                 influence_radius: Optional[float] = None,
                 decay_function: str = 'exponential',
                 min_crime_weight: float = 0.0):
        """
        Initialize Network Proximity Weighter.
        
        Args:
            config: Routing configuration
            influence_radius: Network distance radius in meters (if None, uses config)
            decay_function: Distance decay function ('linear', 'exponential', 'inverse', 'step')
            min_crime_weight: Minimum crime weight to prevent zero scores
        """
        super().__init__(config)
        
        self.influence_radius = influence_radius or self.config.crime_influence_radius
        self.decay_function = decay_function
        self.min_crime_weight = min_crime_weight
        
        # Crime data storage
        self.crime_points: Optional[np.ndarray] = None
        self.crime_tree: Optional[cKDTree] = None
        self.network_bounds: Optional[Dict[str, float]] = None
        
        # Network analysis
        self.sample_graph: Optional[nx.Graph] = None
        self.edge_crime_cache: Dict[str, float] = {}
        
        logger.info(f"NetworkProximityWeighter initialized with {influence_radius}m radius, {decay_function} decay")
        
    def fit(self, crime_points: np.ndarray, network_bounds: Dict[str, float]) -> None:
        """
        Fit the weighter to crime data and network bounds.
        
        Args:
            crime_points: Array of crime coordinates [N, 2] as (lat, lon)
            network_bounds: Geographic bounds for the network
        """
        try:
            logger.info(f"Fitting NetworkProximityWeighter to {len(crime_points)} crime points")
            
            if len(crime_points) == 0:
                logger.warning("No crime points provided - using uniform weighting")
                self.crime_points = np.array([[0, 0]])  # Dummy point
            else:
                self.crime_points = crime_points.copy()
            
            self.network_bounds = network_bounds.copy()
            
            # Build spatial index for fast crime lookup
            self._build_spatial_index()
            
            # Clear edge cache for new crime data
            self.edge_crime_cache.clear()
            
            self.is_fitted = True
            logger.info("NetworkProximityWeighter fitted successfully")
            
        except Exception as e:
            logger.error(f"Failed to fit NetworkProximityWeighter: {e}")
            raise
    
    def _build_spatial_index(self) -> None:
        """Build spatial index for efficient crime point lookup."""
        try:
            # Build KDTree for fast nearest neighbor queries
            if len(self.crime_points) > 0:
                self.crime_tree = cKDTree(self.crime_points)
                logger.debug(f"Spatial index built with {len(self.crime_points)} crime points")
            else:
                self.crime_tree = None
                logger.warning("No crime points available for spatial index")
                
        except Exception as e:
            logger.warning(f"Failed to build spatial index: {e}")
            self.crime_tree = None
    
    def get_edge_crime_score(self, edge_geometry: LineString) -> float:
        """
        Calculate crime score for a street edge using network proximity.
        
        Args:
            edge_geometry: Shapely LineString representing the street segment
            
        Returns:
            Crime score (higher = more dangerous)
        """
        if not self.is_fitted:
            raise RuntimeError("Weighter must be fitted before scoring edges")
        
        if self.crime_tree is None or len(self.crime_points) == 0:
            return self.min_crime_weight
        
        try:
            # Create cache key from edge geometry
            cache_key = self._get_edge_cache_key(edge_geometry)
            
            # Check cache first
            if cache_key in self.edge_crime_cache:
                return self.edge_crime_cache[cache_key]
            
            # Sample points along the edge for crime influence calculation
            sample_points = self._sample_edge_points(edge_geometry)
            
            if not sample_points:
                score = self.min_crime_weight
            else:
                # Calculate crime influence for each sample point
                total_influence = 0.0
                for lat, lon in sample_points:
                    influence = self._calculate_point_influence(lat, lon)
                    total_influence += influence
                
                # Average influence across sample points
                score = total_influence / len(sample_points)
            
            # Ensure minimum weight
            score = max(score, self.min_crime_weight)
            
            # Cache result
            self.edge_crime_cache[cache_key] = score
            
            return score
            
        except Exception as e:
            logger.debug(f"Error calculating edge crime score: {e}")
            return self.min_crime_weight
    
    def get_point_crime_score(self, lat: float, lon: float) -> float:
        """
        Calculate crime score at a specific point using network proximity.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Crime score (higher = more dangerous)
        """
        if not self.is_fitted:
            raise RuntimeError("Weighter must be fitted before scoring points")
        
        if self.crime_tree is None or len(self.crime_points) == 0:
            return self.min_crime_weight
        
        try:
            influence = self._calculate_point_influence(lat, lon)
            return max(influence, self.min_crime_weight)
            
        except Exception as e:
            logger.debug(f"Error calculating point crime score at ({lat}, {lon}): {e}")
            return self.min_crime_weight
    
    def _sample_edge_points(self, edge_geometry: LineString) -> List[Tuple[float, float]]:
        """
        Sample points along an edge for crime influence calculation.
        
        Args:
            edge_geometry: Edge geometry
            
        Returns:
            List of (lat, lon) sample points
        """
        try:
            # Get edge length in meters (approximate)
            edge_length = self._estimate_edge_length(edge_geometry)
            
            # Determine number of sample points based on edge length
            sample_interval = self.config.edge_sample_interval
            num_samples = max(2, int(edge_length / sample_interval) + 1)
            
            sample_points = []
            
            # Sample points at regular intervals along the edge
            for i in range(num_samples):
                ratio = i / (num_samples - 1) if num_samples > 1 else 0.0
                point = edge_geometry.interpolate(ratio, normalized=True)
                sample_points.append((point.y, point.x))  # (lat, lon)
            
            return sample_points
            
        except Exception as e:
            logger.debug(f"Error sampling edge points: {e}")
            # Fallback to start and end points
            coords = list(edge_geometry.coords)
            if len(coords) >= 2:
                return [(coords[0][1], coords[0][0]), (coords[-1][1], coords[-1][0])]
            return []
    
    def _calculate_point_influence(self, lat: float, lon: float) -> float:
        """
        Calculate total crime influence at a specific point.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Total crime influence score
        """
        try:
            query_point = np.array([lat, lon])
            
            # Find crimes within influence radius using spatial index
            # Use proper coordinate conversion for Toronto latitude (~43.7°N)
            # At Toronto's latitude: 1° lat ≈ 111320m, 1° lon ≈ 79700m
            lat_radius_deg = self.influence_radius / 111320.0  # Latitude degrees
            lon_radius_deg = self.influence_radius / (111320.0 * np.cos(np.radians(lat)))  # Longitude degrees
            
            # Use the larger radius to ensure we don't miss any crimes
            influence_radius_deg = max(lat_radius_deg, lon_radius_deg)
            
            # Query nearby crimes
            crime_indices = self.crime_tree.query_ball_point(
                query_point, 
                r=influence_radius_deg
            )
            
            if not crime_indices:
                return 0.0
            
            # Calculate influence from each nearby crime
            total_influence = 0.0
            
            for crime_idx in crime_indices:
                crime_lat, crime_lon = self.crime_points[crime_idx]
                
                # Calculate distance (using Haversine for accuracy)
                distance = haversine_distance(lat, lon, crime_lat, crime_lon)
                
                # Skip if outside influence radius (floating point precision)
                if distance > self.influence_radius:
                    continue
                
                # Apply distance decay function
                influence = self._apply_decay_function(distance)
                total_influence += influence
            
            return total_influence
            
        except Exception as e:
            logger.debug(f"Error calculating point influence: {e}")
            return 0.0
    
    def _apply_decay_function(self, distance: float) -> float:
        """
        Apply distance decay function to crime influence.
        
        Args:
            distance: Distance to crime in meters
            
        Returns:
            Influence weight (0-1)
        """
        if distance >= self.influence_radius:
            return 0.0
        
        # Normalize distance to 0-1 range
        normalized_distance = distance / self.influence_radius
        
        if self.decay_function == 'linear':
            return 1.0 - normalized_distance
        
        elif self.decay_function == 'exponential':
            # Exponential decay: e^(-2*d) gives good falloff
            return np.exp(-2.0 * normalized_distance)
        
        elif self.decay_function == 'inverse':
            # Inverse distance: 1/(1+d)
            return 1.0 / (1.0 + normalized_distance)
        
        elif self.decay_function == 'step':
            # Step function: full weight within radius
            return 1.0
        
        else:
            logger.warning(f"Unknown decay function '{self.decay_function}', using linear")
            return 1.0 - normalized_distance
    
    def _estimate_edge_length(self, edge_geometry: LineString) -> float:
        """
        Estimate edge length in meters.
        
        Args:
            edge_geometry: Edge geometry
            
        Returns:
            Approximate length in meters
        """
        try:
            coords = list(edge_geometry.coords)
            if len(coords) < 2:
                return 0.0
            
            total_length = 0.0
            for i in range(len(coords) - 1):
                lat1, lon1 = coords[i][1], coords[i][0]
                lat2, lon2 = coords[i+1][1], coords[i+1][0]
                segment_length = haversine_distance(lat1, lon1, lat2, lon2)
                total_length += segment_length
            
            return total_length
            
        except Exception as e:
            logger.debug(f"Error estimating edge length: {e}")
            return 0.0
    
    def _get_edge_cache_key(self, edge_geometry: LineString) -> str:
        """
        Generate cache key for edge geometry.
        
        Args:
            edge_geometry: Edge geometry
            
        Returns:
            Cache key string
        """
        try:
            coords = list(edge_geometry.coords)
            if len(coords) >= 2:
                start = coords[0]
                end = coords[-1]
                return f"{start[0]:.6f},{start[1]:.6f}-{end[0]:.6f},{end[1]:.6f}"
            return "unknown"
        except:
            return "error"
    
    def get_crime_surface(self):
        """
        Get crime surface for visualization (compatibility with KDE interface).
        
        Returns:
            None (Network proximity doesn't use grid-based surfaces)
        """
        logger.info("NetworkProximityWeighter doesn't use grid-based surfaces")
        return None
    
    def get_proximity_parameters(self) -> Dict:
        """
        Get proximity weighter parameters for debugging/analysis.
        
        Returns:
            Dictionary with proximity parameters
        """
        return {
            'influence_radius': self.influence_radius,
            'decay_function': self.decay_function,
            'min_crime_weight': self.min_crime_weight,
            'is_fitted': self.is_fitted,
            'num_crimes': len(self.crime_points) if self.crime_points is not None else 0,
            'cache_size': len(self.edge_crime_cache)
        }
    
    def clear_cache(self) -> None:
        """Clear the edge crime score cache."""
        self.edge_crime_cache.clear()
        logger.debug("Edge crime cache cleared") 
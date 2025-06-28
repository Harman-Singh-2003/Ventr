"""
KDE-based crime weighting strategy using Gaussian Kernel Density Estimation.
"""

import numpy as np
import logging
from typing import Dict, Tuple, Optional, List
from sklearn.neighbors import KernelDensity
from shapely.geometry import LineString
from scipy.interpolate import RegularGridInterpolator
from .base_weighter import BaseCrimeWeighter
from ...config.routing_config import RoutingConfig

logger = logging.getLogger(__name__)


class CrimeSurface:
    """Container for KDE-generated crime density surface."""
    
    def __init__(self, lat_grid: np.ndarray, lon_grid: np.ndarray, 
                 density_values: np.ndarray, bounds: Dict[str, float]):
        """
        Initialize crime surface.
        
        Args:
            lat_grid: 1D array of latitude coordinates
            lon_grid: 1D array of longitude coordinates  
            density_values: 2D array of density values [lat_idx, lon_idx]
            bounds: Geographic bounds dictionary
        """
        self.lat_grid = lat_grid
        self.lon_grid = lon_grid
        self.density_values = density_values
        self.bounds = bounds
        
        # Create interpolator for querying arbitrary points
        self.interpolator = RegularGridInterpolator(
            (lat_grid, lon_grid), 
            density_values,
            method='linear',
            bounds_error=False,
            fill_value=0.0
        )
    
    def interpolate_at_point(self, lat: float, lon: float) -> float:
        """
        Get crime density at a specific point using interpolation.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Interpolated crime density value
        """
        try:
            return float(self.interpolator([lat, lon])[0])
        except (ValueError, IndexError):
            return 0.0
    
    def get_statistics(self) -> Dict:
        """Get statistical summary of the crime surface."""
        return {
            'min_density': float(self.density_values.min()),
            'max_density': float(self.density_values.max()),
            'mean_density': float(self.density_values.mean()),
            'std_density': float(self.density_values.std()),
            'grid_shape': self.density_values.shape,
            'bounds': self.bounds
        }


class KDECrimeWeighter(BaseCrimeWeighter):
    """
    Crime weighting using Kernel Density Estimation to create smooth crime surfaces.
    
    This approach creates a continuous density surface from discrete crime points,
    naturally handling hotspots and providing smooth transitions.
    """
    
    def __init__(self, config: Optional[RoutingConfig] = None, 
                 bandwidth: Optional[float] = None, kernel: str = 'gaussian'):
        """
        Initialize KDE crime weighter.
        
        Args:
            config: Routing configuration
            bandwidth: KDE bandwidth in meters (if None, uses config value)
            kernel: Kernel type for KDE
        """
        super().__init__(config)
        
        self.bandwidth = bandwidth or self.config.kde_bandwidth
        self.kernel = kernel
        self.kde_model: Optional[KernelDensity] = None
        self.crime_surface: Optional[CrimeSurface] = None
        self.network_bounds: Optional[Dict[str, float]] = None
        
    def fit(self, crime_points: np.ndarray, network_bounds: Dict[str, float]) -> None:
        """
        Fit KDE model to crime data and generate crime surface.
        
        Args:
            crime_points: Array of crime coordinates [N, 2] as (lat, lon)
            network_bounds: Geographic bounds for the network
        """
        try:
            logger.info(f"Fitting KDE model to {len(crime_points)} crime points")
            
            if len(crime_points) == 0:
                raise ValueError("No crime points provided for KDE fitting")
            
            self.network_bounds = network_bounds.copy()
            
            # Convert bandwidth from meters to approximate degrees
            bandwidth_deg = self.bandwidth / 111000.0
            
            # Fit KDE model (sklearn expects [N, 2] array)
            self.kde_model = KernelDensity(
                bandwidth=bandwidth_deg,
                kernel=self.kernel,
                metric='euclidean'
            )
            
            # Fit on (lat, lon) coordinates
            self.kde_model.fit(crime_points)
            
            # Generate crime surface
            self._generate_crime_surface()
            
            self.is_fitted = True
            self._crime_surface = self.crime_surface
            
            logger.info("KDE model fitted successfully")
            
        except Exception as e:
            logger.error(f"Failed to fit KDE model: {e}")
            raise
    
    def _generate_crime_surface(self) -> None:
        """Generate the crime density surface using the fitted KDE model."""
        if self.kde_model is None or self.network_bounds is None:
            raise RuntimeError("KDE model must be fitted before generating surface")
        
        # Create coordinate grid
        resolution_deg = self.config.kde_resolution / 111000.0  # Convert to degrees
        
        lat_min = self.network_bounds['lat_min']
        lat_max = self.network_bounds['lat_max'] 
        lon_min = self.network_bounds['lon_min']
        lon_max = self.network_bounds['lon_max']
        
        # Generate grid points
        lat_grid = np.arange(lat_min, lat_max + resolution_deg, resolution_deg)
        lon_grid = np.arange(lon_min, lon_max + resolution_deg, resolution_deg)
        
        # Create meshgrid for evaluation
        lat_mesh, lon_mesh = np.meshgrid(lat_grid, lon_grid, indexing='ij')
        grid_points = np.column_stack((lat_mesh.ravel(), lon_mesh.ravel()))
        
        logger.info(f"Evaluating KDE on {len(grid_points)} grid points")
        
        # Evaluate KDE at grid points
        log_densities = self.kde_model.score_samples(grid_points)
        densities = np.exp(log_densities)
        
        # Reshape back to grid
        density_grid = densities.reshape(lat_mesh.shape)
        
        # Normalize if requested
        if self.config.normalize_crime_scores:
            if density_grid.max() > density_grid.min():
                density_grid = (density_grid - density_grid.min()) / (density_grid.max() - density_grid.min())
        
        # Create crime surface object
        self.crime_surface = CrimeSurface(
            lat_grid=lat_grid,
            lon_grid=lon_grid,
            density_values=density_grid,
            bounds=self.network_bounds
        )
        
        logger.info(f"Crime surface generated: {density_grid.shape} grid, "
                   f"density range [{density_grid.min():.6f}, {density_grid.max():.6f}]")
    
    def get_edge_crime_score(self, edge_geometry: LineString) -> float:
        """
        Calculate crime score for a street edge using maximum density along the path.
        
        Args:
            edge_geometry: Shapely LineString representing the street segment
            
        Returns:
            Crime score (higher = more dangerous)
        """
        self.validate_fitted()
        
        if self.crime_surface is None:
            return 0.0
        
        # Get sample points along the edge
        sample_points = self.interpolate_points_along_edge(edge_geometry)
        
        if not sample_points:
            return 0.0
        
        # Calculate crime density at each sample point
        crime_scores = []
        for lat, lon in sample_points:
            score = self.crime_surface.interpolate_at_point(lat, lon)
            crime_scores.append(score)
        
        # Use maximum score (conservative approach for safety)
        # Alternative strategies: mean, weighted average, etc.
        max_score = max(crime_scores) if crime_scores else 0.0
        
        return self.normalize_score(max_score)
    
    def get_point_crime_score(self, lat: float, lon: float) -> float:
        """
        Calculate crime score at a specific point.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Crime score (higher = more dangerous)
        """
        self.validate_fitted()
        
        if self.crime_surface is None:
            return 0.0
        
        score = self.crime_surface.interpolate_at_point(lat, lon)
        return self.normalize_score(score)
    
    def get_crime_surface_for_visualization(self) -> Optional[CrimeSurface]:
        """
        Get the crime surface for visualization purposes.
        
        Returns:
            CrimeSurface object or None if not fitted
        """
        return self.crime_surface
    
    def get_kde_parameters(self) -> Dict:
        """
        Get KDE model parameters for debugging/analysis.
        
        Returns:
            Dictionary with KDE parameters
        """
        return {
            'bandwidth': self.bandwidth,
            'bandwidth_degrees': self.bandwidth / 111000.0,
            'kernel': self.kernel,
            'is_fitted': self.is_fitted,
            'surface_statistics': self.crime_surface.get_statistics() if self.crime_surface else None
        }
    
    def update_bandwidth(self, new_bandwidth: float) -> None:
        """
        Update KDE bandwidth and regenerate surface.
        
        Args:
            new_bandwidth: New bandwidth value in meters
        """
        if new_bandwidth <= 0:
            raise ValueError("Bandwidth must be positive")
        
        logger.info(f"Updating KDE bandwidth from {self.bandwidth}m to {new_bandwidth}m")
        
        self.bandwidth = new_bandwidth
        
        # If already fitted, regenerate surface with new bandwidth
        if self.is_fitted and hasattr(self, "_last_crime_points") and self.network_bounds is not None:
            self.fit(self._last_crime_points, self.network_bounds)
    
    def _cache_crime_points(self, crime_points: np.ndarray) -> None:
        """Cache crime points for bandwidth updates."""
        self._last_crime_points = crime_points.copy() 
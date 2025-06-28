"""
Configuration management for crime-aware routing parameters.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class RoutingConfig:
    """Configuration parameters for crime-aware routing algorithms."""
    
    # KDE Parameters
    kde_bandwidth: float = 200.0  # meters - influence radius for crime density
    kde_kernel: str = 'gaussian'  # kernel type for KDE
    crime_influence_radius: float = 100.0  # meters - max distance crime affects route
    kde_resolution: float = 50.0  # meters - grid resolution for crime surface
    
    # Weight Balancing
    distance_weight: float = 0.7  # importance of route distance (0-1)
    crime_weight: float = 0.3     # importance of crime avoidance (0-1)
    adaptive_weighting: bool = True  # dynamically adjust weights based on context
    min_detour_threshold: float = 200.0  # meters - min route length to apply crime weighting
    
    # Performance Optimization
    edge_sample_interval: float = 25.0  # meters - sample points along edges for crime scoring
    max_network_radius: float = 2000.0  # meters - max network size to prevent huge graphs
    enable_caching: bool = True  # cache crime scores for edges
    spatial_index_resolution: int = 100  # grid size for spatial indexing
    
    # Algorithm Behavior
    fallback_to_shortest: bool = True  # use shortest path if weighted fails
    max_detour_ratio: float = 1.5  # max allowed detour (1.5 = 50% longer than shortest)
    crime_penalty_scale: float = 1000.0  # scaling factor for crime penalties in edge weights
    
    # Visualization
    map_style: str = 'OpenStreetMap'  # base map style
    route_colors: Dict[str, str] = field(default_factory=lambda: {
        'shortest': '#FF0000',    # red
        'safest': '#00FF00',      # green  
        'weighted': '#0000FF',    # blue
        'alternative': '#FF8000'  # orange
    })
    crime_heatmap_alpha: float = 0.6  # transparency of crime heatmap overlay
    
    # Data Processing
    crime_data_buffer: float = 500.0  # meters - extra buffer around route for crime data
    normalize_crime_scores: bool = True  # normalize crime density to [0,1]
    
    def validate(self) -> None:
        """Validate configuration parameters."""
        if not 0 <= self.distance_weight <= 1:
            raise ValueError("distance_weight must be between 0 and 1")
        if not 0 <= self.crime_weight <= 1:
            raise ValueError("crime_weight must be between 0 and 1")
        if abs(self.distance_weight + self.crime_weight - 1.0) > 1e-6:
            raise ValueError("distance_weight + crime_weight must equal 1.0")
        if self.kde_bandwidth <= 0:
            raise ValueError("kde_bandwidth must be positive")
        if self.max_detour_ratio < 1.0:
            raise ValueError("max_detour_ratio must be >= 1.0")
    
    @classmethod
    def create_conservative_config(cls) -> 'RoutingConfig':
        """Create configuration that prioritizes safety over speed."""
        return cls(
            distance_weight=0.4,
            crime_weight=0.6,
            kde_bandwidth=300.0,
            max_detour_ratio=2.0
        )
    
    @classmethod 
    def create_balanced_config(cls) -> 'RoutingConfig':
        """Create balanced configuration (default)."""
        return cls()
    
    @classmethod
    def create_speed_focused_config(cls) -> 'RoutingConfig':
        """Create configuration that prioritizes speed over safety."""
        return cls(
            distance_weight=0.9,
            crime_weight=0.1,
            kde_bandwidth=100.0,
            max_detour_ratio=1.2
        ) 
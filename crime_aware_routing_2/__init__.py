"""
Crime-Aware Routing System - Refactored Version 2.0

A clean, efficient implementation of crime-aware routing algorithms for urban navigation.
Built with lessons learned from extensive experimentation and improved organization.

## Quick Start

```python
from crime_aware_routing_2 import RouteOptimizer, RoutingConfig

# Create configuration
config = RoutingConfig.create_optimized_safety_config()

# Initialize optimizer
optimizer = RouteOptimizer("path/to/crime_data.geojson", config)

# Find route
result = optimizer.find_safe_route(
    start_coords=(43.6426, -79.3871),  # CN Tower
    end_coords=(43.6452, -79.3806)     # Union Station
)
```

## Main Components

- **RouteOptimizer**: Main interface for route calculation
- **CachedRouteOptimizer**: Performance-optimized version with caching
- **RoutingConfig**: Configuration management
- **RouteVisualizer**: Interactive map generation
- **GridCache**: High-performance grid-based caching

## Architecture

- `algorithms/`: Core routing and optimization algorithms
- `mapping/`: Network building, caching, and graph enhancement
- `data/`: Data loading and processing utilities
- `visualization/`: Map generation and route visualization
- `config/`: Configuration management
- `examples/`: Demonstration scripts
- `testing/`: Benchmarks and unit tests
"""

# Main public API - expose the most commonly used classes
from .algorithms import RouteOptimizer, CachedRouteOptimizer, WeightedAStarRouter
from .config import RoutingConfig
from .visualization import RouteVisualizer
from .mapping import GridCache, CachedNetworkBuilder
from .data import load_crime_data

# Version information
__version__ = "2.0.0"
__author__ = "Crime-Aware Routing Team"

# Public API
__all__ = [
    # Main interfaces
    'RouteOptimizer',
    'CachedRouteOptimizer', 
    'RoutingConfig',
    'RouteVisualizer',
    
    # Performance components
    'GridCache',
    'CachedNetworkBuilder',
    
    # Core algorithms
    'WeightedAStarRouter',
    
    # Utilities
    'load_crime_data',
    
    # Metadata
    '__version__',
    '__author__'
] 
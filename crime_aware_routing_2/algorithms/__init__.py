"""
Routing algorithms and optimization functionality.

This module contains:
- Core routing algorithms (A*, shortest path)
- Route optimization and comparison
- Crime weighting algorithms
"""

from .routing.astar_weighted import WeightedAStarRouter, RouteDetails
from .optimization.route_optimizer import RouteOptimizer
from .optimization.cached_route_optimizer import CachedRouteOptimizer
from .crime_weighting.kde_weighter import KDECrimeWeighter
from .crime_weighting.base_weighter import BaseCrimeWeighter

__all__ = [
    'WeightedAStarRouter',
    'RouteDetails',
    'RouteOptimizer',
    'CachedRouteOptimizer', 
    'KDECrimeWeighter',
    'BaseCrimeWeighter'
] 
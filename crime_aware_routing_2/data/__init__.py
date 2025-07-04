"""
Data processing and utilities for crime-aware routing.

This module contains:
- Crime data loading and processing
- Distance calculations
- Geographic data utilities
"""

from .data_loader import load_crime_data
from .crime_processor import CrimeProcessor
from .distance_utils import haversine_distance, calculate_route_distance

__all__ = [
    'load_crime_data',
    'CrimeProcessor', 
    'haversine_distance',
    'calculate_route_distance'
] 
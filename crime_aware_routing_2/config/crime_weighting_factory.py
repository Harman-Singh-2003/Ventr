"""
Factory for creating different crime weighting strategies.

This makes it easy to switch between crime weighting methods through
simple configuration rather than code changes.
"""

from typing import Optional, Dict, Any
from enum import Enum

from .routing_config import RoutingConfig
from ..algorithms.crime_weighting import BaseCrimeWeighter, KDECrimeWeighter, NetworkProximityWeighter


class CrimeWeightingMethod(Enum):
    """Available crime weighting methods."""
    KDE = "kde"
    NETWORK_PROXIMITY = "network_proximity"


class CrimeWeightingFactory:
    """
    Factory for creating crime weighting strategies.
    
    This centralizes the creation of different crime weighting methods
    and makes it easy to switch between them through configuration.
    """
    
    @staticmethod
    def create_weighter(method: CrimeWeightingMethod, 
                       config: Optional[RoutingConfig] = None,
                       **kwargs) -> BaseCrimeWeighter:
        """
        Create a crime weighter using the specified method.
        
        Args:
            method: Crime weighting method to use
            config: Routing configuration
            **kwargs: Additional method-specific parameters
            
        Returns:
            Configured crime weighter instance
            
        Raises:
            ValueError: If method is not supported
        """
        if config is None:
            config = RoutingConfig()
            
        if method == CrimeWeightingMethod.KDE:
            return CrimeWeightingFactory._create_kde_weighter(config, **kwargs)
        
        elif method == CrimeWeightingMethod.NETWORK_PROXIMITY:
            return CrimeWeightingFactory._create_network_proximity_weighter(config, **kwargs)
        
        else:
            raise ValueError(f"Unsupported crime weighting method: {method}")
    
    @staticmethod
    def _create_kde_weighter(config: RoutingConfig, **kwargs) -> KDECrimeWeighter:
        """Create KDE crime weighter with configuration."""
        return KDECrimeWeighter(
            config=config,
            bandwidth=kwargs.get('bandwidth', config.kde_bandwidth),
            kernel=kwargs.get('kernel', config.kde_kernel)
        )
    
    @staticmethod
    def _create_network_proximity_weighter(config: RoutingConfig, **kwargs) -> NetworkProximityWeighter:
        """Create Network Proximity crime weighter with configuration."""
        return NetworkProximityWeighter(
            config=config,
            influence_radius=kwargs.get('influence_radius', config.crime_influence_radius),
            decay_function=kwargs.get('decay_function', 'exponential'),
            min_crime_weight=kwargs.get('min_crime_weight', 0.0)
        )
    
    @staticmethod
    def get_available_methods() -> Dict[str, str]:
        """
        Get available crime weighting methods with descriptions.
        
        Returns:
            Dictionary mapping method names to descriptions
        """
        return {
            CrimeWeightingMethod.KDE.value: "Kernel Density Estimation - smooth grid-based crime surfaces",
            CrimeWeightingMethod.NETWORK_PROXIMITY.value: "Network Proximity - direct edge scoring without grids"
        }
    
    @staticmethod
    def get_method_parameters(method: CrimeWeightingMethod) -> Dict[str, Dict[str, Any]]:
        """
        Get configurable parameters for a specific method.
        
        Args:
            method: Crime weighting method
            
        Returns:
            Dictionary of parameter names with their descriptions and defaults
        """
        if method == CrimeWeightingMethod.KDE:
            return {
                'bandwidth': {
                    'description': 'KDE bandwidth in meters (influence radius)',
                    'type': float,
                    'default': 200.0,
                    'range': (50.0, 1000.0)
                },
                'kernel': {
                    'description': 'Kernel type for density estimation',
                    'type': str,
                    'default': 'gaussian',
                    'options': ['gaussian', 'tophat', 'epanechnikov']
                }
            }
        
        elif method == CrimeWeightingMethod.NETWORK_PROXIMITY:
            return {
                'influence_radius': {
                    'description': 'Crime influence radius in meters',
                    'type': float,
                    'default': 100.0,
                    'range': (50.0, 500.0)
                },
                'decay_function': {
                    'description': 'Distance decay function',
                    'type': str,
                    'default': 'exponential',
                    'options': ['linear', 'exponential', 'inverse', 'step']
                },
                'min_crime_weight': {
                    'description': 'Minimum crime weight to prevent zero scores',
                    'type': float,
                    'default': 0.0,
                    'range': (0.0, 1.0)
                }
            }
        
        else:
            return {}


# Convenience functions for common use cases

def create_kde_weighter(config: Optional[RoutingConfig] = None, **kwargs) -> KDECrimeWeighter:
    """Convenience function to create KDE weighter."""
    return CrimeWeightingFactory.create_weighter(
        CrimeWeightingMethod.KDE, config, **kwargs
    )


def create_network_proximity_weighter(config: Optional[RoutingConfig] = None, **kwargs) -> NetworkProximityWeighter:
    """Convenience function to create Network Proximity weighter."""
    return CrimeWeightingFactory.create_weighter(
        CrimeWeightingMethod.NETWORK_PROXIMITY, config, **kwargs
    )


def create_weighter_from_string(method_name: str, 
                               config: Optional[RoutingConfig] = None,
                               **kwargs) -> BaseCrimeWeighter:
    """
    Create weighter from string name.
    
    Args:
        method_name: Name of the method ('kde' or 'network_proximity')
        config: Routing configuration
        **kwargs: Method-specific parameters
        
    Returns:
        Configured crime weighter
    """
    try:
        method = CrimeWeightingMethod(method_name.lower())
        return CrimeWeightingFactory.create_weighter(method, config, **kwargs)
    except ValueError:
        available = list(CrimeWeightingFactory.get_available_methods().keys())
        raise ValueError(f"Unknown method '{method_name}'. Available: {available}")


# Configuration presets for common scenarios

def get_consistent_weighter(config: Optional[RoutingConfig] = None) -> NetworkProximityWeighter:
    """
    Get a weighter optimized for consistent results.
    
    Recommended for production use where consistent results are critical.
    """
    return create_network_proximity_weighter(
        config=config,
        decay_function='exponential',
        influence_radius=150.0
    )


def get_smooth_weighter(config: Optional[RoutingConfig] = None) -> KDECrimeWeighter:
    """
    Get a weighter optimized for smooth crime surfaces.
    
    Recommended for visualization and research applications.
    """
    return create_kde_weighter(
        config=config,
        bandwidth=200.0,
        kernel='gaussian'
    )


def get_fast_weighter(config: Optional[RoutingConfig] = None) -> NetworkProximityWeighter:
    """
    Get a weighter optimized for speed.
    
    Recommended for real-time applications.
    """
    return create_network_proximity_weighter(
        config=config,
        decay_function='step',
        influence_radius=100.0
    ) 
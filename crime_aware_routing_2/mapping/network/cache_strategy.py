"""
Cache strategy management for memory-optimized cache loading.

This module provides utilities to manage cache loading strategy and track
memory optimization effectiveness.
"""

import logging
from typing import Tuple, Dict, Any, Optional
from .network_cache import get_network_cache
from .enhanced_graph_cache import get_enhanced_cache

logger = logging.getLogger(__name__)


class CacheStrategy:
    """Manages cache loading strategy and provides unified interface."""
    
    @staticmethod
    def get_active_cache_info() -> Dict[str, Any]:
        """
        Get information about the currently active cache.
        
        Returns:
            Dictionary with cache type, availability, and statistics
        """
        enhanced_cache = get_enhanced_cache()
        
        # Check enhanced cache first (memory-optimized primary)
        # Note: Cache loading happens only during startup - this is purely informational
        if enhanced_cache.enhanced_graph is not None:
            enhanced_edges = sum(1 for _, _, data in enhanced_cache.enhanced_graph.edges(data=True) 
                                if 'crime_score' in data)
            
            return {
                'type': 'enhanced',
                'available': True,
                'nodes': len(enhanced_cache.enhanced_graph.nodes),
                'edges': len(enhanced_cache.enhanced_graph.edges),
                'radius_km': enhanced_cache.cache_radius / 1000.0 if enhanced_cache.cache_radius else 30.0,
                'enhanced_edges': enhanced_edges,
                'memory_optimized': True,
                'source': 'enhanced_cache'
            }
        
        # Fallback to network cache
        network_cache = get_network_cache()
        if network_cache.large_graph:
            return {
                'type': 'network',
                'available': True, 
                'nodes': len(network_cache.large_graph.nodes),
                'edges': len(network_cache.large_graph.edges),
                'radius_km': network_cache.cache_radius / 1000.0 if network_cache.cache_radius else 30.0,
                'enhanced_edges': 0,
                'memory_optimized': False,
                'source': 'network_cache'
            }
        
        return {
            'type': 'none',
            'available': False,
            'nodes': 0,
            'edges': 0,
            'radius_km': 0,
            'enhanced_edges': 0,
            'memory_optimized': False,
            'source': 'none'
        }
    
    @staticmethod
    def is_route_supported(start_coords: Tuple[float, float], 
                          end_coords: Tuple[float, float]) -> bool:
        """
        Check if route is supported by current cache strategy.
        
        Args:
            start_coords: (lat, lon) of start point
            end_coords: (lat, lon) of end point
            
        Returns:
            True if route is supported by active cache
        """
        enhanced_cache = get_enhanced_cache()
        
        # Check enhanced cache first (memory-optimized)
        # Note: Cache loading happens only during startup - this is purely checking loaded state
        if enhanced_cache.enhanced_graph is not None:
            return enhanced_cache.is_route_in_cache(start_coords, end_coords)
        
        # Fallback to network cache
        network_cache = get_network_cache()
        if network_cache.large_graph:
            return network_cache.is_route_in_cache(start_coords, end_coords)
        
        return False  # No cache available
    
    @staticmethod
    def get_memory_usage_info() -> Dict[str, Any]:
        """
        Get information about memory usage by cache strategy.
        
        Returns:
            Dictionary with memory usage information and optimization status
        """
        enhanced_cache = get_enhanced_cache()
        network_cache = get_network_cache()
        
        info = {
            'enhanced_cache_loaded': enhanced_cache.enhanced_graph is not None,
            'network_cache_loaded': network_cache.large_graph is not None,
            'memory_optimized': False,
            'estimated_memory_gb': 0
        }
        
        if info['enhanced_cache_loaded'] and not info['network_cache_loaded']:
            # Optimal: Enhanced cache only
            info['memory_optimized'] = True
            info['estimated_memory_gb'] = 1.26
            info['strategy'] = 'enhanced_only'
            info['description'] = 'Memory optimized: Enhanced cache only'
        elif info['enhanced_cache_loaded'] and info['network_cache_loaded']:
            # Sub-optimal: Both loaded (old behavior)
            info['memory_optimized'] = False
            info['estimated_memory_gb'] = 2.37
            info['strategy'] = 'both_loaded'
            info['description'] = 'Both caches loaded (not optimized)'
        elif info['network_cache_loaded']:
            # Fallback: Network cache only
            info['memory_optimized'] = True
            info['estimated_memory_gb'] = 1.11
            info['strategy'] = 'network_only'
            info['description'] = 'Fallback: Network cache only'
        else:
            # No cache loaded
            info['strategy'] = 'none'
            info['description'] = 'No cache loaded'
        
        return info
    
    @staticmethod
    def get_optimization_status() -> Dict[str, Any]:
        """
        Get detailed optimization status for monitoring and debugging.
        
        Returns:
            Dictionary with optimization effectiveness and recommendations
        """
        cache_info = CacheStrategy.get_active_cache_info()
        memory_info = CacheStrategy.get_memory_usage_info()
        
        return {
            'active_cache': cache_info,
            'memory_usage': memory_info,
            'optimization_effective': memory_info['memory_optimized'],
            'estimated_savings_gb': 2.37 - memory_info['estimated_memory_gb'] if memory_info['memory_optimized'] else 0,
            'recommendations': CacheStrategy._get_optimization_recommendations(memory_info)
        }
    
    @staticmethod
    def _get_optimization_recommendations(memory_info: Dict[str, Any]) -> list:
        """Get recommendations based on current cache strategy."""
        recommendations = []
        
        if memory_info['strategy'] == 'both_loaded':
            recommendations.append("Memory optimization not active - both caches loaded")
            recommendations.append("Consider restarting with optimized startup sequence")
        elif memory_info['strategy'] == 'network_only':
            recommendations.append("Enhanced cache not available - using network cache fallback")
            recommendations.append("Consider creating enhanced cache for better performance")
        elif memory_info['strategy'] == 'enhanced_only':
            recommendations.append("Memory optimization active - optimal configuration")
        elif memory_info['strategy'] == 'none':
            recommendations.append("No cache loaded - performance will be degraded")
            recommendations.append("Check cache initialization in startup sequence")
        
        return recommendations


def get_cache_strategy() -> CacheStrategy:
    """Get the global cache strategy instance."""
    return CacheStrategy()

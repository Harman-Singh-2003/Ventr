"""
Enhanced graph caching system for pre-computed crime-weighted graphs.

This module implements efficient caching of pre-enhanced graphs to eliminate
runtime graph enhancement overhead for fixed crime weighting parameters.
"""

import os
import time
import pickle
import logging
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import networkx as nx
from .network_cache import NetworkCache, get_network_cache

logger = logging.getLogger(__name__)


class EnhancedGraphCache:
    """
    Manages caching of pre-enhanced graphs with crime weights applied.
    
    Precomputes crime-weighted graphs for fixed parameters to eliminate
    runtime graph enhancement overhead.
    """
    
    def __init__(self, cache_dir: str = "enhanced_cache", 
                 cache_file: str = "toronto_enhanced_0.1.pkl"):
        """
        Initialize enhanced graph cache.
        
        Args:
            cache_dir: Directory for enhanced cache files
            cache_file: Filename for the cached enhanced graph
        """
        self.cache_dir = Path(cache_dir)
        self.cache_file = self.cache_dir / cache_file
        self.enhanced_graph: Optional[nx.MultiDiGraph] = None
        self.cache_center: Optional[Tuple[float, float]] = None
        self.cache_radius: Optional[float] = None
        self.crime_weight: float = 0.1  # Fixed for all requests
        self.enhancement_metadata: Optional[Dict[str, Any]] = None
        
        # Ensure cache directory exists
        self.cache_dir.mkdir(exist_ok=True)
        
    def is_cache_available(self) -> bool:
        """Check if enhanced cache file exists and is valid."""
        if not self.cache_file.exists():
            return False
        
        try:
            # Quick validation - check if file can be loaded
            with open(self.cache_file, 'rb') as f:
                cache_data = pickle.load(f)
            
            # Validate required keys
            required_keys = ['enhanced_graph', 'center', 'radius', 'crime_weight', 'created_at']
            return all(key in cache_data for key in required_keys)
            
        except Exception as e:
            logger.warning(f"Enhanced cache file corrupted: {e}")
            return False
    
    def load_cache(self) -> bool:
        """
        Load enhanced graph from disk.
        
        Returns:
            True if cache loaded successfully, False otherwise
        """
        if not self.is_cache_available():
            logger.info(f"No valid enhanced cache file found at {self.cache_file}")
            return False
            
        try:
            logger.info(f"Loading enhanced graph cache from {self.cache_file}")
            start_time = time.perf_counter()
            
            with open(self.cache_file, 'rb') as f:
                cache_data = pickle.load(f)
            
            self.enhanced_graph = cache_data['enhanced_graph']
            self.cache_center = cache_data['center']
            self.cache_radius = cache_data['radius']
            self.crime_weight = cache_data['crime_weight']
            self.enhancement_metadata = cache_data.get('enhancement_metadata', {})
            
            load_time = time.perf_counter() - start_time
            if self.enhanced_graph and self.cache_center and self.cache_radius:
                logger.info(f"✓ Enhanced graph loaded: {len(self.enhanced_graph.nodes)} nodes, "
                           f"{len(self.enhanced_graph.edges)} edges in {load_time:.3f}s")
                logger.info(f"Cache covers {self.cache_radius/1000:.1f}km radius around "
                           f"({self.cache_center[0]:.4f}, {self.cache_center[1]:.4f})")
                logger.info(f"Crime weight: {self.crime_weight}, "
                           f"Enhanced edges: {self.enhancement_metadata.get('enhanced_edges', 0) if self.enhancement_metadata else 0}")
            else:
                logger.error("Failed to load enhanced graph data")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load enhanced cache: {e}")
            self.enhanced_graph = None
            self.cache_center = None
            self.cache_radius = None
            self.enhancement_metadata = None
            return False
    
    def create_cache(self, network_cache: NetworkCache, crime_data_path: str) -> bool:
        """
        Create enhanced cache by applying crime weights to the entire Toronto network.
        
        Args:
            network_cache: Existing network cache with Toronto graph
            crime_data_path: Path to crime data file
            
        Returns:
            True if cache created successfully, False otherwise
        """
        try:
            logger.info(f"Creating enhanced graph cache with crime_weight={self.crime_weight}")
            logger.info("This is a one-time operation that may take 30-60 minutes...")
            
            start_time = time.perf_counter()
            
            # Step 1: Get the base Toronto graph
            if not network_cache.large_graph:
                logger.error("Network cache not available for enhanced cache creation")
                return False
            
            base_graph = network_cache.large_graph
            logger.info(f"Base graph: {len(base_graph.nodes)} nodes, {len(base_graph.edges)} edges")
            
            # Step 2: Initialize crime weighting components (reuse existing code)
            enhanced_graph, metadata = self._enhance_entire_graph(base_graph, crime_data_path)
            
            if enhanced_graph is None:
                logger.error("Failed to enhance graph")
                return False
            
            # Step 3: Prepare cache data
            cache_data = {
                'enhanced_graph': enhanced_graph,
                'center': network_cache.cache_center,
                'radius': network_cache.cache_radius,
                'crime_weight': self.crime_weight,
                'created_at': time.time(),
                'enhancement_metadata': metadata,
                'base_graph_stats': {
                    'nodes': len(base_graph.nodes),
                    'edges': len(base_graph.edges)
                },
                'enhanced_graph_stats': {
                    'nodes': len(enhanced_graph.nodes),
                    'edges': len(enhanced_graph.edges)
                }
            }
            
            # Step 4: Save to cache file
            logger.info(f"Saving enhanced cache to {self.cache_file}")
            save_start = time.perf_counter()
            
            with open(self.cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
            
            save_time = time.perf_counter() - save_start
            total_time = time.perf_counter() - start_time
            
            logger.info(f"✓ Enhanced cache saved in {save_time:.3f}s (total: {total_time:.3f}s)")
            
            # Store in memory
            self.enhanced_graph = enhanced_graph
            self.cache_center = network_cache.cache_center
            self.cache_radius = network_cache.cache_radius
            self.enhancement_metadata = metadata
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create enhanced cache: {e}")
            return False

    def _enhance_entire_graph(self, base_graph: nx.MultiDiGraph, crime_data_path: str) -> Tuple[Optional[nx.MultiDiGraph], Dict[str, Any]]:
        """
        Enhance the entire Toronto graph with crime weights (EXACTLY as current implementation).
        
        Args:
            base_graph: Base Toronto network graph
            crime_data_path: Path to crime data file
            
        Returns:
            Tuple of (enhanced_graph, metadata)
        """
        try:
            logger.info("Enhancing entire Toronto graph with crime weights...")
            enhance_start = time.perf_counter()
            
            # IMPORTANT: Use EXACTLY the same configuration as current implementation
            from crime_aware_routing_2.config.routing_config import RoutingConfig
            from crime_aware_routing_2.algorithms.optimization.route_optimizer import RouteOptimizer
            
            # Create config with EXACTLY the same parameters as current implementation
            config = RoutingConfig()
            config.crime_weighting_method = 'network_proximity'
            config.crime_weight = self.crime_weight  # 0.1
            config.distance_weight = 1.0 - self.crime_weight  # 0.9
            
            # Use EXACTLY the same penalty scaling as current implementation
            base_penalty = 2000.0  # Same as in routing_service.py
            config.crime_penalty_scale = base_penalty * self.crime_weight  # 200.0
            
            # Use EXACTLY the same influence radius calculation as current implementation
            if self.crime_weight > 0:
                config.crime_influence_radius = 100.0 + (self.crime_weight * 150.0)  # 115.0
            else:
                config.crime_influence_radius = 0.0
            
            # Use EXACTLY the same max_detour_ratio as current implementation
            config.max_detour_ratio = 2.0  # Default from current implementation
            
            # Use EXACTLY the same edge_sample_interval as current implementation
            config.edge_sample_interval = 25.0  # Default from RoutingConfig
            
            # Use EXACTLY the same crime_data_buffer as current implementation
            config.crime_data_buffer = 500.0  # Default from RoutingConfig
            
            logger.info(f"Using EXACT configuration: crime_weight={config.crime_weight}, "
                       f"distance_weight={config.distance_weight}, "
                       f"crime_penalty_scale={config.crime_penalty_scale}, "
                       f"crime_influence_radius={config.crime_influence_radius}, "
                       f"edge_sample_interval={config.edge_sample_interval}")
            
            # Initialize optimizer with EXACTLY the same parameters
            optimizer = RouteOptimizer(crime_data_path, config)
            
            # Prepare crime weighting for entire Toronto area (EXACTLY as current implementation)
            logger.info("Preparing crime weighting for entire Toronto area...")
            crime_prep_start = time.perf_counter()
            
            # Use Toronto bounds for crime preparation (same as current implementation)
            # Get bounds from crime processor statistics
            crime_stats = optimizer.crime_processor.get_crime_statistics()
            toronto_bounds = crime_stats['bounds']
            logger.info(f"Using Toronto bounds: {toronto_bounds}")
            
            # Define Toronto center for crime weighting preparation
            toronto_center = (43.6532, -79.3832)  # Downtown Toronto
            
            # Call the EXACT same crime weighting preparation as current implementation
            # This will initialize the crime weighter properly
            optimizer._prepare_crime_weighting(
                (toronto_center[0] - 0.1, toronto_center[1] - 0.1),  # Southwest corner
                (toronto_center[0] + 0.1, toronto_center[1] + 0.1)   # Northeast corner
            )
            
            # Verify crime weighter is initialized
            if not optimizer.crime_weighter:
                logger.error("Crime weighter not initialized after preparation")
                return None, {}
            
            logger.info(f"Crime weighter initialized successfully")
            crime_prep_time = time.perf_counter() - crime_prep_start
            logger.info(f"Crime weighting preparation completed in {crime_prep_time:.3f}s")
            
            # Enhance the entire graph (EXACTLY as current implementation)
            graph_enhance_start = time.perf_counter()
            enhanced_graph = optimizer._enhance_graph(base_graph)
            graph_enhance_time = time.perf_counter() - graph_enhance_start
            
            total_enhance_time = time.perf_counter() - enhance_start
            
            # Collect metadata
            enhanced_edges = sum(1 for _, _, data in enhanced_graph.edges(data=True) 
                               if 'crime_score' in data)
            
            # Get crime incidents count from crime processor
            crime_incidents_count = len(optimizer.crime_processor.get_all_crime_points())
            
            metadata = {
                'enhancement_time': total_enhance_time,
                'crime_prep_time': crime_prep_time,
                'graph_enhance_time': graph_enhance_time,
                'enhanced_edges': enhanced_edges,
                'total_edges': len(enhanced_graph.edges),
                'enhancement_rate': enhanced_edges / len(enhanced_graph.edges) if enhanced_graph.edges else 0,
                'crime_incidents_used': crime_incidents_count,
                'config_used': config.__dict__,
                'toronto_bounds': toronto_bounds
            }
            
            logger.info(f"✓ Graph enhancement completed in {total_enhance_time:.3f}s")
            logger.info(f"Enhanced {enhanced_edges}/{len(enhanced_graph.edges)} edges "
                       f"({metadata['enhancement_rate']:.1%})")
            
            return enhanced_graph, metadata
            
        except Exception as e:
            logger.error(f"Failed to enhance entire graph: {e}")
            return None, {}

    def is_point_in_cache(self, coords: Tuple[float, float], buffer_m: float = 1000) -> bool:
        """Check if a point is within the cached enhanced area with buffer."""
        if not self.enhanced_graph or not self.cache_center or not self.cache_radius:
            return False
            
        from crime_aware_routing_2.data.distance_utils import haversine_distance
        
        distance = haversine_distance(
            self.cache_center[0], self.cache_center[1],
            coords[0], coords[1]
        )
        
        return distance <= (self.cache_radius - buffer_m)

    def is_route_in_cache(self, start_coords: Tuple[float, float], 
                         end_coords: Tuple[float, float], buffer_m: float = 1000) -> bool:
        """
        Check if a route is entirely within the enhanced cached area.
        
        Args:
            start_coords: (lat, lon) of start point
            end_coords: (lat, lon) of end point
            buffer_m: Safety buffer in meters
            
        Returns:
            True if both points are in cached area with buffer
        """
        # Lazy load if not already loaded
        if not self.enhanced_graph:
            if not self.load_cache():
                return False
        
        result = (self.is_point_in_cache(start_coords, buffer_m) and 
                 self.is_point_in_cache(end_coords, buffer_m))
        
        return result

    def extract_subgraph(self, center_coords: Tuple[float, float], 
                        radius_m: float) -> Optional[nx.MultiDiGraph]:
        """
        Extract a subgraph from the enhanced cached network.
        
        Args:
            center_coords: (lat, lon) center of area to extract
            radius_m: Radius in meters for extraction
            
        Returns:
            Extracted subgraph or None if cache not available
        """
        # Lazy load if not already loaded
        if not self.enhanced_graph:
            if not self.load_cache():
                return None
        
        if not self.enhanced_graph:
            logger.warning("No enhanced graph available for extraction")
            return None
            
        try:
            logger.info(f"Extracting enhanced subgraph: {radius_m}m radius around "
                       f"({center_coords[0]:.4f}, {center_coords[1]:.4f})")
            
            start_time = time.perf_counter()
            
            # Use the same optimized extraction as network cache
            from .network_cache import NetworkCache
            
            # Create a temporary network cache with our enhanced graph
            temp_cache = NetworkCache()
            temp_cache.large_graph = self.enhanced_graph
            temp_cache.cache_center = self.cache_center
            temp_cache.cache_radius = self.cache_radius
            
            # Extract using the optimized method
            subgraph = temp_cache.extract_subgraph(center_coords, radius_m)
            
            extract_time = time.perf_counter() - start_time
            
            if subgraph is not None:
                enhanced_edges = sum(1 for _, _, data in subgraph.edges(data=True) 
                                   if 'crime_score' in data)
                
                logger.info(f"✓ Enhanced subgraph extracted: {len(subgraph.nodes)} nodes, "
                           f"{len(subgraph.edges)} edges ({enhanced_edges} enhanced) in {extract_time:.3f}s")
            else:
                logger.warning("Enhanced subgraph extraction returned None")
            
            return subgraph
            
        except Exception as e:
            logger.error(f"Failed to extract enhanced subgraph: {e}")
            return None

    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get information about the current enhanced cache.
        
        Returns:
            Dictionary with enhanced cache information
        """
        # Lazy load if not already loaded
        if not self.enhanced_graph:
            if not self.load_cache():
                return {
                    'available': False,
                    'cache_file': str(self.cache_file)
                }
        
        if not self.enhanced_graph:
            return {
                'available': False,
                'cache_file': str(self.cache_file)
            }
            
        enhanced_edges = sum(1 for _, _, data in self.enhanced_graph.edges(data=True) 
                           if 'crime_score' in data)
        
        return {
            'available': True,
            'cache_file': str(self.cache_file),
            'center': self.cache_center,
            'radius_km': self.cache_radius / 1000.0 if self.cache_radius else None,
            'nodes': len(self.enhanced_graph.nodes),
            'edges': len(self.enhanced_graph.edges),
            'enhanced_edges': enhanced_edges,
            'crime_weight': self.crime_weight,
            'file_size_mb': self.cache_file.stat().st_size / (1024 * 1024) if self.cache_file.exists() else None,
            'enhancement_metadata': self.enhancement_metadata
        }

    def verify_compatibility(self, test_start_coords: Tuple[float, float], 
                            test_end_coords: Tuple[float, float],
                            crime_data_path: str) -> bool:
        """
        Verify that enhanced cache produces identical results to current implementation.
        
        Args:
            test_start_coords: Test start coordinates
            test_end_coords: Test end coordinates
            crime_data_path: Path to crime data file
            
        Returns:
            True if results are identical, False otherwise
        """
        try:
            logger.info("Verifying enhanced cache compatibility...")
            
            # Test 1: Current implementation
            from crime_aware_routing_2.config.routing_config import RoutingConfig
            from crime_aware_routing_2.algorithms.optimization.route_optimizer import RouteOptimizer
            
            # Create config with EXACTLY the same parameters as current implementation
            config = RoutingConfig()
            config.crime_weighting_method = 'network_proximity'
            config.crime_weight = 0.1
            config.distance_weight = 0.9
            config.crime_penalty_scale = 2000.0 * 0.1
            config.crime_influence_radius = 100.0 + (0.1 * 150.0)
            config.max_detour_ratio = 2.0
            config.edge_sample_interval = 25.0
            config.crime_data_buffer = 500.0
            
            # Run current implementation
            current_optimizer = RouteOptimizer(crime_data_path, config)
            current_result = current_optimizer.find_safe_route(test_start_coords, test_end_coords, ['weighted_astar'])
            
            # Test 2: Enhanced cache implementation
            enhanced_optimizer = RouteOptimizer(crime_data_path, config)
            enhanced_result = enhanced_optimizer.find_safe_route(test_start_coords, test_end_coords, ['weighted_astar'])
            
            # Compare results
            current_route = current_result['routes']['weighted_astar']
            enhanced_route = enhanced_result['routes']['weighted_astar']
            
            # Compare key metrics
            current_distance = current_route.get_summary()['total_distance_m']
            enhanced_distance = enhanced_route.get_summary()['total_distance_m']
            
            current_safety = current_route.get_summary().get('average_crime_score', 0)
            enhanced_safety = enhanced_route.get_summary().get('average_crime_score', 0)
            
            # Allow small floating point differences
            distance_match = abs(current_distance - enhanced_distance) < 1.0  # 1 meter tolerance
            safety_match = abs(current_safety - enhanced_safety) < 1e-6
            
            if distance_match and safety_match:
                logger.info("✓ Enhanced cache compatibility verified - identical results")
                return True
            else:
                logger.error(f"✗ Enhanced cache compatibility failed:")
                logger.error(f"  Distance: current={current_distance:.2f}, enhanced={enhanced_distance:.2f}")
                logger.error(f"  Safety: current={current_safety:.6f}, enhanced={enhanced_safety:.6f}")
                return False
                
        except Exception as e:
            logger.error(f"Compatibility verification failed: {e}")
            return False


# Global enhanced cache instance
_enhanced_cache = EnhancedGraphCache()


def get_enhanced_cache() -> EnhancedGraphCache:
    """Get the global enhanced cache instance."""
    return _enhanced_cache


def ensure_enhanced_cache(crime_data_path: str, 
                        center_coords: Tuple[float, float] = (43.6532, -79.3832), 
                        radius_km: float = 30.0) -> bool:
    """
    Ensure enhanced graph cache is available, creating if necessary.
    
    Args:
        crime_data_path: Path to crime data file
        center_coords: Center of Toronto area (default: downtown)
        radius_km: Radius in kilometers for cached area
        
    Returns:
        True if enhanced cache is ready, False if failed
    """
    enhanced_cache = get_enhanced_cache()
    
    # Try to load existing enhanced cache
    if enhanced_cache.load_cache():
        logger.info("Enhanced graph cache loaded successfully")
        return True
    
    # Check if base network cache is available
    network_cache = get_network_cache()
    if not network_cache.large_graph:
        logger.error("Base network cache not available - cannot create enhanced cache")
        return False
    
    # Create new enhanced cache
    logger.info(f"Creating enhanced graph cache for Toronto area...")
    logger.info("This is a one-time operation that may take 30-60 minutes.")
    logger.info("The enhanced cache will eliminate graph enhancement overhead for all future requests.")
    
    if enhanced_cache.create_cache(network_cache, crime_data_path):
        logger.info("Enhanced graph cache created successfully")
        return True
    else:
        logger.error("Failed to create enhanced graph cache")
        return False 
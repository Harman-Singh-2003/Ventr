"""
Pydantic schemas for the crime-aware routing API.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from geojson import Feature, FeatureCollection


class LocationRequest(BaseModel):
    """Request model for a single location."""
    latitude: float = Field(..., ge=-90, le=90, description="Latitude coordinate")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude coordinate")
    
    @validator('latitude')
    def validate_toronto_latitude(cls, v):
        """Validate latitude is within reasonable Toronto bounds."""
        if not (43.0 <= v <= 44.5):
            raise ValueError('Latitude must be within Toronto area (43.0 to 44.5)')
        return v
    
    @validator('longitude') 
    def validate_toronto_longitude(cls, v):
        """Validate longitude is within reasonable Toronto bounds."""
        if not (-80.5 <= v <= -78.5):
            raise ValueError('Longitude must be within Toronto area (-80.5 to -78.5)')
        return v


class RouteRequest(BaseModel):
    """Request model for route calculation."""
    start: LocationRequest = Field(..., description="Starting location")
    destination: LocationRequest = Field(..., description="Destination location")
    route_type: str = Field(default="crime_aware", description="Type of route: 'shortest', 'crime_aware', or 'safest'")
    distance_weight: float = Field(default=0.7, ge=0.0, le=1.0, description="Weight for distance component (0-1)")
    crime_weight: float = Field(default=0.3, ge=0.0, le=1.0, description="Weight for crime component (0-1)")
    max_detour_factor: float = Field(default=1.5, ge=1.0, le=3.0, description="Maximum detour factor relative to shortest path")
    
    @validator('crime_weight')
    def validate_weights_sum(cls, v, values):
        """Ensure distance_weight + crime_weight = 1.0"""
        if 'distance_weight' in values:
            if abs(values['distance_weight'] + v - 1.0) > 1e-6:
                raise ValueError('distance_weight + crime_weight must equal 1.0')
        return v


class RouteStats(BaseModel):
    """Statistics about a calculated route."""
    total_distance_m: float = Field(..., description="Total route distance in meters")
    total_time_s: float = Field(..., description="Estimated travel time in seconds")
    crime_incidents_nearby: int = Field(..., description="Number of crime incidents near the route")
    safety_score: float = Field(..., ge=0.0, le=1.0, description="Safety score (1.0 = safest)")
    detour_factor: float = Field(..., description="Detour factor compared to shortest path")


class RouteResponse(BaseModel):
    """Response model for route calculation."""
    success: bool = Field(..., description="Whether the route calculation was successful")
    message: str = Field(..., description="Status message")
    route_geojson: Optional[Dict[str, Any]] = Field(default=None, description="Route as GeoJSON FeatureCollection")
    route_stats: Optional[RouteStats] = Field(default=None, description="Route statistics")
    shortest_path_stats: Optional[RouteStats] = Field(default=None, description="Shortest path statistics for comparison")
    enhanced_cache_used: Optional[bool] = Field(default=None, description="Whether enhanced cache was used for this calculation")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    crime_data_loaded: bool = Field(..., description="Whether crime data is loaded")
    crime_incidents_count: int = Field(..., description="Number of crime incidents loaded")
    network_cache_available: bool = Field(..., description="Whether network cache is available")
    cache_coverage_km: float = Field(..., description="Network cache coverage radius in kilometers")
    enhanced_cache_available: bool = Field(..., description="Whether enhanced graph cache is available")
    enhanced_cache_enhanced_edges: int = Field(..., description="Number of enhanced edges in cache")
    
    # NEW FIELDS for memory optimization tracking
    active_cache_strategy: str = Field(..., description="Active cache strategy: enhanced, network, or none")
    memory_optimized: bool = Field(..., description="Whether memory optimization is active")
    estimated_memory_usage_gb: float = Field(..., description="Estimated memory usage in GB")


class MultipleRouteRequest(BaseModel):
    """Request model for calculating multiple route types simultaneously."""
    start: LocationRequest = Field(..., description="Starting location")
    destination: LocationRequest = Field(..., description="Destination location")
    include_shortest: bool = Field(default=True, description="Include shortest path route")
    include_safest: bool = Field(default=True, description="Include safest (crime-aware) route")
    crime_weight_safest: float = Field(default=0.7, ge=0.0, le=1.0, description="Crime weight for safest route (0-1)")
    max_detour_factor: float = Field(default=2.0, ge=1.0, le=3.0, description="Maximum detour factor for safest route")
    
    @validator('include_shortest', 'include_safest')
    def at_least_one_route(cls, v, values):
        """Ensure at least one route type is requested."""
        if 'include_shortest' in values:
            if not values['include_shortest'] and not v:
                raise ValueError('At least one route type must be requested')
        return v


class MultipleRouteResponse(BaseModel):
    """Response model for multiple route calculation."""
    success: bool = Field(..., description="Whether the route calculation was successful")
    message: str = Field(..., description="Status message")
    shortest_route: Optional[Dict[str, Any]] = Field(default=None, description="Shortest route data")
    shortest_stats: Optional[RouteStats] = Field(default=None, description="Shortest route statistics")
    safest_route: Optional[Dict[str, Any]] = Field(default=None, description="Safest route data")
    safest_stats: Optional[RouteStats] = Field(default=None, description="Safest route statistics")
    comparison_stats: Optional[Dict[str, Any]] = Field(default=None, description="Comparison statistics between routes")
    enhanced_cache_used: Optional[bool] = Field(default=None, description="Whether enhanced cache was used for this calculation")


class ErrorResponse(BaseModel):
    """Error response model."""
    success: bool = Field(False, description="Always false for error responses")
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Detailed error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
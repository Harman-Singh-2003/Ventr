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


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    crime_data_loaded: bool = Field(..., description="Whether crime data is loaded")
    crime_incidents_count: int = Field(..., description="Number of crime incidents loaded")


class ErrorResponse(BaseModel):
    """Error response model."""
    success: bool = Field(False, description="Always false for error responses")
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Detailed error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details") 
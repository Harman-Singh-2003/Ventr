# Multiple Routes API Implementation

## Overview

This implementation adds a new endpoint `/api/routing/calculate-multiple` that efficiently calculates both shortest and safest routes in a single operation. This optimization eliminates the redundant work of extracting subgraphs and enhancing graphs multiple times when both route types are needed.

## Key Benefits

1. **Performance Optimization**: Single network extraction and graph enhancement instead of multiple operations
2. **Reduced API Calls**: Get both routes in one request instead of two separate calls
3. **Comparison Data**: Automatic calculation of route comparison statistics
4. **Resource Efficiency**: Lower CPU and memory usage for multiple route scenarios

## Implementation Details

### New API Endpoint

**POST `/api/routing/calculate-multiple`**

Calculates both shortest and safest routes efficiently in one operation.

#### Request Schema

```json
{
    "start": {
        "latitude": 43.6426,
        "longitude": -79.3871
    },
    "destination": {
        "latitude": 43.6452,
        "longitude": -79.3806
    },
    "include_shortest": true,
    "include_safest": true,
    "crime_weight_safest": 0.7,
    "max_detour_factor": 2.0
}
```

#### Response Schema

```json
{
    "success": true,
    "message": "Multiple routes calculated successfully",
    "shortest_route": {
        "type": "FeatureCollection",
        "features": [...]
    },
    "shortest_stats": {
        "total_distance_m": 1250.5,
        "total_time_s": 900,
        "crime_incidents_nearby": 15,
        "safety_score": 0.75,
        "detour_factor": 1.0
    },
    "safest_route": {
        "type": "FeatureCollection", 
        "features": [...]
    },
    "safest_stats": {
        "total_distance_m": 1450.8,
        "total_time_s": 1044,
        "crime_incidents_nearby": 8,
        "safety_score": 0.92,
        "detour_factor": 1.16
    },
    "comparison_stats": {
        "distance_difference_m": 200.3,
        "distance_difference_percent": 16.0,
        "time_difference_s": 144,
        "safety_improvement": 0.17,
        "crime_incidents_avoided": 7
    }
}
```

### Architecture Changes

#### 1. New Schemas (`api/schemas/routing.py`)

- **MultipleRouteRequest**: Request model for multiple route calculation
- **MultipleRouteResponse**: Response model with both routes and comparison data

#### 2. Enhanced Service (`api/services/routing_service.py`)

- **calculate_multiple_routes()**: Main method for efficient multi-route calculation
- **_convert_to_multiple_response()**: Converts optimizer results to API response format

#### 3. New Route Handler (`api/routes/routing.py`)

- **calculate_multiple_routes()**: FastAPI endpoint handler with proper error handling

### Performance Optimization Details

The key optimization is in the RouteOptimizer workflow:

**Before (Separate Calls)**:
```
Call 1 (Shortest):
├── Extract network subgraph
├── Process crime data  
├── Enhance graph (minimal)
└── Calculate shortest route

Call 2 (Safest):
├── Extract network subgraph (duplicate work)
├── Process crime data (duplicate work)
├── Enhance graph with crime weights
└── Calculate weighted route
```

**After (Single Call)**:
```
Single Call:
├── Extract network subgraph (once)
├── Process crime data (once)
├── Enhance graph with crime weights (once)
├── Calculate shortest route
└── Calculate weighted route
```

### Usage Examples

#### Basic Usage - Both Routes

```python
import httpx

request_data = {
    "start": {"latitude": 43.6426, "longitude": -79.3871},
    "destination": {"latitude": 43.6452, "longitude": -79.3806},
    "include_shortest": True,
    "include_safest": True,
    "crime_weight_safest": 0.7
}

response = httpx.post("http://localhost:8000/api/routing/calculate-multiple", json=request_data)
result = response.json()

if result["success"]:
    print(f"Shortest route: {result['shortest_stats']['total_distance_m']}m")
    print(f"Safest route: {result['safest_stats']['total_distance_m']}m")
    print(f"Safety improvement: {result['comparison_stats']['safety_improvement']}")
```

#### Safest Route Only

```python
request_data = {
    "start": {"latitude": 43.6426, "longitude": -79.3871},
    "destination": {"latitude": 43.6452, "longitude": -79.3806},
    "include_shortest": False,
    "include_safest": True,
    "crime_weight_safest": 0.8,
    "max_detour_factor": 3.0
}
```

### Configuration Options

- **include_shortest**: Whether to calculate shortest path route (default: true)
- **include_safest**: Whether to calculate crime-aware safest route (default: true)
- **crime_weight_safest**: Crime weight for safest route (0-1, default: 0.7)
- **max_detour_factor**: Maximum detour factor for safest route (1-3, default: 2.0)

### Error Handling

The endpoint provides comprehensive error handling:

- **400 Bad Request**: Invalid coordinates or parameter validation errors
- **500 Internal Server Error**: Unexpected errors during route calculation
- **Success with Partial Results**: If one route fails, returns the successful route

### Comparison with Existing Endpoints

| Endpoint | Use Case | Performance | Response |
|----------|----------|-------------|----------|
| `/calculate` | Custom crime-aware route | Medium | Single route |
| `/shortest` | Fastest/shortest only | Fast | Single route |
| `/safest` | Safety-prioritized only | Medium | Single route |
| `/calculate-multiple` | Both routes needed | **Optimized** | Multiple routes + comparison |

### Migration Guide

**From separate calls:**
```python
# Old approach - 2 API calls
shortest = httpx.post("/api/routing/shortest", json=data)
safest = httpx.post("/api/routing/safest", json=data)

# New approach - 1 API call  
both = httpx.post("/api/routing/calculate-multiple", json=data)
```

### Testing

Run the test script to validate the implementation:

```bash
python test_multiple_routes.py
```

### Future Enhancements

1. **Route Caching**: Cache results for frequently requested route pairs
2. **Additional Algorithms**: Support for more routing algorithms in single call
3. **Batch Processing**: Multiple start/end pairs in single request
4. **Real-time Updates**: WebSocket support for live route updates

## Files Modified

1. `api/schemas/routing.py` - Added MultipleRouteRequest and MultipleRouteResponse schemas
2. `api/services/routing_service.py` - Added calculate_multiple_routes method
3. `api/routes/routing.py` - Added /calculate-multiple endpoint
4. `test_multiple_routes.py` - Test script for validation

This implementation provides a more efficient way to get both shortest and safest routes while maintaining backward compatibility with existing endpoints.

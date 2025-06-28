# Crime-Aware Routing API

A FastAPI-based REST API for calculating crime-aware routes in Toronto using real crime data and OpenStreetMap.

## Quick Start

### 1. Install Dependencies

Make sure you're in the virtual environment:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Run the API Server

```bash
# Simple start
python run_api.py

# Development mode with auto-reload
python run_api.py --reload

# Custom host/port
python run_api.py --host 127.0.0.1 --port 3000
```

### 3. Access the API

- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **API Info**: http://localhost:8000/api/routing/

## API Endpoints

### Health & Info

- `GET /health` - API health status
- `GET /api/routing/health` - Detailed service health with crime data status
- `GET /api/routing/` - API information and endpoint list

### Route Calculation

#### Main Endpoint
- `POST /api/routing/calculate` - Calculate crime-aware route with custom parameters

#### Convenience Endpoints
- `POST /api/routing/shortest` - Calculate shortest route (ignoring crime data)
- `POST /api/routing/safest` - Calculate safest route (prioritizing crime avoidance)

## Example Usage

### Calculate a Crime-Aware Route

```bash
curl -X POST "http://localhost:8000/api/routing/calculate" \
  -H "Content-Type: application/json" \
  -d '{
    "start": {
      "latitude": 43.6426,
      "longitude": -79.3871
    },
    "destination": {
      "latitude": 43.6452,
      "longitude": -79.3806
    },
    "route_type": "crime_aware",
    "distance_weight": 0.7,
    "crime_weight": 0.3,
    "max_detour_factor": 1.5
  }'
```

### Calculate Shortest Route

```bash
curl -X POST "http://localhost:8000/api/routing/shortest" \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 43.6426,
    "longitude": -79.3871
  }' \
  -d '{
    "latitude": 43.6452,
    "longitude": -79.3806
  }'
```

## Response Format

All route endpoints return a `RouteResponse` with:

```json
{
  "success": true,
  "message": "Route calculated successfully",
  "route_geojson": {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "geometry": {
          "type": "LineString",
          "coordinates": [[-79.3871, 43.6426], [-79.3806, 43.6452]]
        },
        "properties": {
          "algorithm": "weighted_astar",
          "total_distance_m": 1234.5,
          "node_count": 15
        }
      }
    ]
  },
  "route_stats": {
    "total_distance_m": 1234.5,
    "total_time_s": 890,
    "crime_incidents_nearby": 3,
    "safety_score": 0.85,
    "detour_factor": 1.1
  },
  "shortest_path_stats": {
    "total_distance_m": 1100.0,
    "total_time_s": 792,
    "crime_incidents_nearby": 5,
    "safety_score": 0.65,
    "detour_factor": 1.0
  }
}
```

## Route Types

### `crime_aware` (default)
Balanced route that considers both distance and crime data. Returns both the crime-aware route and shortest path for comparison.

### `shortest`
Traditional shortest path routing that ignores crime data. Fastest calculation.

### `safest`
Prioritizes crime avoidance over distance. May result in longer routes but avoids high-crime areas.

## Parameters

### Location Parameters
- `latitude`: Float between 43.0 and 44.5 (Toronto area)
- `longitude`: Float between -80.5 and -78.5 (Toronto area)

### Route Calculation Parameters
- `distance_weight`: Float 0-1, importance of route distance (default: 0.7)
- `crime_weight`: Float 0-1, importance of crime avoidance (default: 0.3)
- `max_detour_factor`: Float 1.0-3.0, maximum allowed detour relative to shortest path (default: 1.5)

Note: `distance_weight + crime_weight` must equal 1.0

## Coverage Area

Currently supports routing within Toronto, Ontario, Canada:
- **Latitude**: 43.0° to 44.5° N
- **Longitude**: 80.5° to 78.5° W

## Data Sources

- **Crime Data**: Toronto Police Service Assault Open Data (5,583+ incidents)
- **Street Network**: OpenStreetMap via OSMnx
- **Area Coverage**: Toronto metropolitan area

## Development

### Project Structure

```
api/
├── __init__.py
├── main.py              # FastAPI application
├── routes/
│   ├── __init__.py
│   └── routing.py       # API endpoints
├── services/
│   ├── __init__.py
│   └── routing_service.py  # Business logic
└── schemas/
    ├── __init__.py
    └── routing.py       # Pydantic models
```

### Running in Development Mode

```bash
# Auto-reload on file changes
python run_api.py --reload --log-level debug

# Or directly with uvicorn
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### Testing

Visit http://localhost:8000/docs for interactive API documentation and testing interface.

## Error Handling

The API returns consistent error responses:

```json
{
  "success": false,
  "error": "validation_error",
  "message": "Request validation failed",
  "details": [...]
}
```

Common error types:
- `validation_error`: Invalid request parameters
- `service_unavailable`: Crime data not loaded
- `route_calculation_failed`: No valid route found
- `internal_server_error`: Unexpected server error 
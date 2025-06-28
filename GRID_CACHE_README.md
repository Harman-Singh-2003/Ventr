# Grid-Based Caching System

This document describes the smart grid-based caching system implemented for the crime-aware routing service. This system dramatically improves performance by predownloading and caching map data in a spatial grid structure.

## Overview

The grid-based caching system transforms the routing service from **reactive** (download-per-request) to **proactive** (predownloaded grid), providing:

- **Sub-second routing** from cached data
- **Predictable performance** regardless of OSM server load  
- **Complete Toronto coverage** with ~150-200 grid tiles
- **Intelligent spatial indexing** using geohash

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────┐
│                   Grid Cache System                     │
├─────────────────────────────────────────────────────────┤
│ 1. GridCache              - Spatial indexing & storage  │
│ 2. CachedNetworkBuilder   - Network loading with cache  │
│ 3. CachedRouteOptimizer   - Drop-in optimizer replacement│
│ 4. Cache Manager CLI      - Management & predownload    │
└─────────────────────────────────────────────────────────┘
```

### Spatial Indexing Strategy

- **Geohash precision 6**: ~1.22km × 0.61km cells
- **Toronto coverage**: 150-200 tiles for complete area
- **Overlap handling**: Buffered boundaries ensure route continuity
- **SQLite metadata**: Fast spatial queries for tile lookup

## Quick Start

### 1. Install Dependencies

```bash
# Install geohash library (already in requirements.txt)
pip install python-geohash==0.8.5
```

### 2. Test the System

```bash
# Run comprehensive tests
python test_grid_cache.py

# Test cache management CLI
python crime_aware_routing/cache_manager.py --help
```

### 3. Predownload Cache (Recommended)

```bash
# Download complete Toronto cache (~150-200 tiles, ~300-750MB)
python crime_aware_routing/cache_manager.py predownload

# Monitor progress and check final statistics
python crime_aware_routing/cache_manager.py stats
```

### 4. Use Cached Routing

The caching system is automatically integrated into the API. Routes will now use cached data when available:

```python
# The API automatically uses CachedRouteOptimizer
# No code changes needed - it's a drop-in replacement
```

## Cache Management

### CLI Commands

```bash
# View cache statistics
python crime_aware_routing/cache_manager.py stats

# Predownload Toronto area cache
python crime_aware_routing/cache_manager.py predownload

# Force refresh existing cache
python crime_aware_routing/cache_manager.py predownload --force

# Test cache with sample routes
python crime_aware_routing/cache_manager.py test

# Clear old cache entries (>60 days)
python crime_aware_routing/cache_manager.py clear --older-than 60

# Clear all cache
python crime_aware_routing/cache_manager.py clear --all
```

### Cache Structure

```
crime_aware_routing/cache/
├── grid_cache.db          # SQLite metadata database
└── networks/              # Cached network files
    ├── f25dvk.graphml     # Geohash tile: Downtown Core
    ├── f25dvm.graphml     # Geohash tile: University Ave
    └── ...                # ~150-200 tiles for Toronto
```

## Performance Comparison

### Before (Reactive System)
- **Route calculation**: 3-15 seconds per request
- **Network download**: Required for every unique route area
- **Cache efficiency**: Only exact URL matches reused
- **Cold start**: Always downloads fresh data

### After (Grid-Based Cache)
- **Route calculation**: <1 second from cache
- **Network loading**: Instant from predownloaded tiles  
- **Cache efficiency**: Spatial coverage with overlap handling
- **Warm start**: Most routes use cached data

### Typical Performance Gains

| Route Type | Before (No Cache) | After (With Cache) | Improvement |
|------------|-------------------|-------------------|-------------|
| Downtown Core | 3.26s | <0.5s | **6-7x faster** |
| University Ave | 9.87s | <0.5s | **15-20x faster** |
| Cross-town | 8.30s | <0.5s | **15-20x faster** |

## Technical Details

### Geohash Spatial Indexing

The system uses **geohash precision 6** for optimal balance:

```python
# Precision 6 characteristics
Cell Size: ~1.22km × 0.61km
Toronto Coverage: ~150-200 tiles
Storage per tile: ~2-5MB
Total storage: ~300-750MB
```

### Database Schema

```sql
CREATE TABLE grid_cache (
    geohash TEXT PRIMARY KEY,           -- Spatial index key
    center_lat REAL NOT NULL,          -- Tile center coordinates
    center_lon REAL NOT NULL,
    bounds_north REAL NOT NULL,        -- Spatial bounds for queries
    bounds_south REAL NOT NULL,
    bounds_east REAL NOT NULL,
    bounds_west REAL NOT NULL,
    last_updated TEXT NOT NULL,        -- Freshness tracking
    node_count INTEGER,                -- Network statistics
    edge_count INTEGER,
    file_path TEXT NOT NULL,           -- GraphML file location
    download_radius REAL NOT NULL,     -- Download parameters
    created_at TEXT NOT NULL,
    file_size_bytes INTEGER DEFAULT 0
);
```

### Spatial Query Process

1. **Route Request**: User requests route from A to B
2. **Bounding Box**: Calculate route bbox with buffer
3. **Tile Lookup**: Find geohash tiles that intersect bbox
4. **Network Loading**: Load and merge cached networks
5. **Validation**: Ensure coverage of route endpoints
6. **Fallback**: Use original method if cache miss

## Integration Guide

### For API Usage (Automatic)

The caching system is automatically integrated. No code changes needed:

```python
# Before: Used RouteOptimizer
# After: Automatically uses CachedRouteOptimizer
# Same API, better performance
```

### For Direct Usage

```python
from crime_aware_routing.algorithms.cached_route_optimizer import CachedRouteOptimizer

# Initialize with caching enabled
optimizer = CachedRouteOptimizer(
    crime_data_path="crime_aware_routing/data/crime_data.geojson",
    cache_dir="crime_aware_routing/cache",
    cache_precision=6,
    enable_cache=True
)

# Find route (will use cache when available)
result = optimizer.find_safe_route(
    start_coords=(43.6426, -79.3871),
    end_coords=(43.6544, -79.3807),
    prefer_cache=True
)
```

### For Testing/Development

```python
# Disable cache for testing original behavior
optimizer = CachedRouteOptimizer(
    crime_data_path="...",
    enable_cache=False  # Forces fallback to original method
)

# Or prefer live downloads over cache
result = optimizer.find_safe_route(
    start_coords=(...),
    end_coords=(...),
    prefer_cache=False  # Will use original download method
)
```

## Monitoring & Maintenance

### Cache Statistics

```bash
$ python crime_aware_routing/cache_manager.py stats

Cache Statistics:
  Total tiles: 150
  Total nodes: 2,450,000
  Total edges: 6,890,000
  Total size: 342.1 MB
  Oldest data: 2024-01-15T10:30:00Z
  Newest data: 2024-01-15T12:45:00Z
```

### Cache Refresh Strategy

- **Weekly refresh**: For high-traffic areas
- **Monthly refresh**: For complete Toronto area
- **Selective refresh**: Only outdated tiles
- **Force refresh**: When OSM data significantly changes

```bash
# Refresh cache older than 30 days
python crime_aware_routing/cache_manager.py clear --older-than 30
python crime_aware_routing/cache_manager.py predownload
```

## Troubleshooting

### Common Issues

1. **"No cached networks found for route"**
   - Cache not predownloaded for the area
   - Run: `python crime_aware_routing/cache_manager.py predownload`

2. **"Cache disabled or not preferred"**
   - Cache intentionally disabled or route preferring live download
   - Check `enable_cache=True` and `prefer_cache=True`

3. **Slow performance despite cache**
   - Cache miss due to route outside cached area
   - System falls back to original method (expected behavior)

4. **High storage usage**
   - Complete Toronto cache: ~300-750MB (normal)
   - Clear old cache: `cache_manager.py clear --older-than 60`

### Performance Monitoring

```python
# Monitor cache hit/miss in logs
import logging
logging.basicConfig(level=logging.INFO)

# Look for these log messages:
# "✓ Using cached network data" (cache hit)
# "Using original network download method" (cache miss)
```

## Future Enhancements

- **Dynamic precision**: Adjust geohash precision based on area density
- **Multi-city support**: Extend beyond Toronto
- **Cache warming**: Proactive cache updates based on usage patterns
- **Compression**: Reduce storage requirements
- **Distributed cache**: Scale across multiple servers

## Technical References

- **Geohash Algorithm**: [Wikipedia](https://en.wikipedia.org/wiki/Geohash)
- **Spatial Indexing**: [PostGIS Documentation](https://postgis.net/docs/using_postgis_dbmanagement.html#spatial_indexes)
- **OSMnx Caching**: [OSMnx Documentation](https://osmnx.readthedocs.io/en/stable/)

---

**Built for the Crime-Aware Routing System**  
*Transforming reactive downloads into proactive grid-based caching* 
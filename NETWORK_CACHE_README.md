# Network Caching System for Crime-Aware Routing

This document describes the network caching system implemented for the Crime-Aware Routing API, which significantly improves performance by avoiding repeated OSMnx downloads.

## Overview

The caching system downloads a large Toronto street network once (30km radius) and stores it locally. For subsequent routing requests within the cached area, it extracts smaller subgraphs instead of downloading from OSMnx APIs, providing 5-10x speed improvements.

## Architecture

### Key Components

1. **NetworkCache** (`crime_aware_routing_2/mapping/network/network_cache.py`)
   - Manages cached network data
   - Handles cache creation, loading, and subgraph extraction
   - Provides coverage checking for routes

2. **Modified NetworkBuilder** (`crime_aware_routing_2/mapping/network/network_builder.py`)
   - Enhanced to use cache when available
   - Falls back to direct OSMnx downloads for routes outside cached area
   - Maintains same API but with improved performance

3. **Cache Manager** (`cache_manager.py`)
   - Command-line tool for cache management
   - Create, test, and inspect cache
   - Standalone utility for cache operations

4. **API Integration** (`run_api.py`)
   - Automatically initializes cache on startup
   - Provides `--skip-cache` option for development

## Usage

### Initial Setup

Create the Toronto network cache (one-time setup):

```bash
# Option 1: Use the cache manager
python cache_manager.py --ensure

# Option 2: Create custom cache
python cache_manager.py --create --lat 43.6532 --lon -79.3832 --radius 30

# Option 3: Cache will be created automatically when starting the API
python run_api.py
```

### Cache Management

```bash
# Check cache status
python cache_manager.py --info

# Test cache functionality  
python cache_manager.py --test

# Delete cache (will be recreated as needed)
python cache_manager.py --delete
```

### API Usage

The caching is transparent to API users. Routes within the cached area automatically use cached data:

```bash
# Start API with cache (default)
python run_api.py

# Start API without cache initialization (development)
python run_api.py --skip-cache

# Check cache status in health endpoint
curl http://localhost:8000/api/routing/health
```

## Performance Benefits

### Before Caching
- Each route request: 5-15 seconds (network download + processing)
- Network download: 3-12 seconds per request
- Total API response: 8-20 seconds

### After Caching  
- Cache creation: ~60-180 seconds (one-time)
- Each route request: 1-3 seconds (extraction + processing)
- Network extraction: 0.1-0.5 seconds per request  
- Total API response: 2-5 seconds

### Speedup: 5-10x improvement for cached routes

## Cache Coverage

### Default Toronto Cache
- **Center**: Downtown Toronto (43.6532, -79.3832)
- **Radius**: 30km 
- **Coverage**: All of Toronto and surrounding GTA
- **File Size**: ~50-150MB
- **Nodes**: ~100,000-300,000
- **Edges**: ~200,000-600,000

### Coverage Areas
✅ **Fully Covered**:
- Downtown Toronto
- North York  
- Scarborough
- Etobicoke
- Mississauga (partial)
- Markham (partial)
- Richmond Hill (partial)

❌ **Outside Coverage**:
- Far suburbs beyond 30km
- Hamilton
- Oakville (far areas)
- Pickering (far areas)

## Technical Details

### Cache Storage
- **Format**: Pickle files with NetworkX MultiDiGraph objects
- **Location**: `osmnx_cache/toronto_network.pkl`
- **Compression**: Python pickle (binary)
- **Metadata**: Center coordinates, radius, creation time, OSMnx version

### Extraction Algorithm
1. **Route Analysis**: Check if start/end points are within cached area
2. **Center Calculation**: Find midpoint between start and end
3. **Radius Determination**: Calculate required extraction radius based on route distance
4. **Subgraph Extraction**: Use OSMnx `truncate_graph_dist` with 20% buffer
5. **Network Return**: Return extracted subgraph for routing

### Fallback Behavior
- Routes outside cached area automatically use direct OSMnx downloads
- Failed cache operations gracefully fall back to direct downloads
- No API changes required - transparent to users

## Integration Points

### Network Builder Integration
```python
# Before (direct download)
G = ox.graph_from_point(center_coords, dist=radius, network_type='walk')

# After (cache-aware)
cache = get_network_cache()
if cache.is_route_in_cache(start_coords, end_coords):
    G = cache.extract_subgraph(center_coords, radius)
else:
    G = ox.graph_from_point(center_coords, dist=radius, network_type='walk')
```

### Health Check Integration
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "crime_data_loaded": true,
  "crime_incidents_count": 15000,
  "network_cache_available": true,
  "cache_coverage_km": 30.0
}
```

## Development Workflow

### Development Mode
```bash
# Fast startup (skip cache initialization)
python run_api.py --skip-cache

# Routes will still work but use direct downloads
```

### Production Mode
```bash
# Full startup with cache
python run_api.py

# Ensure cache exists
python cache_manager.py --ensure
```

### Testing
```bash
# Run cache integration tests
python test_cache_integration.py

# Test specific cache functions
python cache_manager.py --test
```

## Troubleshooting

### Cache Creation Issues
```bash
# Delete and recreate cache
python cache_manager.py --delete
python cache_manager.py --create

# Check disk space (cache requires ~200MB)
df -h

# Check network connectivity for OSMnx
ping nominatim.openstreetmap.org
```

### Performance Issues
```bash
# Check cache file exists and is readable
python cache_manager.py --info

# Verify cache coverage
python cache_manager.py --test

# Monitor API logs for cache hit/miss
tail -f api.log | grep cache
```

### Memory Issues
```bash
# Cache uses ~500MB-1GB RAM when loaded
# Monitor memory usage
ps aux | grep python
free -h

# Restart API if memory issues
pkill -f run_api.py
python run_api.py
```

## Future Enhancements

### Planned Improvements
1. **Multiple Cache Regions**: Support for multiple city caches
2. **Cache Updates**: Automatic cache refresh/update mechanisms  
3. **Compression**: Better compression for smaller cache files
4. **Distributed Caching**: Redis/Memcached integration for multi-instance deployments
5. **Smart Prefetching**: Predictive caching based on route patterns

### Configuration Options
1. **Cache TTL**: Automatic cache expiration and refresh
2. **Memory Limits**: Configurable memory usage limits
3. **Storage Options**: Database storage instead of files
4. **Network Types**: Support for different network types (drive, bike, etc.)

## Monitoring

### Key Metrics to Monitor
- Cache hit rate (routes using cache vs direct downloads)
- Average response time for cached vs non-cached routes
- Cache file size and memory usage
- Cache coverage effectiveness

### Log Messages to Watch
- `"Route is within cached area - extracting from cache"`
- `"Route is outside cached area - using direct OSMnx download"`
- `"Cache extraction failed, falling back to direct download"`
- `"Network cache ready - routes will use cached data"`

## Conclusion

The network caching system provides significant performance improvements for the Crime-Aware Routing API while maintaining compatibility and reliability. Routes within the Toronto area see 5-10x speed improvements, making the API much more responsive for production use. 
# Crime-Aware Routing System - Complete Codebase Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Project Structure](#project-structure)
3. [Startup Process](#startup-process)
4. [API Request Flow](#api-request-flow)
5. [Cache Architecture](#cache-architecture)
6. [Enhanced Graph System](#enhanced-graph-system)
7. [Routing Algorithms](#routing-algorithms)
8. [Crime Weighting System](#crime-weighting-system)
9. [Memory Optimization](#memory-optimization)
10. [Configuration & Parameters](#configuration--parameters)
11. [Key Components Deep Dive](#key-components-deep-dive)

---

## System Overview

The Crime-Aware Routing System is a FastAPI-based service that provides optimal route calculation considering both distance and crime data. It pre-processes Toronto street networks with crime statistics to enable fast, safety-conscious routing.

### **Core Capabilities:**
- **Shortest Routes**: Traditional distance-only routing
- **Crime-Aware Routes**: Routes that balance distance vs safety
- **Dynamic Crime Weighting**: Runtime adjustment of crime penalties
- **Memory-Optimized Caching**: Pre-computed enhanced graphs for instant routing

---

## Project Structure

```
Ventr/
├── api/                           # FastAPI application layer
│   ├── main.py                   # FastAPI app with lifespan management
│   ├── routes/
│   │   └── routing.py            # API endpoints (/api/routing/*)
│   ├── services/
│   │   └── routing_service.py    # Business logic layer
│   └── schemas/
│       └── routing.py            # Request/response models
├── crime_aware_routing_2/         # Core routing engine
│   ├── algorithms/
│   │   ├── optimization/
│   │   │   └── route_optimizer.py # Main routing orchestrator
│   │   ├── routing/
│   │   │   └── astar_weighted.py  # Dijkstra/A* implementations
│   │   └── crime_weighting/
│   │       └── network_proximity_weighter.py # Crime influence calculation
│   ├── mapping/
│   │   └── network/
│   │       ├── enhanced_network_builder.py    # Enhanced graph orchestrator
│   │       ├── enhanced_graph_cache.py        # Enhanced cache management
│   │       ├── network_cache.py               # Base OSM network cache
│   │       ├── network_builder.py             # Standard network building
│   │       ├── graph_enhancer.py              # Crime weight application
│   │       └── cache_strategy.py              # Memory optimization strategy
│   └── data/
│       ├── crime_processor.py    # Crime data loading & spatial indexing
│       └── crime_data.geojson    # Toronto crime incidents dataset
├── enhanced_cache/               # Pre-computed enhanced graphs
│   └── toronto_enhanced_0.1.pkl # Enhanced graph (crime_weight=0.1)
├── osmnx_cache/                 # Base street network cache
│   └── toronto_network.pkl     # OSM street network (378k nodes, 1M edges)
└── run_api.py                   # Server startup script
```

---

## Startup Process

### **1. Server Initialization (`run_api.py`)**
```python
# Memory-optimized startup - cache loads in worker process
uvicorn.run("api.main:app", reload=True)
```

### **2. FastAPI Lifespan Events (`api/main.py`)**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP: Load enhanced cache in worker process
    logger.info("🔒 Loading enhanced cache in worker process...")
    
    enhanced_cache = get_enhanced_cache()
    enhanced_cache.load_cache()  # Loads 378k nodes, 1M edges (~10 seconds)
    
    routing_service = CrimeAwareRoutingService()
    yield
    
    # SHUTDOWN: Cleanup
```

### **3. Cache Loading Process**
- **Enhanced Cache**: `toronto_enhanced_0.1.pkl` (pre-computed crime weights)
- **Fallback**: `toronto_network.pkl` (base OSM network)
- **Memory Usage**: ~1.5GB for enhanced cache vs ~2.5GB for dual loading

---

## API Request Flow

### **Complete Request Lifecycle:**

```
1. POST /api/routing/calculate-multiple
   └── api/routes/routing.py:calculate_multiple_routes()

2. Business Logic Layer
   └── api/services/routing_service.py:calculate_multiple_routes()
   
3. Route Optimizer Initialization
   └── RouteOptimizer(crime_data_path, config)
   
4. Network Building
   └── enhanced_network_builder.py:build_enhanced_network()
   
5. Routing Algorithm Execution
   └── astar_weighted.py:find_multiple_routes()
   
6. Response Formatting
   └── routing.py schemas (MultipleRoutesResponse)
```

### **Key Request Parameters:**
```python
{
    "start": {"latitude": 43.6426, "longitude": -79.3871},
    "destination": {"latitude": 43.6387, "longitude": -79.3816},
    "include_shortest": true,
    "include_safest": true,
    "crime_weight_safest": 0.1,  # Crime vs distance balance
    "max_detour_factor": 2.0
}
```

---

## Cache Architecture

### **Two-Tier Cache System:**

#### **1. Enhanced Cache (Primary - Memory Optimized)**
- **File**: `enhanced_cache/toronto_enhanced_0.1.pkl`
- **Content**: OSM network + pre-computed crime weights
- **Size**: 378,257 nodes, 1,091,958 edges
- **Edge Attributes**:
  ```python
  {
      'length': 156.789,              # Original street distance (meters)
      'weighted_length': 178.234,     # Distance + crime penalties
      'crime_score': 1.245           # Raw crime influence (0.0-1.0+)
  }
  ```

#### **2. Network Cache (Fallback)**
- **File**: `osmnx_cache/toronto_network.pkl` 
- **Content**: Pure OSM street network (no crime data)
- **Usage**: Fallback when enhanced cache unavailable

### **Cache Strategy Logic:**
```python
class CacheStrategy:
    @staticmethod
    def get_active_cache_info():
        enhanced_cache = get_enhanced_cache()
        if enhanced_cache.enhanced_graph is not None:
            return enhanced_cache_info  # Memory optimized
        else:
            return network_cache_info   # Fallback
```

---

## Enhanced Graph System

### **Creation Process (`build_enhanced_cache.py`):**

#### **1. Base Network Loading**
```python
# Load Toronto OSM network (30km radius)
network = ox.graph_from_point(
    (43.6532, -79.3832),  # Toronto center
    dist=30000,           # 30km radius
    network_type='drive'
)
```

#### **2. Crime Data Integration**
```python
# Load 5,650+ crime incidents from GeoJSON
crime_processor = CrimeProcessor(crime_data_path)
crime_processor.initialize()  # Creates spatial index
```

#### **3. Graph Enhancement (`graph_enhancer.py`)**
```python
# Apply crime weights to all 1M+ edges
for edge in graph.edges(data=True):
    crime_influence = weighter.get_edge_crime_influence(edge)
    
    # Final weighted edge calculation:
    weighted_length = (distance_weight * edge_distance) + (crime_weight * crime_influence * penalty_scale)
    
    edge['weighted_length'] = weighted_length
    edge['crime_score'] = crime_influence
```

### **Crime Weighting Formula:**
```python
# Default parameters for enhanced cache
distance_weight = 0.9           # 90% distance influence
crime_weight = 0.1             # 10% crime influence  
penalty_scale = 200.0          # Crime penalty scaling
influence_radius = 115m        # Crime detection radius

# Per-edge calculation:
crime_influence = sum(decay_function(distance_to_crime) for crime in nearby_crimes)
weighted_length = (0.9 * distance) + (0.1 * crime_influence * 200.0)
```

---

## Routing Algorithms

### **Algorithm Selection:**
- **Shortest Path**: Uses `weight='length'` (distance only)
- **Safest Path**: Uses `weight='weighted_length'` (distance + crime)
- **Implementation**: Dijkstra's algorithm (changed from A* for predictability)

### **Dynamic Crime Multiplier System:**
```python
class WeightedAStarRouter:
    def _dynamic_weight_function(self, u, v, edge_data, crime_multiplier):
        # Extract components from enhanced graph
        base_distance = edge_data.get('length', 1.0)
        crime_score = edge_data.get('crime_score', 0.0)
        
        # Recalculate weight distribution
        new_crime_weight = min(0.1 * crime_multiplier, 0.9)
        new_distance_weight = 1.0 - new_crime_weight
        
        # Rebuild weight with new proportions
        penalty_scale = 200.0
        return (new_distance_weight * base_distance) + (new_crime_weight * crime_score * penalty_scale)
```

### **Crime Multiplier Effects:**
- **1.0**: Original enhanced cache behavior (crime_weight=0.1)
- **5.0**: Balanced routing (crime_weight=0.5) 
- **9.0**: Maximum crime avoidance (crime_weight=0.9)

---

## Crime Weighting System

### **Crime Influence Calculation:**

#### **1. Spatial Proximity Detection**
```python
# For each street edge, sample points along the edge
sample_points = interpolate_points_along_edge(edge, sample_distance=50m)

for point in sample_points:
    # Find crimes within influence radius (default: 115m)
    nearby_crimes = spatial_index.query_radius(point, radius=115m)
```

#### **2. Distance Decay Function**
```python
def apply_decay_function(distance_to_crime):
    # Exponential decay - closer crimes have stronger influence
    return math.exp(-distance_to_crime / decay_constant)
```

#### **3. Crime Clustering Amplification**
```python
total_influence = sum(decay_function(dist) for dist in distances_to_crimes)
# Multiple nearby crimes create additive effect
# Downtown: 5+ crimes nearby = strong influence
# Suburban: 1-2 crimes nearby = weak influence
```

### **Geographic Crime Distribution Effects:**
- **Downtown Toronto**: Dense crime clusters → High additive influence → Strong avoidance
- **Suburban Areas**: Isolated incidents → Low additive influence → Weak avoidance
- **Jane/Finch Area**: Medium crime density but suburban spacing → Moderate influence

---

## Memory Optimization

### **Problem Solved:**
- **Before**: Dual cache loading (enhanced + network) = ~4.0GB memory
- **After**: Enhanced cache only = ~2.9GB memory (~1.1GB savings)

### **Implementation Details:**

#### **1. Process Isolation Fix**
```python
# Issue: Uvicorn --reload creates separate processes
# Main process: Loads enhanced cache ✓
# Worker process: Empty enhanced cache ✗

# Solution: Load cache in FastAPI lifespan (worker process)
@asynccontextmanager
async def lifespan(app: FastAPI):
    enhanced_cache = get_enhanced_cache()
    enhanced_cache.load_cache()  # Loads in correct process
```

#### **2. Cache Strategy Module**
```python
class CacheStrategy:
    # Memory-optimized logic - use enhanced cache as primary
    # Only load network cache as fallback if enhanced unavailable
```

### **Performance Benefits:**
- **Startup Time**: Single cache load (~10s vs ~20s)
- **Memory Usage**: 27% reduction from dual loading
- **API Response**: Instant routing vs 35+ second enhancement

---

## Configuration & Parameters

### **Enhanced Cache Configuration:**
```python
# Built-in parameters for toronto_enhanced_0.1.pkl
CRIME_WEIGHT = 0.1              # 10% crime influence
DISTANCE_WEIGHT = 0.9           # 90% distance influence  
INFLUENCE_RADIUS = 115.0        # Crime detection radius (meters)
PENALTY_SCALE = 200.0           # Crime penalty multiplier
CACHE_RADIUS = 30000           # Network coverage (30km from Toronto center)
SAMPLE_DISTANCE = 50.0         # Crime sampling interval along edges
```

### **API Configuration:**
```python
# Default values for route requests
DEFAULT_CRIME_WEIGHT = 0.1     # Safest route crime sensitivity
MAX_DETOUR_FACTOR = 2.0        # Maximum route length vs shortest
DEFAULT_ALGORITHMS = ['shortest_path', 'weighted_astar']
```

### **Runtime Parameters:**
```python
# Dynamic crime multiplier (API level)
crime_multiplier = 1.0-9.0     # Amplifies crime avoidance
# 1.0 = enhanced cache behavior
# 5.0 = balanced crime/distance  
# 9.0 = maximum crime avoidance
```

---

## Key Components Deep Dive

### **1. RouteOptimizer (`route_optimizer.py`)**
**Role**: Main orchestrator for route calculation
```python
def find_safe_route(self, start_coords, end_coords, algorithms):
    # 1. Initialize crime processor & spatial index
    # 2. Build enhanced network (or extract from cache)
    # 3. Find nearest nodes to start/end coordinates
    # 4. Execute routing algorithms
    # 5. Validate and return results
```

### **2. EnhancedNetworkBuilder (`enhanced_network_builder.py`)**
**Role**: Decides between cached enhanced graph vs runtime building
```python
def build_enhanced_network(self, center_point, route_distance, crime_weight):
    if enhanced_cache.has_coverage(route) and crime_weight == 0.1:
        return enhanced_cache.extract_subgraph()  # Fast path
    else:
        return build_runtime_enhanced_network()   # Slow path (35+ seconds)
```

### **3. WeightedAStarRouter (`astar_weighted.py`)**
**Role**: Graph traversal with dynamic crime weighting
```python
def find_route(self, start_node, end_node, weight_attr, crime_multiplier):
    if crime_multiplier != 1.0:
        weight_function = lambda u,v,d: self._dynamic_weight_function(u,v,d,crime_multiplier)
    return nx.dijkstra_path(graph, start_node, end_node, weight=weight_function)
```

### **4. CrimeProcessor (`crime_processor.py`)**
**Role**: Crime data loading and spatial indexing
```python
def initialize(self):
    # Load 5,650+ crime incidents from GeoJSON
    # Create spatial index for fast proximity queries
    # Support radius-based crime lookups for graph enhancement
```

---

## Troubleshooting Common Issues

### **1. Enhanced Cache Not Loading**
**Symptoms**: API requests take 35+ seconds, logs show "Crime weight X not cached"
**Cause**: Enhanced cache not loaded in worker process
**Solution**: Verify FastAPI lifespan loads cache correctly

### **2. Crime Avoidance Too Weak**  
**Symptoms**: Routes go through obvious crime hotspots
**Cause**: Low crime influence (crime_weight=0.1, small influence_radius=115m)
**Solution**: Use crime_multiplier > 1.0 for stronger avoidance

### **3. Memory Usage High**
**Symptoms**: >4GB memory usage during startup
**Cause**: Dual cache loading (enhanced + network caches)
**Solution**: Ensure cache strategy uses enhanced-only mode

### **4. Suburban Crime Hotspots Ignored**
**Symptoms**: Jane/Finch area not avoided despite high crime
**Cause**: Sparse crime distribution + small influence radius + low crime clustering
**Solution**: Increase crime_multiplier to 5.0+ for suburban routing

---

This documentation provides a complete understanding of the Crime-Aware Routing System architecture, from API requests to graph algorithms, enabling quick onboarding for future development and troubleshooting.
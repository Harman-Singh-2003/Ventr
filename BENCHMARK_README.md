# Routing Performance Benchmark System

## Overview

This benchmark system tests various performance optimizations for the crime-aware routing algorithms while ensuring **exact output compatibility** with the baseline implementation.

## Files

- **`routing_benchmark.py`** - Core benchmark framework with output verification
- **`routing_optimizations.py`** - Optimized router implementations  
- **`run_benchmark.py`** - Main script to execute all benchmarks
- **`comprehensive_routing_tests.py`** - Original baseline implementation

## Implemented Optimizations

### 1. **NetworkCacheRouter** - OSM Network Caching
- **Optimization**: Cache downloaded OpenStreetMap networks using pickle
- **Benefit**: Eliminates repeated API calls (10-50x speedup on network loading)
- **Strategy**: Hash center coordinates + radius to create unique cache keys
- **Files**: Saved to `network_cache/` directory

### 2. **VectorizedRouter** - NumPy Vectorization  
- **Optimization**: Replace nested loops with vectorized NumPy operations
- **Benefit**: Faster crime proximity calculations (3-5x speedup on edge weights)
- **Strategy**: Broadcast operations across all edges and crimes simultaneously
- **Memory**: Uses more RAM but significantly faster computation

### 3. **CombinedOptimizedRouter** - Multi-Optimization
- **Optimization**: Combines network caching + vectorized calculations
- **Benefit**: Cumulative speedup from both approaches
- **Strategy**: Best of both worlds for maximum performance

## Verification System

The benchmark ensures **EXACT** output compatibility:

- ✅ **Route Coordinates**: Must match exactly (rounded to 10 decimal places)
- ✅ **Distance Calculations**: Must match within 1e-6 tolerance  
- ✅ **Crime Exposure**: Must match exactly
- ✅ **Routing Statistics**: All metrics must be identical
- ❌ **Automatic Failure**: Any mismatch fails verification

## Usage

### Run Complete Benchmark
```bash
python run_benchmark.py
```

### Run Individual Tests
```python
from routing_benchmark import RoutingBenchmark
from routing_optimizations import NetworkCacheRouter

benchmark = RoutingBenchmark()
benchmark.register_router('cache_test', NetworkCacheRouter)
results = benchmark.run_benchmark(num_runs=3)
```

## Expected Performance Gains

| Optimization | Expected Speedup | Primary Benefit |
|-------------|------------------|-----------------|
| Network Cache | 10-50x | Eliminates OSM downloads |
| Vectorized | 3-5x | Faster crime calculations |
| Combined | 15-100x | Cumulative benefits |

## Test Routes

The benchmark tests 6 different routes in Toronto:
1. CN Tower → Union Station
2. Union Station → City Hall  
3. City Hall → St. Lawrence Market
4. St. Lawrence Market → Harbourfront
5. CN Tower → Harbourfront (longer route)
6. **Custom Location A → Custom Location B** (your new route)

## Routing Methods Tested

All optimizations maintain compatibility with:
- **Shortest Path** (baseline)
- **Exponential Decay** (crime-aware with exponential distance weighting)
- **Linear Penalty** (crime-aware with linear distance weighting)
- **Threshold Avoidance** (avoids areas within 75m of crimes)
- **Raw Data Weighted** (considers crimes within 200m with distance-based risk)

## Output

### Console Output
```
🚀 Starting Routing Performance Benchmark
================================================================================
✅ Registered: network_cache (NetworkCacheRouter)
✅ Registered: vectorized (VectorizedRouter)
✅ Registered: combined (CombinedOptimizedRouter)

📊 Running benchmark with 3 optimizations...
🔄 Each implementation will run 3 times for average timing
✔️  Output verification ensures exact route matching

🔄 Running baseline...
  Run 1/3...
  Run 2/3...
  Run 3/3...
  ✅ Baseline: 45.231s avg

🔄 Running network_cache...
  Run 1/3...
  Run 2/3...  
  Run 3/3...
  ✅ network_cache: 8.142s avg (5.55x speedup)

🎯 BENCHMARK COMPLETED
================================================================================
🏆 Best optimization: combined (12.34x speedup)
📈 Speedup range: 3.2x - 12.3x
✅ 3/3 optimizations successful
```

### Saved Results
- **JSON file**: `benchmark_results_YYYYMMDD_HHMMSS.json`
- **Detailed timing**: Average, standard deviation, speedup ratios
- **Verification status**: Pass/fail for each optimization

## Requirements

```bash
pip install osmnx networkx folium numpy pandas scikit-learn
```

## Notes

- **First Run**: Network downloads may take time, subsequent runs use cache
- **Memory Usage**: Vectorized operations use more RAM for speed
- **Exact Output**: Any optimization that changes routes will fail verification
- **Error Handling**: Failed optimizations are reported but don't stop the benchmark

## Adding New Optimizations

1. Create new router class inheriting from `BaseRouter`
2. Implement `run_all_tests()` method
3. Register with benchmark: `benchmark.register_router(name, class)`
4. Ensure exact output compatibility for verification

The system is designed to safely test performance improvements while maintaining algorithmic correctness. 
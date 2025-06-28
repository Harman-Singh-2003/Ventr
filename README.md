# Crime-Aware Routing System v2.0

A clean, efficient implementation of crime-aware routing algorithms for urban navigation in Toronto. Built from the ground up using lessons learned from extensive experimentation.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the system
cd crime_aware_routing
python main.py
```

## Features

- **Clean Architecture**: Modular design with clear separation of concerns
- **Essential Algorithms**: Focus on proven methods (exponential decay, linear penalty)
- **Distance Constraints**: Routes stay within practical distance limits
- **Performance Optimized**: Efficient data structures and algorithms
- **Toronto Crime Data**: 5,583 assault incidents with precise coordinates

## Architecture

```
crime_aware_routing/
├── data/                  # Crime data (8.5MB GeoJSON)
├── core/                  # Data loading, network building, utilities
├── algorithms/            # Routing algorithms (TODO)
├── optimization/          # Distance constraint solving (TODO)
├── visualization/         # Map generation (TODO)
└── tests/                 # Unit tests (TODO)
```

## Key Learnings Applied

### What Works
- **Binary search optimization** for distance constraints
- **Pre-computation** of crime penalties for performance
- **Modular design** for maintainability
- **Clean data loading** with validation

### What Was Removed
- Over-engineered complex algorithms (8+ methods → 2-3 core methods)
- Excessive caching and premature optimization
- Inconsistent distance calculations
- Feature creep and experimental code

## Next Steps

1. **Phase 1**: Implement core exponential decay algorithm
2. **Phase 2**: Add distance constraint optimization
3. **Phase 3**: Create route visualization
4. **Phase 4**: Performance testing and benchmarks

## Data Source

- **Crime Data**: Toronto Police Service Assault Open Data
- **Network Data**: OpenStreetMap via OSMnx
- **Coverage**: Toronto metropolitan area (43.5-44.0°N, 79.0-80.0°W)

## Reset History

This is a complete rewrite based on extensive experimentation. See `ROUTING_LEARNINGS_AND_RESET.md` for detailed analysis of what worked, what didn't, and why this fresh start was necessary.

---

*Built with lessons learned from real-world routing algorithm development.* 
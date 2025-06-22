# Mapbox Crime Heatmap Usage Guide

## Overview
This project has generated crime density heatmap data for Toronto roads that can be uploaded to Mapbox Studio for visualization. The data shows crime density on a 0-1 scale where 1.0 represents streets with 3 or more crimes in close proximity.

## Generated Files

### 1. `mapbox_crime_heatmap_multi.geojson` (Recommended)
- **680 road segments** across 5 Toronto locations
- **211 segments** with crime exposure
- **21 high-crime segments** (weight > 0.5)
- Covers: CN Tower, Downtown Core, Entertainment District, Financial District, King West

### 2. `mapbox_crime_heatmap_single.geojson`
- **66 road segments** around CN Tower area only
- Limited crime data in this specific area

### 3. `crime_heatmap_preview.html`
- Local preview of the heatmap using Folium
- Color-coded visualization to preview before uploading to Mapbox

## Data Structure

Each road segment in the GeoJSON has these properties:

```json
{
  "weight": 0.456,           // Crime density (0-1 scale)
  "edge_id": "12345_67890_0", // Unique identifier
  "length": 125.3,           // Road segment length in meters
  "road_type": "primary",    // Type of road (primary, secondary, etc.)
  "name": "King Street",     // Road name (if available)
  "location": "Downtown Core" // Area location
}
```

## Crime Density Algorithm

The `weight` value represents crime density calculated as follows:

### Distance-Based Weighting:
- **0-5m from road**: Full weight (1.0)
- **5-15m from road**: 80% weight with linear decay
- **15-50m from road**: 30% weight with linear decay
- **>50m from road**: No influence (0.0)

### Normalization:
- Scale: 0.0 to 1.0
- **1.0 = 3 crimes** at maximum influence
- Values capped at 1.0 for visualization consistency

## Upload to Mapbox Studio

### Step 1: Upload Data
1. Go to [Mapbox Studio](https://studio.mapbox.com/)
2. Navigate to **Tilesets** → **New tileset**
3. Upload `mapbox_crime_heatmap_multi.geojson`
4. Name it "Toronto Crime Heatmap"

### Step 2: Create Style
1. Go to **Styles** → **New style**
2. Choose a base map (recommended: Monochrome Dark or Light)
3. Add a new layer → Choose your uploaded tileset

### Step 3: Configure Heatmap Layer
1. **Layer type**: Choose "Heatmap"
2. **Weight property**: Select `weight`
3. **Radius**: 15-25 pixels (adjust as needed)
4. **Intensity**: 1.0

### Step 4: Color Configuration
Recommended color stops for the `weight` property:

```
0.0  → rgba(0, 0, 255, 0)      // Transparent (no crime)
0.2  → rgba(0, 0, 255, 0.4)    // Blue (low crime)
0.4  → rgba(0, 255, 255, 0.6)  // Cyan (low-medium)
0.6  → rgba(255, 255, 0, 0.8)  // Yellow (medium-high)  
0.8  → rgba(255, 165, 0, 0.9)  // Orange (high)
1.0  → rgba(255, 0, 0, 1.0)    // Red (very high)
```

### Step 5: Zoom Levels
- **Min zoom**: 10 (city-wide view)
- **Max zoom**: 18 (street-level detail)
- **Optimal viewing**: 14-16

## Alternative: Line-based Visualization

Instead of heatmap, you can also create a line-based visualization showing individual road segments:

1. **Layer type**: Choose "Line"
2. **Width**: 2-4 pixels
3. **Color**: Data-driven by `weight` property
4. **Opacity**: Data-driven by `weight` property

## Data Statistics

### Multi-location Dataset:
- **Total segments**: 680
- **With crime exposure**: 211 (31%)
- **High crime (>0.5)**: 21 (3%)
- **Average weight**: 0.076
- **Maximum weight**: 1.000

### Weight Distribution:
- **No crime (0.0)**: 469 segments (69%)
- **Low (0.0-0.2)**: 117 segments (17%)
- **Low-Med (0.2-0.4)**: 63 segments (9%)
- **Medium (0.4-0.6)**: 15 segments (2%)
- **Med-High (0.6-0.8)**: 2 segments (<1%)
- **High (0.8-1.0)**: 14 segments (2%)

## Customization Options

### Adjust Crime Influence
To modify the algorithm, edit `mapbox_crime_heatmap_generator.py`:
- Change `max_influence_distance` parameter (default: 50m)
- Modify distance-based weights in `calculate_crime_density_for_edge()`
- Adjust normalization scale (default: 3 crimes = 1.0)

### Add More Locations
Add coordinates to the `locations` array in `generate_multiple_locations()`:

```python
locations = [
    {"name": "Your Location", "lat": 43.xxxx, "lon": -79.xxxx},
    # ... existing locations
]
```

### Change Network Size
Modify the `radius` parameter (default: 100m for 200m diameter networks)

## Preview Your Data

Before uploading to Mapbox, view `crime_heatmap_preview.html` in your browser to see:
- Color-coded road segments
- Interactive popups with crime weights
- Legend showing weight categories
- Overall data distribution

## Troubleshooting

### No Crime Data Showing
- Check if your area has crime incidents in the source data
- Increase `max_influence_distance` for broader coverage
- Verify coordinate system (should be WGS84)

### Performance Issues in Mapbox
- Use the single-location file for better performance
- Reduce `radius` parameter to create smaller networks
- Consider breaking large areas into multiple tilesets

## Source Data
- **Crime Data**: Toronto Police Assault Open Data
- **Road Network**: OpenStreetMap via OSMnx
- **Coordinate System**: WGS84 (EPSG:4326)

## Next Steps
1. Preview your data locally with `crime_heatmap_preview.html`
2. Upload to Mapbox Studio
3. Configure visualization style
4. Publish and embed in your application

For questions or modifications, refer to the source code in `mapbox_crime_heatmap_generator.py`. 
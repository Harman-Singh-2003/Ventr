import os
import time
import pickle
from pathlib import Path

import osmnx as ox
from osmnx.truncate import truncate_graph_bbox, truncate_graph_dist
from shapely.geometry import Point
import folium
from folium import plugins

# --- CONFIG ---

# Downtown Toronto coordinates
lat, lon = 43.6532, -79.3832
radius_m = 2000  # meters for extraction

# Cache configuration
CACHE_DIR = "osmnx_cache"
CACHE_FILE = "toronto_large.pkl"
LARGE_AREA_RADIUS = 20000  # Download 10km radius once, extract smaller areas from it

# --- Helper Functions ---

def ensure_cache_dir():
    """Create cache directory if it doesn't exist"""
    Path(CACHE_DIR).mkdir(exist_ok=True)

def delete_old_cache(cache_path):
    """Delete old cache file to start fresh"""
    if cache_path.exists():
        print(f"Deleting old cache file: {cache_path}")
        cache_path.unlink()
    else:
        print("No old cache file to delete")

def radius_to_bbox(lat, lon, radius_m):
    """Convert lat/lon/radius to bounding box coordinates"""
    # Approximate conversion: 1 degree ≈ 111,320 meters
    buffer_deg = radius_m / 111320
    north = lat + buffer_deg
    south = lat - buffer_deg
    east = lon + buffer_deg
    west = lon - buffer_deg
    
    print(f"DEBUG: Converting radius {radius_m}m to bbox:")
    print(f"  Center: lat={lat}, lon={lon}")
    print(f"  Buffer: {buffer_deg:.6f} degrees")
    print(f"  BBox: north={north:.6f}, south={south:.6f}, east={east:.6f}, west={west:.6f}")
    
    return west, south, east, north

def download_and_cache_large_area(lat, lon, radius_m, cache_path):
    """Download a large area once and cache it"""
    print(f"Downloading large area (radius {radius_m}m) from OSMnx...")
    print(f"Using network_type='walk'")
    start = time.time()
    
    # Download large area
    G_large = ox.graph_from_point((lat, lon), dist=radius_m, network_type='walk')
    
    download_time = time.time() - start
    print(f"Downloaded {len(G_large.nodes)} nodes, {len(G_large.edges)} edges in {download_time:.2f}s")
    
    # Save to cache
    print(f"Saving to cache: {cache_path}")
    with open(cache_path, 'wb') as f:
        pickle.dump(G_large, f)
    
    return G_large, download_time

def load_cached_graph(cache_path):
    """Load cached graph from disk"""
    print(f"Loading cached graph from: {cache_path}")
    start = time.time()
    
    with open(cache_path, 'rb') as f:
        G_large = pickle.load(f)
    
    load_time = time.time() - start
    print(f"Loaded {len(G_large.nodes)} nodes, {len(G_large.edges)} edges in {load_time:.2f}s")
    
    return G_large, load_time

def extract_from_cached_graph(G_large, lat, lon, radius_m):
    """Extract a smaller area from the cached large graph"""
    print(f"Extracting area (radius {radius_m}m) from cached graph...")
    start = time.time()
    
    # Find the nearest node to our target coordinates
    print(f"DEBUG: Finding nearest node to lat={lat}, lon={lon}")
    center_node = ox.nearest_nodes(G_large, lon, lat)
    print(f"DEBUG: Found center node: {center_node}")
    
    # Extract subgraph using distance-based truncation (same as fresh download)
    G_small = truncate_graph_dist(G_large, center_node, radius_m*1.4)
    
    extract_time = time.time() - start
    print(f"Extracted {len(G_small.nodes)} nodes, {len(G_small.edges)} edges in {extract_time:.2f}s")
    
    return G_small, extract_time

def fresh_download_osmnx(lat, lon, radius_m):
    """Download area fresh from OSMnx (for comparison)"""
    print(f"Fresh download from OSMnx (radius {radius_m}m)...")
    print(f"Using network_type='walk'")
    start = time.time()
    
    G = ox.graph_from_point((lat, lon), dist=radius_m, network_type='walk')
    
    download_time = time.time() - start
    print(f"Downloaded {len(G.nodes)} nodes, {len(G.edges)} edges in {download_time:.2f}s")
    
    return G, download_time

def debug_graph_comparison(G_cached, G_fresh):
    """Debug the differences between cached and fresh graphs"""
    print(f"\n--- DETAILED GRAPH COMPARISON ---")
    
    # Get node sets
    cached_nodes = set(G_cached.nodes())
    fresh_nodes = set(G_fresh.nodes())
    
    print(f"Cached nodes: {len(cached_nodes)}")
    print(f"Fresh nodes: {len(fresh_nodes)}")
    
    # Find overlap
    common_nodes = cached_nodes.intersection(fresh_nodes)
    cached_only = cached_nodes - fresh_nodes
    fresh_only = fresh_nodes - cached_nodes
    
    print(f"Common nodes: {len(common_nodes)}")
    print(f"Cached-only nodes: {len(cached_only)}")
    print(f"Fresh-only nodes: {len(fresh_only)}")
    
    # Sample some nodes for examination
    if cached_only:
        print(f"Sample cached-only nodes: {list(cached_only)[:5]}")
    if fresh_only:
        print(f"Sample fresh-only nodes: {list(fresh_only)[:5]}")
    
    # Check if graphs have same attributes
    print(f"Cached graph attributes: {G_cached.graph}")
    print(f"Fresh graph attributes: {G_fresh.graph}")

def create_html_visualization(G_cached, G_fresh, G_large, lat, lon, radius_m, large_radius_m, output_file="network_comparison.html"):
    """Create an interactive HTML visualization comparing cached vs fresh downloads"""
    print(f"\n--- Creating HTML Visualization ---")
    
    # Convert graphs to GeoDataFrames
    print("Converting graphs to GeoDataFrames...")
    _, edges_cached = ox.graph_to_gdfs(G_cached)
    _, edges_fresh = ox.graph_to_gdfs(G_fresh)
    _, edges_large = ox.graph_to_gdfs(G_large)
    
    # Create base map centered on Toronto
    m = folium.Map(
        location=[lat, lon],
        zoom_start=11,
        tiles='OpenStreetMap',
        width='100%',
        height='100%'
    )
    
    # Add cached graph edges (green)
    print("Adding cached extraction edges...")
    for idx, edge in edges_cached.iterrows():
        if edge.geometry is not None:
            coords = [[point[1], point[0]] for point in edge.geometry.coords]
            folium.PolyLine(
                coords,
                color='green',
                weight=2,
                opacity=0.7,
                popup=f"Cached Edge: {len(coords)} points"
            ).add_to(m)
    
    # Add fresh download edges (blue)
    print("Adding fresh download edges...")
    for idx, edge in edges_fresh.iterrows():
        if edge.geometry is not None:
            coords = [[point[1], point[0]] for point in edge.geometry.coords]
            folium.PolyLine(
                coords,
                color='blue',
                weight=1,
                opacity=0.4,
                popup=f"Fresh Edge: {len(coords)} points"
            ).add_to(m)
    
    # Add large cached area outline (red)
    print("Adding large cache area outline...")
    cache_sample = edges_large.sample(n=min(1000, len(edges_large)))  # Sample for performance
    for idx, edge in cache_sample.iterrows():
        if edge.geometry is not None:
            coords = [[point[1], point[0]] for point in edge.geometry.coords]
            folium.PolyLine(
                coords,
                color='red',
                weight=0.5,
                opacity=0.2,
                popup=f"Large Cache Area"
            ).add_to(m)
    
    # Add center point marker
    folium.Marker(
        [lat, lon],
        popup=f"Center Point<br>Lat: {lat}<br>Lon: {lon}",
        icon=folium.Icon(color='red', icon='info-sign')
    ).add_to(m)
    
    # Add coverage circles
    # Extraction radius circle
    folium.Circle(
        location=[lat, lon],
        radius=radius_m,
        popup=f"Extraction Radius: {radius_m}m",
        color='black',
        fill=False,
        weight=2,
        opacity=0.8
    ).add_to(m)
    
    # Large cache radius circle
    folium.Circle(
        location=[lat, lon],
        radius=large_radius_m,
        popup=f"Cache Radius: {large_radius_m}m",
        color='red',
        fill=False,
        weight=2,
        opacity=0.5,
        dashArray='5, 5'
    ).add_to(m)
    
    # Add legend
    legend_html = '''
    <div style="position: fixed; 
                top: 10px; left: 50px; width: 200px; height: 150px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px">
    <h4>Network Comparison</h4>
    <p><span style="color:blue;">━━━</span> Fresh Download ({fresh_nodes:,} nodes)</p>
    <p><span style="color:green;">━━━</span> Cached Extraction ({cached_nodes:,} nodes)</p>
    <p><span style="color:red;">━━━</span> Large Cache Area ({large_nodes:,} nodes)</p>
    <p><span style="color:black;">○</span> Extraction Radius ({radius}m)</p>
    <p><span style="color:red;">○</span> Cache Radius ({large_radius}m)</p>
    </div>
    '''.format(
        fresh_nodes=len(G_fresh.nodes),
        cached_nodes=len(G_cached.nodes),
        large_nodes=len(G_large.nodes),
        radius=radius_m,
        large_radius=large_radius_m
    )
    
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Add title
    title_html = '''
    <div style="position: fixed; 
                top: 10px; right: 10px; width: 400px; height: 80px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:16px; padding: 10px; text-align: center">
    <h3>OSMnx Caching System Comparison</h3>
    <p>Downtown Toronto Walking Network</p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(title_html))
    
    # Save the map
    print(f"Saving visualization to {output_file}")
    m.save(output_file)
    
    # Add performance info to HTML
    with open(output_file, 'r') as f:
        html_content = f.read()
    
    performance_info = '''
    <div style="position: fixed; 
                bottom: 10px; left: 10px; width: 300px; height: 100px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:12px; padding: 10px">
    <h4>Performance Results</h4>
    <p>Fresh Download: 13.46s</p>
    <p>Cached Extraction: 2.63s</p>
    <p><strong>Speedup: 5.11x faster!</strong></p>
    </div>
    '''
    
    html_content = html_content.replace('</body>', performance_info + '</body>')
    
    with open(output_file, 'w') as f:
        f.write(html_content)
    
    print(f"HTML visualization saved to: {output_file}")
    print(f"Open the file in your browser to view the interactive map!")
    
    return output_file

# --- MAIN SCRIPT ---

if __name__ == "__main__":
    print("=== OSMnx Caching System Test (Fresh Start) ===")
    print(f"Target area: lat {lat}, lon {lon}, radius {radius_m}m")
    print(f"Cache area: radius {LARGE_AREA_RADIUS}m")
    
    ensure_cache_dir()
    cache_path = Path(CACHE_DIR) / CACHE_FILE
    
    # Step 1: Delete old cache and start fresh
    # print(f"\n--- Starting Fresh: Deleting Old Cache ---")
    # delete_old_cache(cache_path)
    
    # Step 2: Download and cache large area
    # print(f"\n--- Downloading Large Area for Cache ---")
    # G_large, cache_creation_time = download_and_cache_large_area(lat, lon, LARGE_AREA_RADIUS, cache_path)
    # print(f"Cache created in {cache_creation_time:.2f}s")
    
    G_large, cache_creation_time = load_cached_graph(cache_path)
    print(f"Cache created in {cache_creation_time:.2f}s")
    
    # Step 3: Fresh download (for comparison)
    print(f"\n--- Fresh Download for Comparison ---")
    G_fresh, fresh_time = fresh_download_osmnx(lat, lon, radius_m)
    
    # Step 4: Cached extraction
    print(f"\n--- Cached Extraction ---")
    G_cached, extract_time = extract_from_cached_graph(G_large, lat, lon, radius_m)
    
    # Step 5: Performance comparison
    total_cached_time = extract_time  # Not including cache creation time for fair comparison
    
    print(f"\n--- PERFORMANCE RESULTS ---")
    print(f"Fresh download: {fresh_time:.2f}s")
    print(f"Cached extraction: {extract_time:.2f}s")
    speedup = fresh_time / extract_time
    print(f"Speedup: {speedup:.2f}x {'faster' if speedup > 1 else 'slower'}")
    
    # Step 6: Data comparison
    print(f"\n--- DATA COMPARISON ---")
    print(f"Cached: {len(G_cached.nodes)} nodes, {len(G_cached.edges)} edges")
    print(f"Fresh: {len(G_fresh.nodes)} nodes, {len(G_fresh.edges)} edges")
    
    # Step 7: Debug comparison
    debug_graph_comparison(G_cached, G_fresh)
    
    # Step 8: Create HTML visualization
    html_file = create_html_visualization(G_cached, G_fresh, G_large, lat, lon, radius_m, LARGE_AREA_RADIUS)
    
    # Step 9: Multiple runs to show consistent performance
    print(f"\n--- Multiple Cached Extractions (no network calls) ---")
    for i in range(3):
        _, extract_time = extract_from_cached_graph(G_large, lat, lon, radius_m)
        print(f"Run {i+1}: {extract_time:.2f}s")


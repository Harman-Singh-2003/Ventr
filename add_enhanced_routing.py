import nbformat as nbf

# Read the existing notebook
with open('safe_routing_algorithm.ipynb', 'r') as f:
    nb = nbf.read(f, as_version=4)

# Add markdown cell for new section
new_markdown = nbf.v4.new_markdown_cell("""## Step 7: Enhanced Street-Level Safe Routing

Now let's implement proper street-level routing that follows actual walking paths and considers crime density when choosing between different street routes.""")

# Read the enhanced routing code
with open('street_routing_enhanced.py', 'r') as f:
    enhanced_code = f.read()

# Add code cell with enhanced routing
new_code = nbf.v4.new_code_cell(enhanced_code)

# Add demonstration cell
demo_code = """# Demonstrate the enhanced street-level routing
print("Setting up Enhanced Street-Level Safe Routing...")

# Initialize the enhanced router
try:
    street_router = StreetLevelSafeRouter(crime_df, crime_clusters)
    print("✅ Street router initialized successfully")
    
    # Test with a route in downtown Toronto core
    print("\\nTesting street-level routing...")
    
    # Example coordinates within Toronto core
    start_coords = (43.65, -79.38)  # Financial District
    end_coords = (43.66, -79.39)    # Entertainment District
    
    print(f"Route: {start_coords} → {end_coords}")
    
    # Find safe route
    route_coords, route_info = street_router.find_safe_route(
        start_coords, end_coords, route_type='safest'
    )
    
    # Display results
    if route_coords and len(route_coords) > 2:
        print("\\n" + "="*60)
        print("ENHANCED STREET-LEVEL ROUTING RESULTS")
        print("="*60)
        print(f"Route follows {route_info['num_segments']} street segments")
        print(f"Total distance: {route_info['distance_km']:.2f} km")
        print(f"Average risk per segment: {route_info['avg_risk']:.2f}")
        print(f"\\nComparison with shortest route:")
        print(f"  📏 Distance increase: {route_info['distance_increase_percent']:.1f}%")
        print(f"  🛡️  Risk reduction: {route_info['risk_reduction_percent']:.1f}%")
        
        if route_info['risk_reduction_percent'] > 0:
            print(f"\\n✅ Found safer route with {route_info['risk_reduction_percent']:.1f}% risk reduction!")
        else:
            print(f"\\n⚠️  Shortest route is already the safest option.")
        
        # Create visualization
        print("\\nCreating enhanced route visualization...")
        route_map = street_router.visualize_route(
            route_coords, route_info, start_coords, end_coords
        )
        
        # Save map
        enhanced_map_filename = 'enhanced_street_route.html'
        route_map.save(enhanced_map_filename)
        print(f"Enhanced route map saved as: {enhanced_map_filename}")
        
        # Display map in notebook
        route_map
    else:
        print("⚠️  Using fallback routing - street network may not be available")
        
except Exception as e:
    print(f"❌ Error in enhanced routing: {e}")
    print("The enhanced routing requires a street network download which may take time.")"""

demo_cell = nbf.v4.new_code_cell(demo_code)

# Add interactive function cell
interactive_code = """def plan_enhanced_safe_route(start_lat, start_lon, end_lat, end_lon, route_type='safest', show_map=True):
    '''
    Plan a safe route using enhanced street-level routing
    
    Args:
        start_lat, start_lon: Starting coordinates
        end_lat, end_lon: Ending coordinates  
        route_type: 'safest', 'shortest', or 'balanced'
        show_map: Whether to create and display a map
        
    Returns:
        Dictionary with enhanced route information
    '''
    
    print(f"Planning enhanced safe route from ({start_lat}, {start_lon}) to ({end_lat}, {end_lon})")
    print(f"Route type: {route_type}")
    
    # Check if coordinates are in reasonable Toronto area
    toronto_bounds = {'lat_min': 43.6, 'lat_max': 43.7, 'lon_min': -79.5, 'lon_max': -79.3}
    
    if not (toronto_bounds['lat_min'] <= start_lat <= toronto_bounds['lat_max'] and 
            toronto_bounds['lat_min'] <= end_lat <= toronto_bounds['lat_max'] and
            toronto_bounds['lon_min'] <= start_lon <= toronto_bounds['lon_max'] and
            toronto_bounds['lon_min'] <= end_lon <= toronto_bounds['lon_max']):
        print("⚠️  WARNING: Coordinates may be outside Toronto core area.")
        print(f"Recommended range: Lat {toronto_bounds['lat_min']} to {toronto_bounds['lat_max']}, Lon {toronto_bounds['lon_min']} to {toronto_bounds['lon_max']}")
    
    try:
        # Use the street router
        if 'street_router' not in globals():
            print("Initializing street router...")
            global street_router
            street_router = StreetLevelSafeRouter(crime_df, crime_clusters)
        
        # Calculate route
        start_coords = (start_lat, start_lon)
        end_coords = (end_lat, end_lon)
        
        route_coords, route_info = street_router.find_safe_route(start_coords, end_coords, route_type)
        
        # Create result summary
        result = {
            'start': start_coords,
            'end': end_coords,
            'route_coords': route_coords,
            'route_type': route_type,
            'follows_streets': len(route_coords) > 2,
            **route_info  # Include all route_info data
        }
        
        # Print detailed results
        print("\\n" + "="*50)
        print("ENHANCED ROUTE PLANNING RESULTS")
        print("="*50)
        
        if result['follows_streets']:
            print(f"🛣️  Route follows {result['num_segments']} street segments")
            print(f"📏 Total distance: {result['distance_km']:.2f} km")
            print(f"🛡️  Average risk: {result['avg_risk']:.2f} per segment")
            print(f"\\n📊 Comparison with shortest route:")
            print(f"   Distance increase: +{result['distance_increase_percent']:.1f}%")
            print(f"   Risk reduction: -{result['risk_reduction_percent']:.1f}%")
            
            if result['risk_reduction_percent'] > 5:
                print(f"\\n✅ Significantly safer route found!")
            elif result['risk_reduction_percent'] > 0:
                print(f"\\n✅ Slightly safer route found")
            else:
                print(f"\\n⚠️  Shortest route is already safest")
        else:
            print(f"📏 Direct route distance: {result['distance_km']:.2f} km")
            print(f"⚠️  Using direct routing (street network unavailable)")
        
        # Create map if requested
        if show_map:
            print("\\nCreating interactive route map...")
            
            if result['follows_streets']:
                route_map = street_router.visualize_route(
                    route_coords, route_info, start_coords, end_coords
                )
            else:
                # Fallback map creation
                center_lat = (start_lat + end_lat) / 2
                center_lon = (start_lon + end_lon) / 2
                
                route_map = folium.Map(location=[center_lat, center_lon], zoom_start=14)
                
                # Add markers and route
                folium.Marker(start_coords, popup="Start", icon=folium.Icon(color='green')).add_to(route_map)
                folium.Marker(end_coords, popup="End", icon=folium.Icon(color='red')).add_to(route_map)
                folium.PolyLine(locations=route_coords, color='blue', weight=4).add_to(route_map)
            
            # Save map
            map_filename = f'enhanced_route_{start_lat}_{start_lon}_to_{end_lat}_{end_lon}.html'
            route_map.save(map_filename)
            print(f"Map saved as: {map_filename}")
            
            result['map'] = route_map
            result['map_filename'] = map_filename
        
        return result
        
    except Exception as e:
        print(f"❌ Error in enhanced routing: {e}")
        return None

# Test the enhanced routing function
print("Enhanced routing function ready! Try:")
print("result = plan_enhanced_safe_route(43.651, -79.383, 43.661, -79.390)")"""

interactive_cell = nbf.v4.new_code_cell(interactive_code)

# Add cells to notebook
nb.cells.extend([new_markdown, new_code, demo_cell, interactive_cell])

# Save the updated notebook
with open('safe_routing_algorithm.ipynb', 'w') as f:
    nbf.write(nb, f)

print('✅ Enhanced street-level routing added to notebook!')
print('Added 4 new cells:')
print('1. Markdown introduction')
print('2. StreetLevelSafeRouter class definition')  
print('3. Demonstration code')
print('4. Interactive planning function') 
import osmnx as ox
import networkx as nx
import numpy as np
import folium
from scipy.spatial.distance import cdist
import pandas as pd

class StreetLevelSafeRouter:
    """
    Enhanced routing that follows actual streets and considers crime density
    """
    
    def __init__(self, crime_data, crime_clusters, street_graph=None):
        """
        Initialize the street-level safe router
        
        Args:
            crime_data: DataFrame with crime locations
            crime_clusters: DataFrame with crime cluster data
            street_graph: OSMnx street network graph
        """
        self.crime_data = crime_data
        self.crime_clusters = crime_clusters
        self.street_graph = street_graph
        
        # Build spatial index for crime clusters
        if len(crime_clusters) > 0:
            self.cluster_coords = crime_clusters[['center_lat', 'center_lon']].values
            self.cluster_scores = crime_clusters['density_score'].values
        else:
            self.cluster_coords = np.array([])
            self.cluster_scores = np.array([])
    
    def load_toronto_street_network(self, use_cache=True):
        """
        Load Toronto street network with reasonable bounds
        """
        # Focus on Toronto core for manageable size
        toronto_bbox = (43.70, 43.62, -79.30, -79.50)  # N, S, E, W
        
        print(f"Loading Toronto street network...")
        print(f"Bounding box: {toronto_bbox}")
        print(f"Area: ~{(toronto_bbox[0]-toronto_bbox[1])*111:.1f}km x {(toronto_bbox[3]-toronto_bbox[2])*85:.1f}km")
        
        try:
            # Load walking network
            G = ox.graph_from_bbox(toronto_bbox, network_type='walk', simplify=True)
            
            # Add crime risk to edges
            G = self._add_crime_risk_to_edges(G)
            
            print(f"Loaded {len(G.nodes)} nodes and {len(G.edges)} edges")
            self.street_graph = G
            return G
            
        except Exception as e:
            print(f"Error loading street network: {e}")
            return None
    
    def _add_crime_risk_to_edges(self, G):
        """
        Add crime risk scores to street network edges
        """
        print("Adding crime risk data to street edges...")
        
        for u, v, key, data in G.edges(keys=True, data=True):
            # Get edge coordinates
            if 'geometry' in data:
                # Use geometry if available
                coords = [(point[1], point[0]) for point in data['geometry'].coords]
            else:
                # Use node coordinates
                start_node = G.nodes[u]
                end_node = G.nodes[v]
                coords = [(start_node['y'], start_node['x']), 
                         (end_node['y'], end_node['x'])]
            
            # Calculate risk for this edge
            edge_risk = self._calculate_edge_risk(coords)
            
            # Add risk to edge data
            G[u][v][key]['crime_risk'] = edge_risk
            
            # Modify edge weight to include crime risk
            original_length = data.get('length', 100)  # meters
            
            # Crime risk penalty (adjust multiplier as needed)
            risk_penalty = 1 + (edge_risk * 0.01)  # 1% penalty per risk point
            
            # New weight combines distance and risk
            G[u][v][key]['safe_weight'] = original_length * risk_penalty
        
        print("Crime risk data added to all edges")
        return G
    
    def _calculate_edge_risk(self, coords, sample_points=3):
        """
        Calculate crime risk for a street edge by sampling points along it
        """
        if len(self.cluster_coords) == 0:
            return 0
        
        total_risk = 0
        
        # Sample points along the edge
        for i in range(sample_points):
            if len(coords) == 2:
                # Linear interpolation for straight edge
                t = i / max(1, sample_points - 1)
                lat = coords[0][0] + t * (coords[1][0] - coords[0][0])
                lon = coords[0][1] + t * (coords[1][1] - coords[0][1])
            else:
                # Use actual point from geometry
                idx = min(i, len(coords) - 1)
                lat, lon = coords[idx]
            
            # Calculate risk at this point
            point_risk = self._calculate_point_risk(lat, lon)
            total_risk += point_risk
        
        return total_risk / sample_points
    
    def _calculate_point_risk(self, lat, lon, influence_radius=0.002):
        """
        Calculate crime risk at a specific point
        """
        if len(self.cluster_coords) == 0:
            return 0
        
        # Calculate distances to all crime clusters
        point = np.array([[lat, lon]])
        distances = cdist(point, self.cluster_coords)[0]
        
        # Calculate influence of nearby clusters
        risk_score = 0
        for i, distance in enumerate(distances):
            if distance <= influence_radius:
                # Closer clusters have more influence
                influence = max(0, 1 - (distance / influence_radius))
                risk_score += self.cluster_scores[i] * influence
        
        return risk_score
    
    def find_safe_route(self, start_coords, end_coords, route_type='safest'):
        """
        Find a safe route using street network
        
        Args:
            start_coords: (lat, lon) tuple for start
            end_coords: (lat, lon) tuple for end
            route_type: 'safest', 'shortest', or 'balanced'
        
        Returns:
            route_coords: List of (lat, lon) coordinates following streets
            route_info: Dictionary with route statistics
        """
        if self.street_graph is None:
            print("No street network loaded. Loading Toronto network...")
            if self.load_toronto_street_network() is None:
                return self._fallback_route(start_coords, end_coords)
        
        try:
            # Find nearest nodes to start and end points
            start_node = ox.nearest_nodes(self.street_graph, start_coords[1], start_coords[0])
            end_node = ox.nearest_nodes(self.street_graph, end_coords[1], end_coords[0])
            
            # Choose weight based on route type
            if route_type == 'shortest':
                weight = 'length'
            elif route_type == 'safest':
                weight = 'safe_weight'
            else:  # balanced
                weight = 'safe_weight'
            
            # Calculate route
            route_nodes = nx.shortest_path(self.street_graph, start_node, end_node, weight=weight)
            
            # Convert to coordinates
            route_coords = []
            total_distance = 0
            total_risk = 0
            
            for i, node in enumerate(route_nodes):
                node_data = self.street_graph.nodes[node]
                route_coords.append((node_data['y'], node_data['x']))
                
                # Calculate edge statistics
                if i > 0:
                    prev_node = route_nodes[i-1]
                    edge_data = self.street_graph[prev_node][node][0]  # Get first edge
                    total_distance += edge_data.get('length', 0)
                    total_risk += edge_data.get('crime_risk', 0)
            
            # Calculate comparison with shortest route
            shortest_nodes = nx.shortest_path(self.street_graph, start_node, end_node, weight='length')
            shortest_distance = nx.shortest_path_length(self.street_graph, start_node, end_node, weight='length')
            
            # Calculate shortest route risk
            shortest_risk = 0
            for i in range(len(shortest_nodes) - 1):
                edge_data = self.street_graph[shortest_nodes[i]][shortest_nodes[i+1]][0]
                shortest_risk += edge_data.get('crime_risk', 0)
            
            route_info = {
                'distance_m': total_distance,
                'distance_km': total_distance / 1000,
                'total_risk': total_risk,
                'avg_risk': total_risk / max(len(route_nodes) - 1, 1),
                'shortest_distance_m': shortest_distance,
                'shortest_risk': shortest_risk,
                'distance_increase_m': total_distance - shortest_distance,
                'distance_increase_percent': ((total_distance - shortest_distance) / shortest_distance) * 100,
                'risk_reduction': shortest_risk - total_risk,
                'risk_reduction_percent': ((shortest_risk - total_risk) / max(shortest_risk, 0.001)) * 100,
                'num_segments': len(route_nodes) - 1
            }
            
            return route_coords, route_info
            
        except Exception as e:
            print(f"Error in street routing: {e}")
            return self._fallback_route(start_coords, end_coords)
    
    def _fallback_route(self, start_coords, end_coords):
        """
        Fallback to simple routing if street network fails
        """
        print("Using fallback routing (direct line)")
        route_coords = [start_coords, end_coords]
        
        # Calculate basic stats
        distance = np.sqrt((end_coords[0] - start_coords[0])**2 + 
                          (end_coords[1] - start_coords[1])**2) * 111000  # rough meters
        
        route_info = {
            'distance_m': distance,
            'distance_km': distance / 1000,
            'total_risk': 0,
            'avg_risk': 0,
            'shortest_distance_m': distance,
            'shortest_risk': 0,
            'distance_increase_m': 0,
            'distance_increase_percent': 0,
            'risk_reduction': 0,
            'risk_reduction_percent': 0,
            'num_segments': 1
        }
        
        return route_coords, route_info
    
    def visualize_route(self, route_coords, route_info, start_coords, end_coords, 
                       show_crime_data=True, show_streets=True):
        """
        Create an interactive map showing the route
        """
        # Create map centered on route
        center_lat = (start_coords[0] + end_coords[0]) / 2
        center_lon = (start_coords[1] + end_coords[1]) / 2
        
        route_map = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=15,
            tiles='OpenStreetMap'
        )
        
        # Add crime heatmap if requested
        if show_crime_data and len(self.crime_data) > 0:
            sample_size = min(500, len(self.crime_data))
            crime_sample = self.crime_data.sample(sample_size)
            heat_data = [[row['latitude'], row['longitude']] for _, row in crime_sample.iterrows()]
            folium.plugins.HeatMap(heat_data, radius=8, blur=10).add_to(route_map)
        
        # Add crime clusters
        if show_crime_data and len(self.crime_clusters) > 0:
            for _, cluster in self.crime_clusters.iterrows():
                folium.CircleMarker(
                    location=[cluster['center_lat'], cluster['center_lon']],
                    radius=min(cluster['crime_count']/3, 15),
                    popup=f"Crime Cluster: {cluster['crime_count']} incidents",
                    color='red',
                    fillColor='red',
                    fillOpacity=0.6
                ).add_to(route_map)
        
        # Add start and end markers
        folium.Marker(
            start_coords,
            popup="Start",
            icon=folium.Icon(color='green', icon='play')
        ).add_to(route_map)
        
        folium.Marker(
            end_coords,
            popup="End", 
            icon=folium.Icon(color='red', icon='stop')
        ).add_to(route_map)
        
        # Add route
        folium.PolyLine(
            locations=route_coords,
            color='blue',
            weight=4,
            opacity=0.8,
            popup=f"Safe Route: {route_info['distance_km']:.2f}km, Risk: {route_info['avg_risk']:.2f}"
        ).add_to(route_map)
        
        # Add route info
        info_html = f"""
        <div style="position: fixed; top: 10px; left: 10px; width: 300px; 
                    background-color: white; border: 2px solid grey; z-index: 9999; 
                    font-size: 12px; padding: 10px;">
        <h4>Route Information</h4>
        <p><b>Distance:</b> {route_info['distance_km']:.2f} km</p>
        <p><b>Average Risk:</b> {route_info['avg_risk']:.2f}</p>
        <p><b>vs Shortest Route:</b></p>
        <p>  • Distance increase: {route_info['distance_increase_percent']:.1f}%</p>
        <p>  • Risk reduction: {route_info['risk_reduction_percent']:.1f}%</p>
        </div>
        """
        route_map.get_root().html.add_child(folium.Element(info_html))
        
        return route_map

# Example usage function
def demonstrate_street_routing(crime_df, crime_clusters):
    """
    Demonstrate the enhanced street-level routing
    """
    print("Initializing Street-Level Safe Router...")
    
    # Initialize router
    router = StreetLevelSafeRouter(crime_df, crime_clusters)
    
    # Load street network
    street_graph = router.load_toronto_street_network()
    
    if street_graph is None:
        print("Failed to load street network")
        return None
    
    # Test route in downtown Toronto
    start_coords = (43.651, -79.383)  # Near CN Tower
    end_coords = (43.661, -79.390)    # Near Kensington Market
    
    print(f"\nTesting route from {start_coords} to {end_coords}")
    
    # Find safe route
    route_coords, route_info = router.find_safe_route(start_coords, end_coords, 'safest')
    
    # Print results
    print("\n" + "="*50)
    print("STREET-LEVEL SAFE ROUTING RESULTS")
    print("="*50)
    print(f"Route distance: {route_info['distance_km']:.2f} km")
    print(f"Route segments: {route_info['num_segments']}")
    print(f"Average risk per segment: {route_info['avg_risk']:.2f}")
    print(f"Total risk score: {route_info['total_risk']:.2f}")
    print(f"\nComparison with shortest route:")
    print(f"  Distance increase: {route_info['distance_increase_percent']:.1f}%")
    print(f"  Risk reduction: {route_info['risk_reduction_percent']:.1f}%")
    
    # Create visualization
    route_map = router.visualize_route(route_coords, route_info, start_coords, end_coords)
    
    # Save map
    map_filename = 'street_level_safe_route.html'
    route_map.save(map_filename)
    print(f"\nStreet-level route map saved as: {map_filename}")
    
    return router, route_coords, route_info, route_map

print("Street-level safe routing module ready!") 
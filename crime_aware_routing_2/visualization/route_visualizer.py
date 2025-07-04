"""
Route visualization tools for creating interactive HTML maps with crime data overlay.
"""

import logging
import json
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
import folium
import numpy as np
from ..algorithms.routing.astar_weighted import RouteDetails
from ..algorithms.crime_weighting.kde_weighter import CrimeSurface
from ..config.routing_config import RoutingConfig

logger = logging.getLogger(__name__)


class RouteVisualizer:
    """
    Create interactive HTML visualizations for route comparison and analysis.
    """
    
    def __init__(self, config: Optional[RoutingConfig] = None):
        """
        Initialize route visualizer.
        
        Args:
            config: Routing configuration for styling options
        """
        self.config = config or RoutingConfig()
        
    def create_comparison_map(self, routes: Dict[str, RouteDetails],
                            crime_surface: Optional[CrimeSurface] = None,
                            crime_points: Optional[np.ndarray] = None,
                            center_coords: Optional[Tuple[float, float]] = None,
                            route_colors: Optional[Dict[str, str]] = None) -> folium.Map:
        """
        Create interactive map comparing multiple routes.
        
        Args:
            routes: Dictionary mapping algorithm names to RouteDetails
            crime_surface: KDE crime surface for heatmap overlay
            crime_points: Raw crime point data for markers
            center_coords: Map center coordinates (lat, lon)
            route_colors: Optional dictionary mapping route names to colors
            
        Returns:
            Folium map object
        """
        if not routes:
            raise ValueError("No routes provided for visualization")
        
        # Determine map center and bounds
        if center_coords is None:
            center_coords = self._calculate_map_center(routes)
        
        # Initialize map
        m = folium.Map(
            location=center_coords,
            zoom_start=14,
            tiles=self.config.map_style
        )
        
        # Add crime heatmap if available
        if crime_surface is not None:
            self._add_crime_heatmap(m, crime_surface)
        
        # Add crime points if available
        if crime_points is not None and len(crime_points) > 0:
            self._add_crime_points(m, crime_points)
        
        # Add route layers
        for algorithm, route in routes.items():
            self._add_route_layer(m, route, algorithm, route_colors)
        
        # Add start/end markers
        self._add_start_end_markers(m, routes)
        
        # Add legend
        self._add_legend(m, routes)
        
        # Fit map to show all routes
        self._fit_map_to_routes(m, routes)
        
        return m
    
    def _calculate_map_center(self, routes: Dict[str, RouteDetails]) -> Tuple[float, float]:
        """Calculate optimal map center from route coordinates."""
        all_coords = []
        for route in routes.values():
            all_coords.extend(route.coordinates)
        
        if not all_coords:
            return (43.6532, -79.3832)  # Default to Toronto center
        
        lats = [coord[0] for coord in all_coords]
        lons = [coord[1] for coord in all_coords]
        
        return (float(np.mean(lats)), float(np.mean(lons)))
    
    def _add_crime_heatmap(self, m: folium.Map, crime_surface: CrimeSurface) -> None:
        """Add crime density heatmap overlay to map."""
        try:
            # Create heatmap data from crime surface
            heat_data = []
            
            # Sample the crime surface at regular intervals
            lat_step = max(1, len(crime_surface.lat_grid) // 50)  # Limit to ~50 points per dimension
            lon_step = max(1, len(crime_surface.lon_grid) // 50)
            
            for i in range(0, len(crime_surface.lat_grid), lat_step):
                for j in range(0, len(crime_surface.lon_grid), lon_step):
                    lat = crime_surface.lat_grid[i]
                    lon = crime_surface.lon_grid[j]
                    density = crime_surface.density_values[i, j]
                    
                    if density > 0.1:  # Only include significant density values
                        heat_data.append([lat, lon, density])
            
            if heat_data:
                # Add heatmap layer
                from folium.plugins import HeatMap
                HeatMap(
                    heat_data,
                    name='Crime Density',
                    radius=15,
                    blur=20,
                    max_zoom=1,
                    gradient={
                        0.0: 'blue',
                        0.3: 'lime', 
                        0.5: 'yellow',
                        0.7: 'orange',
                        1.0: 'red'
                    }
                ).add_to(m)
                
                logger.debug(f"Added crime heatmap with {len(heat_data)} points")
            
        except Exception as e:
            logger.warning(f"Failed to add crime heatmap: {e}")
    
    def _add_crime_points(self, m: folium.Map, crime_points: np.ndarray, 
                         max_points: int = 500) -> None:
        """Add individual crime incident markers to map."""
        try:
            # Limit number of points for performance
            if len(crime_points) > max_points:
                # Sample random subset
                indices = np.random.choice(len(crime_points), max_points, replace=False)
                sampled_points = crime_points[indices]
            else:
                sampled_points = crime_points
            
            # Create marker cluster for crime points
            from folium.plugins import MarkerCluster
            crime_cluster = MarkerCluster(name='Crime Incidents')
            
            for point in sampled_points:
                lat, lon = point[0], point[1]
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=3,
                    popup='Crime Incident',
                    color='red',
                    fill=True,
                    fillOpacity=0.6
                ).add_to(crime_cluster)
            
            crime_cluster.add_to(m)
            logger.debug(f"Added {len(sampled_points)} crime point markers")
            
        except Exception as e:
            logger.warning(f"Failed to add crime points: {e}")
    
    def _add_route_layer(self, m: folium.Map, route: RouteDetails, algorithm: str, 
                        route_colors: Optional[Dict[str, str]] = None) -> None:
        """Add a route as a colored line on the map."""
        try:
            # Get route color - prefer custom colors over config colors
            if route_colors and algorithm in route_colors:
                color = route_colors[algorithm]
            else:
                color = self.config.route_colors.get(algorithm, '#000000')
            
            # Create route line
            folium.PolyLine(
                locations=route.coordinates,
                color=color,
                weight=4,
                opacity=0.8,
                popup=self._create_route_popup(route, algorithm)
            ).add_to(m)
            
            logger.debug(f"Added {algorithm} route with {len(route.coordinates)} points")
            
        except Exception as e:
            logger.warning(f"Failed to add route layer for {algorithm}: {e}")
    
    def _create_route_popup(self, route: RouteDetails, algorithm: str) -> str:
        """Create HTML popup content for a route."""
        summary = route.get_summary()
        
        popup_html = f"""
        <div style="width: 200px;">
            <h4>{algorithm.replace('_', ' ').title()}</h4>
            <p><strong>Distance:</strong> {summary['total_distance_m']:.0f}m</p>
            <p><strong>Nodes:</strong> {summary['node_count']}</p>
            <p><strong>Avg Crime Score:</strong> {summary['average_crime_score']:.3f}</p>
            <p><strong>Max Crime Score:</strong> {summary['max_crime_score']:.3f}</p>
            <p><strong>Calc Time:</strong> {summary['calculation_time_ms']:.1f}ms</p>
        </div>
        """
        
        return popup_html
    
    def _add_start_end_markers(self, m: folium.Map, routes: Dict[str, RouteDetails]) -> None:
        """Add start and end point markers."""
        if not routes:
            return
        
        # Get coordinates from first route
        first_route = next(iter(routes.values()))
        if not first_route.coordinates:
            return
        
        start_coord = first_route.coordinates[0]
        end_coord = first_route.coordinates[-1]
        
        # Start marker (green)
        folium.Marker(
            location=start_coord,
            popup='Start Point',
            icon=folium.Icon(color='green', icon='play')
        ).add_to(m)
        
        # End marker (red)
        folium.Marker(
            location=end_coord,
            popup='End Point',
            icon=folium.Icon(color='red', icon='stop')
        ).add_to(m)
    
    def _add_legend(self, m: folium.Map, routes: Dict[str, RouteDetails]) -> None:
        """Add legend explaining route colors and metrics."""
        legend_html = self._create_legend_html(routes)
        m.get_root().add_child(folium.Element(legend_html))
    
    def _create_legend_html(self, routes: Dict[str, RouteDetails]) -> str:
        """Create HTML legend for the map."""
        legend_items = []
        
        for algorithm, route in routes.items():
            color = self.config.route_colors.get(algorithm, '#000000')
            summary = route.get_summary()
            
            legend_items.append(f"""
                <div style="margin-bottom: 8px;">
                    <span style="background-color: {color}; 
                                 width: 20px; height: 4px; 
                                 display: inline-block; margin-right: 8px;"></span>
                    <strong>{algorithm.replace('_', ' ').title()}</strong><br>
                    <small>{summary['total_distance_m']:.0f}m • 
                           Crime: {summary['average_crime_score']:.3f}</small>
                </div>
            """)
        
        legend_html = f"""
        <div style="position: fixed; 
                   bottom: 50px; left: 50px; width: 200px; height: auto; 
                   background-color: white; border:2px solid grey; z-index:9999; 
                   font-size:14px; padding: 10px;">
            <h4 style="margin-top: 0;">Route Comparison</h4>
            {''.join(legend_items)}
        </div>
        """
        
        return legend_html
    
    def _fit_map_to_routes(self, m: folium.Map, routes: Dict[str, RouteDetails]) -> None:
        """Adjust map zoom and center to show all routes."""
        all_coords = []
        for route in routes.values():
            all_coords.extend(route.coordinates)
        
        if len(all_coords) > 1:
            # Calculate bounds
            lats = [coord[0] for coord in all_coords]
            lons = [coord[1] for coord in all_coords]
            
            # Add small buffer
            lat_buffer = (max(lats) - min(lats)) * 0.1
            lon_buffer = (max(lons) - min(lons)) * 0.1
            
            bounds = [
                [min(lats) - lat_buffer, min(lons) - lon_buffer],
                [max(lats) + lat_buffer, max(lons) + lon_buffer]
            ]
            
            m.fit_bounds(bounds)
    
    def save_interactive_html(self, map_obj: folium.Map, filepath: str) -> None:
        """
        Save interactive map to HTML file.
        
        Args:
            map_obj: Folium map object
            filepath: Output file path
        """
        try:
            # Ensure directory exists
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            
            # Save map
            map_obj.save(filepath)
            logger.info(f"Interactive map saved to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save map to {filepath}: {e}")
            raise
    
    def generate_route_comparison_report(self, routes: Dict[str, RouteDetails],
                                       analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate comprehensive route comparison report.
        
        Args:
            routes: Dictionary of routes
            analysis: Route analysis results
            
        Returns:
            Formatted report data
        """
        report = {
            'summary': {
                'total_routes': len(routes),
                'algorithms_used': list(routes.keys()),
                'recommendation': analysis.get('recommendation', {})
            },
            'route_details': {},
            'comparative_metrics': {},
            'safety_analysis': {}
        }
        
        # Route details
        for algorithm, route in routes.items():
            summary = route.get_summary()
            report['route_details'][algorithm] = {
                'distance_m': summary['total_distance_m'],
                'node_count': summary['node_count'],
                'calculation_time_ms': summary['calculation_time_ms'],
                'average_crime_score': summary['average_crime_score'],
                'max_crime_score': summary['max_crime_score']
            }
        
        # Comparative metrics
        summaries = analysis.get('route_summaries', {})
        if summaries:
            distances = [s['total_distance_m'] for s in summaries.values()]
            crime_scores = [s.get('average_crime_score', 0) for s in summaries.values()]
            
            report['comparative_metrics'] = {
                'distance_range': {
                    'min_m': min(distances),
                    'max_m': max(distances),
                    'range_m': max(distances) - min(distances)
                },
                'safety_range': {
                    'safest_score': min(crime_scores),
                    'riskiest_score': max(crime_scores),
                    'safety_spread': max(crime_scores) - min(crime_scores)
                }
            }
        
        # Safety analysis
        report['safety_analysis'] = self._analyze_route_safety(routes)
        
        return report
    
    def _analyze_route_safety(self, routes: Dict[str, RouteDetails]) -> Dict[str, Any]:
        """Analyze safety characteristics of routes."""
        safety_analysis = {
            'route_safety_scores': {},
            'high_risk_segments': {},
            'safety_recommendation': ''
        }
        
        for algorithm, route in routes.items():
            if route.crime_scores:
                safety_analysis['route_safety_scores'][algorithm] = {
                    'average': np.mean(route.crime_scores),
                    'maximum': np.max(route.crime_scores),
                    'std_dev': np.std(route.crime_scores),
                    'high_risk_segments': sum(1 for score in route.crime_scores if score > 0.7)
                }
        
        # Generate safety recommendation
        if safety_analysis['route_safety_scores']:
            safest_route = min(
                safety_analysis['route_safety_scores'].items(),
                key=lambda x: x[1]['average']
            )
            safety_analysis['safety_recommendation'] = f"{safest_route[0]} appears to be the safest option"
        
        return safety_analysis 
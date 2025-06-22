#!/usr/bin/env python3
"""
Routing Methods Performance Summary
Creates a visual summary of all routing algorithm performance across test routes.
"""

import matplotlib.pyplot as plt
import numpy as np

def create_routing_summary():
    """Create summary charts of routing algorithm performance."""
    
    # Test results data from the comprehensive tests
    test_data = {
        'CN Tower to Union Station': {
            'Shortest Path': {'distance': 662, 'crime_exp': 58, 'time': 8.3},
            'Exponential Decay': {'distance': 662, 'crime_exp': 58, 'time': 8.3},
            'Linear Penalty': {'distance': 662, 'crime_exp': 0, 'time': 8.3},
            'Threshold Avoidance': {'distance': 777, 'crime_exp': 0, 'time': 9.7},
            'Raw Data Weighted': {'distance': 662, 'crime_exp': 244, 'time': 8.3}
        },
        'Union Station to City Hall': {
            'Shortest Path': {'distance': 1134, 'crime_exp': 923, 'time': 14.2},
            'Exponential Decay': {'distance': 1510, 'crime_exp': 152, 'time': 18.9},
            'Linear Penalty': {'distance': 1515, 'crime_exp': 0, 'time': 18.9},
            'Threshold Avoidance': {'distance': 1585, 'crime_exp': 0, 'time': 19.8},
            'Raw Data Weighted': {'distance': 1307, 'crime_exp': 551, 'time': 16.3}
        },
        'City Hall to St. Lawrence Market': {
            'Shortest Path': {'distance': 1497, 'crime_exp': 381, 'time': 18.7},
            'Exponential Decay': {'distance': 2019, 'crime_exp': 237, 'time': 25.2},
            'Linear Penalty': {'distance': 2131, 'crime_exp': 0, 'time': 26.6},
            'Threshold Avoidance': {'distance': 2016, 'crime_exp': 0, 'time': 25.2},
            'Raw Data Weighted': {'distance': 1555, 'crime_exp': 353, 'time': 19.4}
        },
        'St. Lawrence Market to Harbourfront': {
            'Shortest Path': {'distance': 1676, 'crime_exp': 335, 'time': 20.9},
            'Exponential Decay': {'distance': 1889, 'crime_exp': 121, 'time': 23.6},
            'Linear Penalty': {'distance': 1895, 'crime_exp': 0, 'time': 23.7},
            'Threshold Avoidance': {'distance': 2061, 'crime_exp': 0, 'time': 25.8},
            'Raw Data Weighted': {'distance': 1846, 'crime_exp': 211, 'time': 23.1}
        },
        'CN Tower to Harbourfront': {
            'Shortest Path': {'distance': 818, 'crime_exp': 105, 'time': 10.2},
            'Exponential Decay': {'distance': 910, 'crime_exp': 9, 'time': 11.4},
            'Linear Penalty': {'distance': 1007, 'crime_exp': 0, 'time': 12.6},
            'Threshold Avoidance': {'distance': 1003, 'crime_exp': 0, 'time': 12.5},
            'Raw Data Weighted': {'distance': 1007, 'crime_exp': 17, 'time': 12.6}
        }
    }
    
    # Extract method names and route names
    methods = ['Shortest Path', 'Exponential Decay', 'Linear Penalty', 'Threshold Avoidance', 'Raw Data Weighted']
    routes = list(test_data.keys())
    
    # Create figure with subplots
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle('Crime-Aware Routing Algorithms Performance Summary', fontsize=16, fontweight='bold')
    
    # 1. Distance vs Crime Exposure scatter plot
    colors = ['blue', 'red', 'green', 'orange', 'purple']
    method_colors = dict(zip(methods, colors))
    
    for i, route in enumerate(routes):
        for method in methods:
            data = test_data[route][method]
            ax1.scatter(data['distance'], data['crime_exp'], 
                       color=method_colors[method], alpha=0.7, s=60,
                       label=method if i == 0 else "")
    
    ax1.set_xlabel('Distance (meters)')
    ax1.set_ylabel('Crime Exposure')
    ax1.set_title('Distance vs Crime Exposure Trade-off')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. Average performance by method
    avg_distance_increase = []
    avg_crime_reduction = []
    
    for method in methods:
        distances = []
        crime_reductions = []
        
        for route in routes:
            baseline_distance = test_data[route]['Shortest Path']['distance']
            baseline_crime = test_data[route]['Shortest Path']['crime_exp']
            
            method_distance = test_data[route][method]['distance']
            method_crime = test_data[route][method]['crime_exp']
            
            distance_increase = ((method_distance - baseline_distance) / baseline_distance) * 100
            crime_reduction = ((baseline_crime - method_crime) / max(baseline_crime, 1)) * 100
            
            distances.append(distance_increase)
            crime_reductions.append(crime_reduction)
        
        avg_distance_increase.append(np.mean(distances))
        avg_crime_reduction.append(np.mean(crime_reductions))
    
    x_pos = np.arange(len(methods))
    width = 0.35
    
    bars1 = ax2.bar(x_pos - width/2, avg_distance_increase, width, label='Distance Increase (%)', color='lightcoral')
    bars2 = ax2.bar(x_pos + width/2, avg_crime_reduction, width, label='Crime Reduction (%)', color='lightgreen')
    
    ax2.set_xlabel('Routing Method')
    ax2.set_ylabel('Percentage Change')
    ax2.set_title('Average Performance vs Shortest Path')
    ax2.set_xticks(x_pos)
    ax2.set_xticklabels([m.replace(' ', '\n') for m in methods], fontsize=9)
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Add value labels on bars
    for bar in bars1:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height + 1,
                f'{height:.1f}%', ha='center', va='bottom', fontsize=8)
    
    for bar in bars2:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height + 1,
                f'{height:.1f}%', ha='center', va='bottom', fontsize=8)
    
    # 3. Route length comparison
    route_names_short = ['CN→Union', 'Union→City', 'City→Market', 'Market→Harbour', 'CN→Harbour']
    
    x_pos = np.arange(len(routes))
    width = 0.15
    
    for i, method in enumerate(methods):
        distances = [test_data[route][method]['distance'] for route in routes]
        ax3.bar(x_pos + i*width, distances, width, label=method, color=colors[i], alpha=0.8)
    
    ax3.set_xlabel('Route')
    ax3.set_ylabel('Distance (meters)')
    ax3.set_title('Distance Comparison by Route')
    ax3.set_xticks(x_pos + width * 2)
    ax3.set_xticklabels(route_names_short, rotation=45)
    ax3.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax3.grid(True, alpha=0.3)
    
    # 4. Safety effectiveness (crime reduction vs distance penalty)
    for method in methods[1:]:  # Skip shortest path as baseline
        safety_scores = []
        efficiency_scores = []
        
        for route in routes:
            baseline = test_data[route]['Shortest Path']
            method_data = test_data[route][method]
            
            # Safety score: % crime reduction
            safety = ((baseline['crime_exp'] - method_data['crime_exp']) / max(baseline['crime_exp'], 1)) * 100
            
            # Efficiency score: inverse of % distance increase
            efficiency = 100 - (((method_data['distance'] - baseline['distance']) / baseline['distance']) * 100)
            
            safety_scores.append(safety)
            efficiency_scores.append(efficiency)
        
        avg_safety = np.mean(safety_scores)
        avg_efficiency = np.mean(efficiency_scores)
        
        ax4.scatter(avg_efficiency, avg_safety, color=method_colors[method], s=100, alpha=0.7)
        ax4.annotate(method.replace(' ', '\n'), (avg_efficiency, avg_safety), 
                    xytext=(5, 5), textcoords='offset points', fontsize=9)
    
    ax4.set_xlabel('Route Efficiency (100 - % distance increase)')
    ax4.set_ylabel('Safety Improvement (% crime reduction)')
    ax4.set_title('Safety vs Efficiency Trade-off')
    ax4.grid(True, alpha=0.3)
    ax4.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax4.axvline(x=100, color='gray', linestyle='--', alpha=0.5)
    
    plt.tight_layout()
    plt.savefig('routing_algorithms_summary.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    # Print summary statistics
    print("ROUTING ALGORITHMS PERFORMANCE SUMMARY")
    print("=" * 50)
    
    print(f"\n{'Method':<20} {'Avg Dist Inc':<12} {'Avg Crime Red':<14} {'Best Use Case'}")
    print("-" * 70)
    
    use_cases = {
        'Shortest Path': 'Speed priority',
        'Exponential Decay': 'Balanced approach',
        'Linear Penalty': 'Maximum safety',
        'Threshold Avoidance': 'Clear danger avoidance',
        'Raw Data Weighted': 'Granular risk assessment'
    }
    
    for i, method in enumerate(methods):
        dist_inc = avg_distance_increase[i]
        crime_red = avg_crime_reduction[i]
        use_case = use_cases[method]
        
        print(f"{method:<20} {dist_inc:>8.1f}%{'':<3} {crime_red:>10.1f}%{'':<3} {use_case}")
    
    print(f"\n✅ Summary chart saved as: routing_algorithms_summary.png")

if __name__ == "__main__":
    create_routing_summary() 
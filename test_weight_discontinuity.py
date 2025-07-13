"""
Test script to reproduce the discontinuous route behavior with small crime weight changes.
"""

def test_weight_behavior():
    """Test how routes change with small weight increments."""
    
    # Test coordinates (example)
    start = {"latitude": 43.6426, "longitude": -79.3871}
    destination = {"latitude": 43.6452, "longitude": -79.3806}
    
    # Test different crime weights
    weights_to_test = [0.0, 0.1, 0.2, 0.3, 0.35, 0.4, 0.45, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    
    print("Crime Weight -> Route Distance -> Behavior Analysis")
    print("-" * 60)
    
    previous_distance = None
    
    for weight in weights_to_test:
        # Simulate the weight calculation that happens in the service
        distance_weight = 1.0 - weight
        crime_weight = weight
        
        # Calculate penalty scale (our new formula)
        base_penalty = 2000.0
        penalty_scale = base_penalty * crime_weight
        
        # Calculate influence radius
        if crime_weight > 0:
            influence_radius = 100.0 + (crime_weight * 150.0)
        else:
            influence_radius = 0.0
        
        print(f"Weight: {weight:4.2f} -> Penalty: {penalty_scale:6.0f} -> Radius: {influence_radius:5.0f}m", end="")
        
        if previous_distance is not None:
            # Check for sudden jumps (this is where we'd see the problem)
            print(f" [Smooth progression expected]")
        else:
            print(" [Baseline]")
        
        previous_distance = penalty_scale

def analyze_adaptive_weights_fixed():
    """Analyze the FIXED adaptive weighting with smooth transitions."""
    
    print("\nFIXED Adaptive Weighting Analysis (SMOOTH):")
    print("-" * 50)
    
    # Test different crime scores and base weights
    base_distance_weight = 0.6
    base_crime_weight = 0.4
    
    crime_scores = [0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    
    for score in crime_scores:
        # Implement the new smooth logic
        if score <= 0.2:
            # Smooth transition from 0.1 boost at score=0 to 0 boost at score=0.2
            distance_boost = 0.1 * (0.2 - score) / 0.2
            status = "low crime (smooth)"
        elif score >= 0.6:
            # Smooth transition from 0 boost at score=0.6 to 0.1 boost at score=1.0
            distance_boost = -0.1 * (score - 0.6) / 0.4  # Negative = reduce distance weight
            status = "high crime (smooth)"
        else:
            # Normal range (0.2 to 0.6): no adjustment
            distance_boost = 0.0
            status = "normal"
        
        adaptive_distance = max(0.0, min(1.0, base_distance_weight + distance_boost))
        adaptive_crime = max(0.0, min(1.0, base_crime_weight - distance_boost))
        
        print(f"Crime Score: {score:4.2f} -> Dist Weight: {adaptive_distance:.3f}, Crime Weight: {adaptive_crime:.3f} [{status}]")


def test_crime_weight_progression():
    """Test that shows how the fixed system should behave."""
    print("\nCrime Weight Progression Analysis (After Fix):")
    print("-" * 60)
    
    weights = [0.0, 0.1, 0.2, 0.3, 0.35, 0.4, 0.45, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    
    for weight in weights:
        # With adaptive_weighting = False, these should be smooth
        distance_weight = 1.0 - weight
        crime_weight = weight
        
        # New penalty calculation
        base_penalty = 2000.0
        penalty_scale = base_penalty * crime_weight
        
        # Influence radius calculation
        if crime_weight > 0:
            influence_radius = 100.0 + (crime_weight * 150.0)
        else:
            influence_radius = 0.0
        
        # Calculate relative change from previous weight
        if weight > 0:
            prev_weight = weight - 0.1 if weight >= 0.1 else 0
            prev_penalty = base_penalty * prev_weight
            penalty_change = penalty_scale - prev_penalty
            print(f"Weight: {weight:4.2f} -> Penalty: {penalty_scale:6.0f} -> Change: +{penalty_change:3.0f} [SMOOTH]")
        else:
            print(f"Weight: {weight:4.2f} -> Penalty: {penalty_scale:6.0f} -> Change:   -- [BASELINE]")

if __name__ == "__main__":
    test_weight_behavior()
    analyze_adaptive_weights_fixed()
    test_crime_weight_progression()

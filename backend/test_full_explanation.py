#!/usr/bin/env python
"""Test full explanation generation with conflicts."""

import requests
import json

print("=" * 60)
print("TESTING FULL EXPLANATION GENERATION")
print("=" * 60)

# Step 1: Inject conflicts
print("\nStep 1: Injecting conflicts...")
try:
    r = requests.post('http://localhost:8010/api/v1/conflicts/inject')
    result = r.json()
    print(f"✓ {result['message']}")
    print(f"  Trains affected: {result['trains_affected']}")
except Exception as e:
    print(f"✗ Failed to inject conflicts: {e}")
    exit(1)

# Step 2: Run optimization
print("\nStep 2: Running optimization...")
try:
    r = requests.post('http://localhost:8010/api/v1/optimization/run', json={'include_predictions': True})
    result = r.json()
    print(f"✓ Optimization complete")
    print(f"  Status: {result.get('status', 'unknown')}")
    print(f"  Conflicts resolved: {result.get('conflicts_resolved', 0)}")
    print(f"  Total weighted delay: {result.get('total_weighted_delay', 0):.1f} min")
except Exception as e:
    print(f"✗ Failed to run optimization: {e}")
    exit(1)

# Step 3: Check explanation
print("\nStep 3: Checking explanation in latest plan...")
try:
    r = requests.get('http://localhost:8010/api/v1/optimization/latest-plan')
    data = r.json()
    
    if not data.get('explanation'):
        print("✗ No explanation found")
        exit(1)
    
    exp = data['explanation']
    
    print(f"\n✓ Explanation generated:")
    print(f"  Conflicts detected: {len(exp.get('conflicts_detected', []))}")
    print(f"  Decisions made: {len(exp.get('decisions_made', []))}")
    print(f"  Train actions: {len(exp.get('train_actions', []))}")
    
    if exp.get('objective_improvement'):
        obj = exp['objective_improvement']
        print(f"  Delay reduction: {obj.get('improvement_percent', 0):.1f}%")
    
    # Show sample decision if available
    if exp.get('decisions_made'):
        print(f"\n  Sample decision:")
        decision = exp['decisions_made'][0]
        print(f"    {decision.get('explanation', 'N/A')}")
    
    print("\n" + "=" * 60)
    print("FULL EXPLANATION:")
    print("=" * 60)
    print(json.dumps(exp, indent=2))
    
except Exception as e:
    print(f"✗ Failed to check explanation: {e}")
    exit(1)

print("\n" + "=" * 60)
print("✓ TEST COMPLETE - Refresh dashboard to see full explanation")
print("=" * 60)

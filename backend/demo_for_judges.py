#!/usr/bin/env python
"""
DEMO SCRIPT FOR JUDGES PRESENTATION
====================================

This script demonstrates the full optimization explanation feature by:
1. Resetting the system to a clean state
2. Using the built-in conflict injection to create realistic scenarios
3. Running optimization to generate explanations
4. Displaying what judges will see on the dashboard

Run this before your demo to ensure all explanation sections are populated.
"""

import requests
import json
import time

API_BASE = "http://localhost:8010/api/v1"

def print_header(text):
    print("\n" + "=" * 80)
    print(text.center(80))
    print("=" * 80)

def print_step(step, text):
    print(f"\n[{step}] {text}")

print_header("OPTIMIZATION EXPLANATION DEMO FOR JUDGES")

# Step 1: Reset system
print_step("1/4", "Resetting system to clean state...")
try:
    r = requests.post(f"{API_BASE}/conflicts/reset")
    if r.status_code == 200:
        result = r.json()
        print(f"    ✓ Reset {result.get('trains_reset', 0)} trains")
    else:
        print(f"    ⚠ Reset endpoint returned {r.status_code}")
except Exception as e:
    print(f"    ⚠ Could not reset (may not be needed): {e}")

time.sleep(1)

# Step 2: Inject conflicts
print_step("2/4", "Injecting realistic conflicts...")
try:
    r = requests.post(f"{API_BASE}/conflicts/inject")
    result = r.json()
    print(f"    ✓ {result.get('message', 'Conflicts injected')}")
    print(f"    ✓ Trains affected: {result.get('trains_affected', 0)}")
    
    if result.get('injected_conflicts'):
        print(f"\n    Injected conflicts:")
        for conflict in result['injected_conflicts'][:3]:
            print(f"      - {conflict.get('train_number', 'N/A')}: +{conflict.get('delay_added_minutes', 0)} min delay")
except Exception as e:
    print(f"    ✗ Failed to inject conflicts: {e}")
    exit(1)

time.sleep(2)

# Step 3: Run optimization
print_step("3/4", "Running optimization with explanation generation...")
try:
    r = requests.post(f"{API_BASE}/optimization/run", json={'include_predictions': True})
    result = r.json()
    
    if result.get('status') == 'success' or result.get('optimization_success'):
        print(f"    ✓ Optimization complete")
        print(f"      - Conflicts resolved: {result.get('conflicts_resolved', 0)}")
        print(f"      - Total weighted delay: {result.get('total_weighted_delay', 0):.1f} min")
        print(f"      - Solver runtime: {result.get('solver_runtime_seconds', 0):.2f}s")
    else:
        print(f"    ⚠ Optimization status: {result.get('message', 'Unknown')}")
except Exception as e:
    print(f"    ✗ Failed to run optimization: {e}")
    exit(1)

time.sleep(1)

# Step 4: Verify explanation
print_step("4/4", "Verifying explanation for dashboard...")
try:
    r = requests.get(f"{API_BASE}/optimization/latest-plan")
    data = r.json()
    
    if not data.get('explanation'):
        print("    ✗ No explanation in response")
        exit(1)
    
    exp = data['explanation']
    
    conflicts = exp.get('conflicts_detected', [])
    decisions = exp.get('decisions_made', [])
    improvement = exp.get('objective_improvement', {})
    actions = exp.get('train_actions', [])
    
    print(f"\n    ✓ Explanation generated:")
    print(f"      - Conflicts detected: {len(conflicts)}")
    print(f"      - Decisions made: {len(decisions)}")
    print(f"      - Train actions: {len(actions)}")
    
    if improvement:
        print(f"\n    📊 Delay Reduction Metrics:")
        print(f"      - Improvement: {improvement.get('improvement_percent', 0):.1f}%")
        print(f"      - Minutes saved: {improvement.get('delay_reduction', 0):.1f} min")
        print(f"      - Before: {improvement.get('previous_weighted_delay', 0):.1f} min")
        print(f"      - After: {improvement.get('optimized_weighted_delay', 0):.1f} min")
    
    if decisions:
        print(f"\n    🚂 Sample Decision (for judges):")
        decision = decisions[0]
        print(f"      Priority: {decision.get('priority_train', 'N/A')}")
        print(f"      Yielded: {decision.get('yielded_train', 'N/A')}")
        print(f"      Section: {decision.get('section_name', 'N/A')}")
        print(f"      → {decision.get('explanation', 'N/A')}")
    
    if conflicts:
        print(f"\n    ⚠️  Sample Conflict (for judges):")
        conflict = conflicts[0]
        print(f"      Section: {conflict.get('section_name', 'N/A')}")
        print(f"      Type: {conflict.get('type', 'N/A')}")
        print(f"      Trains: {', '.join(conflict.get('train_numbers', []))}")
        print(f"      Competing: {conflict.get('competing_trains', 0)} trains")

except Exception as e:
    print(f"    ✗ Failed to verify explanation: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Final summary
print_header("DEMO READY FOR JUDGES")

print("\n📋 WHAT JUDGES WILL SEE ON DASHBOARD:\n")

if improvement:
    print(f"  ✅ Delay Reduction Section:")
    print(f"     • {improvement.get('improvement_percent', 0):.1f}% improvement")
    print(f"     • {improvement.get('delay_reduction', 0):.1f} minutes saved")
    print(f"     • {improvement.get('previous_weighted_delay', 0):.1f} → {improvement.get('optimized_weighted_delay', 0):.1f} min")

if conflicts:
    print(f"\n  ✅ Conflicts Resolved Section:")
    print(f"     • {len(conflicts)} conflicts detected and resolved")
    print(f"     • Shows section names and competing trains")
else:
    print(f"\n  ⚠️  Conflicts Resolved Section:")
    print(f"     • Hidden (no conflicts in this run)")

if decisions:
    print(f"\n  ✅ Decisions Made Section:")
    print(f"     • {len(decisions)} precedence decisions")
    print(f"     • Human-readable explanations like:")
    if decisions:
        print(f"       \"{decisions[0].get('explanation', 'N/A')[:70]}...\"")
else:
    print(f"\n  ⚠️  Decisions Made Section:")
    print(f"     • Hidden (no precedence decisions needed)")

print("\n" + "=" * 80)
print("NEXT STEPS FOR DEMO:")
print("=" * 80)
print("  1. Open dashboard: http://localhost:3001")
print("  2. Navigate to 'Optimization Plan' panel")
print("  3. Show judges the explanation sections")
print("  4. (Optional) Click 'Force Optimization' to run again")
print("  5. (Optional) Run this script again to reset demo")
print("=" * 80)

# Show full JSON for reference
print("\n💾 FULL EXPLANATION DATA (for debugging):")
print("=" * 80)
print(json.dumps(exp, indent=2))
print("=" * 80)

print("\n✅ Demo preparation complete! Ready for judges presentation.\n")

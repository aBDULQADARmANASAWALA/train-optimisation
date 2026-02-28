#!/usr/bin/env python
"""
Demo script to generate full optimization explanations for judges presentation.

This script:
1. Clears existing delays
2. Injects strategic conflicts that trigger optimizer precedence decisions
3. Runs optimization to generate full explanation
4. Verifies all explanation sections are populated
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
import json
from app.config import Settings
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.models.db_models import TrainState, Train, TrainStatus
from datetime import datetime, timedelta

# Load settings
settings = Settings()

# Create engine
if settings.database_url:
    engine = create_engine(settings.database_url)
else:
    db_url = f"postgresql://{settings.supabase_db_user}:{settings.supabase_db_password}@{settings.supabase_db_host}:{settings.supabase_db_port}/{settings.supabase_db_name}"
    engine = create_engine(db_url)

Session = sessionmaker(bind=engine)

print("=" * 80)
print("DEMO: FULL OPTIMIZATION EXPLANATION GENERATION")
print("=" * 80)

# Step 1: Clear existing delays
print("\n[1/5] Clearing existing delays...")
db = Session()
try:
    delayed_states = db.query(TrainState).filter(TrainState.accumulated_delay_minutes > 0).all()
    for state in delayed_states:
        state.accumulated_delay_minutes = 0.0
        state.status = TrainStatus.IN_TRANSIT
    db.commit()
    print(f"    ✓ Cleared {len(delayed_states)} delayed trains")
except Exception as e:
    print(f"    ✗ Error: {e}")
    db.rollback()
finally:
    db.close()

# Step 2: Inject strategic conflicts
print("\n[2/5] Injecting strategic conflicts...")
print("    Creating scenario: Multiple trains competing for same section")

db = Session()
try:
    # Get active trains
    trains = db.query(Train).join(TrainState).limit(4).all()
    
    if len(trains) < 3:
        print("    ✗ Not enough trains in database")
        exit(1)
    
    # Inject delays to create competing scenario
    # Train 1: Heavy delay (will need to be held)
    state1 = db.query(TrainState).filter(TrainState.train_id == trains[0].id).first()
    state1.accumulated_delay_minutes = 35.0
    state1.status = TrainStatus.DELAYED
    
    # Train 2: Medium delay (will get priority)
    state2 = db.query(TrainState).filter(TrainState.train_id == trains[1].id).first()
    state2.accumulated_delay_minutes = 25.0
    state2.status = TrainStatus.DELAYED
    
    # Train 3: Light delay (will compete)
    state3 = db.query(TrainState).filter(TrainState.train_id == trains[2].id).first()
    state3.accumulated_delay_minutes = 15.0
    state3.status = TrainStatus.DELAYED
    
    db.commit()
    
    print(f"    ✓ Injected delays:")
    print(f"      - {trains[0].train_number}: 35.0 min delay")
    print(f"      - {trains[1].train_number}: 25.0 min delay")
    print(f"      - {trains[2].train_number}: 15.0 min delay")
    
except Exception as e:
    print(f"    ✗ Error: {e}")
    db.rollback()
    exit(1)
finally:
    db.close()

# Step 3: Run optimization
print("\n[3/5] Running optimization...")
try:
    r = requests.post('http://localhost:8010/api/v1/optimization/run', json={'include_predictions': True})
    result = r.json()
    
    if result.get('status') == 'success':
        print(f"    ✓ Optimization complete")
        print(f"      - Status: {result.get('optimization_success', False)}")
        print(f"      - Conflicts resolved: {result.get('conflicts_resolved', 0)}")
        print(f"      - Total weighted delay: {result.get('total_weighted_delay', 0):.1f} min")
        print(f"      - Solver runtime: {result.get('solver_runtime_seconds', 0):.2f}s")
    else:
        print(f"    ✗ Optimization failed: {result.get('message', 'Unknown error')}")
        exit(1)
        
except Exception as e:
    print(f"    ✗ Error: {e}")
    exit(1)

# Step 4: Verify explanation
print("\n[4/5] Verifying explanation generation...")
try:
    r = requests.get('http://localhost:8010/api/v1/optimization/latest-plan')
    data = r.json()
    
    if not data.get('explanation'):
        print("    ✗ No explanation found in response")
        exit(1)
    
    exp = data['explanation']
    
    # Check all sections
    conflicts = exp.get('conflicts_detected', [])
    decisions = exp.get('decisions_made', [])
    improvement = exp.get('objective_improvement', {})
    actions = exp.get('train_actions', [])
    
    print(f"    ✓ Explanation structure:")
    print(f"      - Conflicts detected: {len(conflicts)}")
    print(f"      - Decisions made: {len(decisions)}")
    print(f"      - Train actions: {len(actions)}")
    
    if improvement:
        print(f"      - Delay reduction: {improvement.get('improvement_percent', 0):.1f}%")
        print(f"      - Minutes saved: {improvement.get('delay_reduction', 0):.1f} min")
    
    # Display sample decision if available
    if decisions:
        print(f"\n    Sample Decision:")
        decision = decisions[0]
        print(f"      Priority train: {decision.get('priority_train', 'N/A')}")
        print(f"      Yielded train: {decision.get('yielded_train', 'N/A')}")
        print(f"      Section: {decision.get('section_name', 'N/A')}")
        print(f"      Explanation: {decision.get('explanation', 'N/A')[:80]}...")
    
    # Display sample conflict if available
    if conflicts:
        print(f"\n    Sample Conflict:")
        conflict = conflicts[0]
        print(f"      Section: {conflict.get('section_name', 'N/A')}")
        print(f"      Type: {conflict.get('type', 'N/A')}")
        print(f"      Competing trains: {conflict.get('competing_trains', 0)}")
        print(f"      Train numbers: {', '.join(conflict.get('train_numbers', []))}")
    
except Exception as e:
    print(f"    ✗ Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Step 5: Summary
print("\n[5/5] Demo Summary")
print("=" * 80)

if conflicts and decisions:
    print("✓ SUCCESS: Full explanation generated with all sections!")
    print("\nWhat judges will see on dashboard:")
    print("  1. Delay Reduction: {:.1f}%".format(improvement.get('improvement_percent', 0)))
    print("  2. Conflicts Resolved: {} conflicts".format(len(conflicts)))
    print("  3. Decisions Made: {} precedence decisions".format(len(decisions)))
    print("\nNext steps:")
    print("  → Refresh the dashboard (http://localhost:3001)")
    print("  → Click on 'Optimization Plan' panel")
    print("  → All three explanation sections should be visible")
elif improvement:
    print("⚠ PARTIAL: Only Delay Reduction section generated")
    print("\nThis happens when trains don't directly compete for same section.")
    print("The optimizer still works, but no precedence decisions were needed.")
    print("\nWhat judges will see:")
    print("  1. Delay Reduction: {:.1f}%".format(improvement.get('improvement_percent', 0)))
    print("  2. Conflicts Resolved: (hidden - no conflicts)")
    print("  3. Decisions Made: (hidden - no decisions)")
else:
    print("✗ FAILED: No explanation generated")
    print("Check the logs above for errors")

print("\n" + "=" * 80)
print("FULL EXPLANATION DATA:")
print("=" * 80)
print(json.dumps(exp, indent=2))
print("=" * 80)

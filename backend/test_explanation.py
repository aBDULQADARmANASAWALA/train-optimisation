#!/usr/bin/env python
"""Test script to verify explanation generation produces domain-language output."""

import sys
sys.path.insert(0, '.')

from app.services.optimizer_explanation import generate_explanation
from datetime import datetime, timedelta
from uuid import uuid4

print("=" * 60)
print("TESTING EXPLANATION GENERATION")
print("=" * 60)

# Mock solver and variables
class MockSolver:
    def Value(self, var):
        # Return mock values
        if hasattr(var, '_mock_value'):
            return var._mock_value
        return 1  # Default precedence decision

class MockVar:
    def __init__(self, value=1):
        self._mock_value = value

# Create mock data
train_id_1 = uuid4()
train_id_2 = uuid4()
section_id = uuid4()
station_id_1 = uuid4()
station_id_2 = uuid4()

class MockStop:
    def __init__(self, train_id, station_id, station_name, stop_order):
        self.train_id = train_id
        self.station_id = station_id
        self.station_name = station_name
        self.stop_order = stop_order
        self.scheduled_arrival = datetime.utcnow()
        self.scheduled_departure = datetime.utcnow() + timedelta(minutes=5)

class MockSection:
    def __init__(self, section_id, from_station_id, to_station_id):
        self.section_id = section_id
        self.from_station_id = from_station_id
        self.to_station_id = to_station_id
        self.capacity = 1
        self.headway_minutes = 5.0

class MockSnapshot:
    def __init__(self):
        self.trains = {
            train_id_1: {"train_number": "C-8001", "priority_weight": 1.5},
            train_id_2: {"train_number": "D-9002", "priority_weight": 1.0},
        }
        self.predicted_delays = {
            train_id_1: 15.0,
            train_id_2: 10.0,
        }
        self.sections = [
            MockSection(section_id, station_id_1, station_id_2)
        ]

# Create mock inputs
solver = MockSolver()
variables = {
    "precedence_vars": {
        (train_id_1, train_id_2, section_id): MockVar(1),  # train_1 has priority
    },
    "horizon_start": datetime.utcnow(),
}

snapshot = MockSnapshot()

relevant_stops = [
    MockStop(train_id_1, station_id_1, "Dadar", 1),
    MockStop(train_id_1, station_id_2, "Kalyan", 2),
    MockStop(train_id_2, station_id_1, "Dadar", 1),
    MockStop(train_id_2, station_id_2, "Kalyan", 2),
]

adjusted_timings = {
    train_id_1: [
        {"delay_minutes": 5.0, "station_name": "Dadar"},
        {"delay_minutes": 3.0, "station_name": "Kalyan"},
    ],
    train_id_2: [
        {"delay_minutes": 12.0, "station_name": "Dadar"},
        {"delay_minutes": 10.0, "station_name": "Kalyan"},
    ],
}

total_weighted_delay = 25.5

# Generate explanation
print("\nGenerating explanation...")
explanation = generate_explanation(
    solver,
    variables,
    snapshot,
    relevant_stops,
    adjusted_timings,
    total_weighted_delay,
)

print("\n" + "=" * 60)
print("EXPLANATION OUTPUT")
print("=" * 60)

import json
print(json.dumps(explanation, indent=2, default=str))

print("\n" + "=" * 60)
print("VERIFICATION CHECKS")
print("=" * 60)

# Verify structure
checks = []

# Check 1: Has required fields
required_fields = ["conflicts_detected", "decisions_made", "objective_improvement", "train_actions"]
for field in required_fields:
    if field in explanation:
        checks.append(f"✓ Has '{field}' field")
    else:
        checks.append(f"✗ Missing '{field}' field")

# Check 2: No raw solver variable names
explanation_str = json.dumps(explanation, default=str).lower()
forbidden_terms = ["boolvar", "intvar", "cp_model", "solver", "constraint", "variable"]
has_forbidden = False
for term in forbidden_terms:
    if term in explanation_str:
        checks.append(f"✗ Contains raw solver term: '{term}'")
        has_forbidden = True

if not has_forbidden:
    checks.append("✓ No raw solver variable names")

# Check 3: Has domain language
domain_terms = ["train", "section", "station", "delay", "hold", "priority"]
domain_count = sum(1 for term in domain_terms if term in explanation_str)
if domain_count >= 4:
    checks.append(f"✓ Uses domain language ({domain_count}/{len(domain_terms)} terms found)")
else:
    checks.append(f"✗ Insufficient domain language ({domain_count}/{len(domain_terms)} terms)")

# Check 4: Has human-readable explanations
if explanation.get("decisions_made"):
    decision = explanation["decisions_made"][0]
    if "explanation" in decision and len(decision["explanation"]) > 20:
        checks.append("✓ Has human-readable explanations")
    else:
        checks.append("✗ Missing human-readable explanations")

# Check 5: Has comparative metrics
obj_imp = explanation.get("objective_improvement", {})
if "previous_weighted_delay" in obj_imp and "optimized_weighted_delay" in obj_imp:
    checks.append("✓ Has comparative metrics (before/after)")
else:
    checks.append("✗ Missing comparative metrics")

for check in checks:
    print(check)

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)

"""
Examples and tests for OptimizationService (CP-SAT Solver).

Demonstrates:
- Creating optimization snapshots
- Running optimization with various scenarios
- Interpreting results
- Handling infeasibility
- Rolling horizon optimization
- Warm-start usage
"""

from datetime import datetime, timedelta
from uuid import uuid4, UUID
from typing import List, Dict, Any
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.services.optimizer import (
    OptimizationService,
    OptimizationSnapshot,
    TrainStop,
    SectionInfo,
    OptimizationStatus,
)


def create_test_snapshot() -> OptimizationSnapshot:
    """Create a test optimization snapshot with realistic data"""
    print("=== Creating Test Snapshot ===")

    base_time = datetime.utcnow().replace(second=0, microsecond=0)
    horizon_end = base_time + timedelta(hours=1)

    # Create station IDs
    station_ids = {
        "central": UUID("10000000-0000-0000-0000-000000000001"),
        "north": UUID("10000000-0000-0000-0000-000000000002"),
        "south": UUID("10000000-0000-0000-0000-000000000003"),
        "east": UUID("10000000-0000-0000-0000-000000000004"),
        "west": UUID("10000000-0000-0000-0000-000000000005"),
    }

    # Create section IDs
    section_ids = {
        "c_n": UUID("20000000-0000-0000-0000-000000000001"),  # Central -> North
        "c_s": UUID("20000000-0000-0000-0000-000000000002"),  # Central -> South
        "n_e": UUID("20000000-0000-0000-0000-000000000003"),  # North -> East
        "s_e": UUID("20000000-0000-0000-0000-000000000004"),  # South -> East
        "e_w": UUID("20000000-0000-0000-0000-000000000005"),  # East -> West
    }

    # Define sections
    sections = [
        SectionInfo(
            section_id=section_ids["c_n"],
            from_station_id=station_ids["central"],
            to_station_id=station_ids["north"],
            capacity=4,
            headway_minutes=3.0,
            travel_time_minutes=12.0,
            safety_margin_minutes=1.0,
        ),
        SectionInfo(
            section_id=section_ids["c_s"],
            from_station_id=station_ids["central"],
            to_station_id=station_ids["south"],
            capacity=4,
            headway_minutes=3.0,
            travel_time_minutes=15.0,
            safety_margin_minutes=1.0,
        ),
        SectionInfo(
            section_id=section_ids["n_e"],
            from_station_id=station_ids["north"],
            to_station_id=station_ids["east"],
            capacity=3,
            headway_minutes=4.0,
            travel_time_minutes=20.0,
            safety_margin_minutes=1.5,
        ),
        SectionInfo(
            section_id=section_ids["s_e"],
            from_station_id=station_ids["south"],
            to_station_id=station_ids["east"],
            capacity=3,
            headway_minutes=4.0,
            travel_time_minutes=18.0,
            safety_margin_minutes=1.5,
        ),
        SectionInfo(
            section_id=section_ids["e_w"],
            from_station_id=station_ids["east"],
            to_station_id=station_ids["west"],
            capacity=2,
            headway_minutes=5.0,
            travel_time_minutes=25.0,
            safety_margin_minutes=2.0,
        ),
    ]

    # Create trains with schedules
    train_ids = [
        UUID("30000000-0000-0000-0000-000000000001"),
        UUID("30000000-0000-0000-0000-000000000002"),
        UUID("30000000-0000-0000-0000-000000000003"),
        UUID("30000000-0000-0000-0000-000000000004"),
        UUID("30000000-0000-0000-0000-000000000005"),
    ]

    train_info = {
        train_ids[0]: {"train_number": "IC-101", "priority_weight": 2.5},
        train_ids[1]: {"train_number": "IC-102", "priority_weight": 2.0},
        train_ids[2]: {"train_number": "RG-201", "priority_weight": 1.5},
        train_ids[3]: {"train_number": "RG-202", "priority_weight": 1.0},
        train_ids[4]: {"train_number": "S-301", "priority_weight": 1.0},
    }

    # Create scheduled stops
    train_stops: List[TrainStop] = []

    # Train IC-101: Central -> North -> East
    train_stops.extend([
        TrainStop(
            train_id=train_ids[0],
            train_number="IC-101",
            station_id=station_ids["central"],
            station_name="Central Station",
            sequence=1,
            scheduled_arrival=base_time + timedelta(minutes=0),
            scheduled_departure=base_time + timedelta(minutes=5),
            platform_dwell_time_minutes=5.0,
        ),
        TrainStop(
            train_id=train_ids[0],
            train_number="IC-101",
            station_id=station_ids["north"],
            station_name="North Terminal",
            sequence=2,
            scheduled_arrival=base_time + timedelta(minutes=17),
            scheduled_departure=base_time + timedelta(minutes=22),
            platform_dwell_time_minutes=5.0,
        ),
        TrainStop(
            train_id=train_ids[0],
            train_number="IC-101",
            station_id=station_ids["east"],
            station_name="East Hub",
            sequence=3,
            scheduled_arrival=base_time + timedelta(minutes=42),
            scheduled_departure=base_time + timedelta(minutes=47),
            platform_dwell_time_minutes=5.0,
        ),
    ])

    # Train IC-102: Central -> South -> East
    train_stops.extend([
        TrainStop(
            train_id=train_ids[1],
            train_number="IC-102",
            station_id=station_ids["central"],
            station_name="Central Station",
            sequence=1,
            scheduled_arrival=base_time + timedelta(minutes=10),
            scheduled_departure=base_time + timedelta(minutes=15),
            platform_dwell_time_minutes=5.0,
        ),
        TrainStop(
            train_id=train_ids[1],
            train_number="IC-102",
            station_id=station_ids["south"],
            station_name="South Station",
            sequence=2,
            scheduled_arrival=base_time + timedelta(minutes=30),
            scheduled_departure=base_time + timedelta(minutes=35),
            platform_dwell_time_minutes=5.0,
        ),
        TrainStop(
            train_id=train_ids[1],
            train_number="IC-102",
            station_id=station_ids["east"],
            station_name="East Hub",
            sequence=3,
            scheduled_arrival=base_time + timedelta(minutes=53),
            scheduled_departure=base_time + timedelta(minutes=58),
            platform_dwell_time_minutes=5.0,
        ),
    ])

    # Train RG-201: North -> East
    train_stops.extend([
        TrainStop(
            train_id=train_ids[2],
            train_number="RG-201",
            station_id=station_ids["north"],
            station_name="North Terminal",
            sequence=1,
            scheduled_arrival=base_time + timedelta(minutes=5),
            scheduled_departure=base_time + timedelta(minutes=10),
            platform_dwell_time_minutes=5.0,
        ),
        TrainStop(
            train_id=train_ids[2],
            train_number="RG-201",
            station_id=station_ids["east"],
            station_name="East Hub",
            sequence=2,
            scheduled_arrival=base_time + timedelta(minutes=30),
            scheduled_departure=base_time + timedelta(minutes=35),
            platform_dwell_time_minutes=5.0,
        ),
    ])

    # Train RG-202: South -> East
    train_stops.extend([
        TrainStop(
            train_id=train_ids[3],
            train_number="RG-202",
            station_id=station_ids["south"],
            station_name="South Station",
            sequence=1,
            scheduled_arrival=base_time + timedelta(minutes=15),
            scheduled_departure=base_time + timedelta(minutes=20),
            platform_dwell_time_minutes=5.0,
        ),
        TrainStop(
            train_id=train_ids[3],
            train_number="RG-202",
            station_id=station_ids["east"],
            station_name="East Hub",
            sequence=2,
            scheduled_arrival=base_time + timedelta(minutes=38),
            scheduled_departure=base_time + timedelta(minutes=43),
            platform_dwell_time_minutes=5.0,
        ),
    ])

    # Platform capacity
    platform_capacity = {
        station_ids["central"]: 3,
        station_ids["north"]: 2,
        station_ids["south"]: 2,
        station_ids["east"]: 4,
        station_ids["west"]: 2,
    }

    # Predicted delays (simulate some prediction uncertainty)
    predicted_delays = {
        train_ids[0]: 2.0,  # IC-101: 2 min predicted delay
        train_ids[1]: 0.0,  # IC-102: On schedule
        train_ids[2]: 3.0,  # RG-201: 3 min delay
        train_ids[3]: 1.0,  # RG-202: 1 min delay
        train_ids[4]: 0.0,  # S-301: On schedule
    }

    # Current positions (all at starting stations)
    current_positions = {
        train_ids[0]: (None, station_ids["central"]),
        train_ids[1]: (None, station_ids["central"]),
        train_ids[2]: (None, station_ids["north"]),
        train_ids[3]: (None, station_ids["south"]),
        train_ids[4]: (None, station_ids["east"]),
    }

    snapshot = OptimizationSnapshot(
        timestamp=base_time,
        trains=train_info,
        train_stops=train_stops,
        sections=sections,
        current_positions=current_positions,
        predicted_delays=predicted_delays,
        platform_capacity=platform_capacity,
    )

    print(f"✓ Created snapshot with {len(train_info)} trains and {len(train_stops)} scheduled stops")
    print(f"  Time window: {base_time.time()} to {horizon_end.time()}")

    return snapshot


def example_basic_optimization():
    """Example: Run basic optimization"""
    print("\n=== Basic Optimization ===")

    # Create test data
    snapshot = create_test_snapshot()

    # Initialize optimizer
    optimizer = OptimizationService(
        max_solver_time_seconds=10.0,
        time_precision_minutes=0.5,
    )

    # Run optimization
    result = optimizer.optimize(
        snapshot=snapshot,
        horizon_minutes=60,
        use_warm_start=False,
    )

    print(f"\nOptimization Result:")
    print(f"  Status: {result.status.value}")
    print(f"  Runtime: {result.solver_runtime_seconds:.2f} seconds")

    if result.status == OptimizationStatus.OPTIMAL:
        print(f"  Solution Quality: OPTIMAL")
    elif result.status == OptimizationStatus.FEASIBLE:
        print(f"  Solution Quality: FEASIBLE (not optimal)")

    if result.objective_value:
        print(f"  Objective Value: {result.objective_value:.2f}")

    print(f"  Total Weighted Delay: {result.total_weighted_delay:.2f} minutes")
    print(f"  Trains Adjusted: {result.trains_adjusted}")
    print(f"  Conflicts Resolved: {result.conflicts_resolved}")

    if result.infeasibility_reasons:
        print(f"\n  Infeasibility Reasons:")
        for reason in result.infeasibility_reasons[:3]:
            print(f"    - {reason}")

    return result


def example_examine_adjusted_schedule(result):
    """Example: Examine adjusted schedule for trains"""
    print("\n=== Adjusted Schedule Detail ===")

    if not result.adjusted_timings:
        print("No adjusted timings in result")
        return

    for train_id_str, stops in list(result.adjusted_timings.items())[:2]:  # Show first 2 trains
        print(f"\nTrain: {stops[0]['station_name']} (first stop)")

        for stop in stops[:2]:  # Show first 2 stops
            delay = stop["delay_minutes"]
            status = "✓ On time" if delay <= 0.5 else f"⚠ {delay:.1f}min late"

            print(f"  {stop['sequence']}. {stop['station_name']}")
            print(f"     Scheduled: {stop['scheduled_arrival'][11:16]}")
            print(f"     Adjusted:  {stop['adjusted_arrival'][11:16]} ({status})")


def example_rolling_horizon():
    """Example: Multiple optimization cycles (rolling horizon)"""
    print("\n=== Rolling Horizon Optimization ===")

    snapshot = create_test_snapshot()
    optimizer = OptimizationService(max_solver_time_seconds=5.0)

    print(f"Starting rolling horizon at {snapshot.timestamp.time()}")

    results = []
    for cycle in range(3):
        print(f"\nCycle {cycle + 1}:")

        result = optimizer.optimize(
            snapshot=snapshot,
            horizon_minutes=60,
            use_warm_start=(cycle > 0),  # Use warm start after first cycle
        )

        print(f"  Status: {result.status.value}")
        print(f"  Runtime: {result.solver_runtime_seconds:.2f}s")
        print(f"  Weighted Delay: {result.total_weighted_delay:.2f}min")
        print(f"  Warm Start: {'Yes' if result.warm_start_applied else 'No'}")

        results.append(result)

        # Advance time for next cycle
        snapshot.timestamp = snapshot.timestamp + timedelta(minutes=15)

    print(f"\n✓ Completed {len(results)} optimization cycles")

    return results


def example_handle_infeasibility():
    """Example: Handle infeasible scenarios"""
    print("\n=== Handling Infeasibility ===")

    snapshot = create_test_snapshot()

    # Reduce capacity to create infeasibility
    for section in snapshot.sections:
        section.capacity = 1

    optimizer = OptimizationService(max_solver_time_seconds=5.0)

    result = optimizer.optimize(snapshot=snapshot, horizon_minutes=60)

    print(f"Result with reduced capacity:")
    print(f"  Status: {result.status.value}")
    print(f"  Infeasible: {result.status == OptimizationStatus.INFEASIBLE}")

    if result.infeasibility_reasons:
        print(f"\n  Reasons for infeasibility:")
        for reason in result.infeasibility_reasons[:5]:
            print(f"    • {reason}")


def example_priority_weighting():
    """Example: Show how priority weights affect optimization"""
    print("\n=== Priority Weight Impact ===")

    snapshot = create_test_snapshot()
    optimizer = OptimizationService(max_solver_time_seconds=10.0)

    result = optimizer.optimize(snapshot=snapshot, horizon_minutes=60)

    print(f"Optimization Result:")
    print(f"  Total Weighted Delay: {result.total_weighted_delay:.2f} min")

    # Show delay by train (with priorities)
    if result.adjusted_timings:
        for train_id_str, stops in list(result.adjusted_timings.items())[:3]:
            train_number = stops[0].get("station_name", "?")
            total_delay = sum(s["delay_minutes"] for s in stops)
            print(f"\n  {train_number}: {total_delay:.1f}min total delay")

            for stop in stops[:1]:
                print(f"    First stop: {stop['delay_minutes']:.1f}min")


if __name__ == "__main__":
    print("OptimizationService (CP-SAT Solver) Examples and Tests\n")
    print("=" * 70)

    try:
        # Run examples
        result = example_basic_optimization()
        example_examine_adjusted_schedule(result)
        example_priority_weighting()
        example_rolling_horizon()
        example_handle_infeasibility()

        print("\n" + "=" * 70)
        print("\n✅ All optimizer examples completed!")
        print("\nKey Capabilities Demonstrated:")
        print("  ✓ Basic constraint programming optimization")
        print("  ✓ Schedule adjustment generation")
        print("  ✓ Priority-weighted delay minimization")
        print("  ✓ Rolling horizon support")
        print("  ✓ Infeasibility detection")
        print("  ✓ Solution quality reporting")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

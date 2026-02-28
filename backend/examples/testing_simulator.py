"""
Examples and tests for SimulationOrchestrator.

Demonstrates:
- Running orchestration cycles
- Monitoring KPI metrics
- Injecting disruptions
- Manual override mode
- Execution summaries
- Trend analysis
"""

from datetime import datetime, timedelta
from uuid import uuid4, UUID
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.models import Base, Station, Section, Train, TrainSchedule, TrainState, TrainStatus
from app.repositories import TrainRepository, SectionRepository
from app.services import (
    RailwayStateEngine,
    OptimizationService,
    PredictionService,
    SimulationOrchestrator,
    DisruptionType,
)


def setup_test_environment():
    """Create test database and services"""
    print("=== Setting Up Test Environment ===")

    # Create in-memory database
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create test data
    base_time = datetime.utcnow()

    # Stations
    stations = {
        "central": Station(id=uuid4(), name="Central", zone="A", latitude=40.7, longitude=-74.0),
        "north": Station(id=uuid4(), name="North", zone="B", latitude=40.8, longitude=-74.0),
        "south": Station(id=uuid4(), name="South", zone="C", latitude=40.6, longitude=-74.0),
    }

    # Sections
    sections = [
        Section(
            id=uuid4(),
            from_station_id=stations["central"].id,
            to_station_id=stations["north"].id,
            capacity=4,
            headway_minutes=3.0,
            travel_time_minutes=12.0,
        ),
        Section(
            id=uuid4(),
            from_station_id=stations["central"].id,
            to_station_id=stations["south"].id,
            capacity=4,
            headway_minutes=3.0,
            travel_time_minutes=15.0,
        ),
    ]

    # Trains
    trains = [
        Train(id=uuid4(), train_number="IC-101", priority_weight=2.5,
              origin_id=stations["central"].id, destination_id=stations["north"].id),
        Train(id=uuid4(), train_number="RG-201", priority_weight=1.0,
              origin_id=stations["central"].id, destination_id=stations["south"].id),
    ]

    # Schedules
    for train in trains:
        TrainSchedule(
            id=uuid4(),
            train_id=train.id,
            station_id=stations["central"].id,
            scheduled_arrival=base_time + timedelta(minutes=0),
            scheduled_departure=base_time + timedelta(minutes=5),
            sequence=1,
        )

    # Train states
    for train in trains:
        TrainState(
            id=uuid4(),
            train_id=train.id,
            status=TrainStatus.SCHEDULED,
            accumulated_delay_minutes=0.0,
        )

    # Add to session
    for station in stations.values():
        session.add(station)
    for section in sections:
        session.add(section)
    for train in trains:
        session.add(train)

    session.commit()

    # Create repositories and services
    train_repo = TrainRepository(session)
    section_repo = SectionRepository(session)
    state_engine = RailwayStateEngine(train_repo, section_repo, base_time)
    optimizer = OptimizationService()
    predictor = PredictionService(train_repo, section_repo)

    # Train predictor
    predictor.train_models()

    print(f"✓ Test environment ready")
    print(f"  Stations: {len(stations)}")
    print(f"  Sections: {len(sections)}")
    print(f"  Trains: {len(trains)}")

    return train_repo, section_repo, state_engine, optimizer, predictor


def example_basic_orchestration():
    """Example: Run basic orchestration cycles"""
    print("\n=== Running Basic Orchestration ===")

    train_repo, section_repo, state_engine, optimizer, predictor = setup_test_environment()

    orchestrator = SimulationOrchestrator(
        train_repo, section_repo, state_engine, optimizer, predictor,
        horizon_minutes=60,
        rolling_step_minutes=5,
    )

    print(f"Running 3 orchestration cycles...")

    for cycle in range(1, 4):
        print(f"\n  Cycle {cycle}:")
        result = orchestrator.execute_cycle()

        print(f"    Status: {result.status.value}")
        print(f"    Duration: {result.duration_seconds:.2f}s")
        print(f"    Validated: {result.validated}")

        if result.kpis:
            kpis = result.kpis
            print(f"    Weighted Delay: {kpis.total_weighted_delay_minutes:.1f}min")
            print(f"    Utilization: {kpis.average_section_utilization_percent:.1f}%")
            print(f"    Conflicts: {kpis.conflicts_detected} detected, {kpis.conflicts_avoided} avoided")

    return orchestrator


def example_disruption_injection():
    """Example: Inject disruptions and observe impact"""
    print("\n=== Disruption Injection Test ===")

    train_repo, section_repo, state_engine, optimizer, predictor = setup_test_environment()

    orchestrator = SimulationOrchestrator(
        train_repo, section_repo, state_engine, optimizer, predictor,
    )

    # Normal cycle (baseline)
    print("Baseline cycle (no disruption):")
    result1 = orchestrator.execute_cycle()
    baseline_delay = result1.kpis.total_weighted_delay_minutes if result1.kpis else 0
    print(f"  Weighted delay: {baseline_delay:.1f}min")

    # Inject train delay disruption
    train_id = list(orchestrator.state_engine.trains.keys())[0]
    print(f"\nInjecting 10min delay on train {orchestrator.state_engine.trains[train_id]['train_number']}...")

    orchestrator.inject_disruption(
        disruption_type=DisruptionType.TRAIN_DELAY,
        affected_id=train_id,
        magnitude=10.0,  # 10 minute delay
        duration_minutes=30,
        start_time=datetime.utcnow(),
    )

    # Run cycles with disruption
    print("Cycle with disruption:")
    result2 = orchestrator.execute_cycle()
    disrupted_delay = result2.kpis.total_weighted_delay_minutes if result2.kpis else 0
    print(f"  Weighted delay: {disrupted_delay:.1f}min")

    impact = disrupted_delay - baseline_delay
    print(f"\n  Impact: {impact:+.1f}min ({(impact/baseline_delay*100 if baseline_delay > 0 else 0):+.0f}%)")


def example_manual_override():
    """Example: Test manual override mode"""
    print("\n=== Manual Override Test ===")

    train_repo, section_repo, state_engine, optimizer, predictor = setup_test_environment()

    orchestrator = SimulationOrchestrator(
        train_repo, section_repo, state_engine, optimizer, predictor,
    )

    # Run initial cycle
    print("Initial cycle (normal mode):")
    result1 = orchestrator.execute_cycle()
    print(f"  Result: {result1.status.value}, validated={result1.validated}")

    # Enable manual override
    print("\nEnabling manual override...")
    orchestrator.set_manual_override(True)

    # Run cycle with override
    print("Cycle with manual override:")
    result2 = orchestrator.execute_cycle()
    print(f"  Result: {result2.status.value}, validated={result2.validated}")
    print(f"  Uses last known good schedule instead of optimizing")

    # Disable override
    print("\nDisabling manual override...")
    orchestrator.set_manual_override(False)


def example_kpi_tracking():
    """Example: Track KPI metrics and trends"""
    print("\n=== KPI Tracking ===")

    train_repo, section_repo, state_engine, optimizer, predictor = setup_test_environment()

    orchestrator = SimulationOrchestrator(
        train_repo, section_repo, state_engine, optimizer, predictor,
    )

    print(f"Running 5 cycles to build KPI history...")

    for i in range(5):
        result = orchestrator.execute_cycle()
        if result.kpis:
            kpis = result.kpis
            print(f"  Cycle {i+1}: delay={kpis.total_weighted_delay_minutes:.1f}min, "
                  f"util={kpis.average_section_utilization_percent:.1f}%")

    # Get latest KPIs
    print("\nLatest KPIs:")
    latest = orchestrator.get_latest_kpis()
    if latest:
        print(f"  Total Weighted Delay: {latest.total_weighted_delay_minutes:.1f} min")
        print(f"  Average Section Utilization: {latest.average_section_utilization_percent:.1f}%")
        print(f"  Trains Delayed: {latest.trains_delayed}/{latest.trains_delayed + latest.trains_on_time}")
        print(f"  Conflicts Avoided: {latest.conflicts_avoided}")
        print(f"  Schedule Adherence: {latest.schedule_adherence_percent:.1f}%")

    # Get trends
    print("\nKPI Trends (last 5 cycles):")
    trends = orchestrator.get_kpi_trends(5)
    for i, kpi in enumerate(trends):
        print(f"  {i+1}. Delay={kpi.total_weighted_delay_minutes:.1f}min, "
              f"Util={kpi.average_section_utilization_percent:.1f}%")


def example_execution_summary():
    """Example: Get overall execution summary"""
    print("\n=== Execution Summary ===")

    train_repo, section_repo, state_engine, optimizer, predictor = setup_test_environment()

    orchestrator = SimulationOrchestrator(
        train_repo, section_repo, state_engine, optimizer, predictor,
    )

    # Run multiple cycles
    print("Running 10 orchestration cycles...")
    for _ in range(10):
        orchestrator.execute_cycle()

    # Get summary
    summary = orchestrator.get_execution_summary()

    print(f"\nExecution Summary:")
    print(f"  Total Cycles: {summary['cycles_executed']}")
    print(f"  Successful: {summary['successful']}")
    print(f"  Failed: {summary['failed']}")
    print(f"  Success Rate: {summary['success_rate']:.1%}")
    print(f"  Cumulative Conflicts Avoided: {summary['total_conflicts_avoided']}")

    # Show execution history snippets
    print(f"\nRecent Execution History:")
    for i, result in enumerate(orchestrator.execution_history[-3:]):
        print(f"  Cycle {result.cycle_number}: {result.status.value} ({result.duration_seconds:.2f}s)")


if __name__ == "__main__":
    print("SimulationOrchestrator Examples and Tests\n")
    print("=" * 70)

    try:
        example_basic_orchestration()
        example_disruption_injection()
        example_manual_override()
        example_kpi_tracking()
        example_execution_summary()

        print("\n" + "=" * 70)
        print("\n✅ All orchestrator examples completed!")
        print("\nKey Capabilities Demonstrated:")
        print("  ✓ Multi-cycle orchestration execution")
        print("  ✓ State engine + optimizer + predictor integration")
        print("  ✓ Disruption injection and impact measurement")
        print("  ✓ Manual override mode for emergency control")
        print("  ✓ KPI tracking and trend analysis")
        print("  ✓ Execution history and success metrics")
        print("  ✓ Transactional validation")
        print("  ✓ Rolling horizon support")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

"""
Examples and tests for RailwayStateEngine.

Demonstrates:
- Initializing the state engine
- Building network graph
- Detecting conflicts
- Checking section loads
- Predicting future conflicts
- Rolling horizon updates
- Snapshotting state
"""

from datetime import datetime, timedelta
from uuid import uuid4, UUID
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Station, Section, Train, TrainSchedule, TrainState, TrainStatus, SignallingType
from app.repositories import TrainRepository, SectionRepository
from app.services import RailwayStateEngine


def setup_test_network():
    """Example: Set up a test network with stations and sections"""
    print("=== Setting Up Test Network ===")

    # Create in-memory database
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create stations
    stations = {
        "central": Station(id=uuid4(), name="Central Station", zone="Downtown", latitude=40.7128, longitude=-74.0060),
        "north": Station(id=uuid4(), name="North Terminal", zone="North", latitude=40.7580, longitude=-73.9855),
        "south": Station(id=uuid4(), name="South Station", zone="South", latitude=40.6892, longitude=-74.0445),
        "east": Station(id=uuid4(), name="East Hub", zone="East", latitude=40.7489, longitude=-73.9680),
    }

    # Create sections connecting stations
    sections = [
        Section(
            id=uuid4(),
            from_station_id=stations["central"].id,
            to_station_id=stations["north"].id,
            capacity=4,
            headway_minutes=3.0,
            travel_time_minutes=12.0,
            signalling_type=SignallingType.AUTOMATIC,
        ),
        Section(
            id=uuid4(),
            from_station_id=stations["central"].id,
            to_station_id=stations["south"].id,
            capacity=4,
            headway_minutes=3.0,
            travel_time_minutes=15.0,
            signalling_type=SignallingType.AUTOMATIC,
        ),
        Section(
            id=uuid4(),
            from_station_id=stations["north"].id,
            to_station_id=stations["east"].id,
            capacity=3,
            headway_minutes=4.0,
            travel_time_minutes=20.0,
            signalling_type=SignallingType.MIXED,
        ),
        Section(
            id=uuid4(),
            from_station_id=stations["south"].id,
            to_station_id=stations["east"].id,
            capacity=3,
            headway_minutes=4.0,
            travel_time_minutes=18.0,
            signalling_type=SignallingType.AUTOMATIC,
        ),
    ]

    # Create trains
    base_time = datetime.utcnow()
    trains = [
        Train(
            id=uuid4(),
            train_number="IC-101",
            priority_weight=2.0,
            origin_id=stations["central"].id,
            destination_id=stations["north"].id,
        ),
        Train(
            id=uuid4(),
            train_number="IC-102",
            priority_weight=1.5,
            origin_id=stations["central"].id,
            destination_id=stations["east"].id,
        ),
        Train(
            id=uuid4(),
            train_number="RG-201",
            priority_weight=1.0,
            origin_id=stations["south"].id,
            destination_id=stations["north"].id,
        ),
    ]

    # Create schedules
    for i, train in enumerate(trains):
        # Find path for train (simplified: just use origin and destination)
        stations_list = list(stations.values())
        for j, station in enumerate(stations_list):
            TrainSchedule(
                id=uuid4(),
                train_id=train.id,
                station_id=station.id,
                scheduled_arrival=base_time + timedelta(hours=i, minutes=j * 30),
                scheduled_departure=base_time + timedelta(hours=i, minutes=j * 30 + 10),
                sequence=j,
            )

    # Create train states
    for train in trains:
        TrainState(
            id=uuid4(),
            train_id=train.id,
            current_section_id=None,
            current_station_id=stations["central"].id,
            status=TrainStatus.SCHEDULED,
            actual_arrival=None,
            actual_departure=None,
            accumulated_delay_minutes=0.0,
        )

    # Add all to session
    for station in stations.values():
        session.add(station)
    for section in sections:
        session.add(section)
    for train in trains:
        session.add(train)

    session.commit()

    print(f"✓ Created {len(stations)} stations")
    print(f"✓ Created {len(sections)} sections")
    print(f"✓ Created {len(trains)} trains")

    return session, stations, sections, trains


def example_initialize_state_engine(session):
    """Example: Initialize the state engine"""
    print("\n=== Initializing State Engine ===")

    train_repo = TrainRepository(session)
    section_repo = SectionRepository(session)

    engine = RailwayStateEngine(
        train_repository=train_repo,
        section_repository=section_repo,
        current_time=datetime.utcnow(),
        horizon_minutes=60,
        rolling_step_minutes=5,
    )

    print(f"✓ State engine initialized")
    print(f"  Network: {engine.graph.number_of_nodes()} stations, {engine.graph.number_of_edges()} sections")
    print(f"  Active trains: {len(engine.trains)}")
    print(f"  Horizon: {engine.horizon_minutes} minutes")

    return engine


def example_detect_conflicts(engine: RailwayStateEngine):
    """Example: Detect conflicts in current state"""
    print("\n=== Detecting Conflicts ===")

    conflicts = engine.detect_conflicts()

    print(f"Total conflicts detected: {conflicts['total_conflicts']}")
    print(f"  Capacity violations: {len(conflicts['capacity_conflicts'])}")
    print(f"  Headway violations: {len(conflicts['headway_conflicts'])}")
    print(f"  Platform conflicts: {len(conflicts['platform_conflicts'])}")

    if conflicts['capacity_conflicts']:
        print("\nCapacity Conflicts:")
        for conflict in conflicts['capacity_conflicts']:
            print(f"  Section: {conflict['section_id']}")
            print(f"    Trains: {len(conflict['train_ids'])}, Capacity: {conflict['capacity']}")

    if conflicts['headway_conflicts']:
        print("\nHeadway Violations:")
        for conflict in conflicts['headway_conflicts']:
            print(f"  Section: {conflict['section_id']}")
            print(f"    Gap: {conflict['headway_gap_minutes']} min (required: {conflict['required_headway_minutes']})")

    if conflicts['platform_conflicts']:
        print("\nPlatform Conflicts:")
        for conflict in conflicts['platform_conflicts']:
            print(f"  Station: {conflict['station_id']}")
            print(f"    Trains occupying platform: {conflict['count']}")

    return conflicts


def example_get_section_load(engine: RailwayStateEngine):
    """Example: Check section utilization"""
    print("\n=== Checking Section Load ===")

    # Get first section from graph
    if engine.graph.number_of_edges() > 0:
        first_edge = list(engine.graph.edges(data=True))[0]
        section_id = UUID(first_edge[2]["section_id"])

        load = engine.get_section_load(section_id)

        print(f"Section Load Analysis:")
        print(f"  Section ID: {load['section_id']}")
        print(f"  Current Occupancy: {load['current_occupancy']} trains")
        print(f"  Capacity: {load['capacity']} trains")
        print(f"  Utilization: {load['utilization_percent']}%")

        if load['occupying_trains']:
            print(f"  Occupying Trains:")
            for train in load['occupying_trains']:
                print(f"    - {train['train_id']}")

        return load
    else:
        print("No sections in network")
        return None


def example_predict_future_conflicts(engine: RailwayStateEngine):
    """Example: Predict future conflicts"""
    print("\n=== Predicting Future Conflicts ===")

    # Create predicted arrivals for demo
    base_time = engine.current_time
    predicted_arrivals = {}

    for train_id, train_info in engine.trains.items():
        # Simulate train moving through sections
        predicted_arrivals[train_id] = [
            (
                UUID("00000000-0000-0000-0000-000000000001"),  # section_id (example)
                base_time + timedelta(minutes=10),
                base_time + timedelta(minutes=25),
            ),
            (
                UUID("00000000-0000-0000-0000-000000000002"),  # section_id (example)
                base_time + timedelta(minutes=28),
                base_time + timedelta(minutes=45),
            ),
        ]

    predictions = engine.get_future_conflict_predictions(predicted_arrivals)

    print(f"Prediction Window: {predictions['horizon_start']} to {predictions['horizon_end']}")
    print(f"Predicted Conflicts: {predictions['total_predicted_conflicts']}")

    if predictions['predicted_conflicts']:
        print(f"\nPredicted Issues:")
        for conflict in predictions['predicted_conflicts'][:3]:  # Show first 3
            print(f"  [{conflict['type'].upper()}] Section: {conflict['section_id']}")

    if predictions['critical_sections']:
        print(f"\nCritical Sections (>70% utilization):")
        for section in predictions['critical_sections']:
            print(f"  Section: {section['section_id']}")
            print(f"    Predicted Occupancy: {section['predicted_occupancy']}/{section['capacity']}")
            print(f"    Utilization: {section['utilization_percent']}%")

    return predictions


def example_snapshot_state(engine: RailwayStateEngine):
    """Example: Capture state snapshot"""
    print("\n=== Snapshotting State ===")

    snapshot = engine.snapshot_state()

    print(f"State Snapshot at {snapshot['timestamp']}")
    print(f"  Active Trains: {snapshot['active_trains_count']}")
    print(f"  Network: {snapshot['network_stats']['total_stations']} stations, "
          f"{snapshot['network_stats']['total_sections']} sections")
    print(f"\nOccupancy Summary:")
    print(f"  Sections with trains: {snapshot['occupancy_summary']['sections_with_trains']}")
    print(f"  Platforms with trains: {snapshot['occupancy_summary']['platforms_with_trains']}")

    print(f"\nTrain Positions:")
    for train in snapshot['train_positions'][:3]:  # Show first 3
        print(f"  {train['train_number']} ({train['status']})")
        if train['current_section_id']:
            print(f"    On section: {train['current_section_id']}")
        if train['current_station_id']:
            print(f"    At station: {train['current_station_id']}")
        print(f"    Delay: {train['accumulated_delay_minutes']} min")

    return snapshot


def example_rolling_horizon_update(engine: RailwayStateEngine):
    """Example: Simulate rolling horizon time advance"""
    print("\n=== Rolling Horizon Update ===")

    original_time = engine.current_time
    print(f"Current time: {original_time.time()}")

    # Advance time by rolling step
    new_time = original_time + timedelta(minutes=engine.rolling_step_minutes)
    engine.update_time(new_time)

    print(f"New time: {engine.current_time.time()}")
    print(f"✓ Cleaned up expired occupancy records")
    print(f"✓ Ready for next optimization cycle")

    return engine.current_time


def example_update_train_state_in_engine(engine: RailwayStateEngine):
    """Example: Update train state in engine"""
    print("\n=== Updating Train State in Engine ===")

    if engine.trains:
        train_id = list(engine.trains.keys())[0]
        initial_delay = engine.trains[train_id].get("accumulated_delay_minutes", 0)

        print(f"Train: {engine.trains[train_id]['train_number']}")
        print(f"  Initial Delay: {initial_delay} min")

        # Update state
        engine.update_train_state(
            train_id=train_id,
            updates={
                "status": "in_transit",
                "accumulated_delay_minutes": 5.5,
            },
        )

        print(f"  Updated Delay: {engine.trains[train_id]['accumulated_delay_minutes']} min")
        print(f"  Updated Status: {engine.trains[train_id]['status']}")
    else:
        print("No trains in engine")


if __name__ == "__main__":
    print("RailwayStateEngine Examples and Tests\n")
    print("=" * 60)

    try:
        # Setup test network
        session, stations, sections, trains = setup_test_network()

        # Initialize engine
        engine = example_initialize_state_engine(session)

        # Run examples
        example_detect_conflicts(engine)
        example_get_section_load(engine)
        example_predict_future_conflicts(engine)
        example_snapshot_state(engine)
        example_update_train_state_in_engine(engine)
        example_rolling_horizon_update(engine)

        print("\n" + "=" * 60)
        print("\n✅ All state engine examples completed successfully!")
        print("\nKey Capabilities Demonstrated:")
        print("  ✓ Network graph building")
        print("  ✓ Conflict detection (capacity, headway, platform)")
        print("  ✓ Section load analysis")
        print("  ✓ Future conflict prediction")
        print("  ✓ State snapshots")
        print("  ✓ Rolling horizon updates")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

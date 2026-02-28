"""
Examples and tests for database models.

Demonstrates:
- Creating ORM instances
- Relationships between models
- Enume values
- Timestamp handling
"""

from datetime import datetime, timedelta
from uuid import uuid4
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.models import (
    Station,
    Section,
    Train,
    TrainSchedule,
    TrainState,
    OptimizationLog,
    TrainStatus,
    SignallingType,
)


def example_create_stations():
    """Example: Create station instances"""
    print("=== Creating Stations ===")

    station1 = Station(
        id=uuid4(),
        name="Central Station",
        zone="Downtown",
        latitude=40.7128,
        longitude=-74.0060,
    )

    station2 = Station(
        id=uuid4(),
        name="North Terminal",
        zone="North",
        latitude=40.7580,
        longitude=-73.9855,
    )

    print(f"Station 1: {station1.name} (Zone: {station1.zone})")
    print(f"  Coordinates: {station1.latitude}, {station1.longitude}")
    print(f"  ID: {station1.id}")

    print(f"\nStation 2: {station2.name} (Zone: {station2.zone})")
    print(f"  Coordinates: {station2.latitude}, {station2.longitude}")
    print(f"  ID: {station2.id}")

    return station1, station2


def example_create_section(station1: Station, station2: Station):
    """Example: Create a section between stations"""
    print("\n=== Creating Section ===")

    section = Section(
        id=uuid4(),
        from_station_id=station1.id,
        to_station_id=station2.id,
        capacity=5,
        headway_minutes=3.0,
        travel_time_minutes=15.0,
        signalling_type=SignallingType.AUTOMATIC,
    )

    print(f"Section: {station1.name} → {station2.name}")
    print(f"  Capacity: {section.capacity} trains")
    print(f"  Headway: {section.headway_minutes} minutes")
    print(f"  Travel Time: {section.travel_time_minutes} minutes")
    print(f"  Signalling: {section.signalling_type.value}")

    return section


def example_create_train(station1: Station, station2: Station):
    """Example: Create a train"""
    print("\n=== Creating Train ===")

    train = Train(
        id=uuid4(),
        train_number="IC-101",
        priority_weight=2.5,
        origin_id=station1.id,
        destination_id=station2.id,
    )

    print(f"Train: {train.train_number}")
    print(f"  Priority Weight: {train.priority_weight}")
    print(f"  Origin: {station1.name}")
    print(f"  Destination: {station2.name}")

    return train


def example_create_schedule(train: Train, station1: Station, station2: Station):
    """Example: Create scheduled stops for a train"""
    print("\n=== Creating Train Schedule ===")

    now = datetime.utcnow()

    schedule1 = TrainSchedule(
        id=uuid4(),
        train_id=train.id,
        station_id=station1.id,
        scheduled_arrival=now + timedelta(hours=1),
        scheduled_departure=now + timedelta(hours=1, minutes=5),
        sequence=1,
    )

    schedule2 = TrainSchedule(
        id=uuid4(),
        train_id=train.id,
        station_id=station2.id,
        scheduled_arrival=now + timedelta(hours=1, minutes=20),
        scheduled_departure=now + timedelta(hours=1, minutes=25),
        sequence=2,
    )

    print(f"Stop 1: {station1.name}")
    print(f"  Arrival: {schedule1.scheduled_arrival.time()}")
    print(f"  Departure: {schedule1.scheduled_departure.time()}")

    print(f"\nStop 2: {station2.name}")
    print(f"  Arrival: {schedule2.scheduled_arrival.time()}")
    print(f"  Departure: {schedule2.scheduled_departure.time()}")

    return [schedule1, schedule2]


def example_create_train_state(train: Train):
    """Example: Create and update train state"""
    print("\n=== Creating Train State ===")

    state = TrainState(
        id=uuid4(),
        train_id=train.id,
        current_station_id=None,
        current_section_id=None,
        status=TrainStatus.SCHEDULED,
        actual_arrival=None,
        actual_departure=None,
        accumulated_delay_minutes=0.0,
    )

    print(f"Train {train.train_number} State:")
    print(f"  Status: {state.status.value}")
    print(f"  Current Position: None (not departed yet)")
    print(f"  Accumulated Delay: {state.accumulated_delay_minutes} min")

    # Example: Update state
    state.status = TrainStatus.IN_TRANSIT
    state.accumulated_delay_minutes = 5.2

    print(f"\nAfter update:")
    print(f"  Status: {state.status.value}")
    print(f"  Accumulated Delay: {state.accumulated_delay_minutes} min")

    return state


def example_create_optimization_log():
    """Example: Create an optimization log entry"""
    print("\n=== Creating Optimization Log ===")

    log = OptimizationLog(
        id=uuid4(),
        timestamp=datetime.utcnow(),
        objective_value=1245.67,
        total_weighted_delay=45.3,
        conflicts_detected=2,
        solver_runtime=12.5,
        notes="Optimization run successful, 2 capacity conflicts resolved",
    )

    print(f"Optimization Run at {log.timestamp.time()}")
    print(f"  Objective Value: {log.objective_value}")
    print(f"  Total Weighted Delay: {log.total_weighted_delay} min")
    print(f"  Conflicts Detected: {log.conflicts_detected}")
    print(f"  Solver Runtime: {log.solver_runtime} sec")
    print(f"  Notes: {log.notes}")

    return log


def example_train_status_enum():
    """Example: Using TrainStatus enum"""
    print("\n=== Train Status Enum ===")

    statuses = [
        TrainStatus.SCHEDULED,
        TrainStatus.IN_TRANSIT,
        TrainStatus.STOPPED,
        TrainStatus.DELAYED,
        TrainStatus.COMPLETED,
        TrainStatus.CANCELLED,
    ]

    print("Available train statuses:")
    for status in statuses:
        print(f"  - {status.value}")

    # Example: Check status
    train_state = TrainStatus.IN_TRANSIT
    if train_state == TrainStatus.IN_TRANSIT:
        print(f"\nTrain is {train_state.value}")


def example_signalling_type_enum():
    """Example: Using SignallingType enum"""
    print("\n=== Signalling Type Enum ===")

    types = [
        SignallingType.AUTOMATIC,
        SignallingType.MANUAL,
        SignallingType.MIXED,
    ]

    print("Available signalling types:")
    for sig_type in types:
        print(f"  - {sig_type.value}")


if __name__ == "__main__":
    print("Database Models Examples and Tests\n")
    print("=" * 50)

    try:
        station1, station2 = example_create_stations()
        section = example_create_section(station1, station2)
        train = example_create_train(station1, station2)
        schedules = example_create_schedule(train, station1, station2)
        state = example_create_train_state(train)
        log = example_create_optimization_log()
        example_train_status_enum()
        example_signalling_type_enum()

        print("\n" + "=" * 50)
        print("\n✅ All model examples created successfully!")
        print("\nNote: These are in-memory objects. To persist to database,")
        print("you need to add them to a SQLAlchemy session and commit.")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

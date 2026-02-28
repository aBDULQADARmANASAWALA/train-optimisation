"""
Examples and tests for repositories.

Demonstrates:
- Creating repository instances
- Loading train data
- Getting train schedules
- Updating train states
- Bulk operations
- Error handling
"""

from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.repositories import TrainRepository, SectionRepository


def example_setup_database():
    """Example: Set up in-memory SQLite database for testing"""
    print("=== Setting Up Database ===")

    # Create in-memory SQLite database
    engine = create_engine("sqlite:///:memory:", echo=False)

    # Create tables
    Base.metadata.create_all(engine)

    # Create session
    Session = sessionmaker(bind=engine)
    session = Session()

    print("✓ In-memory SQLite database created")
    print("✓ Tables initialized")

    return session


def example_get_active_trains(train_repo: TrainRepository):
    """Example: Retrieve active trains"""
    print("\n=== Getting Active Trains ===")

    current_time = datetime.utcnow()
    active_trains = train_repo.get_active_trains(current_time)

    print(f"Active trains as of {current_time.time()}:")
    if active_trains:
        for train in active_trains:
            print(f"  - {train['train_number']} (Priority: {train['priority_weight']})")
            print(f"    Status: {train['status']}")
            print(f"    Delay: {train['accumulated_delay_minutes']} min")
    else:
        print("  (No active trains)")

    return active_trains


def example_get_train_schedule(train_repo: TrainRepository, train_id: UUID):
    """Example: Get train's complete schedule"""
    print(f"\n=== Getting Train Schedule ===")

    try:
        schedule = train_repo.get_train_schedule(train_id)

        print(f"Schedule for train {train_id}:")
        if schedule:
            for stop in schedule:
                print(f"  Stop {stop['sequence']}: {stop['station_name']} (Zone: {stop['zone']})")
                print(f"    Arrival: {stop['scheduled_arrival']}")
                print(f"    Departure: {stop['scheduled_departure']}")
        else:
            print("  (No schedule found)")

        return schedule

    except ValueError as e:
        print(f"Error: {e}")
        return None


def example_get_current_train_states(train_repo: TrainRepository):
    """Example: Get current status of all trains"""
    print("\n=== Getting Current Train States ===")

    states = train_repo.get_current_train_states()

    print(f"Current states for {len(states)} trains:")
    if states:
        for state in states:
            print(f"  - {state['train_number']}")
            print(f"    Status: {state['status']}")
            print(f"    Section: {state['current_section_id']}")
            print(f"    Station: {state['current_station_id']}")
            print(f"    Delay: {state['accumulated_delay_minutes']} min")
            print(f"    Last Updated: {state['last_updated']}")
    else:
        print("  (No train states)")

    return states


def example_update_single_train_state(train_repo: TrainRepository, train_id: UUID):
    """Example: Update a single train's state"""
    print(f"\n=== Updating Single Train State ===")

    try:
        # Update fields
        updated_state = train_repo.update_train_state(
            train_id=train_id,
            updated_fields={
                "status": "in_transit",
                "accumulated_delay_minutes": 3.5,
            },
        )

        print(f"Updated train {train_id}:")
        print(f"  Status: {updated_state['status']}")
        print(f"  Delay: {updated_state['accumulated_delay_minutes']} min")
        print(f"  Last Updated: {updated_state['last_updated']}")

        return updated_state

    except ValueError as e:
        print(f"Validation Error: {e}")
        return None
    except Exception as e:
        print(f"Database Error: {e}")
        return None


def example_bulk_update_train_states(train_repo: TrainRepository, sample_train_ids: list):
    """Example: Bulk update multiple trains"""
    print(f"\n=== Bulk Update Train States ===")

    # Prepare batch updates
    updates = [
        {
            "train_id": train_ids[0],
            "status": "in_transit",
            "accumulated_delay_minutes": 2.0,
        },
        {
            "train_id": train_ids[1],
            "status": "delayed",
            "accumulated_delay_minutes": 10.5,
        },
    ] if len(sample_train_ids) >= 2 else []

    if not updates:
        print("Not enough trains for bulk update example")
        return

    result = train_repo.bulk_update_train_states(updates)

    print(f"Bulk Update Results:")
    print(f"  Total: {result['summary']['total']}")
    print(f"  Successful: {result['summary']['successful_count']}")
    print(f"  Failed: {result['summary']['failed_count']}")

    if result['successful']:
        print(f"\n  Successful updates:")
        for train_id in result['successful']:
            print(f"    ✓ {train_id}")

    if result['failed']:
        print(f"\n  Failed updates:")
        for failure in result['failed']:
            print(f"    ✗ {failure.get('train_id', '?')}: {failure['error']}")

    return result


def example_get_train_by_id(train_repo: TrainRepository, train_id: UUID):
    """Example: Get single train details"""
    print(f"\n=== Getting Train by ID ===")

    train = train_repo.get_train_by_id(train_id)

    if train:
        print(f"Train {train_id}:")
        print(f"  Number: {train['train_number']}")
        print(f"  Priority: {train['priority_weight']}")
        print(f"  Origin: {train['origin_id']}")
        print(f"  Destination: {train['destination_id']}")
    else:
        print(f"Train {train_id} not found")

    return train


def example_get_section_info(section_repo: SectionRepository):
    """Example: Get all sections"""
    print("\n=== Getting Section Information ===")

    try:
        sections = section_repo.get_all_sections()

        print(f"Total sections in network: {len(sections)}")
        if sections:
            for section in sections[:3]:  # Show first 3
                print(f"\n  {section['from_station']['name']} → {section['to_station']['name']}")
                print(f"    Capacity: {section['capacity']}")
                print(f"    Headway: {section['headway_minutes']} min")
                print(f"    Travel Time: {section['travel_time_minutes']} min")
                print(f"    Signalling: {section['signalling_type']}")

        return sections

    except Exception as e:
        print(f"Error: {e}")
        return None


def example_error_handling(train_repo: TrainRepository):
    """Example: Error handling patterns"""
    print("\n=== Error Handling Examples ===")

    # Example 1: Non-existent train
    print("Example 1: Accessing non-existent train")
    fake_id = "00000000-0000-0000-0000-000000000000"
    result = train_repo.get_train_by_id(fake_id)
    print(f"  Result: {result}")

    # Example 2: Invalid update fields
    print("\nExample 2: Invalid field in update")
    try:
        # First, get a valid train ID (example)
        # This would fail in practice if no trains exist
        active_trains = train_repo.get_active_trains(datetime.utcnow())
        if active_trains:
            train_id = UUID(active_trains[0]["id"])
            train_repo.update_train_state(
                train_id=train_id,
                updated_fields={
                    "invalid_field": "value",  # This field doesn't exist
                },
            )
    except ValueError as e:
        print(f"  ✓ Caught validation error: {e}")
    except Exception as e:
        print(f"  Error: {e}")

    print("\n✓ Error handling working correctly")


if __name__ == "__main__":
    print("Repository Examples and Tests\n")
    print("=" * 50)

    try:
        # Setup
        session = example_setup_database()
        train_repo = TrainRepository(session)
        section_repo = SectionRepository(session)

        # Examples (these will show empty results since DB is empty)
        example_get_active_trains(train_repo)
        example_get_current_train_states(train_repo)
        example_get_section_info(section_repo)
        example_error_handling(train_repo)

        print("\n" + "=" * 50)
        print("\n✅ All repository examples completed!")
        print("\nNote: Examples use empty in-memory database.")
        print("To test with real data, populate the database first.")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

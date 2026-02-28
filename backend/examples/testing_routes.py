"""
Examples and tests for FastAPI routes.

Demonstrates:
- Health check endpoint
- Optimization run endpoint with request/response validation
- Live state retrieval
- KPI metrics dashboard
- Manual override control
- Status and diagnostics

This uses FastAPI's TestClient to simulate HTTP requests without a running server.
"""

from datetime import datetime, timedelta
from uuid import uuid4, UUID
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Station, Section, Train, TrainSchedule, TrainState, TrainStatus
from app.repositories import TrainRepository, SectionRepository
from app.services import (
    RailwayStateEngine,
    OptimizationService,
    PredictionService,
    SimulationOrchestrator,
)


def setup_test_client():
    """Create test database and FastAPI test client"""
    print("=== Setting Up Test Client ===")

    # Create in-memory database
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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
        Train(
            id=uuid4(),
            train_number="IC-101",
            priority_weight=2.5,
            origin_id=stations["central"].id,
            destination_id=stations["north"].id,
        ),
        Train(
            id=uuid4(),
            train_number="RG-201",
            priority_weight=1.0,
            origin_id=stations["central"].id,
            destination_id=stations["south"].id,
        ),
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

    # Create orchestrator
    orchestrator = SimulationOrchestrator(
        train_repo,
        section_repo,
        state_engine,
        optimizer,
        predictor,
        horizon_minutes=60,
        rolling_step_minutes=5,
    )

    # Create FastAPI app and inject dependencies
    from fastapi import FastAPI
    from app.apis.routes import router

    app = FastAPI()
    app.include_router(router)

    # Override dependency for testing
    def override_get_db_session():
        return session

    def override_get_train_repository():
        return train_repo

    def override_get_section_repository():
        return section_repo

    def override_get_state_engine():
        return state_engine

    def override_get_optimizer():
        return optimizer

    def override_get_predictor():
        return predictor

    def override_get_orchestrator():
        return orchestrator

    from app.apis.routes import (
        get_db_session,
        get_train_repository,
        get_section_repository,
        get_state_engine,
        get_optimizer,
        get_predictor,
        get_orchestrator,
    )

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_train_repository] = override_get_train_repository
    app.dependency_overrides[get_section_repository] = override_get_section_repository
    app.dependency_overrides[get_state_engine] = override_get_state_engine
    app.dependency_overrides[get_optimizer] = override_get_optimizer
    app.dependency_overrides[get_predictor] = override_get_predictor
    app.dependency_overrides[get_orchestrator] = override_get_orchestrator

    client = TestClient(app)

    print(f"✓ Test client ready")
    print(f"  Stations: {len(stations)}")
    print(f"  Sections: {len(sections)}")
    print(f"  Trains: {len(trains)}")

    return client, orchestrator


def example_health_check():
    """Example: Test health check endpoint"""
    print("\n=== Health Check Endpoint ===")

    client, _ = setup_test_client()

    response = client.get("/api/v1/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "services" in data
    assert "timestamp" in data

    print("✓ Health check endpoint works correctly")


def example_optimization_run():
    """Example: Test optimization run endpoint"""
    print("\n=== Optimization Run Endpoint ===")

    client, _ = setup_test_client()

    # Prepare request
    request_body = {
        "include_predictions": True,
        "include_state_snapshot": True,
        "timeout_seconds": None,
    }

    print(f"Request: POST /api/v1/optimization/run")
    print(f"Body: {request_body}")

    response = client.post("/api/v1/optimization/run", json=request_body)
    print(f"\nStatus Code: {response.status_code}")

    assert response.status_code == 200
    data = response.json()

    print(f"Response:")
    print(f"  Cycle Number: {data['cycle_number']}")
    print(f"  Status: {data['status']}")
    print(f"  Weighted Delay: {data['total_weighted_delay']:.1f} min")
    print(f"  Conflicts Resolved: {data['conflicts_resolved']}")
    print(f"  Trains Adjusted: {data['trains_adjusted']}")
    print(f"  Solver Runtime: {data['solver_runtime_seconds']:.2f}s")
    print(f"  Validated: {data['validated']}")
    print(f"  Optimization Success: {data['optimization_success']}")

    assert "cycle_number" in data
    assert "status" in data
    assert "total_weighted_delay" in data
    assert "validated" in data

    print("\n✓ Optimization run endpoint works correctly")


def example_live_state():
    """Example: Test live state endpoint"""
    print("\n=== Live State Endpoint ===")

    client, _ = setup_test_client()

    print(f"Request: GET /api/v1/state/live")

    response = client.get("/api/v1/state/live")
    print(f"\nStatus Code: {response.status_code}")

    assert response.status_code == 200
    data = response.json()

    print(f"Response:")
    print(f"  Active Trains: {data['active_trains']}")
    print(f"  Total Trains: {data['total_trains']}")
    print(f"  Sections Occupied: {data['sections_occupied']}")
    print(f"  Total Sections: {data['total_sections']}")
    print(f"  Average Utilization: {data['average_section_utilization']:.1f}%")
    print(f"  Current Conflicts: {data['current_conflicts']}")
    print(f"  Number of Trains in Response: {len(data['trains'])}")
    print(f"  Number of Sections in Response: {len(data['sections'])}")

    assert "timestamp" in data
    assert "active_trains" in data
    assert "total_trains" in data
    assert "trains" in data
    assert "sections" in data

    if data["trains"]:
        train = data["trains"][0]
        print(f"\n  Sample Train:")
        print(f"    Train Number: {train['train_number']}")
        print(f"    Status: {train['status']}")
        print(f"    Accumulated Delay: {train['accumulated_delay_minutes']:.1f} min")

    print("\n✓ Live state endpoint works correctly")


def example_metrics_dashboard():
    """Example: Test metrics/KPI dashboard endpoint"""
    print("\n=== Metrics Dashboard Endpoint ===")

    client, orchestrator = setup_test_client()

    # Run a cycle first to generate KPIs
    print("Running an orchestration cycle to generate KPIs...")
    orchestrator.execute_cycle()

    print(f"\nRequest: GET /api/v1/metrics")

    response = client.get("/api/v1/metrics")
    print(f"Status Code: {response.status_code}")

    assert response.status_code == 200
    data = response.json()

    if data is None:
        print("Response: None (no KPIs available yet)")
    else:
        print(f"Response:")
        print(f"  Cycle Number: {data['cycle_number']}")
        print(f"  Total Weighted Delay: {data['total_weighted_delay_minutes']:.1f} min")
        print(f"  Average Utilization: {data['average_section_utilization_percent']:.1f}%")
        print(f"  Conflicts Detected: {data['conflicts_detected']}")
        print(f"  Conflicts Avoided: {data['conflicts_avoided']}")
        print(f"  Trains Delayed: {data['trains_delayed']}")
        print(f"  Trains On-Time: {data['trains_on_time']}")
        print(f"  Optimization Runtime: {data['optimization_runtime_seconds']:.2f}s")
        print(f"  Schedule Adherence: {data['schedule_adherence_percent']:.1f}%")
        print(f"  Prediction Accuracy (MAE): {data['prediction_accuracy_mae']:.2f}")

        assert "cycle_number" in data
        assert "total_weighted_delay_minutes" in data
        assert "average_section_utilization_percent" in data

    print("\n✓ Metrics dashboard endpoint works correctly")


def example_manual_override():
    """Example: Test manual override endpoint"""
    print("\n=== Manual Override Endpoint ===")

    client, orchestrator = setup_test_client()

    # Enable override
    print("Enabling manual override...")
    request_body = {
        "enabled": True,
        "reason": "Emergency maintenance detected",
    }

    print(f"Request: POST /api/v1/override")
    print(f"Body: {request_body}")

    response = client.post("/api/v1/override", json=request_body)
    print(f"\nStatus Code: {response.status_code}")

    assert response.status_code == 200
    data = response.json()

    print(f"Response:")
    print(f"  Enabled: {data['enabled']}")
    print(f"  Message: {data['message']}")

    assert data["enabled"] is True
    assert "timestamp" in data

    # Disable override
    print("\nDisabling manual override...")
    request_body["enabled"] = False
    request_body["reason"] = "Maintenance complete"

    response = client.post("/api/v1/override", json=request_body)
    print(f"Status Code: {response.status_code}")

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False

    print("\n✓ Manual override endpoint works correctly")


def example_status_endpoint():
    """Example: Test status/diagnostics endpoint"""
    print("\n=== Status Endpoint ===")

    client, orchestrator = setup_test_client()

    # Run a few cycles to have status data
    print("Running 3 orchestration cycles...")
    for _ in range(3):
        orchestrator.execute_cycle()

    print(f"\nRequest: GET /api/v1/status")

    response = client.get("/api/v1/status")
    print(f"\nStatus Code: {response.status_code}")

    assert response.status_code == 200
    data = response.json()

    print(f"Response:")
    print(f"  Cycles Executed: {data.get('cycles_executed', 0)}")
    print(f"  Successful: {data.get('successful', 0)}")
    print(f"  Failed: {data.get('failed', 0)}")
    print(f"  Success Rate: {data.get('success_rate', '0%')}")
    print(f"  Total Conflicts Avoided: {data.get('total_conflicts_avoided', 0)}")
    print(f"  Timestamp: {data.get('timestamp')}")

    if data.get("latest_kpis"):
        print(f"\n  Latest KPIs Available: Yes")
    else:
        print(f"\n  Latest KPIs Available: No")

    assert "cycles_executed" in data
    assert "success_rate" in data

    print("\n✓ Status endpoint works correctly")


def example_error_handling():
    """Example: Test error handling"""
    print("\n=== Error Handling ===")

    client, _ = setup_test_client()

    # Test invalid request
    print("Testing invalid optimization request...")
    invalid_request = {
        "include_predictions": "invalid",  # Should be boolean
        "timeout_seconds": -1,  # Should be positive
    }

    response = client.post("/api/v1/optimization/run", json=invalid_request)
    print(f"Status Code: {response.status_code}")
    assert response.status_code in [400, 422]  # Validation error
    print(f"✓ Invalid request properly rejected")

    # Test GET with body (should be ignored)
    print("\nTesting GET request without body...")
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    print(f"✓ GET request handled correctly")

    print("\n✓ Error handling works correctly")


def example_endpoint_sequence():
    """Example: Test realistic sequence of API calls"""
    print("\n=== Realistic API Call Sequence ===")

    client, orchestrator = setup_test_client()

    print("\n[1] Check system health...")
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    print(f"    ✓ System healthy")

    print("\n[2] Get current network state...")
    response = client.get("/api/v1/state/live")
    assert response.status_code == 200
    state = response.json()
    print(f"    ✓ {state['active_trains']} active trains, {state['current_conflicts']} conflicts")

    print("\n[3] Run optimization cycle...")
    response = client.post("/api/v1/optimization/run", json={"include_predictions": True})
    assert response.status_code == 200
    result = response.json()
    print(f"    ✓ Cycle {result['cycle_number']}: {result['status']}, delay={result['total_weighted_delay']:.1f}min")

    print("\n[4] Check KPI metrics...")
    response = client.get("/api/v1/metrics")
    assert response.status_code == 200
    metrics = response.json()
    if metrics:
        print(f"    ✓ Utilization {metrics['average_section_utilization_percent']:.1f}%, "
              f"Adherence {metrics['schedule_adherence_percent']:.1f}%")
    else:
        print(f"    ✓ Metrics available")

    print("\n[5] Get orchestrator status...")
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    status = response.json()
    print(f"    ✓ {status['cycles_executed']} cycles executed, "
          f"success rate {status['success_rate']}")

    print("\n[6] Enable manual override for testing...")
    response = client.post(
        "/api/v1/override",
        json={"enabled": True, "reason": "Testing override mode"}
    )
    assert response.status_code == 200
    print(f"    ✓ Manual override enabled")

    print("\n[7] Run cycle with override active...")
    response = client.post("/api/v1/optimization/run", json={})
    assert response.status_code == 200
    print(f"    ✓ Cycle completed with override")

    print("\n[8] Disable override...")
    response = client.post(
        "/api/v1/override",
        json={"enabled": False, "reason": "Resume normal operation"}
    )
    assert response.status_code == 200
    print(f"    ✓ Manual override disabled")

    print("\n✓ Full API sequence executed successfully")


if __name__ == "__main__":
    print("FastAPI Routes Examples and Tests\n")
    print("=" * 70)

    try:
        example_health_check()
        example_optimization_run()
        example_live_state()
        example_metrics_dashboard()
        example_manual_override()
        example_status_endpoint()
        example_error_handling()
        example_endpoint_sequence()

        print("\n" + "=" * 70)
        print("\n✅ All route examples completed!")
        print("\nKey Endpoints Demonstrated:")
        print("  ✓ GET /api/v1/health - Service health check")
        print("  ✓ POST /api/v1/optimization/run - Trigger optimization cycle")
        print("  ✓ GET /api/v1/state/live - Current network state")
        print("  ✓ GET /api/v1/metrics - KPI dashboard metrics")
        print("  ✓ POST /api/v1/override - Manual override control")
        print("  ✓ GET /api/v1/status - Orchestrator status and summary")
        print("\nKey Features Tested:")
        print("  ✓ Request/response validation with Pydantic")
        print("  ✓ Dependency injection integration")
        print("  ✓ Error handling and HTTP status codes")
        print("  ✓ Realistic API call sequences")
        print("  ✓ Manual override mode")
        print("  ✓ KPI metrics retrieval")

    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()

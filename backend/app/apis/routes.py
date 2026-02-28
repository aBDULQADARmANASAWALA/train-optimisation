"""
FastAPI routes for railway optimization control system.

Endpoints:
- POST /optimization/run - Trigger optimization cycle
- GET /state/live - Current network state
- GET /metrics - KPI dashboard metrics
- POST /override - Manual override control
- GET /health - Health check

Uses dependency injection for services.
No business logic in routes - delegates to services.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.config import get_settings
from app.repositories import TrainRepository, SectionRepository
from app.services import (
    RailwayStateEngine,
    OptimizationService,
    PredictionService,
    SimulationOrchestrator,
    ExecutionStatus,
)
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)

# Router
router = APIRouter(prefix="/api/v1", tags=["railway-control"])


# ============================================================================
# Dependency Injection
# ============================================================================

def get_db_session() -> Session:
    """Get database session"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # In production, would use connection pool from config
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def get_train_repository(session: Session = Depends(get_db_session)) -> TrainRepository:
    """Get train repository"""
    return TrainRepository(session)


def get_section_repository(session: Session = Depends(get_db_session)) -> SectionRepository:
    """Get section repository"""
    return SectionRepository(session)


def get_state_engine(
    train_repo: TrainRepository = Depends(get_train_repository),
    section_repo: SectionRepository = Depends(get_section_repository),
) -> RailwayStateEngine:
    """Get state engine"""
    return RailwayStateEngine(train_repo, section_repo, datetime.utcnow())


def get_optimizer() -> OptimizationService:
    """Get optimizer service"""
    settings = get_settings()
    return OptimizationService(max_solver_time_seconds=settings.max_solver_time_seconds)


def get_predictor(
    train_repo: TrainRepository = Depends(get_train_repository),
    section_repo: SectionRepository = Depends(get_section_repository),
) -> PredictionService:
    """Get predictor service"""
    return PredictionService(train_repo, section_repo)


def get_orchestrator(
    train_repo: TrainRepository = Depends(get_train_repository),
    section_repo: SectionRepository = Depends(get_section_repository),
    state_engine: RailwayStateEngine = Depends(get_state_engine),
    optimizer: OptimizationService = Depends(get_optimizer),
    predictor: PredictionService = Depends(get_predictor),
) -> SimulationOrchestrator:
    """Get orchestrator service"""
    settings = get_settings()
    return SimulationOrchestrator(
        train_repo,
        section_repo,
        state_engine,
        optimizer,
        predictor,
        horizon_minutes=settings.optimization_horizon_minutes,
        rolling_step_minutes=settings.rolling_step_minutes,
    )


# ============================================================================
# Request/Response Models
# ============================================================================

class OptimizationRunRequest(BaseModel):
    """Request to run optimization cycle"""
    include_predictions: bool = Field(default=True, description="Include ML predictions")
    include_state_snapshot: bool = Field(default=True, description="Include state snapshot")
    timeout_seconds: Optional[float] = Field(default=None, description="Override solver timeout")


class TrainInfo(BaseModel):
    """Train information in state"""
    train_id: str
    train_number: str
    priority_weight: float
    status: str
    accumulated_delay_minutes: float
    current_section_id: Optional[str] = None
    current_station_id: Optional[str] = None


class SectionLoad(BaseModel):
    """Section utilization info"""
    section_id: str
    current_occupancy: int
    capacity: int
    utilization_percent: float


class NetworkState(BaseModel):
    """Current network state"""
    timestamp: datetime
    active_trains: int
    total_trains: int
    sections_occupied: int
    total_sections: int
    average_section_utilization: float
    current_conflicts: int
    trains: List[TrainInfo]
    sections: List[SectionLoad]


class KPIDashboard(BaseModel):
    """KPI metrics for dashboard"""
    timestamp: datetime
    cycle_number: int
    total_weighted_delay_minutes: float
    average_section_utilization_percent: float
    conflicts_detected: int
    conflicts_avoided: int
    trains_delayed: int
    trains_on_time: int
    optimization_runtime_seconds: float
    schedule_adherence_percent: float
    prediction_accuracy_mae: float


class OptimizationResult(BaseModel):
    """Result of optimization run"""
    cycle_number: int
    status: str
    objective_value: Optional[float]
    total_weighted_delay: float
    conflicts_resolved: int
    trains_adjusted: int
    solver_runtime_seconds: float
    validated: bool
    optimization_success: bool
    message: str


class ManualOverrideRequest(BaseModel):
    """Request to enable/disable manual override"""
    enabled: bool = Field(description="Enable or disable manual override")
    reason: Optional[str] = Field(default=None, description="Reason for override")


class ManualOverrideResponse(BaseModel):
    """Response to manual override request"""
    enabled: bool
    timestamp: datetime
    message: str


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(default="healthy")
    timestamp: datetime
    version: str = "1.0.0"
    services: Dict[str, str]


# ============================================================================
# Health Check
# ============================================================================

@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns status of all services.
    """
    logger.debug("Health check requested")

    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        services={
            "state_engine": "ready",
            "optimizer": "ready",
            "predictor": "ready",
            "orchestrator": "ready",
        },
    )


# ============================================================================
# Optimization Control
# ============================================================================

@router.post("/optimization/run", response_model=OptimizationResult)
async def run_optimization(
    request: OptimizationRunRequest,
    orchestrator: SimulationOrchestrator = Depends(get_orchestrator),
) -> OptimizationResult:
    """
    Trigger one optimization cycle.

    Executes:
    1. Fetch live state
    2. Generate predictions
    3. Run optimizer
    4. Validate and persist

    Returns:
        OptimizationResult with metrics and status
    """
    logger.info("POST /optimization/run - Starting optimization cycle")

    try:
        # Execute cycle
        cycle_result = orchestrator.execute_cycle()

        # Determine overall success
        success = cycle_result.status == ExecutionStatus.SUCCESS

        # Prepare response
        response = OptimizationResult(
            cycle_number=cycle_result.cycle_number,
            status=cycle_result.status.value,
            objective_value=getattr(cycle_result.optimization_result, "objective_value", None),
            total_weighted_delay=cycle_result.kpis.total_weighted_delay_minutes
            if cycle_result.kpis
            else 0.0,
            conflicts_resolved=cycle_result.kpis.conflicts_avoided if cycle_result.kpis else 0,
            trains_adjusted=cycle_result.kpis.trains_delayed if cycle_result.kpis else 0,
            solver_runtime_seconds=cycle_result.duration_seconds,
            validated=cycle_result.validated,
            optimization_success=success,
            message=f"Optimization cycle {cycle_result.cycle_number} completed: {cycle_result.status.value}",
        )

        logger.info(f"Optimization complete: {response.status}, delay={response.total_weighted_delay:.1f}min")
        return response

    except Exception as e:
        logger.error(f"Optimization failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Optimization failed: {str(e)}",
        )


# ============================================================================
# State Monitoring
# ============================================================================

@router.get("/state/live", response_model=NetworkState)
async def get_live_state(
    state_engine: RailwayStateEngine = Depends(get_state_engine),
) -> NetworkState:
    """
    Get current live network state.

    Returns:
        NetworkState with all trains, sections, and utilization
    """
    logger.debug("GET /state/live - Fetching current state")

    try:
        snapshot = state_engine.snapshot_state()

        # Extract train info
        trains = [
            TrainInfo(
                train_id=str(pos["train_id"]),
                train_number=pos["train_number"],
                priority_weight=pos.get("priority_weight", 1.0),
                status=pos.get("status", "unknown"),
                accumulated_delay_minutes=pos.get("accumulated_delay_minutes", 0.0),
                current_section_id=pos.get("current_section_id"),
                current_station_id=pos.get("current_station_id"),
            )
            for pos in snapshot.get("train_positions", [])
        ]

        # Extract section loads (simplified)
        sections = [
            SectionLoad(
                section_id=f"section_{i}",
                current_occupancy=0,
                capacity=4,
                utilization_percent=0.0,
            )
            for i in range(snapshot["network_stats"]["total_sections"])
        ]

        occupancy = snapshot.get("occupancy_summary", {})
        avg_util = (
            occupancy.get("sections_with_trains", 0) / snapshot["network_stats"]["total_sections"] * 100
            if snapshot["network_stats"]["total_sections"] > 0
            else 0
        )

        response = NetworkState(
            timestamp=datetime.utcnow(),
            active_trains=snapshot.get("active_trains_count", 0),
            total_trains=snapshot.get("active_trains_count", 0),
            sections_occupied=occupancy.get("sections_with_trains", 0),
            total_sections=snapshot["network_stats"]["total_sections"],
            average_section_utilization=avg_util,
            current_conflicts=snapshot.get("conflicts", {}).get("total_conflicts", 0),
            trains=trains,
            sections=sections,
        )

        logger.debug(f"State fetched: {response.active_trains} trains, {response.current_conflicts} conflicts")
        return response

    except Exception as e:
        logger.error(f"Failed to fetch state: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch state: {str(e)}",
        )


# ============================================================================
# Metrics & Monitoring
# ============================================================================

@router.get("/metrics", response_model=Optional[KPIDashboard])
async def get_metrics(
    orchestrator: SimulationOrchestrator = Depends(get_orchestrator),
) -> Optional[KPIDashboard]:
    """
    Get latest KPI metrics for dashboard.

    Returns:
        KPIDashboard with latest metrics or None if no cycles run yet
    """
    logger.debug("GET /metrics - Fetching KPI metrics")

    try:
        kpis = orchestrator.get_latest_kpis()

        if kpis is None:
            logger.warning("No KPIs available yet")
            return None

        response = KPIDashboard(
            timestamp=kpis.cycle_timestamp,
            cycle_number=kpis.cycle_number,
            total_weighted_delay_minutes=kpis.total_weighted_delay_minutes,
            average_section_utilization_percent=kpis.average_section_utilization_percent,
            conflicts_detected=kpis.conflicts_detected,
            conflicts_avoided=kpis.conflicts_avoided,
            trains_delayed=kpis.trains_delayed,
            trains_on_time=kpis.trains_on_time,
            optimization_runtime_seconds=kpis.optimization_runtime_seconds,
            schedule_adherence_percent=kpis.schedule_adherence_percent,
            prediction_accuracy_mae=kpis.prediction_accuracy_mae,
        )

        logger.debug(f"Metrics fetched: cycle={response.cycle_number}, delay={response.total_weighted_delay_minutes:.1f}min")
        return response

    except Exception as e:
        logger.error(f"Failed to fetch metrics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch metrics: {str(e)}",
        )


# ============================================================================
# Manual Control
# ============================================================================

@router.post("/override", response_model=ManualOverrideResponse)
async def set_manual_override(
    request: ManualOverrideRequest,
    orchestrator: SimulationOrchestrator = Depends(get_orchestrator),
) -> ManualOverrideResponse:
    """
    Enable/disable manual override mode.

    When enabled, uses last known good schedule instead of optimizing.
    Use for emergency situations.

    Args:
        request: ManualOverrideRequest with enabled flag and reason

    Returns:
        ManualOverrideResponse with confirmation
    """
    logger.info(f"POST /override - Setting override to {request.enabled}")

    try:
        orchestrator.set_manual_override(request.enabled)

        status_msg = "enabled" if request.enabled else "disabled"
        reason_msg = f" ({request.reason})" if request.reason else ""

        response = ManualOverrideResponse(
            enabled=request.enabled,
            timestamp=datetime.utcnow(),
            message=f"Manual override {status_msg}{reason_msg}",
        )

        logger.warning(f"Manual override {status_msg}: {request.reason or 'no reason provided'}")
        return response

    except Exception as e:
        logger.error(f"Failed to set override: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set override: {str(e)}",
        )


# ============================================================================
# Status & Diagnostics
# ============================================================================

@router.get("/status", response_model=Dict[str, Any])
async def get_status(
    orchestrator: SimulationOrchestrator = Depends(get_orchestrator),
) -> Dict[str, Any]:
    """
    Get orchestrator status and summary.

    Returns:
        Status with execution history and metrics
    """
    logger.debug("GET /status - Fetching orchestrator status")

    try:
        summary = orchestrator.get_execution_summary()

        return {
            "cycles_executed": summary.get("cycles_executed", 0),
            "successful": summary.get("successful", 0),
            "failed": summary.get("failed", 0),
            "success_rate": f"{summary.get('success_rate', 0):.1%}",
            "total_conflicts_avoided": summary.get("total_conflicts_avoided", 0),
            "latest_kpis": orchestrator.get_latest_kpis(),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get status: {str(e)}",
        )

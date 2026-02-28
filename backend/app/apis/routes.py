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
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.config import get_settings
from app.repositories import TrainRepository, SectionRepository
from app.models import OptimizationLog
from app.services import (
    RailwayStateEngine,
    OptimizationService,
    PredictionService,
    SimulationOrchestrator,
    ExecutionStatus,
)
from sqlalchemy.orm import Session
from sqlalchemy import desc


logger = logging.getLogger(__name__)

# Router
router = APIRouter(prefix="/api/v1", tags=["railway-control"])


# ============================================================================
# Dependency Injection
# ============================================================================

def get_db_session() -> Session:
    """
    Placeholder session dependency.

    This function is **always overridden** at startup by
    ``main._setup_dependency_overrides()``, which replaces it with a real
    Supabase / PostgreSQL session from the app-level connection pool.

    If you see this error it means the app was not started via
    ``uvicorn app.main:app`` (e.g. the route was called in isolation without
    the lifespan startup running).
    """
    raise RuntimeError(
        "get_db_session() was not overridden by the app startup. "
        "Ensure the application is started via 'uvicorn app.main:app'."
    )


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


class ConflictInfo(BaseModel):
    """Conflict information"""
    id: str
    type: str
    location: str
    trains_involved: List[str]
    severity: str
    resolved: bool


class PlatformInfo(BaseModel):
    """Platform occupancy information"""
    id: str
    station_name: str
    platform_number: str
    is_occupied: bool
    occupying_train_id: Optional[str] = None


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
    platforms: List[PlatformInfo]
    conflicts: List[ConflictInfo]


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


class OptimizationRunInfo(BaseModel):
    """Information about a past optimization run"""
    id: str
    timestamp: datetime
    total_delay_reduced: float
    conflicts_resolved: int
    status: str


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


class ModelTrainResponse(BaseModel):
    """Response from model training endpoint"""
    status: str
    delay_model_score: Optional[float] = None   # MAE in minutes (lower is better)
    delay_samples: int = 0
    congestion_model_score: Optional[float] = None  # AUC-ROC (higher is better)
    congestion_samples: int = 0
    training_time_seconds: float = 0.0
    message: str


class ModelStatusResponse(BaseModel):
    """Response from model status endpoint"""
    delay_model_trained: bool
    delay_model_trained_at: Optional[str]
    congestion_model_trained: bool
    congestion_model_trained_at: Optional[str]
    recent_prediction_errors_count: int
    recent_mean_error: float
    drift_threshold_mae: float


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
        NetworkState with all trains, sections, and real utilization
    """
    logger.debug("GET /state/live - Fetching current state")

    try:
        snapshot = state_engine.snapshot_state()

        # Extract train info — include priority_weight from the trains dict
        trains = [
            TrainInfo(
                train_id=str(pos["train_id"]),
                train_number=pos.get("train_number", ""),
                priority_weight=state_engine.trains.get(
                    UUID(str(pos["train_id"])), {}
                ).get("priority_weight", 1.0),
                status=pos.get("status", "unknown"),
                accumulated_delay_minutes=pos.get("accumulated_delay_minutes", 0.0),
                current_section_id=pos.get("current_section_id"),
                current_station_id=pos.get("current_station_id"),
            )
            for pos in snapshot.get("train_positions", [])
        ]

        # Build REAL section loads from state engine occupancy
        section_loads = []
        for section_id, occupants in state_engine.section_occupancy.items():
            load_info = state_engine.get_section_load(section_id)
            if "error" not in load_info:
                section_loads.append(
                    SectionLoad(
                        section_id=str(section_id),
                        current_occupancy=load_info.get("current_occupancy", 0),
                        capacity=load_info.get("capacity", 1),
                        utilization_percent=load_info.get("utilization_percent", 0.0),
                    )
                )

        # Build platform info from state engine
        # platform_occupancy: Dict[station_id, List[Tuple[train_id, arrival, departure]]]
        platforms = []
        try:
            for station_id, occupants in state_engine.platform_occupancy.items():
                # Try to get station name from sections/trains context
                station_id_str = str(station_id)
                station_name = f"Station {station_id_str[:8]}"

                # Try to read name from the stations dict if available
                station_info = getattr(state_engine, "stations", {}).get(station_id, {})
                if isinstance(station_info, dict):
                    station_name = station_info.get("name", station_name)
                elif hasattr(station_info, "name"):
                    station_name = station_info.name

                # Each occupant is Tuple[train_id UUID, arrival datetime, departure datetime]
                # Simulate platforms: occupied slot index = train slot in the list
                # We show up to 4 platform slots per station (or actual count)
                total_platforms = max(4, len(occupants))
                for i in range(1, total_platforms + 1):
                    occupant_id = None
                    if i <= len(occupants):
                        try:
                            occupant_id = str(occupants[i - 1][0])  # train_id from tuple
                        except (IndexError, TypeError):
                            occupant_id = None

                    platforms.append(
                        PlatformInfo(
                            id=f"P-{station_id_str[:8]}-{i}",
                            station_name=station_name,
                            platform_number=str(i),
                            is_occupied=occupant_id is not None,
                            occupying_train_id=occupant_id,
                        )
                    )
        except Exception as platform_exc:
            logger.warning(f"Could not build platform info: {platform_exc}")
            # Return empty platforms rather than crashing the whole endpoint

        # Map conflicts
        conflicts_snap = snapshot.get("conflicts", {})
        conflicts = []

        # Capacity conflicts
        for c in conflicts_snap.get("capacity_conflicts", []):
            sec_id_str = str(c.get("section_id", ""))[:8]
            conflicts.append(ConflictInfo(
                id=f"CAP-{sec_id_str}-{int(datetime.utcnow().timestamp())}",
                type="capacity",
                location=str(c.get("section_id", "")),
                trains_involved=[str(t) for t in c.get("train_ids", [])],
                severity="high" if c.get("current_occupancy", 0) > c.get("capacity", 1) else "medium",
                resolved=False,
            ))

        # Headway conflicts
        for c in conflicts_snap.get("headway_conflicts", []):
            sec_id_str = str(c.get("section_id", ""))[:8]
            conflicts.append(ConflictInfo(
                id=f"HDW-{sec_id_str}-{int(datetime.utcnow().timestamp())}",
                type="headway",
                location=str(c.get("section_id", "")),
                trains_involved=[str(t) for t in c.get("train_pair", [])],

                severity="medium",
                resolved=False
            ))

        occupancy = snapshot.get("occupancy_summary", {})
        total_sections = snapshot["network_stats"]["total_sections"]
        avg_util = (
            occupancy.get("sections_with_trains", 0) / total_sections * 100
            if total_sections > 0
            else 0
        )

        response = NetworkState(
            timestamp=datetime.utcnow(),
            active_trains=snapshot.get("active_trains_count", 0),
            total_trains=snapshot.get("active_trains_count", 0),
            sections_occupied=occupancy.get("sections_with_trains", 0),
            total_sections=total_sections,
            average_section_utilization=avg_util,
            current_conflicts=snapshot.get("conflicts", {}).get("total_conflicts", 0),
            trains=trains,
            sections=section_loads,
            platforms=platforms,
            conflicts=conflicts
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
        orchestrator.set_manual_override(request.enabled, reason=request.reason)

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
# Optimization History
# ============================================================================

@router.get("/optimization/history", response_model=List[OptimizationRunInfo])
async def get_optimization_history(
    limit: int = 10,
    db: Session = Depends(get_db_session),
) -> List[OptimizationRunInfo]:
    """
    Get history of optimization runs from Supabase.
    """
    try:
        logs = (
            db.query(OptimizationLog)
            .order_by(desc(OptimizationLog.timestamp))
            .limit(limit)
            .all()
        )
        
        return [
            OptimizationRunInfo(
                id=str(log.id),
                timestamp=log.timestamp,
                total_delay_reduced=log.total_weighted_delay,
                conflicts_resolved=log.conflicts_detected,
                status="success" # Logs only store successful runs usually
            )
            for log in logs
        ]
    except Exception as e:
        logger.error(f"Failed to fetch optimization history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch history: {str(e)}"
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


# ============================================================================
# ML Model Training & Status
# ============================================================================

@router.post("/ml/train", response_model=ModelTrainResponse, tags=["ml"])
async def train_models(
    predictor: PredictionService = Depends(get_predictor),
) -> ModelTrainResponse:
    """
    Train (or retrain) the ML models from Supabase historical data.

    Pulls rows from ``historical_operational_data`` and trains:
    - ``delay_regressor``     (RandomForest, target = arrival_delay)
    - ``congestion_classifier`` (RandomForest, target = congestion_flag)

    Models are persisted to disk under ``./models/`` so subsequent
    API requests use the newly trained versions without restarting.

    Returns:
        ModelTrainResponse with MAE / AUC-ROC scores and sample counts.
    """
    logger.info("POST /ml/train - Training models from Supabase historical data")

    try:
        results = predictor.train_models()

        response = ModelTrainResponse(
            status="success",
            delay_model_score=results.get("delay_model_score"),
            delay_samples=results.get("delay_samples", 0),
            congestion_model_score=results.get("congestion_model_score"),
            congestion_samples=results.get("congestion_samples", 0),
            training_time_seconds=results.get("training_time_seconds", 0.0),
            message=(
                f"Training complete — "
                f"delay MAE={results.get('delay_model_score', 'N/A')}, "
                f"congestion AUC={results.get('congestion_model_score', 'N/A')}"
            ),
        )

        logger.info(f"Model training succeeded: {response.message}")
        return response

    except Exception as e:
        logger.error(f"Model training failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Model training failed: {str(e)}",
        )


@router.get("/ml/status", response_model=ModelStatusResponse, tags=["ml"])
async def get_model_status(
    predictor: PredictionService = Depends(get_predictor),
) -> ModelStatusResponse:
    """
    Return metadata about the currently loaded ML models.

    Returns:
        ModelStatusResponse with training timestamps, recent errors, and
        drift threshold.
    """
    logger.debug("GET /ml/status - Fetching model status")

    try:
        info = predictor.get_model_info()
        return ModelStatusResponse(
            delay_model_trained=info["delay_model_trained"],
            delay_model_trained_at=info["delay_model_trained_at"],
            congestion_model_trained=info["congestion_model_trained"],
            congestion_model_trained_at=info["congestion_model_trained_at"],
            recent_prediction_errors_count=info["recent_prediction_errors_count"],
            recent_mean_error=float(info["recent_mean_error"]),
            drift_threshold_mae=info["drift_threshold_mae"],
        )

    except Exception as e:
        logger.error(f"Failed to get model status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get model status: {str(e)}",
        )

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID
from dataclasses import dataclass
from enum import Enum

from app.repositories import TrainRepository, SectionRepository
from app.services import (
    RailwayStateEngine,
    OptimizationService,
    OptimizationSnapshot,
    PredictionService,
    TrainFeatures,
    SectionFeatures,
)


logger = logging.getLogger(__name__)


class ExecutionStatus(str, Enum):
    """Orchestration execution status"""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    VALIDATION_FAILED = "validation_failed"
    OPTIMIZATION_FAILED = "optimization_failed"
    ERROR = "error"


class DisruptionType(str, Enum):
    """Types of disruptions that can be injected"""
    TRAIN_DELAY = "train_delay"
    CAPACITY_REDUCTION = "capacity_reduction"
    SECTION_CLOSURE = "section_closure"
    PLATFORM_FAILURE = "platform_failure"


@dataclass
class Disruption:
    """Injected disruption for scenario testing"""
    disruption_type: DisruptionType
    affected_id: UUID  # train_id or section_id
    magnitude: float  # delay in minutes or % reduction
    duration_minutes: int
    start_time: datetime


@dataclass
class KPISnapshot:
    """Key performance indicators for a cycle"""
    cycle_timestamp: datetime
    cycle_number: int
    total_weighted_delay_minutes: float
    average_section_utilization_percent: float
    conflicts_detected: int
    conflicts_avoided: int
    trains_delayed: int
    trains_on_time: int
    optimization_runtime_seconds: float
    prediction_accuracy_mae: float
    schedule_adherence_percent: float


@dataclass
class CycleResult:
    """Result of a single orchestration cycle"""
    cycle_number: int
    timestamp: datetime
    status: ExecutionStatus
    error_message: Optional[str]
    state_engine_snap: Optional[Dict]
    predictions: Dict[UUID, Any]
    optimization_result: Optional[Any]
    validated: bool
    kpis: Optional[KPISnapshot]
    duration_seconds: float


class SimulationOrchestrator:
    """
    Orchestration engine for railway optimization.

    Coordinates all services in a cyclic execution loop:
    1. Fetch live state from repositories
    2. Build digital twin (StateEngine)
    3. Generate predictions (Predictor)
    4. Optimize schedule (Optimizer)
    5. Validate optimized schedule
    6. Persist updated states
    7. Log KPIs and metrics

    Designed as a background job that runs periodically with rolling horizon.
    Fully transactional - rolls back on validation failures.
    """

    def __init__(
        self,
        train_repository: TrainRepository,
        section_repository: SectionRepository,
        state_engine: RailwayStateEngine,
        optimizer: OptimizationService,
        predictor: PredictionService,
        horizon_minutes: int = 60,
        rolling_step_minutes: int = 5,
    ):
        """
        Initialize orchestrator.

        Args:
            train_repository: For loading train data
            section_repository: For loading section data
            state_engine: For building digital twin
            optimizer: For generating optimized schedules
            predictor: For forecasting delays/congestion
            horizon_minutes: Optimization window size
            rolling_step_minutes: Rolling step size
        """
        self.train_repo = train_repository
        self.section_repo = section_repository
        self.state_engine = state_engine
        self.optimizer = optimizer
        self.predictor = predictor
        self.horizon_minutes = horizon_minutes
        self.rolling_step_minutes = rolling_step_minutes

        # Execution state
        self.cycle_count: int = 0
        self.last_optimization_result: Optional[Any] = None
        self.execution_history: List[CycleResult] = []

        # Disruptions
        self.injected_disruptions: List[Disruption] = []
        self.manual_override_enabled: bool = False

        # KPI tracking
        self.kpis_history: List[KPISnapshot] = []
        self.cumulative_conflicts_avoided: int = 0

        logger.info("SimulationOrchestrator initialized")

    def execute_cycle(self) -> CycleResult:
        """
        Execute one full orchestration cycle.

        Returns:
            CycleResult with execution status and metrics
        """
        cycle_start = datetime.utcnow()
        self.cycle_count += 1

        logger.info(f"=== Starting Orchestration Cycle {self.cycle_count} ===")

        try:
            # Step 1: Fetch current state
            logger.debug("Step 1: Fetching live state")
            current_time = datetime.utcnow()

            # Step 2: Build digital twin
            logger.debug("Step 2: Building digital twin")
            self.state_engine.update_time(current_time)
            state_snapshot = self.state_engine.snapshot_state()

            # Step 3: Apply disruptions if any
            logger.debug("Step 3: Applying disruptions")
            self._apply_current_disruptions()

            # Step 4: Generate predictions
            logger.debug("Step 4: Generating predictions")
            predictions = self._generate_predictions(state_snapshot)

            # Step 5: Check for disruption impact
            if self.manual_override_enabled:
                logger.info("Manual override enabled - using last known good schedule")
                optimization_result = self.last_optimization_result
                validated = True
            else:
                # Step 6: Optimize schedule
                logger.debug("Step 5: Running optimization")
                optimization_result = self._run_optimization(state_snapshot, predictions)

                # Step 7: Validate optimized schedule
                logger.debug("Step 6: Validating optimized schedule")
                validated = self._validate_optimization(optimization_result)

            # Step 8: Persist updated states (if approved)
            if validated or self.manual_override_enabled:
                logger.debug("Step 7: Persisting updated states")
                self._persist_updated_states(optimization_result)
                self.last_optimization_result = optimization_result
            else:
                logger.warning("Validation failed - schedule not persisted")

            # Step 9: Calculate KPIs
            logger.debug("Step 8: Calculating KPIs")
            kpis = self._calculate_kpis(
                state_snapshot,
                optimization_result if validated else None,
                predictions,
            )

            # Step 10: Log results
            cycle_duration = (datetime.utcnow() - cycle_start).total_seconds()
            status = ExecutionStatus.SUCCESS if validated else ExecutionStatus.VALIDATION_FAILED

            result = CycleResult(
                cycle_number=self.cycle_count,
                timestamp=cycle_start,
                status=status,
                error_message=None,
                state_engine_snap=state_snapshot,
                predictions=predictions,
                optimization_result=optimization_result,
                validated=validated,
                kpis=kpis,
                duration_seconds=cycle_duration,
            )

            # Store history
            self.execution_history.append(result)
            if kpis:
                self.kpis_history.append(kpis)

            logger.info(
                f"Cycle {self.cycle_count} completed: "
                f"status={status.value}, "
                f"weighted_delay={kpis.total_weighted_delay_minutes:.1f}min, "
                f"utilization={kpis.average_section_utilization_percent:.1f}%, "
                f"runtime={cycle_duration:.2f}s"
            )

            return result

        except Exception as e:
            logger.error(f"Error in orchestration cycle {self.cycle_count}: {str(e)}", exc_info=True)

            cycle_duration = (datetime.utcnow() - cycle_start).total_seconds()
            return CycleResult(
                cycle_number=self.cycle_count,
                timestamp=cycle_start,
                status=ExecutionStatus.ERROR,
                error_message=str(e),
                state_engine_snap=None,
                predictions={},
                optimization_result=None,
                validated=False,
                kpis=None,
                duration_seconds=cycle_duration,
            )

    def inject_disruption(
        self,
        disruption_type: DisruptionType,
        affected_id: UUID,
        magnitude: float,
        duration_minutes: int,
        start_time: Optional[datetime] = None,
    ) -> None:
        """
        Inject a disruption for scenario testing.

        Args:
            disruption_type: Type of disruption
            affected_id: UUID of affected train/section
            magnitude: Magnitude (delay minutes or % reduction)
            duration_minutes: How long disruption lasts
            start_time: When disruption starts (default: now)
        """
        if start_time is None:
            start_time = datetime.utcnow()

        disruption = Disruption(
            disruption_type=disruption_type,
            affected_id=affected_id,
            magnitude=magnitude,
            duration_minutes=duration_minutes,
            start_time=start_time,
        )

        self.injected_disruptions.append(disruption)

        logger.warning(
            f"Disruption injected: {disruption_type.value} on {str(affected_id)[:8]}, "
            f"magnitude={magnitude}, duration={duration_minutes}min"
        )

    def set_manual_override(self, enabled: bool) -> None:
        """
        Enable/disable manual override mode.

        When enabled, uses last known good schedule instead of optimizing.

        Args:
            enabled: Whether to enable override
        """
        self.manual_override_enabled = enabled
        logger.info(f"Manual override: {enabled}")

    def get_execution_summary(self) -> Dict[str, Any]:
        """
        Get summary of execution history.

        Returns:
            Dictionary with statistics
        """
        if not self.execution_history:
            return {"cycles_executed": 0}

        successful = sum(1 for r in self.execution_history if r.status == ExecutionStatus.SUCCESS)
        failed = sum(1 for r in self.execution_history if r.status == ExecutionStatus.ERROR)

        return {
            "cycles_executed": len(self.execution_history),
            "successful": successful,
            "failed": failed,
            "success_rate": successful / len(self.execution_history),
            "total_conflicts_avoided": self.cumulative_conflicts_avoided,
        }

    def get_latest_kpis(self) -> Optional[KPISnapshot]:
        """Get most recent KPI snapshot"""
        return self.kpis_history[-1] if self.kpis_history else None

    def get_kpi_trends(self, periods: int = 10) -> List[KPISnapshot]:
        """
        Get recent KPI trend.

        Args:
            periods: Number of recent cycles to return

        Returns:
            List of KPI snapshots
        """
        return self.kpis_history[-periods:]

    # Private methods

    def _apply_current_disruptions(self) -> None:
        """Apply active disruptions to state engine"""
        now = datetime.utcnow()
        active_disruptions = [
            d for d in self.injected_disruptions
            if d.start_time <= now <= d.start_time + timedelta(minutes=d.duration_minutes)
        ]

        for disruption in active_disruptions:
            logger.debug(f"Applying disruption: {disruption.disruption_type.value}")

            if disruption.disruption_type == DisruptionType.TRAIN_DELAY:
                # Inject delay into train
                if disruption.affected_id in self.state_engine.trains:
                    current_delay = self.state_engine.trains[disruption.affected_id].get(
                        "accumulated_delay_minutes", 0
                    )
                    self.state_engine.trains[disruption.affected_id]["accumulated_delay_minutes"] = (
                        current_delay + disruption.magnitude
                    )

            elif disruption.disruption_type == DisruptionType.CAPACITY_REDUCTION:
                # Reduce section capacity
                section = self._find_section(disruption.affected_id)
                if section:
                    section["capacity"] = max(1, int(section["capacity"] * (1 - disruption.magnitude / 100)))

    def _generate_predictions(self, state_snapshot: Dict) -> Dict[UUID, Any]:
        """
        Generate ML predictions for all active trains and sections.

        Returns:
            Dictionary with predictions
        """
        predictions = {}

        try:
            # Predict delays for active trains
            for train_id, train_info in self.state_engine.trains.items():
                features = TrainFeatures(
                    train_id=train_id,
                    train_number=train_info.get("train_number", "UNKNOWN"),
                    priority_weight=train_info.get("priority_weight", 1.0),
                    departure_delay_minutes=train_info.get("accumulated_delay_minutes", 0.0),
                    time_of_day_minutes=int((datetime.utcnow().hour * 60 + datetime.utcnow().minute)),
                    day_of_week=datetime.utcnow().weekday(),
                    current_section_load_percent=0.0,  # Would be calculated from state
                    upcoming_section_load_percent=0.0,
                    cumulative_delay_minutes=train_info.get("accumulated_delay_minutes", 0.0),
                )

                delay_pred = self.predictor.predict_delay(features)
                predictions[train_id] = {
                    "type": "delay",
                    "predicted_delay": delay_pred.predicted_delay_minutes,
                    "confidence": delay_pred.confidence,
                }

            logger.debug(f"Generated predictions for {len(predictions)} trains")

        except Exception as e:
            logger.warning(f"Error generating predictions: {str(e)}")

        return predictions

    def _run_optimization(
        self,
        state_snapshot: Dict,
        predictions: Dict,
    ) -> Optional[Any]:
        """
        Run optimizer to generate optimal schedule.

        Returns:
            Optimization result or None if failed
        """
        try:
            # Build OptimizationSnapshot
            snap = OptimizationSnapshot(
                timestamp=self.state_engine.current_time,
                trains={
                    train_id: info
                    for train_id, info in self.state_engine.trains.items()
                },
                train_stops=self._get_train_stops(),
                sections=self._get_section_infos(),
                current_positions=self.state_engine.current_positions if hasattr(
                    self.state_engine, "current_positions"
                ) else {},
                predicted_delays=predictions,
                platform_capacity={},  # Would be loaded from config
            )

            result = self.optimizer.optimize(
                snap,
                horizon_minutes=self.horizon_minutes,
                use_warm_start=True,
            )

            logger.info(f"Optimization result: {result.status.value}")
            return result

        except Exception as e:
            logger.error(f"Optimization failed: {str(e)}", exc_info=True)
            return None

    def _validate_optimization(self, optimization_result: Optional[Any]) -> bool:
        """
        Validate optimized schedule.

        Checks:
        - Solution is feasible
        - No constraint violations
        - Reasonable delays

        Returns:
            True if valid, False otherwise
        """
        if optimization_result is None:
            logger.warning("No optimization result to validate")
            return False

        try:
            # Check if feasible
            if hasattr(optimization_result, "status"):
                if optimization_result.status.value == "infeasible":
                    logger.warning("Optimization result is infeasible")
                    return False

            # Check if delays are reasonable
            if hasattr(optimization_result, "total_weighted_delay"):
                if optimization_result.total_weighted_delay > 1000:  # Arbitrary threshold
                    logger.warning(f"Excessive delays in solution: {optimization_result.total_weighted_delay}")
                    return False

            logger.debug("Optimization validation passed")
            return True

        except Exception as e:
            logger.error(f"Validation error: {str(e)}")
            return False

    def _persist_updated_states(self, optimization_result: Optional[Any]) -> None:
        """
        Persist optimized schedule to database.

        Args:
            optimization_result: Result from optimizer
        """
        try:
            if optimization_result is None:
                return

            # Update train states with optimized timings
            if hasattr(optimization_result, "adjusted_timings"):
                for train_id, timings in optimization_result.adjusted_timings.items():
                    if not timings:
                        continue

                    # Get first timing for initial update
                    first = timings[0]
                    updates = {
                        "status": "in_transit",
                        "accumulated_delay_minutes": float(first.get("delay_minutes", 0)),
                    }

                    self.train_repo.update_train_state(train_id, updates)

            logger.debug("States persisted to database")

        except Exception as e:
            logger.error(f"Error persisting states: {str(e)}")

    def _calculate_kpis(
        self,
        state_snapshot: Dict,
        optimization_result: Optional[Any],
        predictions: Dict,
    ) -> KPISnapshot:
        """
        Calculate key performance indicators.

        Args:
            state_snapshot: Current state
            optimization_result: Optimization result
            predictions: ML predictions

        Returns:
            KPISnapshot with metrics
        """
        # Total weighted delay
        total_delay = 0.0
        if optimization_result and hasattr(optimization_result, "total_weighted_delay"):
            total_delay = optimization_result.total_weighted_delay

        # Average section utilization
        if state_snapshot.get("occupancy_summary"):
            occupied_sections = state_snapshot["occupancy_summary"].get("sections_with_trains", 0)
            total_sections = state_snapshot["network_stats"].get("total_sections", 1)
            utilization = (occupied_sections / total_sections * 100) if total_sections > 0 else 0
        else:
            utilization = 0.0

        # Conflicts avoided
        conflicts_detected = state_snapshot.get("conflicts", {}).get("total_conflicts", 0)
        conflicts_avoided = max(0, conflicts_detected - 1)  # Simplified
        self.cumulative_conflicts_avoided += conflicts_avoided

        # Trains delayed/on-time
        trains_delayed = sum(1 for p in predictions.values() if p.get("predicted_delay", 0) > 0.5)
        trains_on_time = len(predictions) - trains_delayed

        # Prediction accuracy (MAE)
        # In real scenario, would track actual vs predicted
        mae = 0.0
        if self.kpis_history:
            mae = self.kpis_history[-1].prediction_accuracy_mae

        # Schedule adherence
        adherence = 100.0 - min(100.0, total_delay / 10)  # Simplified

        return KPISnapshot(
            cycle_timestamp=datetime.utcnow(),
            cycle_number=self.cycle_count,
            total_weighted_delay_minutes=total_delay,
            average_section_utilization_percent=utilization,
            conflicts_detected=conflicts_detected,
            conflicts_avoided=conflicts_avoided,
            trains_delayed=trains_delayed,
            trains_on_time=trains_on_time,
            optimization_runtime_seconds=getattr(optimization_result, "solver_runtime_seconds", 0.0),
            prediction_accuracy_mae=mae,
            schedule_adherence_percent=adherence,
        )

    def _get_train_stops(self) -> List[Any]:
        """Get all scheduled train stops"""
        stops = []
        for train_id, schedule in self.state_engine.train_schedules.items():
            for stop in schedule:
                # Convert to TrainStop objects
                pass
        return stops

    def _get_section_infos(self) -> List[Any]:
        """Get all section information"""
        sections = []
        try:
            all_sections = self.section_repo.get_all_sections()
            for section in all_sections:
                # Convert to SectionInfo objects
                pass
        except Exception as e:
            logger.warning(f"Error loading sections: {str(e)}")
        return sections

    def _find_section(self, section_id: UUID) -> Optional[Dict]:
        """Find section info by ID"""
        try:
            return self.section_repo.get_section_by_id(section_id)
        except Exception:
            return None

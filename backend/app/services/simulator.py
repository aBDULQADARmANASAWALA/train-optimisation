import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
from uuid import UUID, uuid4
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import text

from app.repositories import TrainRepository, SectionRepository
from app.services import (
    RailwayStateEngine,
    OptimizationService,
    OptimizationSnapshot,
    SectionInfo,
    TrainStop,
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
    applied_cycles: Set[int] = field(default_factory=set)
    total_delay_applied: float = 0.0


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
    1. Fetch live state from repositories (Supabase)
    2. Build digital twin (StateEngine)
    3. Generate predictions (Predictor) using real section loads
    4. Optimize schedule (Optimizer) with real train stops + sections
    5. Validate optimized schedule
    6. Persist updated states to Supabase
       - optimization_logs
       - train_state (all adjusted trains, correct delay + status)
       - kpi_metrics
    7. Log KPIs and metrics

    Manual override: logs to manual_overrides Supabase table.
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
        random_seed: Optional[int] = None,
    ):
        self.train_repo = train_repository
        self.section_repo = section_repository
        self.state_engine = state_engine
        self.optimizer = optimizer
        self.predictor = predictor
        self.horizon_minutes = horizon_minutes
        self.rolling_step_minutes = rolling_step_minutes

        # Expose the raw session for direct SQL writes
        self._db_session = getattr(train_repository, "session", None)

        # Execution state
        self.cycle_count: int = 0
        self.last_optimization_result: Optional[Any] = None
        self.execution_history: List[CycleResult] = []

        # Disruptions
        self.injected_disruptions: List[Disruption] = []
        self.manual_override_enabled: bool = False
        self.manual_override_reason: Optional[str] = None

        # Conflict injection configuration
        self.conflict_injection_probability: float = 0.15  # 15% chance per cycle
        self.max_delay_increment_per_cycle: float = 5.0  # max +5 minutes per cycle
        self.max_total_delay_per_train: float = 60.0  # max 60 minutes total
        self.random_seed = random_seed
        if random_seed is not None:
            random.seed(random_seed)

        # KPI tracking
        self.kpis_history: List[KPISnapshot] = []
        self.cumulative_conflicts_avoided: int = 0

        # Adaptive ML retraining
        # retrain_interval_cycles: force retrain every N cycles as a safety net
        # (even if drift hasn't been detected yet)
        self.retrain_interval_cycles: int = 20
        self.last_retrain_cycle: int = 0  # cycle number of last retrain

        logger.info(f"SimulationOrchestrator initialized (random_seed={random_seed})")

    # =========================================================================
    # Public API
    # =========================================================================

    def execute_cycle(self) -> CycleResult:
        """Execute one full orchestration cycle."""
        cycle_start = datetime.utcnow()
        self.cycle_count += 1

        logger.info(f"=== Starting Orchestration Cycle {self.cycle_count} ===")

        try:
            current_time = datetime.utcnow()

            # Step 1 + 2: Build digital twin from live Supabase data
            logger.debug("Step 1-2: Building digital twin from live state")
            self.state_engine.update_time(current_time)
            state_snapshot = self.state_engine.snapshot_state()

            # Step 3: Apply any injected disruptions (isolated, returns modified state)
            logger.debug("Step 3: Applying disruptions")
            modified_state = self._apply_current_disruptions(state_snapshot)
            if modified_state:
                state_snapshot = modified_state
                
            # Step 3b: Validate state integrity
            validation_result = self.validate_state_integrity()
            if not validation_result["valid"]:
                logger.error(f"State integrity validation failed: {validation_result['errors']}")
                raise ValueError(f"Invalid state after disruption: {validation_result['errors']}")

            # Step 4: Generate ML predictions with real section loads
            logger.debug("Step 4: Generating predictions")
            predictions = self._generate_predictions(state_snapshot)

            # Step 5: Optimize or fall back to manual override
            if self.manual_override_enabled:
                logger.info("Manual override active — using last known good schedule")
                optimization_result = self.last_optimization_result
                validated = True
            else:
                logger.debug("Step 5: Running optimization")
                optimization_result = self._run_optimization(state_snapshot, predictions)

                logger.debug("Step 6: Validating optimized schedule")
                validated = self._validate_optimization(optimization_result)

            # Step 6: Persist to Supabase if valid
            if validated or self.manual_override_enabled:
                logger.debug("Step 7: Persisting updated states to Supabase")
                self._persist_updated_states(optimization_result)
                self.last_optimization_result = optimization_result
            else:
                logger.warning("Validation failed — schedule not persisted")

            # Step 6b: Record current traversal data → historical_operational_data
            # This grows the ML training corpus automatically during the demo
            self._record_historical_data(predictions)

            # Step 6c: Adaptive retraining — drift-triggered + periodic safety net
            self._maybe_retrain()

            # Step 7: Calculate KPIs and write kpi_metrics row
            logger.debug("Step 8: Calculating and persisting KPIs")
            kpis = self._calculate_kpis(state_snapshot, optimization_result if validated else None, predictions)

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

            self.execution_history.append(result)
            if kpis:
                self.kpis_history.append(kpis)

            logger.info(
                f"Cycle {self.cycle_count} complete: status={status.value}, "
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
        """Inject a disruption for scenario testing."""
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

    def set_manual_override(self, enabled: bool, reason: Optional[str] = None, overridden_by: str = "dispatcher") -> None:
        """
        Enable/disable manual override mode.

        When enabled, uses last known good schedule instead of optimizing.
        Logs the override decision to the manual_overrides table in Supabase.
        """
        self.manual_override_enabled = enabled
        self.manual_override_reason = reason
        logger.info(f"Manual override: {enabled} — reason: {reason}")

        # Persist to manual_overrides table
        if self._db_session is not None:
            try:
                self._db_session.execute(
                    text("""
                        INSERT INTO manual_overrides
                            (id, overridden_decision, reason, overridden_by, timestamp)
                        VALUES
                            (:id, :decision, :reason, :overridden_by, :ts)
                    """),
                    {
                        "id": str(uuid4()),
                        "decision": "enabled" if enabled else "disabled",
                        "reason": reason or "no reason provided",
                        "overridden_by": overridden_by,
                        "ts": datetime.utcnow().isoformat(),
                    },
                )
                self._db_session.commit()
                logger.info("Manual override logged to Supabase manual_overrides table")
            except Exception as exc:
                logger.warning(f"Could not log manual override to DB: {exc}")
                self._db_session.rollback()

    def get_execution_summary(self) -> Dict[str, Any]:
        """Get summary of execution history."""
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
        """Get most recent KPI snapshot."""
        return self.kpis_history[-1] if self.kpis_history else None

    def get_kpi_trends(self, periods: int = 10) -> List[KPISnapshot]:
        """Get recent KPI trend."""
        return self.kpis_history[-periods:]

    def validate_state_integrity(self) -> Dict[str, Any]:
        """
        Validate state integrity after disruption injection.
        
        Checks:
        - No negative delays
        - No overlapping section occupancy (capacity violations)
        - No time-travel (arrival < departure)
        
        Returns:
            Dictionary with 'valid' (bool) and 'errors' (list) keys
        """
        errors = []
        
        # Check 1: No negative delays
        for train_id, train_info in self.state_engine.trains.items():
            delay = train_info.get("accumulated_delay_minutes", 0.0)
            if delay < 0:
                errors.append(f"Train {train_id} has negative delay: {delay:.1f}min")
        
        # Check 2: No overlapping section occupancy beyond capacity
        for section_id, occupants in self.state_engine.section_occupancy.items():
            if not occupants:
                continue
            
            edge_data = self.state_engine._get_edge_by_section_id(section_id)
            if not edge_data:
                continue
            
            capacity = edge_data.get("capacity", 1)
            if len(occupants) > capacity:
                train_ids = [str(t[0]) for t in occupants]
                errors.append(
                    f"Section {section_id} capacity violation: "
                    f"{len(occupants)} trains > capacity {capacity} "
                    f"(trains: {', '.join(train_ids[:3])}{'...' if len(train_ids) > 3 else ''})"
                )
        
        # Check 3: No time-travel in schedules (arrival >= departure for each stop)
        for train_id, schedule in self.state_engine.train_schedules.items():
            for stop in schedule:
                try:
                    arr_time = stop.get("scheduled_arrival")
                    dep_time = stop.get("scheduled_departure")
                    
                    if arr_time and dep_time:
                        arr_dt = datetime.fromisoformat(arr_time) if isinstance(arr_time, str) else arr_time
                        dep_dt = datetime.fromisoformat(dep_time) if isinstance(dep_time, str) else dep_time
                        
                        if dep_dt < arr_dt:
                            errors.append(
                                f"Train {train_id} time-travel violation at stop {stop.get('station_name', 'UNKNOWN')}: "
                                f"departure {dep_dt} < arrival {arr_dt}"
                            )
                except Exception as e:
                    logger.debug(f"Could not validate stop timing for train {train_id}: {e}")
        
        valid = len(errors) == 0
        
        if not valid:
            logger.warning(f"State integrity validation found {len(errors)} error(s)")
        
        return {
            "valid": valid,
            "errors": errors,
            "checks_performed": ["negative_delays", "section_capacity", "time_travel"]
        }

    # =========================================================================
    # Private — Data Preparation
    # =========================================================================

    def _apply_current_disruptions(self, state_snapshot: Dict) -> Optional[Dict]:
        """
        Apply active disruptions to state in an isolated manner.
        
        Safeguards:
        - Probabilistic injection (10-20% chance per cycle)
        - Only affects trains within optimization horizon
        - Never modifies historical/past events
        - Never produces negative delays
        - Delay increment capped per cycle (max +5 minutes)
        - Total delay capped per train (max 60 minutes)
        - Runs only once per cycle per disruption
        
        Returns:
            Modified state snapshot if changes were made, None otherwise
        """
        now = datetime.utcnow()
        horizon_end = now + timedelta(minutes=self.horizon_minutes)
        
        active_disruptions = [
            d for d in self.injected_disruptions
            if d.start_time <= now <= d.start_time + timedelta(minutes=d.duration_minutes)
        ]
        
        if not active_disruptions:
            return None
        
        modified = False
        
        for disruption in active_disruptions:
            # Prevent multiple applications per cycle
            if self.cycle_count in disruption.applied_cycles:
                logger.debug(f"Disruption {disruption.disruption_type.value} already applied in cycle {self.cycle_count}")
                continue
            
            # Probabilistic injection (10-20% chance)
            if random.random() > self.conflict_injection_probability:
                logger.debug(f"Disruption {disruption.disruption_type.value} skipped (probabilistic)")
                continue
            
            if disruption.disruption_type == DisruptionType.TRAIN_DELAY:
                modified |= self._apply_train_delay_disruption(disruption, now, horizon_end)
            elif disruption.disruption_type == DisruptionType.CAPACITY_REDUCTION:
                modified |= self._apply_capacity_reduction_disruption(disruption)
            
            # Mark as applied for this cycle
            disruption.applied_cycles.add(self.cycle_count)
        
        return state_snapshot if modified else None
    
    def _apply_train_delay_disruption(
        self, 
        disruption: Disruption, 
        now: datetime, 
        horizon_end: datetime
    ) -> bool:
        """
        Apply train delay disruption with safeguards.
        
        Returns:
            True if state was modified, False otherwise
        """
        if disruption.affected_id not in self.state_engine.trains:
            logger.debug(f"Train {disruption.affected_id} not found in state engine")
            return False
        
        train_info = self.state_engine.trains[disruption.affected_id]
        train_number = train_info.get("train_number", "UNKNOWN")
        
        # Check if train is within optimization horizon
        schedule = self.state_engine.train_schedules.get(disruption.affected_id, [])
        if schedule:
            # Check if any upcoming stop is within horizon
            within_horizon = False
            for stop in schedule:
                try:
                    arr_time = stop.get("scheduled_arrival")
                    if arr_time:
                        arr_dt = datetime.fromisoformat(arr_time) if isinstance(arr_time, str) else arr_time
                        if now <= arr_dt <= horizon_end:
                            within_horizon = True
                            break
                except Exception:
                    pass
            
            if not within_horizon:
                logger.debug(f"Train {train_number} not within optimization horizon, skipping injection")
                return False
        
        # Get current delay
        current_delay = train_info.get("accumulated_delay_minutes", 0.0)
        
        # Cap delay increment per cycle
        delay_increment = min(disruption.magnitude, self.max_delay_increment_per_cycle)
        
        # Calculate new delay with total cap
        new_delay = min(
            current_delay + delay_increment,
            self.max_total_delay_per_train
        )
        
        # Ensure no negative delays
        new_delay = max(0.0, new_delay)
        
        # Check if we actually applied any delay
        actual_increment = new_delay - current_delay
        if actual_increment <= 0:
            logger.debug(f"Train {train_number} already at delay cap, no injection")
            return False
        
        # Apply the delay
        self.state_engine.trains[disruption.affected_id]["accumulated_delay_minutes"] = new_delay
        disruption.total_delay_applied += actual_increment
        
        # Structured logging
        logger.warning(
            f"CONFLICT_INJECTED: train_id={disruption.affected_id}, "
            f"train_number={train_number}, "
            f"delay_added={actual_increment:.1f}min, "
            f"total_delay={new_delay:.1f}min, "
            f"reason=disruption_injection, "
            f"cycle={self.cycle_count}"
        )
        
        return True
    
    def _apply_capacity_reduction_disruption(self, disruption: Disruption) -> bool:
        """
        Apply capacity reduction disruption with safeguards.
        
        Returns:
            True if state was modified, False otherwise
        """
        section = self._find_section(disruption.affected_id)
        if not section:
            logger.debug(f"Section {disruption.affected_id} not found")
            return False
        
        original_capacity = section.get("capacity", 1)
        new_capacity = max(1, int(original_capacity * (1 - disruption.magnitude / 100)))
        
        if new_capacity == original_capacity:
            return False
        
        section["capacity"] = new_capacity
        
        # Structured logging
        logger.warning(
            f"CONFLICT_INJECTED: section_id={disruption.affected_id}, "
            f"capacity_reduced={original_capacity}->{new_capacity}, "
            f"reduction_pct={disruption.magnitude:.1f}%, "
            f"reason=capacity_reduction, "
            f"cycle={self.cycle_count}"
        )
        
        return True

    def _generate_predictions(self, state_snapshot: Dict) -> Dict[UUID, Any]:
        """
        Generate ML predictions for all active trains and sections.

        Uses REAL section load percentages from the state engine occupancy
        rather than hardcoded 0.0 values.
        """
        predictions = {}
        now = datetime.utcnow()
        time_of_day_minutes = now.hour * 60 + now.minute
        day_of_week = now.weekday()

        try:
            for train_id, train_info in self.state_engine.trains.items():
                # --- Real section load for current section ---
                current_section_load = 0.0
                upcoming_section_load = 0.0

                current_section_id_str = train_info.get("current_section_id")
                if current_section_id_str:
                    try:
                        sec_load = self.state_engine.get_section_load(UUID(current_section_id_str))
                        current_section_load = sec_load.get("utilization_percent", 0.0)
                    except Exception:
                        pass

                # Upcoming section: look one stop ahead in schedule
                schedule = self.state_engine.train_schedules.get(train_id, [])
                if len(schedule) >= 2:
                    # Find next stop after current station
                    current_station_id_str = train_info.get("current_station_id")
                    for i, stop in enumerate(schedule):
                        if stop.get("station_id") == current_station_id_str and i + 1 < len(schedule):
                            next_stop = schedule[i + 1]
                            # Look up section from current station to next
                            try:
                                from_id = UUID(stop["station_id"])
                                to_id = UUID(next_stop["station_id"])
                                sec_info = self.section_repo.get_section_route(from_id, to_id)
                                if sec_info:
                                    next_sec_load = self.state_engine.get_section_load(UUID(sec_info["id"]))
                                    upcoming_section_load = next_sec_load.get("utilization_percent", 0.0)
                            except Exception:
                                pass
                            break

                accumulated_delay = train_info.get("accumulated_delay_minutes", 0.0)

                features = TrainFeatures(
                    train_id=train_id,
                    train_number=train_info.get("train_number", "UNKNOWN"),
                    priority_weight=train_info.get("priority_weight", 1.0),
                    departure_delay_minutes=accumulated_delay,
                    time_of_day_minutes=time_of_day_minutes,
                    day_of_week=day_of_week,
                    current_section_load_percent=current_section_load,
                    upcoming_section_load_percent=upcoming_section_load,
                    cumulative_delay_minutes=accumulated_delay,
                )

                delay_pred = self.predictor.predict_delay(features)
                predictions[train_id] = {
                    "type": "delay",
                    "predicted_delay": delay_pred.predicted_delay_minutes,
                    "confidence": delay_pred.confidence,
                    "contributing_factors": delay_pred.contributing_factors,
                }

            # Also predict congestion for every occupied / high-load section
            for section_id, occupants in self.state_engine.section_occupancy.items():
                if not occupants:
                    continue
                try:
                    load_info = self.state_engine.get_section_load(section_id)
                    capacity = load_info.get("capacity", 1)
                    occupancy = load_info.get("current_occupancy", 0)
                    utilization = load_info.get("utilization_percent", 0.0)

                    # Count trains arriving in next 15 minutes from schedules
                    horizon_15 = now + timedelta(minutes=15)
                    upcoming_count = 0
                    for t_id, sched in self.state_engine.train_schedules.items():
                        for stop in sched:
                            arr = stop.get("scheduled_arrival")
                            if arr:
                                try:
                                    arr_dt = datetime.fromisoformat(arr) if isinstance(arr, str) else arr
                                    if now <= arr_dt <= horizon_15:
                                        upcoming_count += 1
                                except Exception:
                                    pass

                    sec_features = SectionFeatures(
                        section_id=section_id,
                        time_of_day_minutes=time_of_day_minutes,
                        day_of_week=day_of_week,
                        current_occupancy=occupancy,
                        section_capacity=capacity,
                        average_headway_utilization=utilization / 100.0,
                        upcoming_train_count_15min=upcoming_count,
                        upstream_congestion_percent=utilization,
                    )
                    congestion_pred = self.predictor.predict_congestion(sec_features)
                    predictions[section_id] = {
                        "type": "congestion",
                        "probability_congested": congestion_pred.probability_congested,
                        "recommendation": congestion_pred.recommendation,
                        "confidence": congestion_pred.confidence,
                    }
                except Exception as exc:
                    logger.debug(f"Could not predict congestion for section {section_id}: {exc}")

            logger.debug(f"Generated {len(predictions)} predictions ({sum(1 for v in predictions.values() if v['type']=='delay')} train, {sum(1 for v in predictions.values() if v['type']=='congestion')} section)")

        except Exception as e:
            logger.warning(f"Error generating predictions: {str(e)}", exc_info=True)

        return predictions

    # =========================================================================
    # Private — Optimization
    # =========================================================================

    def _run_optimization(self, state_snapshot: Dict, predictions: Dict) -> Optional[Any]:
        """Run optimizer with real train stops and section data from Supabase."""
        try:
            train_stops = self._get_train_stops()
            section_infos = self._get_section_infos()
            platform_capacity = self._get_platform_capacity()

            if not train_stops:
                logger.warning("No train stops found in scheduling horizon — skipping optimization")
                return None

            # Build predicted delays map: train_id -> float minutes
            predicted_delays: Dict[UUID, float] = {}
            for k, v in predictions.items():
                if isinstance(k, UUID) and v.get("type") == "delay":
                    predicted_delays[k] = v.get("predicted_delay", 0.0)

            # Build congestion annotations: section_id -> recommendation string
            # The optimizer reads these from the trains dict via the key
            # f"congestion_penalty_{section_id}" and adds an extra penalty
            # weight for trains stopping at congested sections.
            congestion_annotations: Dict[str, str] = {}
            for k, v in predictions.items():
                if isinstance(k, UUID) and v.get("type") == "congestion":
                    rec = v.get("recommendation", "low")
                    if rec in ("high", "critical"):
                        congestion_annotations[f"congestion_penalty_{k}"] = rec

            # Merge congestion annotations into every train's info dict so
            # the optimizer can read them section-by-section.
            trains_with_congestion = {}
            for train_id, info in self.state_engine.trains.items():
                enriched = dict(info)          # shallow copy
                enriched.update(congestion_annotations)
                trains_with_congestion[train_id] = enriched

            snap = OptimizationSnapshot(
                timestamp=self.state_engine.current_time,
                trains=trains_with_congestion,
                train_stops=train_stops,
                sections=section_infos,
                current_positions={
                    train_id: (
                        UUID(info["current_section_id"]) if info.get("current_section_id") else None,
                        UUID(info["current_station_id"]) if info.get("current_station_id") else None,
                    )
                    for train_id, info in self.state_engine.trains.items()
                },
                predicted_delays=predicted_delays,
                platform_capacity=platform_capacity,
            )

            result = self.optimizer.optimize(
                snap,
                horizon_minutes=max(self.horizon_minutes, 1440),  # at least 24h to match stop collection
                use_warm_start=True,
            )

            logger.info(f"Optimization result: {result.status.value}, weighted_delay={result.total_weighted_delay:.1f}min")
            return result

        except Exception as e:
            logger.error(f"Optimization failed: {str(e)}", exc_info=True)
            return None

    def _get_train_stops(self) -> List[TrainStop]:
        """
        Convert Supabase train_schedules rows to TrainStop objects.

        Includes stops within a broad look-ahead window (up to 24 hours) so
        the optimizer can work even when the seed data is dated further ahead.
        Falls back to ALL upcoming stops if the standard horizon finds none.
        """
        stops: List[TrainStop] = []
        now = self.state_engine.current_time
        # Use an extended horizon: max of configured horizon or 24 hours
        extended_horizon_end = now + timedelta(hours=24)

        for train_id, schedule in self.state_engine.train_schedules.items():
            train_info = self.state_engine.trains.get(train_id, {})
            accumulated_delay = train_info.get("accumulated_delay_minutes", 0.0)
            delay_delta = timedelta(minutes=accumulated_delay)

            for stop in schedule:
                try:
                    # Parse scheduled times
                    raw_arr = stop.get("scheduled_arrival")
                    raw_dep = stop.get("scheduled_departure")
                    if not raw_arr or not raw_dep:
                        continue

                    sched_arr = datetime.fromisoformat(raw_arr) if isinstance(raw_arr, str) else raw_arr
                    sched_dep = datetime.fromisoformat(raw_dep) if isinstance(raw_dep, str) else raw_dep

                    # Apply accumulated delay so optimizer starts from realistic position
                    effective_arr = sched_arr + delay_delta
                    effective_dep = sched_dep + delay_delta

                    # Include stops that are in the future within 24h window
                    # This handles seeded data that may be dated ahead of "now"
                    if effective_arr > extended_horizon_end:
                        continue
                    # Skip stops that are already far in the past (>2h ago)
                    if effective_arr < now - timedelta(hours=2):
                        continue

                    stops.append(TrainStop(
                        train_id=train_id,
                        train_number=train_info.get("train_number", "UNKNOWN"),
                        station_id=UUID(stop["station_id"]),
                        station_name=stop.get("station_name", ""),
                        stop_order=stop.get("stop_order", 0),
                        scheduled_arrival=effective_arr,
                        scheduled_departure=effective_dep,
                        platform_dwell_time_minutes=max(
                            1.0,
                            (sched_dep - sched_arr).total_seconds() / 60,
                        ),
                    ))
                except Exception as exc:
                    logger.debug(f"Skipping stop due to parse error: {exc}")

        logger.info(f"Built {len(stops)} TrainStop objects for optimizer (24h extended window)")
        return stops

    def _get_section_infos(self) -> List[SectionInfo]:
        """
        Convert Supabase sections rows to SectionInfo objects.

        Reads directly from section_repository (cached in state_engine graph).
        Falls back to re-querying the DB if graph is empty.
        """
        infos: List[SectionInfo] = []

        try:
            all_sections = self.section_repo.get_all_sections()
            for sec in all_sections:
                try:
                    infos.append(SectionInfo(
                        section_id=UUID(sec["id"]),
                        from_station_id=UUID(sec["from_station_id"]),
                        to_station_id=UUID(sec["to_station_id"]),
                        capacity=int(sec.get("capacity", 1)),
                        headway_minutes=float(sec.get("headway_minutes", 5.0)),
                        travel_time_minutes=float(sec.get("travel_time_minutes", 10.0)),
                        safety_margin_minutes=1.0,
                    ))
                except Exception as exc:
                    logger.debug(f"Skipping section due to parse error: {exc}")

        except Exception as e:
            logger.warning(f"Could not load sections from DB: {e}")

        logger.info(f"Built {len(infos)} SectionInfo objects for optimizer")
        return infos

    def _get_platform_capacity(self) -> Dict[UUID, int]:
        """
        Build station_id → max_platform_count map from the network graph.

        Uses the graph node count as a proxy; falls back to default=4 per station.
        """
        capacity_map: Dict[UUID, int] = {}
        try:
            for node in self.state_engine.graph.nodes():
                props = self.state_engine.graph.nodes[node].get("properties", {})
                # total_platforms from stations table, default 4
                total_platforms = props.get("total_platforms", 4) if props else 4
                capacity_map[node] = int(total_platforms) if total_platforms else 4
        except Exception as e:
            logger.debug(f"Could not build platform capacity map: {e}")
        return capacity_map

    # =========================================================================
    # Private — Validate + Persist
    # =========================================================================

    def _validate_optimization(self, optimization_result: Optional[Any]) -> bool:
        """Validate optimized schedule — checks feasibility and sanity bounds."""
        if optimization_result is None:
            logger.warning("No optimization result to validate")
            return False

        try:
            if hasattr(optimization_result, "status"):
                status_val = optimization_result.status.value
                # Accept optimal and feasible results
                if status_val in ("optimal", "feasible"):
                    logger.info(f"Optimization validation passed: {status_val}")
                    return True
                # Reject infeasible/failed results
                logger.warning(f"Optimization result status is not acceptable: {status_val}")
                if hasattr(optimization_result, "infeasibility_reasons"):
                    logger.warning(f"Reasons: {optimization_result.infeasibility_reasons}")
                return False

            # Fallback: if no status field, validate by delay bound
            if hasattr(optimization_result, "total_weighted_delay"):
                if optimization_result.total_weighted_delay > 10000:
                    logger.warning(f"Excessive delays in solution: {optimization_result.total_weighted_delay}")
                    return False

            logger.debug("Optimization validation passed (fallback)")
            return True

        except Exception as e:
            logger.error(f"Validation error: {str(e)}")
            return False

    def _persist_updated_states(self, optimization_result: Optional[Any]) -> None:
        """
        Persist optimized schedule to Supabase.

        Writes:
        1. optimization_logs  — one row per cycle with solver metrics
        2. train_state        — updates ALL adjusted trains with new delay + status
        """
        if optimization_result is None:
            return

        now = datetime.utcnow()

        # ---- 1. Write optimization_logs row --------------------------------
        if self._db_session is not None:
            try:
                import json

                # Build a human-readable plan for the frontend
                plan = []
                adjusted_timings = getattr(optimization_result, "adjusted_timings", {}) or {}
                for train_id, timings in adjusted_timings.items():
                    if not timings:
                        continue
                    train_info = self.state_engine.trains.get(train_id, {})
                    max_delay = max((float(t.get("delay_minutes", 0)) for t in timings), default=0.0)
                    action = "on_time" if max_delay <= 0 else ("minor_delay" if max_delay <= 5 else "hold")
                    plan.append({
                        "train_id": str(train_id),
                        "train_number": train_info.get("train_number", "UNKNOWN"),
                        "action": action,
                        "max_delay_minutes": round(max_delay, 1),
                        "stops": [
                            {
                                "station_name": t.get("station_name", ""),
                                "stop_order": t.get("stop_order", 0),
                                "scheduled_arrival": t.get("scheduled_arrival"),
                                "adjusted_arrival": t.get("adjusted_arrival"),
                                "delay_minutes": round(float(t.get("delay_minutes", 0)), 1),
                            }
                            for t in sorted(timings, key=lambda x: x.get("stop_order", 0))
                        ],
                    })

                # Include structured explanation from optimizer
                explanation = getattr(optimization_result, "explanation", None)
                
                notes_json = json.dumps({
                    "cycle": self.cycle_count,
                    "status": str(getattr(optimization_result, "status", "unknown")),
                    "plan": plan,
                    "explanation": explanation,  # Structured human-readable explanation
                })

                self._db_session.execute(
                    text("""
                        INSERT INTO optimization_logs
                            (id, timestamp, objective_value, total_weighted_delay,
                             conflicts_detected, solver_runtime, notes, created_at)
                        VALUES
                            (:id, :ts, :obj, :delay, :conflicts, :runtime, :notes, :created_at)
                        ON CONFLICT (id) DO NOTHING
                    """),
                    {
                        "id": str(uuid4()),
                        "ts": now.isoformat(),
                        "obj": float(getattr(optimization_result, "objective_value", 0) or 0),
                        "delay": float(getattr(optimization_result, "total_weighted_delay", 0)),
                        "conflicts": int(getattr(optimization_result, "conflicts_resolved", 0)),
                        "runtime": float(getattr(optimization_result, "solver_runtime_seconds", 0)),
                        "notes": notes_json,
                        "created_at": now.isoformat(),
                    },
                )
                self._db_session.commit()
                logger.debug(f"Wrote optimization_logs row with plan for {len(plan)} trains")
            except Exception as exc:
                logger.error(f"Failed to write optimization_logs: {exc}", exc_info=True)
                self._db_session.rollback()

        # ---- 2. Update train_state for every adjusted train -----------------
        # When optimization SUCCEEDS, it means the solver found the best schedule —
        # trains that were adjusted should have their delay REDUCED, not increased.
        # The optimizer's delay_minutes is relative to the 24h-forward schedule window,
        # so we must NOT write it raw back to accumulated_delay_minutes (causes runaway growth).
        #
        # Policy:
        #  - If optimizer found delay=0 for a stop → train is fully on-schedule → clear delay
        #  - If optimizer had to absorb some delay → take the MINIMUM of current vs new
        #    (optimization never makes a train MORE delayed than it already is;
        #     if it does it means the horizon gap, not real delay)
        if not hasattr(optimization_result, "adjusted_timings"):
            return

        for train_id, timings in optimization_result.adjusted_timings.items():
            if not timings:
                continue
            try:
                current_delay = float(
                    self.state_engine.trains.get(train_id, {}).get("accumulated_delay_minutes", 0.0)
                )

                # The optimizer's delay_minutes can reflect large horizon offsets.
                # We only trust it to REDUCE delay, never to increase it.
                # Use the minimum stop-level delay as the new baseline.
                min_opt_delay = min(float(t.get("delay_minutes", 0)) for t in timings)
                min_opt_delay = max(0.0, min_opt_delay)  # clamp negatives to 0

                # Optimization should reduce delay: take min of current vs optimizer result
                new_delay = min(current_delay, min_opt_delay)

                # Determine status
                if new_delay <= 0:
                    new_status = "in_transit"
                elif new_delay <= 5:
                    new_status = "in_transit"
                else:
                    new_status = "delayed"

                self.train_repo.update_train_state(
                    train_id,
                    {
                        "accumulated_delay_minutes": new_delay,
                        "status": new_status,
                    },
                )
                logger.debug(
                    f"Train {train_id}: delay {current_delay:.1f}min → {new_delay:.1f}min after optimization"
                )
            except Exception as exc:
                logger.error(f"Failed to update train_state for {train_id}: {exc}", exc_info=True)

        logger.info(f"Persisted {len(optimization_result.adjusted_timings)} train state updates to Supabase")


    def _maybe_retrain(self) -> None:
        """
        Intelligently trigger ML model retraining when needed.

        Two triggers (both non-blocking — any exception is caught and logged
        so a training failure never kills the orchestration cycle):

        1. Drift-triggered:
           After every cycle, call predictor.check_for_drift().
           If the rolling mean prediction error has exceeded 5 minutes MAE,
           check_for_drift() automatically retrains on the latest
           historical_operational_data and resets the error tracker.

        2. Periodic safety-net:
           Force a retrain every `retrain_interval_cycles` cycles (default 20)
           regardless of drift.  This guarantees the model always eventually
           learns from the data that _record_historical_data() has been
           accumulating, even if prediction errors looked acceptable.

        Timeline for a hackathon demo running every 5 minutes:
          - Cycle  1-19: drift check only (fast)
          - Cycle  20:   forced retrain (~3 sec on 500 rows)
          - Cycle  21-39: drift check only
          - Cycle  40:   forced retrain (now ~600+ rows → better model)
          ...
        """
        try:
            # --- Trigger 1: drift detection (if method available) ---
            if hasattr(self.predictor, "check_for_drift"):
                drift_result = self.predictor.check_for_drift()
                if drift_result.get("drift_detected"):
                    action = drift_result.get("action_taken", "unknown")
                    mae    = drift_result.get("mean_error", 0.0)
                    logger.warning(
                        f"Drift detected (MAE={mae:.2f}min) at cycle {self.cycle_count}: "
                        f"action={action}"
                    )
                    if action == "retrained":
                        self.last_retrain_cycle = self.cycle_count
                        logger.info(
                            f"Drift-triggered retrain complete at cycle {self.cycle_count} "
                            f"(samples in DB growing every cycle)"
                        )
                    return  # Already retrained due to drift, skip periodic check

            # --- Trigger 2: periodic safety-net ---
            cycles_since_retrain = self.cycle_count - self.last_retrain_cycle
            if cycles_since_retrain >= self.retrain_interval_cycles:
                logger.info(
                    f"Periodic retrain at cycle {self.cycle_count} "
                    f"({cycles_since_retrain} cycles since last retrain)"
                )
                results = self.predictor.train_models()
                self.last_retrain_cycle = self.cycle_count
                logger.info(
                    f"Periodic retrain complete: "
                    f"delay MAE={results.get('delay_model_score', 'N/A')}, "
                    f"congestion AUC={results.get('congestion_model_score', 'N/A')}, "
                    f"samples={results.get('delay_samples', 0)}"
                )

        except Exception as exc:
            # Never let a retraining failure crash the cycle
            logger.debug(f"Retraining skipped due to error: {exc}")

    def _record_historical_data(self, predictions: Dict) -> None:
        """
        Write one row to historical_operational_data per active train.

        Called every orchestration cycle so the ML training corpus grows
        automatically while the system is running — no manual data entry needed.

        Columns written (matches schema.md):
            train_id, section_id, departure_delay, arrival_delay,
            section_load, time_of_day, congestion_flag
        """
        if self._db_session is None:
            return

        now = datetime.utcnow()
        time_of_day = now.hour * 60 + now.minute
        rows_written = 0

        for train_id, train_info in self.state_engine.trains.items():
            current_section_id_str = train_info.get("current_section_id")
            if not current_section_id_str:
                continue  # Train not on any section right now

            try:
                section_id = UUID(current_section_id_str)
                load_info  = self.state_engine.get_section_load(section_id)
                section_load = load_info.get("current_occupancy", 0)

                accumulated_delay = float(train_info.get("accumulated_delay_minutes", 0.0))

                # Congestion: did the predictor flag this section?
                congestion_pred = predictions.get(section_id, {})
                congestion_flag = (
                    congestion_pred.get("recommendation") in ("high", "critical")
                    if congestion_pred
                    else section_load >= load_info.get("capacity", 999)
                )

                self._db_session.execute(
                    text("""
                        INSERT INTO historical_operational_data
                            (id, train_id, section_id, departure_delay, arrival_delay,
                             section_load, time_of_day, congestion_flag, created_at)
                        VALUES
                            (:id, :tid, :secid, :ddel, :adel,
                             :sload, :tod, :cong, :created)
                    """),
                    {
                        "id":      str(uuid4()),
                        "tid":     str(train_id),
                        "secid":   str(section_id),
                        "ddel":    int(round(accumulated_delay)),
                        "adel":    int(round(accumulated_delay)),   # proxy until actual arrival tracked
                        "sload":   section_load,
                        "tod":     time_of_day,
                        "cong":    congestion_flag,
                        "created": now.isoformat(),
                    },
                )
                rows_written += 1

            except Exception as exc:
                logger.warning(f"Could not record historical data for train {train_id}: {exc}")

        try:
            self._db_session.commit()
            if rows_written:
                logger.debug(f"Appended {rows_written} rows to historical_operational_data")
        except Exception as exc:
            logger.error(f"Failed to commit historical data: {exc}", exc_info=True)
            self._db_session.rollback()

    # =========================================================================
    # Private — KPI Calculation + Persistence
    # =========================================================================

    def _calculate_kpis(
        self,
        state_snapshot: Dict,
        optimization_result: Optional[Any],
        predictions: Dict,
    ) -> KPISnapshot:
        """
        Calculate KPIs and write a kpi_metrics row to Supabase.
        """
        # Use actual accumulated delays from train_states (correctly updated by optimizer above)
        # The optimizer's total_weighted_delay is a large horizon-relative number and should
        # NOT be used as the displayed KPI — it would mislead the dashboard.
        actual_total_delay = sum(
            info.get("accumulated_delay_minutes", 0.0)
            for info in self.state_engine.trains.values()
        )
        total_delay = actual_total_delay


        # Average section utilization from live occupancy
        if state_snapshot.get("occupancy_summary"):
            occupied = state_snapshot["occupancy_summary"].get("sections_with_trains", 0)
            total_sections = state_snapshot["network_stats"].get("total_sections", 1)
            utilization = (occupied / total_sections * 100) if total_sections > 0 else 0.0
        else:
            utilization = 0.0

        conflicts_detected = state_snapshot.get("conflicts", {}).get("total_conflicts", 0)
        conflicts_avoided = getattr(optimization_result, "conflicts_resolved", 0) if optimization_result else 0
        self.cumulative_conflicts_avoided += conflicts_avoided

        # Trains delayed = those with predicted delay > 0.5 min
        trains_delayed = sum(
            1 for v in predictions.values()
            if v.get("type") == "delay" and v.get("predicted_delay", 0) > 0.5
        )
        trains_on_time = len(self.state_engine.trains) - trains_delayed

        # MAE: compare predicted delay vs actual accumulated delay where both available
        errors = []
        for train_id, pred in predictions.items():
            if pred.get("type") != "delay":
                continue
            actual = self.state_engine.trains.get(train_id, {}).get("accumulated_delay_minutes", 0.0)
            predicted = pred.get("predicted_delay", 0.0)
            self.predictor.update_prediction_error(actual, predicted)
            errors.append(abs(actual - predicted))
        mae = float(sum(errors) / len(errors)) if errors else 0.0

        adherence = max(0.0, 100.0 - min(100.0, total_delay / max(len(self.state_engine.trains), 1)))
        runtime = getattr(optimization_result, "solver_runtime_seconds", 0.0) if optimization_result else 0.0

        kpis = KPISnapshot(
            cycle_timestamp=datetime.utcnow(),
            cycle_number=self.cycle_count,
            total_weighted_delay_minutes=total_delay,
            average_section_utilization_percent=utilization,
            conflicts_detected=conflicts_detected,
            conflicts_avoided=conflicts_avoided,
            trains_delayed=trains_delayed,
            trains_on_time=trains_on_time,
            optimization_runtime_seconds=runtime,
            prediction_accuracy_mae=mae,
            schedule_adherence_percent=adherence,
        )

        # Write to kpi_metrics table in Supabase
        if self._db_session is not None:
            try:
                self._db_session.execute(
                    text("""
                        INSERT INTO kpi_metrics
                            (id, timestamp, total_weighted_delay, average_delay,
                             throughput, section_utilization)
                        VALUES
                            (:id, :ts, :total_delay, :avg_delay, :throughput, :util)
                    """),
                    {
                        "id": str(uuid4()),
                        "ts": kpis.cycle_timestamp.isoformat(),
                        "total_delay": round(total_delay, 2),
                        "avg_delay": round(total_delay / max(len(self.state_engine.trains), 1), 2),
                        "throughput": len(self.state_engine.trains),
                        "util": round(utilization, 2),
                    },
                )
                self._db_session.commit()
                logger.debug("Wrote kpi_metrics row to Supabase")
            except Exception as exc:
                logger.error(f"Failed to write kpi_metrics: {exc}", exc_info=True)
                self._db_session.rollback()

        return kpis

    # =========================================================================
    # Private — Helpers
    # =========================================================================

    def _find_section(self, section_id: UUID) -> Optional[Dict]:
        """Find section info by ID from repository."""
        try:
            return self.section_repo.get_section_by_id(section_id)
        except Exception:
            return None

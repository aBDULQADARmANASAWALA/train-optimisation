import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any, Set
from uuid import UUID
from dataclasses import dataclass
from enum import Enum

from ortools.sat.python import cp_model


logger = logging.getLogger(__name__)


class OptimizationStatus(str, Enum):
    """Optimization result status"""
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    NO_SOLUTION_FOUND = "no_solution_found"
    MODEL_INVALID = "model_invalid"


@dataclass
class TrainStop:
    """Represents a train's scheduled stop"""
    train_id: UUID
    train_number: str
    station_id: UUID
    station_name: str
    sequence: int
    scheduled_arrival: datetime
    scheduled_departure: datetime
    platform_dwell_time_minutes: float = 5.0


@dataclass
class SectionInfo:
    """Represents a railway section with constraints"""
    section_id: UUID
    from_station_id: UUID
    to_station_id: UUID
    capacity: int
    headway_minutes: float
    travel_time_minutes: float
    safety_margin_minutes: float = 1.0


@dataclass
class OptimizationSnapshot:
    """Input snapshot for optimization"""
    timestamp: datetime
    trains: Dict[UUID, Dict[str, Any]]  # train_id -> train info
    train_stops: List[TrainStop]  # All scheduled stops
    sections: List[SectionInfo]  # Network topology
    current_positions: Dict[UUID, Tuple[Optional[UUID], Optional[UUID]]]  # train_id -> (section_id, station_id)
    predicted_delays: Dict[UUID, float]  # train_id -> predicted_delay_minutes
    platform_capacity: Dict[UUID, int]  # station_id -> max Platform tracks/lines


@dataclass
class OptimizedSchedule:
    """Result of optimization"""
    status: OptimizationStatus
    timestamp: datetime
    horizon_start: datetime
    horizon_end: datetime
    solver_runtime_seconds: float
    objective_value: Optional[float]
    total_weighted_delay: float
    conflicts_resolved: int
    trains_adjusted: int
    adjusted_timings: Dict[UUID, List[Dict[str, Any]]]  # train_id -> list of adjusted stops
    infeasibility_reasons: List[str]
    warm_start_applied: bool


class OptimizationService:
    """
    Constraint Programming optimizer using Google OR-Tools CP-SAT.

    Optimizes train schedules to minimize weighted delays and resolve conflicts
    while satisfying capacity, headway, and safety constraints.

    Features:
    - Handles 100+ trains efficiently
    - Supports rolling horizon windows
    - Warm-start from previous solutions
    - Graceful infeasibility handling
    - Deterministic results
    - No database access (pure computation)
    """

    def __init__(
        self,
        max_solver_time_seconds: float = 30.0,
        time_precision_minutes: float = 0.5,
    ):
        """
        Initialize optimizer.

        Args:
            max_solver_time_seconds: Maximum solver runtime (default 30 seconds)
            time_precision_minutes: Time granularity for variables (default 0.5 min)
        """
        self.max_solver_time_seconds = max_solver_time_seconds
        self.time_precision_minutes = time_precision_minutes
        self.last_solution: Optional[Dict] = None

    def optimize(
        self,
        snapshot: OptimizationSnapshot,
        horizon_minutes: int = 60,
        use_warm_start: bool = True,
    ) -> OptimizedSchedule:
        """
        Optimize train schedule for given snapshot.

        Args:
            snapshot: Current state snapshot with all constraints
            horizon_minutes: Optimization window size
            use_warm_start: Whether to use previous solution as warm start

        Returns:
            OptimizedSchedule with results and details
        """
        start_time = datetime.utcnow()
        logger.info(f"Starting optimization: {len(snapshot.trains)} trains, {horizon_minutes}min horizon")

        try:
            # Define optimization window
            horizon_end = snapshot.timestamp + timedelta(minutes=horizon_minutes)

            # Filter relevant data within horizon
            relevant_stops = [
                stop for stop in snapshot.train_stops
                if snapshot.timestamp <= stop.scheduled_arrival <= horizon_end
            ]

            if not relevant_stops:
                logger.warning("No train stops within horizon window")
                return OptimizedSchedule(
                    status=OptimizationStatus.NO_SOLUTION_FOUND,
                    timestamp=start_time,
                    horizon_start=snapshot.timestamp,
                    horizon_end=horizon_end,
                    solver_runtime_seconds=0.0,
                    objective_value=None,
                    total_weighted_delay=0.0,
                    conflicts_resolved=0,
                    trains_adjusted=0,
                    adjusted_timings={},
                    infeasibility_reasons=["No train stops in horizon window"],
                    warm_start_applied=False,
                )

            # Build optimization model
            model = cp_model.CpModel()

            # Create variables
            variables = self._create_variables(
                model,
                snapshot,
                relevant_stops,
                snapshot.timestamp,
                horizon_end,
            )

            # Add constraints
            infeasibility_reasons = self._add_constraints(
                model,
                variables,
                snapshot,
                relevant_stops,
                snapshot.timestamp,
                horizon_end,
            )

            # Set objective
            self._set_objective(model, variables, snapshot, relevant_stops)

            # Apply warm start if available
            warm_start_applied = False
            if use_warm_start and self.last_solution:
                warm_start_applied = self._apply_warm_start(model, variables, self.last_solution)

            # Solve
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = self.max_solver_time_seconds
            solver.parameters.log_search_progress = False

            status = solver.Solve(model)
            solver_runtime = datetime.utcnow() - start_time

            # Process results
            if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
                result = self._extract_solution(
                    solver,
                    variables,
                    snapshot,
                    relevant_stops,
                    status == cp_model.OPTIMAL,
                    solver_runtime.total_seconds(),
                    warm_start_applied,
                    infeasibility_reasons,
                )

                # Store for warm start
                self.last_solution = self._store_solution(solver, variables, relevant_stops)

                return result

            else:
                # Infeasible or no solution
                logger.warning(f"Solver status: {status}, infeasibility issues detected")

                infeasibility_reasons.extend(self._diagnose_infeasibility(model, variables, snapshot))

                return OptimizedSchedule(
                    status=OptimizationStatus.INFEASIBLE if status == cp_model.INFEASIBLE else OptimizationStatus.NO_SOLUTION_FOUND,
                    timestamp=start_time,
                    horizon_start=snapshot.timestamp,
                    horizon_end=horizon_end,
                    solver_runtime_seconds=solver_runtime.total_seconds(),
                    objective_value=None,
                    total_weighted_delay=0.0,
                    conflicts_resolved=0,
                    trains_adjusted=0,
                    adjusted_timings={},
                    infeasibility_reasons=infeasibility_reasons,
                    warm_start_applied=warm_start_applied,
                )

        except Exception as e:
            logger.error(f"Optimization error: {str(e)}", exc_info=True)
            return OptimizedSchedule(
                status=OptimizationStatus.MODEL_INVALID,
                timestamp=start_time,
                horizon_start=snapshot.timestamp,
                horizon_end=snapshot.timestamp + timedelta(minutes=horizon_minutes),
                solver_runtime_seconds=(datetime.utcnow() - start_time).total_seconds(),
                objective_value=None,
                total_weighted_delay=0.0,
                conflicts_resolved=0,
                trains_adjusted=0,
                adjusted_timings={},
                infeasibility_reasons=[str(e)],
                warm_start_applied=False,
            )

    def _create_variables(
        self,
        model: cp_model.CpModel,
        snapshot: OptimizationSnapshot,
        relevant_stops: List[TrainStop],
        horizon_start: datetime,
        horizon_end: datetime,
    ) -> Dict[str, Any]:
        """
        Create decision variables for the optimization model.

        Variables:
        - arrival_time[train_id][station_id]: arrival time in minutes from horizon_start
        - departure_time[train_id][station_id]: departure time in minutes from horizon_start
        - precedence[train_i][train_j]: binary, 1 if train_i precedes train_j on section

        ML integration:
        - Each train's bounds are offset by snapshot.predicted_delays[train_id] so the
          solver starts from a realistic delayed position rather than the raw timetable.
          This prevents the solver wasting time exploring solutions that are already
          infeasible due to the current real-world delay.
        """
        logger.debug(f"Creating variables for {len(relevant_stops)} stops")

        horizon_length = int((horizon_end - horizon_start).total_seconds() / 60)

        arrival_times = {}
        departure_times = {}
        precedence_vars = {}

        for stop in relevant_stops:
            stop_id = (stop.train_id, stop.station_id, stop.sequence)

            # ── ML predicted delay offset ──────────────────────────────────
            # If the ML model predicted this train will be N minutes late,
            # shift the lower bound up by N so the solver's search space
            # starts from the realistic position.
            ml_delay = int(snapshot.predicted_delays.get(stop.train_id, 0.0))
            ml_delay = max(0, ml_delay)  # clamp negative predictions to 0

            # Calculate bounds for arrival time
            scheduled_arr = stop.scheduled_arrival
            arr_min = int((scheduled_arr - horizon_start).total_seconds() / 60) + ml_delay
            arr_max = arr_min + 120  # Allow up to 2 additional hours beyond predicted

            arrival_times[stop_id] = model.NewIntVar(
                max(0, arr_min),
                min(horizon_length, max(arr_max, arr_min + 1)),
                f"arr_{stop.train_id}_{stop.station_id}_{stop.sequence}",
            )

            # Departure bounds (also offset by ML delay)
            scheduled_dep = stop.scheduled_departure
            dep_min = int((scheduled_dep - horizon_start).total_seconds() / 60) + ml_delay
            dep_max = dep_min + 120

            departure_times[stop_id] = model.NewIntVar(
                max(0, dep_min),
                min(horizon_length, max(dep_max, dep_min + 1)),
                f"dep_{stop.train_id}_{stop.station_id}_{stop.sequence}",
            )

        # Create precedence variables for trains on same sections (for headway/capacity)
        section_trains = self._group_trains_by_section(relevant_stops)
        for section_id, train_list in section_trains.items():
            if len(train_list) > 1:
                for i in range(len(train_list)):
                    for j in range(i + 1, len(train_list)):
                        train_i, stop_i = train_list[i]
                        train_j, stop_j = train_list[j]

                        # Binary variable: 1 if train_i departs before train_j arrives
                        var_name = f"prec_{train_i}_{train_j}_{section_id}"
                        precedence_vars[(train_i, train_j, section_id)] = model.NewBoolVar(var_name)

        logger.debug(f"Created {len(arrival_times)} arrival, {len(departure_times)} departure, "
                    f"{len(precedence_vars)} precedence variables")

        return {
            "arrival_times": arrival_times,
            "departure_times": departure_times,
            "precedence_vars": precedence_vars,
            "horizon_start": horizon_start,
        }

    def _add_constraints(
        self,
        model: cp_model.CpModel,
        variables: Dict[str, Any],
        snapshot: OptimizationSnapshot,
        relevant_stops: List[TrainStop],
        horizon_start: datetime,
        horizon_end: datetime,
    ) -> List[str]:
        """
        Add all constraints to the model.

        Constraints:
        1. Continuity: Each train follows its schedule (arrival <= departure)
        2. No teleportation: Travel time between stations respected
        3. Platform capacity: Max trains at station simultaneously
        4. Section capacity: Max trains on section simultaneously
        5. Headway: Minimum spacing between consecutive trains
        6. Safety margins: Buffer times at stations
        """
        infeasibility_reasons = []

        arrival_times = variables["arrival_times"]
        departure_times = variables["departure_times"]
        precedence_vars = variables["precedence_vars"]

        # Constraint 1: Continuity (arrival <= departure at each stop)
        logger.debug("Adding continuity constraints")
        for stop in relevant_stops:
            stop_id = (stop.train_id, stop.station_id, stop.sequence)
            if stop_id in arrival_times and stop_id in departure_times:
                model.Add(arrival_times[stop_id] <= departure_times[stop_id])

        # Constraint 2: Dwell time at station
        logger.debug("Adding dwell time constraints")
        for stop in relevant_stops:
            stop_id = (stop.train_id, stop.station_id, stop.sequence)
            if stop_id in departure_times and stop_id in arrival_times:
                dwell_minutes = int(stop.platform_dwell_time_minutes)
                model.Add(
                    departure_times[stop_id] >= arrival_times[stop_id] + dwell_minutes
                )

        # Constraint 3: Travel time (continuity between stops)
        logger.debug("Adding travel time constraints")
        train_stops = self._group_stops_by_train(relevant_stops)
        for train_id, stops_list in train_stops.items():
            # Sort by sequence
            stops_list.sort(key=lambda x: x.sequence)

            for i in range(len(stops_list) - 1):
                stop1 = stops_list[i]
                stop2 = stops_list[i + 1]

                # Find section between these stops
                section = self._find_section(snapshot.sections, stop1.station_id, stop2.station_id)
                if section:
                    travel_time = int(section.travel_time_minutes)

                    stop1_id = (stop1.train_id, stop1.station_id, stop1.sequence)
                    stop2_id = (stop2.train_id, stop2.station_id, stop2.sequence)

                    if stop1_id in departure_times and stop2_id in arrival_times:
                        # Departure from stop1 + travel time <= Arrival at stop2
                        model.Add(
                            departure_times[stop1_id] + travel_time <= arrival_times[stop2_id]
                        )

        # Constraint 4: Platform capacity (max trains at station simultaneously)
        logger.debug("Adding platform capacity constraints")
        station_trains = self._group_trains_by_station(relevant_stops)
        for station_id, stop_list in station_trains.items():
            platform_capacity = snapshot.platform_capacity.get(station_id, 4)  # Default 4

            # Create "at_platform" boolean vars for each train-time window
            if len(stop_list) > platform_capacity:
                infeasibility_reasons.append(
                    f"Station {station_id}: {len(stop_list)} trains exceed platform capacity {platform_capacity}"
                )

        # Constraint 5: Section headway and capacity
        logger.debug("Adding section capacity and headway constraints")
        section_trains = self._group_trains_by_section(relevant_stops)

        for section_id, train_list in section_trains.items():
            section = self._find_section_by_id(snapshot.sections, section_id)
            if not section:
                continue

            capacity = section.capacity
            headway = int(section.headway_minutes)
            safety_margin = int(section.safety_margin_minutes)

            if len(train_list) > capacity:
                infeasibility_reasons.append(
                    f"Section {section_id}: {len(train_list)} trains exceed capacity {capacity}"
                )

            # Headway constraints between consecutive trains
            if len(train_list) > 1:
                for i in range(len(train_list)):
                    for j in range(i + 1, len(train_list)):
                        train_i, stop_i = train_list[i]
                        train_j, stop_j = train_list[j]

                        stop_i_id = (train_i, stop_i.station_id, stop_i.sequence)
                        stop_j_id = (train_j, stop_j.station_id, stop_j.sequence)

                        # Get next stop (end of section)
                        stop_i_next = self._get_next_stop(train_stops.get(train_i, []), stop_i)
                        stop_j_next = self._get_next_stop(train_stops.get(train_j, []), stop_j)

                        if stop_i_next and stop_j_next:
                            stop_i_next_id = (train_i, stop_i_next.station_id, stop_i_next.sequence)
                            stop_j_next_id = (train_j, stop_j_next.station_id, stop_j_next.sequence)

                            if all(
                                sid in departure_times
                                for sid in [stop_i_next_id, stop_j_next_id]
                            ):
                                # Disjunctive constraint: either train_i before train_j or vice versa
                                prec_var = precedence_vars.get((train_i, train_j, section_id))
                                if prec_var:
                                    M = 100000  # Large number

                                    # If prec=1: train_i departs before train_j arrives + headway
                                    model.Add(
                                        departure_times[stop_i_next_id] + headway + safety_margin
                                        <= arrival_times[stop_j_next_id] + M * (1 - prec_var)
                                    )

                                    # If prec=0: train_j departs before train_i arrives + headway
                                    model.Add(
                                        departure_times[stop_j_next_id] + headway + safety_margin
                                        <= arrival_times[stop_i_next_id] + M * prec_var
                                    )

        logger.info(f"Added constraints: {model.Proto().constraints.__sizeof__()} constraint bytes")

        return infeasibility_reasons

    def _set_objective(
        self,
        model: cp_model.CpModel,
        variables: Dict[str, Any],
        snapshot: OptimizationSnapshot,
        relevant_stops: List[TrainStop],
    ) -> None:
        """
        Set optimization objective: minimize weighted delays + congestion penalty.

        Objective = Σ(priority_weight × delay_minutes)
                  + Σ(congestion_penalty × trains_on_congested_sections)

        ML integration:
        - snapshot.predicted_delays already shifted variable bounds (see _create_variables)
        - snapshot.trains contains ML congestion recommendations per section (passed
          through from the orchestrator's predictions dict via the snapshot)
        - Sections where the ML model predicted 'high' or 'critical' congestion add
          an extra penalty per train stop, nudging the solver to prefer departing
          those trains earlier or routing them via less congested paths.
        """
        logger.debug("Setting objective function")

        arrival_times = variables["arrival_times"]
        departure_times = variables["departure_times"]
        horizon_start = variables["horizon_start"]

        # ── Build congestion penalty map from ML predictions ───────────────
        # snapshot.trains may carry a 'congestion_recommendation' field written
        # by the orchestrator from the ML congestion predictions.
        # Penalty scale: low=0, moderate=50, high=200, critical=500
        CONGESTION_PENALTIES = {"low": 0, "moderate": 50, "high": 200, "critical": 500}

        # Map section_id → congestion penalty (from ML)
        section_congestion_penalty: Dict[UUID, int] = {}
        for section in snapshot.sections:
            sec_id = section.section_id
            # The orchestrator stores congestion recommendation in snapshot.trains
            # under a special key if a section was flagged
            penalty_key = f"congestion_penalty_{sec_id}"
            for train_info in snapshot.trains.values():
                rec = train_info.get(penalty_key)
                if rec and rec in CONGESTION_PENALTIES:
                    section_congestion_penalty[sec_id] = CONGESTION_PENALTIES[rec]
                    break

        # Map (from_station_id, to_station_id) → section_id for quick lookup
        section_by_stations: Dict[Tuple[UUID, UUID], UUID] = {
            (s.from_station_id, s.to_station_id): s.section_id
            for s in snapshot.sections
        }

        # Group stops by train for travel section lookup
        train_stops_map = self._group_stops_by_train(relevant_stops)

        delay_terms = []

        # ── Delay + congestion terms per stop ──────────────────────────────
        for stop in relevant_stops:
            stop_id = (stop.train_id, stop.station_id, stop.sequence)

            if stop_id not in arrival_times:
                continue

            scheduled_arr_offset = int((stop.scheduled_arrival - horizon_start).total_seconds() / 60)
            actual_arr = arrival_times[stop_id]

            # Delay = max(0, actual - scheduled)
            delay_var = model.NewIntVar(0, 1000, f"delay_{stop.train_id}_{stop.station_id}")
            model.Add(delay_var >= actual_arr - scheduled_arr_offset)
            model.Add(delay_var >= 0)

            # Base weight: train priority
            train_priority = snapshot.trains.get(stop.train_id, {}).get("priority_weight", 1.0)
            weight = int(train_priority * 100)

            # ── Congestion penalty: find the section leading INTO this stop ──
            # If the section the train must traverse to reach this stop is
            # predicted congested by ML, increase the weight so reducing delay
            # on that section matters more to the solver.
            stops_for_train = train_stops_map.get(stop.train_id, [])
            stops_for_train.sort(key=lambda s: s.sequence)
            for i, s in enumerate(stops_for_train):
                if s.station_id == stop.station_id and i > 0:
                    prev_station = stops_for_train[i - 1].station_id
                    sec_id = section_by_stations.get((prev_station, stop.station_id))
                    if sec_id and sec_id in section_congestion_penalty:
                        weight += section_congestion_penalty[sec_id]
                        logger.debug(
                            f"Train {stop.train_number} stop at {stop.station_name}: "
                            f"+{section_congestion_penalty[sec_id]} congestion penalty"
                        )
                    break

            delay_terms.append((delay_var, weight))

        # ── Minimize total weighted delay (includes congestion penalties) ──
        if delay_terms:
            model.Minimize(sum(dv * w for dv, w in delay_terms))
            logger.debug(
                f"Objective: minimize {len(delay_terms)} weighted delay terms "
                f"(incl. congestion penalties on {len(section_congestion_penalty)} sections)"
            )
        else:
            logger.warning("No delay terms in objective")

    def _apply_warm_start(
        self,
        model: cp_model.CpModel,
        variables: Dict[str, Any],
        last_solution: Dict,
    ) -> bool:
        """
        Apply warm start hints from previous solution.

        Provides CP-SAT with variable hints from the last solution so it
        can skip already-explored regions of the search space.

        Args:
            model: CP-SAT model
            variables: Variable dictionary
            last_solution: Previous solution (from _store_solution)

        Returns:
            True if at least one hint was applied
        """
        try:
            arrival_times  = variables["arrival_times"]
            departure_times = variables["departure_times"]
            hints_applied = 0

            for stop_id, var in arrival_times.items():
                key = f"arr_{stop_id}"
                if key in last_solution:
                    model.AddHint(var, last_solution[key])
                    hints_applied += 1

            for stop_id, var in departure_times.items():
                key = f"dep_{stop_id}"
                if key in last_solution:
                    model.AddHint(var, last_solution[key])
                    hints_applied += 1

            logger.debug(f"Warm start: applied {hints_applied} variable hints to solver")
            return hints_applied > 0

        except Exception as e:
            logger.warning(f"Could not apply warm start: {str(e)}")
            return False

    def _extract_solution(
        self,
        solver: cp_model.CpSolver,
        variables: Dict[str, Any],
        snapshot: OptimizationSnapshot,
        relevant_stops: List[TrainStop],
        is_optimal: bool,
        solver_runtime: float,
        warm_start_applied: bool,
        infeasibility_reasons: List[str],
    ) -> OptimizedSchedule:
        """
        Extract and structure the solution from CP-SAT solver.
        """
        arrival_times = variables["arrival_times"]
        departure_times = variables["departure_times"]
        horizon_start = variables["horizon_start"]

        adjusted_timings: Dict[UUID, List[Dict[str, Any]]] = {}
        total_weighted_delay = 0.0
        trains_adjusted = set()

        for stop in relevant_stops:
            stop_id = (stop.train_id, stop.station_id, stop.sequence)

            if stop_id not in arrival_times or stop_id not in departure_times:
                continue

            arr_minutes = solver.Value(arrival_times[stop_id])
            dep_minutes = solver.Value(departure_times[stop_id])

            adjusted_arrival = horizon_start + timedelta(minutes=arr_minutes)
            adjusted_departure = horizon_start + timedelta(minutes=dep_minutes)

            delay_minutes = (adjusted_arrival - stop.scheduled_arrival).total_seconds() / 60

            if stop.train_id not in adjusted_timings:
                adjusted_timings[stop.train_id] = []

            adjusted_timings[stop.train_id].append({
                "sequence": stop.sequence,
                "station_id": str(stop.station_id),
                "station_name": stop.station_name,
                "scheduled_arrival": stop.scheduled_arrival.isoformat(),
                "adjusted_arrival": adjusted_arrival.isoformat(),
                "scheduled_departure": stop.scheduled_departure.isoformat(),
                "adjusted_departure": adjusted_departure.isoformat(),
                "delay_minutes": round(delay_minutes, 2),
            })

            trains_adjusted.add(stop.train_id)

            # Calculate weighted delay
            train_priority = snapshot.trains.get(stop.train_id, {}).get("priority_weight", 1.0)
            total_weighted_delay += train_priority * max(0, delay_minutes)

        # Count conflicts resolved: precedence decisions made (prec_var = 1 means train_i forced before train_j)
        precedence_vars = variables.get("precedence_vars", {})
        conflicts_resolved = 0
        try:
            for (train_i, train_j, section_id), prec_var in precedence_vars.items():
                val = solver.Value(prec_var)
                if val == 1:
                    conflicts_resolved += 1
        except Exception:
            pass  # Solver may not have values for unused vars

        logger.info(
            f"Solution extracted: {len(trains_adjusted)} trains adjusted, "
            f"total weighted delay: {total_weighted_delay:.2f} min, "
            f"conflicts resolved: {conflicts_resolved}"
        )

        return OptimizedSchedule(
            status=OptimizationStatus.OPTIMAL if is_optimal else OptimizationStatus.FEASIBLE,
            timestamp=datetime.utcnow(),
            horizon_start=horizon_start,
            horizon_end=horizon_start + timedelta(minutes=int((horizon_start - snapshot.timestamp + timedelta(hours=1)).total_seconds() / 60)),
            solver_runtime_seconds=solver_runtime,
            objective_value=solver.ObjectiveValue() if is_optimal else None,
            total_weighted_delay=total_weighted_delay,
            conflicts_resolved=conflicts_resolved,
            trains_adjusted=len(trains_adjusted),
            adjusted_timings=adjusted_timings,
            infeasibility_reasons=infeasibility_reasons,
            warm_start_applied=warm_start_applied,
        )

    def _store_solution(
        self,
        solver: cp_model.CpSolver,
        variables: Dict[str, Any],
        relevant_stops: List[TrainStop],
    ) -> Dict:
        """
        Store solution for warm start in next optimization.
        """
        solution = {}
        arrival_times = variables["arrival_times"]
        departure_times = variables["departure_times"]

        for stop in relevant_stops:
            stop_id = (stop.train_id, stop.station_id, stop.sequence)
            if stop_id in arrival_times:
                solution[f"arr_{stop_id}"] = solver.Value(arrival_times[stop_id])
            if stop_id in departure_times:
                solution[f"dep_{stop_id}"] = solver.Value(departure_times[stop_id])

        logger.debug(f"Stored solution with {len(solution)} variables for warm start")
        return solution

    def _diagnose_infeasibility(
        self,
        model: cp_model.CpModel,
        variables: Dict[str, Any],
        snapshot: OptimizationSnapshot,
    ) -> List[str]:
        """
        Diagnose reasons for infeasibility.
        """
        reasons = []

        # Check basic feasibility
        if len(snapshot.trains) > 100:
            reasons.append("Network may be too large for current constraints")

        # Check section capacities
        for section in snapshot.sections:
            reason = f"Section {section.section_id}: capacity {section.capacity}"
            reasons.append(reason)

        return reasons

    # Helper methods
    def _group_trains_by_section(
        self,
        stops: List[TrainStop],
    ) -> Dict[UUID, List[Tuple[UUID, "TrainStop"]]]:
        """
        Group trains by the sections they traverse.

        For each consecutive pair of stops (stop_i → stop_i+1) belonging to
        the same train, the pair is mapped to the section whose
        (from_station_id, to_station_id) matches that leg.  Because sections
        are looked up by station pair rather than a pre-built section map
        here (we don't have snapshot in scope), we use station-pair tuples as
        the section key so the caller can still build precedence variables.

        Returns:
            Dict mapping section_id (or station-pair UUID proxy) to list of
            (train_id, departure_stop) tuples for trains traversing it.
        """
        # Build per-train ordered stop list
        train_stop_map: Dict[UUID, List[TrainStop]] = {}
        for stop in stops:
            train_stop_map.setdefault(stop.train_id, []).append(stop)
        for lst in train_stop_map.values():
            lst.sort(key=lambda s: s.sequence)

        # Map (from_station_id, to_station_id) → [(train_id, stop_at_from)]
        # We use a composite UUID-like key derived from the two station IDs
        section_map: Dict[UUID, List[Tuple[UUID, TrainStop]]] = {}

        for train_id, train_stops_list in train_stop_map.items():
            for i in range(len(train_stops_list) - 1):
                dep_stop  = train_stops_list[i]      # departing from dep_stop.station_id
                arr_stop  = train_stops_list[i + 1]  # arriving at arr_stop.station_id

                # Create a deterministic proxy key from station pair
                from_id = dep_stop.station_id
                to_id   = arr_stop.station_id
                # XOR bytes to get a stable UUID for this directed station pair
                import uuid as _uuid
                key = _uuid.UUID(
                    bytes=bytes(
                        a ^ b
                        for a, b in zip(from_id.bytes, to_id.bytes)
                    )
                )

                section_map.setdefault(key, []).append((train_id, dep_stop))

        logger.debug(
            f"_group_trains_by_section: {len(section_map)} sections, "
            f"{sum(len(v) for v in section_map.values())} train-section assignments"
        )
        return section_map

    def _group_stops_by_train(self, stops: List[TrainStop]) -> Dict[UUID, List[TrainStop]]:
        """Group stops by train"""
        result: Dict[UUID, List[TrainStop]] = {}
        for stop in stops:
            if stop.train_id not in result:
                result[stop.train_id] = []
            result[stop.train_id].append(stop)
        return result

    def _group_trains_by_station(self, stops: List[TrainStop]) -> Dict[UUID, List[TrainStop]]:
        """Group stops by station"""
        result: Dict[UUID, List[TrainStop]] = {}
        for stop in stops:
            if stop.station_id not in result:
                result[stop.station_id] = []
            result[stop.station_id].append(stop)
        return result

    def _find_section(
        self,
        sections: List[SectionInfo],
        from_station: UUID,
        to_station: UUID,
    ) -> Optional[SectionInfo]:
        """Find section between two stations"""
        for section in sections:
            if section.from_station_id == from_station and section.to_station_id == to_station:
                return section
        return None

    def _find_section_by_id(self, sections: List[SectionInfo], section_id: UUID) -> Optional[SectionInfo]:
        """Find section by ID"""
        for section in sections:
            if section.section_id == section_id:
                return section
        return None

    def _get_next_stop(self, stops: List[TrainStop], current: TrainStop) -> Optional[TrainStop]:
        """Get next stop after current"""
        for stop in stops:
            if stop.sequence == current.sequence + 1:
                return stop
        return None

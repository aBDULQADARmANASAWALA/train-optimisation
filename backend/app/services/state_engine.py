import logging
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Tuple, Any
from uuid import UUID
from collections import defaultdict
import networkx as nx

from app.models import TrainStatus
from app.repositories import TrainRepository, SectionRepository


logger = logging.getLogger(__name__)


class RailwayStateEngine:
    """
    In-memory state engine for railway network management.

    Maintains a NetworkX graph representation of the railway network with:
    - Nodes: stations
    - Edges: sections with capacity, headway, travel time

    Tracks real-time occupancy and predicts conflicts using a rolling horizon window.
    Does not access database directly; uses repositories for state loading.

    Designed to scale to hundreds of trains with O(1) occupancy lookups.
    """

    def __init__(
        self,
        train_repository: TrainRepository,
        section_repository: SectionRepository,
        current_time: datetime,
        horizon_minutes: int = 60,
        rolling_step_minutes: int = 5,
    ):
        """
        Initialize the state engine.

        Args:
            train_repository: TrainRepository instance for loading train states
            section_repository: SectionRepository instance for loading network
            current_time: Current simulation/real time
            horizon_minutes: Look-ahead window size (minutes)
            rolling_step_minutes: Rolling window step size (minutes)
        """
        self.train_repo = train_repository
        self.section_repo = section_repository
        self.current_time = current_time
        self.horizon_minutes = horizon_minutes
        self.rolling_step_minutes = rolling_step_minutes

        # Network graph
        self.graph: nx.DiGraph = nx.DiGraph()

        # Occupancy tracking: section_id -> list of (train_id, arrival_time, departure_time)
        self.section_occupancy: Dict[UUID, List[Tuple[UUID, datetime, datetime]]] = defaultdict(list)

        # Platform occupancy: station_id -> list of (train_id, arrival_time, departure_time)
        self.platform_occupancy: Dict[UUID, List[Tuple[UUID, datetime, datetime]]] = defaultdict(list)

        # Train schedules for conflict prediction: train_id -> list of scheduled stops
        self.train_schedules: Dict[UUID, List[Dict[str, Any]]] = {}

        # Train current information: train_id -> train info
        self.trains: Dict[UUID, Dict[str, Any]] = {}

        # Initialize state
        self._build_network()
        self._load_train_states()

    def _build_network(self) -> None:
        """
        Build NetworkX graph from repository data.

        Creates nodes for all stations and directed edges for all sections.
        Each edge carries attributes: capacity, headway_minutes, travel_time_minutes.
        """
        try:
            # Get all sections from repository
            sections = self.section_repo.get_all_sections()

            # Add stations as nodes
            for section in sections:
                from_id = UUID(section["from_station_id"])
                to_id = UUID(section["to_station_id"])

                if from_id not in self.graph:
                    self.graph.add_node(from_id, properties=section.get("from_station", {}))
                if to_id not in self.graph:
                    self.graph.add_node(to_id, properties=section.get("to_station", {}))

            # Add sections as edges
            for section in sections:
                from_id = UUID(section["from_station_id"])
                to_id = UUID(section["to_station_id"])
                section_id = UUID(section["id"])

                self.graph.add_edge(
                    from_id,
                    to_id,
                    section_id=section_id,
                    capacity=section["capacity"],
                    headway_minutes=section["headway_minutes"],
                    travel_time_minutes=section["travel_time_minutes"],
                    signalling_type=section.get("signalling_type"),
                )

            logger.info(
                f"Network built: {self.graph.number_of_nodes()} stations, "
                f"{self.graph.number_of_edges()} sections"
            )

        except Exception as e:
            logger.error(f"Error building network: {str(e)}")
            raise

    def _load_train_states(self) -> None:
        """
        Load all train states and schedules from repositories.

        Populates:
        - self.trains: current train info
        - self.train_schedules: complete schedules
        - self.section_occupancy: trains on sections
        - self.platform_occupancy: trains at stations
        """
        try:
            # Load active trains
            active_trains = self.train_repo.get_active_trains(self.current_time)

            for train in active_trains:
                train_id = UUID(train["id"])
                self.trains[train_id] = train

                # Load schedule for this train
                schedule = self.train_repo.get_train_schedule(train_id)
                self.train_schedules[train_id] = schedule

            # Load current states
            states = self.train_repo.get_current_train_states()

            for state in states:
                train_id = UUID(state["train_id"])

                # Add to section occupancy if in transit
                if state["current_section_id"]:
                    section_id = UUID(state["current_section_id"])
                    arrival = datetime.fromisoformat(state["actual_arrival"]) if state["actual_arrival"] else self.current_time
                    departure = datetime.fromisoformat(state["actual_departure"]) if state["actual_departure"] else self.current_time
                    self.section_occupancy[section_id].append((train_id, arrival, departure))

                # Add to platform occupancy if at station
                if state["current_station_id"]:
                    station_id = UUID(state["current_station_id"])
                    arrival = datetime.fromisoformat(state["actual_arrival"]) if state["actual_arrival"] else self.current_time
                    departure = datetime.fromisoformat(state["actual_departure"]) if state["actual_departure"] else self.current_time
                    self.platform_occupancy[station_id].append((train_id, arrival, departure))

            logger.info(f"Loaded {len(self.trains)} active trains")

        except Exception as e:
            logger.error(f"Error loading train states: {str(e)}")
            raise

    def detect_conflicts(self) -> Dict[str, Any]:
        """
        Detect all current and imminent conflicts in the network.

        Conflict types:
        1. Capacity violation: Section exceeds capacity at same time
        2. Headway violation: Trains too close together (violates minimum headway)
        3. Platform occupation: Multiple trains at same platform simultaneously

        Returns:
            Dictionary with:
            - 'capacity_conflicts': List of (section_id, train_ids, occupancy_count)
            - 'headway_conflicts': List of (section_id, train_pair, headway_gap_minutes)
            - 'platform_conflicts': List of (station_id, train_ids, count)
            - 'total_conflicts': Total number of conflict conditions
        """
        capacity_conflicts = []
        headway_conflicts = []
        platform_conflicts = []

        # Check section capacity
        for section_id, occupants in self.section_occupancy.items():
            if not occupants:
                continue

            edge_data = self._get_edge_by_section_id(section_id)
            if not edge_data:
                continue

            capacity = edge_data["capacity"]

            # Group by time window to detect concurrent occupancy
            if len(occupants) > capacity:
                # Simplified: if more than capacity, flag conflict
                train_ids = [str(t[0]) for t in occupants]
                capacity_conflicts.append({
                    "section_id": str(section_id),
                    "train_ids": train_ids,
                    "current_occupancy": len(occupants),
                    "capacity": capacity,
                })

            # Check headway between consecutive trains
            if len(occupants) > 1:
                sorted_occupants = sorted(occupants, key=lambda x: x[1])  # Sort by arrival
                for i in range(len(sorted_occupants) - 1):
                    train1_id, train1_arrival, train1_departure = sorted_occupants[i]
                    train2_id, train2_arrival, train2_departure = sorted_occupants[i + 1]

                    # Headway is departure of first to arrival of second
                    headway_gap = (train2_arrival - train1_departure).total_seconds() / 60
                    min_headway = edge_data["headway_minutes"]

                    if headway_gap < min_headway:
                        headway_conflicts.append({
                            "section_id": str(section_id),
                            "train_pair": [str(train1_id), str(train2_id)],
                            "headway_gap_minutes": round(headway_gap, 2),
                            "required_headway_minutes": min_headway,
                        })

        # Check platform occupation
        for station_id, occupants in self.platform_occupancy.items():
            if len(occupants) > 1:
                # Multiple trains at platform simultaneously
                train_ids = [str(t[0]) for t in occupants]
                platform_conflicts.append({
                    "station_id": str(station_id),
                    "train_ids": train_ids,
                    "count": len(occupants),
                })

        total = len(capacity_conflicts) + len(headway_conflicts) + len(platform_conflicts)

        logger.info(f"Conflict detection: {len(capacity_conflicts)} capacity, "
                   f"{len(headway_conflicts)} headway, {len(platform_conflicts)} platform")

        return {
            "capacity_conflicts": capacity_conflicts,
            "headway_conflicts": headway_conflicts,
            "platform_conflicts": platform_conflicts,
            "total_conflicts": total,
        }

    def get_section_load(self, section_id: UUID) -> Dict[str, Any]:
        """
        Get current occupancy and utilization of a section.

        Args:
            section_id: UUID of the section

        Returns:
            Dictionary with:
            - 'section_id': Section UUID
            - 'current_occupancy': Number of trains currently on section
            - 'capacity': Maximum capacity
            - 'utilization_percent': Occupancy / capacity * 100
            - 'occupying_trains': List of train IDs and their times
        """
        section_id_uuid = section_id if isinstance(section_id, UUID) else UUID(section_id)
        occupants = self.section_occupancy.get(section_id_uuid, [])
        edge_data = self._get_edge_by_section_id(section_id_uuid)

        if not edge_data:
            return {
                "section_id": str(section_id_uuid),
                "error": "Section not found in network",
            }

        capacity = edge_data["capacity"]
        current_occupancy = len(occupants)
        utilization = (current_occupancy / capacity * 100) if capacity > 0 else 0

        return {
            "section_id": str(section_id_uuid),
            "current_occupancy": current_occupancy,
            "capacity": capacity,
            "utilization_percent": round(utilization, 2),
            "occupying_trains": [
                {
                    "train_id": str(train_id),
                    "arrival_time": arrival.isoformat() if arrival else None,
                    "departure_time": departure.isoformat() if departure else None,
                }
                for train_id, arrival, departure in occupants
            ],
        }

    def get_future_conflict_predictions(
        self,
        predicted_arrivals: Dict[UUID, List[Tuple[UUID, datetime, datetime]]],
    ) -> Dict[str, Any]:
        """
        Predict conflicts based on forecasted train arrivals.

        Simulates train movements through the network within the horizon window
        and detects potential conflicts.

        Args:
            predicted_arrivals: Dictionary mapping train_id -> list of
                (section_id, predicted_arrival_time, predicted_departure_time) tuples

        Returns:
            Dictionary with:
            - 'horizon_start': Window start time
            - 'horizon_end': Window end time
            - 'predicted_conflicts': List of predicted conflicts
            - 'critical_sections': Sections with high predicted occupancy
        """
        horizon_start = self.current_time
        horizon_end = self.current_time + timedelta(minutes=self.horizon_minutes)

        predicted_conflicts = []
        section_future_load: Dict[UUID, List[Tuple[UUID, datetime, datetime]]] = defaultdict(list)

        # Build future occupancy map from predictions
        for train_id, arrivals in predicted_arrivals.items():
            for section_id, arrival_time, departure_time in arrivals:
                # Only consider events within horizon
                if horizon_start <= arrival_time <= horizon_end:
                    section_future_load[section_id].append((train_id, arrival_time, departure_time))

        # Detect conflicts in future window
        for section_id, occupants in section_future_load.items():
            if not occupants:
                continue

            edge_data = self._get_edge_by_section_id(section_id)
            if not edge_data:
                continue

            capacity = edge_data["capacity"]
            headway = edge_data["headway_minutes"]

            # Capacity violations
            if len(occupants) > capacity:
                predicted_conflicts.append({
                    "type": "capacity",
                    "section_id": str(section_id),
                    "train_ids": [str(t[0]) for t in occupants],
                    "projected_occupancy": len(occupants),
                    "capacity": capacity,
                })

            # Headway violations
            sorted_occupants = sorted(occupants, key=lambda x: x[1])
            for i in range(len(sorted_occupants) - 1):
                _, departure1, _ = sorted_occupants[i]
                train2_id, arrival2, _ = sorted_occupants[i + 1]
                gap = (arrival2 - departure1).total_seconds() / 60

                if gap < headway:
                    predicted_conflicts.append({
                        "type": "headway",
                        "section_id": str(section_id),
                        "affected_train": str(train2_id),
                        "headway_gap_minutes": round(gap, 2),
                        "required_headway": headway,
                    })

        # Identify critical sections (high future load)
        critical_sections = []
        for section_id, occupants in section_future_load.items():
            edge_data = self._get_edge_by_section_id(section_id)
            if edge_data:
                capacity = edge_data["capacity"]
                utilization = len(occupants) / capacity if capacity > 0 else 0

                if utilization > 0.7:  # >70% is critical
                    critical_sections.append({
                        "section_id": str(section_id),
                        "predicted_occupancy": len(occupants),
                        "capacity": capacity,
                        "utilization_percent": round(utilization * 100, 2),
                    })

        logger.info(f"Predicted {len(predicted_conflicts)} conflicts in horizon window")

        return {
            "horizon_start": horizon_start.isoformat(),
            "horizon_end": horizon_end.isoformat(),
            "predicted_conflicts": predicted_conflicts,
            "critical_sections": critical_sections,
            "total_predicted_conflicts": len(predicted_conflicts),
        }

    def snapshot_state(self) -> Dict[str, Any]:
        """
        Capture complete current state snapshot for analysis/persistence.

        Returns:
            Dictionary containing:
            - 'timestamp': Current engine time
            - 'active_trains_count': Number of active trains
            - 'network_stats': Graph statistics
            - 'occupancy_summary': Section and platform occupancy counts
            - 'train_positions': Current position of each train
            - 'conflicts': Current detected conflicts
        """
        conflicts = self.detect_conflicts()

        train_positions = []
        for train_id, train_info in self.trains.items():
            # Find current position
            current_section = None
            current_station = None

            for section_id, occupants in self.section_occupancy.items():
                if any(t[0] == train_id for t in occupants):
                    current_section = str(section_id)
                    break

            for station_id, occupants in self.platform_occupancy.items():
                if any(t[0] == train_id for t in occupants):
                    current_station = str(station_id)
                    break

            train_positions.append({
                "train_id": str(train_id),
                "train_number": train_info.get("train_number"),
                "status": train_info.get("status"),
                "current_section_id": current_section,
                "current_station_id": current_station,
                "accumulated_delay_minutes": train_info.get("accumulated_delay_minutes", 0),
            })

        occupied_sections = sum(1 for occ in self.section_occupancy.values() if occ)
        occupied_platforms = sum(1 for occ in self.platform_occupancy.values() if occ)

        return {
            "timestamp": self.current_time.isoformat(),
            "active_trains_count": len(self.trains),
            "network_stats": {
                "total_stations": self.graph.number_of_nodes(),
                "total_sections": self.graph.number_of_edges(),
            },
            "occupancy_summary": {
                "sections_with_trains": occupied_sections,
                "platforms_with_trains": occupied_platforms,
                "total_train_position_records": len(train_positions),
            },
            "train_positions": train_positions,
            "conflicts": conflicts,
        }

    def update_time(self, new_time: datetime) -> None:
        """
        Advance the engine time and clear old occupancy records.

        Used for rolling horizon simulation.

        Args:
            new_time: New current time
        """
        self.current_time = new_time

        # Clean up old occupancy records (before current time)
        for section_id in list(self.section_occupancy.keys()):
            occupants = self.section_occupancy[section_id]
            # Keep only occupants still active (departure after current time)
            self.section_occupancy[section_id] = [
                (t, a, d) for t, a, d in occupants if d > self.current_time
            ]

        for station_id in list(self.platform_occupancy.keys()):
            occupants = self.platform_occupancy[station_id]
            self.platform_occupancy[station_id] = [
                (t, a, d) for t, a, d in occupants if d > self.current_time
            ]

    def update_train_state(self, train_id: UUID, updates: Dict[str, Any]) -> None:
        """
        Update a train's state in the engine.

        Args:
            train_id: UUID of train to update
            updates: Dictionary of fields to update (e.g., {'status': 'in_transit'})
        """
        if train_id in self.trains:
            self.trains[train_id].update(updates)
            logger.debug(f"Updated train {train_id}: {updates}")

    def _get_edge_by_section_id(self, section_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Helper: Get edge data by section ID.

        Args:
            section_id: UUID of section

        Returns:
            Edge attribute dictionary or None if not found
        """
        for u, v, data in self.graph.edges(data=True):
            if data.get("section_id") == section_id:
                return data
        return None

    def get_network_graph(self) -> nx.DiGraph:
        """
        Get the underlying NetworkX graph for advanced analysis.

        Returns:
            The DiGraph instance
        """
        return self.graph

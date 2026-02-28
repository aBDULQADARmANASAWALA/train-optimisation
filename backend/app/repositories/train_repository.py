import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.models import Train, TrainSchedule, TrainState, TrainStatus


logger = logging.getLogger(__name__)


class TrainRepository:
    """
    Repository for train-related database operations.

    Provides clean data access abstraction without business logic.
    All methods return domain-friendly dictionaries instead of ORM objects.
    """

    def __init__(self, session: Session):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy session instance
        """
        self.session = session

    def get_active_trains(self, current_time: datetime) -> List[Dict[str, Any]]:
        """
        Retrieve all trains that are currently active (not completed or cancelled).

        Trains are considered active if their status is not COMPLETED or CANCELLED.
        Results are sorted by priority weight (descending) and train number.

        Args:
            current_time: Current datetime for reference (can be used for filtering)

        Returns:
            List of train dictionaries with fields: id, train_number, priority_weight,
            train_type, status, accumulated_delay_minutes

        Raises:
            Exception: Database query error
        """
        try:
            trains = (
                self.session.query(Train, TrainState)
                .outerjoin(TrainState)
                .filter(
                    TrainState.status.notin_([TrainStatus.COMPLETED, TrainStatus.CANCELLED])
                    | (TrainState.status.is_(None))  # Include trains without state
                )
                .order_by(TrainState.status != TrainStatus.IN_TRANSIT, Train.priority_weight.desc())
                .all()
            )

            result = []
            for train, state in trains:
                result.append({
                    "id": str(train.id),
                    "train_number": train.train_number,
                    "priority_weight": train.priority_weight,
                    "train_type": train.train_type,
                    "max_speed_kmph": train.max_speed_kmph,
                    "rake_length": train.rake_length,
                    "status": state.status.value if state else TrainStatus.SCHEDULED.value,
                    "accumulated_delay_minutes": state.accumulated_delay_minutes if state else 0.0,
                })

            return result

        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving active trains: {str(e)}")
            raise Exception(f"Failed to retrieve active trains: {str(e)}")

    def get_train_schedule(self, train_id: UUID) -> List[Dict[str, Any]]:
        """
        Retrieve the complete schedule for a train.

        Returns all scheduled stops in sequence order, including station details
        and scheduled arrival/departure times.

        Args:
            train_id: UUID of the train

        Returns:
            List of schedule dictionaries with fields: id, station_id, station_name,
            zone, scheduled_arrival, scheduled_departure, sequence

        Raises:
            ValueError: If train not found
            Exception: Database query error
        """
        try:
            # Verify train exists
            train = self.session.query(Train).filter(Train.id == train_id).first()
            if not train:
                raise ValueError(f"Train with id {train_id} not found")

            schedules = (
                self.session.query(TrainSchedule)
                .filter(TrainSchedule.train_id == train_id)
                .order_by(TrainSchedule.stop_order)
                .all()
            )

            result = []
            for schedule in schedules:
                station = schedule.station
                result.append({
                    "id": str(schedule.id),
                    "station_id": str(schedule.station_id),
                    "station_name": station.name,
                    "zone": station.zone,
                    "scheduled_arrival": schedule.scheduled_arrival.isoformat() if schedule.scheduled_arrival else None,
                    "scheduled_departure": schedule.scheduled_departure.isoformat() if schedule.scheduled_departure else None,
                    "stop_order": schedule.stop_order,
                    "platform_preference": schedule.platform_preference,
                })

            return result

        except ValueError:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving schedule for train {train_id}: {str(e)}")
            raise Exception(f"Failed to retrieve train schedule: {str(e)}")

    def get_current_train_states(self) -> List[Dict[str, Any]]:
        """
        Retrieve current operational state of all trains.

        Returns the latest state information for all trains including position,
        status, and accumulated delays.

        Returns:
            List of state dictionaries with fields: train_id, train_number,
            current_section_id, current_station_id, status, actual_arrival,
            actual_departure, accumulated_delay_minutes, last_updated

        Raises:
            Exception: Database query error
        """
        try:
            states = (
                self.session.query(TrainState, Train)
                .join(Train, TrainState.train_id == Train.id)
                .all()
            )

            result = []
            for state, train in states:
                result.append({
                    "train_id": str(state.train_id),
                    "train_number": train.train_number,
                    "current_section_id": str(state.current_section_id) if state.current_section_id else None,
                    "current_station_id": str(state.current_station_id) if state.current_station_id else None,
                    "status": state.status.value,
                    "actual_arrival": state.actual_arrival.isoformat() if state.actual_arrival else None,
                    "actual_departure": state.actual_departure.isoformat() if state.actual_departure else None,
                    "accumulated_delay_minutes": state.accumulated_delay_minutes,
                    "last_updated": state.last_updated.isoformat(),
                })

            return result

        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving train states: {str(e)}")
            raise Exception(f"Failed to retrieve train states: {str(e)}")

    def update_train_state(
        self,
        train_id: UUID,
        updated_fields: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update the state of a single train.

        Performs a single transaction update of the specified fields.
        Automatically updates the last_updated timestamp.

        Args:
            train_id: UUID of the train to update
            updated_fields: Dictionary of fields to update (e.g., {'status': 'in_transit', 'accumulated_delay_minutes': 5})

        Returns:
            Dictionary of updated state with all fields

        Raises:
            ValueError: If train state not found or invalid fields provided
            IntegrityError: If update violates constraints
            Exception: Database error
        """
        try:
            state = self.session.query(TrainState).filter(TrainState.train_id == train_id).first()
            if not state:
                raise ValueError(f"Train state for train {train_id} not found")

            # Validate fields exist on model
            valid_fields = {
                "current_section_id",
                "current_station_id",
                "status",
                "actual_arrival",
                "actual_departure",
                "accumulated_delay_minutes",
            }
            invalid_fields = set(updated_fields.keys()) - valid_fields
            if invalid_fields:
                raise ValueError(f"Invalid fields for update: {invalid_fields}")

            # Update fields
            for key, value in updated_fields.items():
                # Coerce 'status' string → TrainStatus enum so SQLAlchemy doesn't
                # raise DataError when the simulator passes plain strings like
                # 'delayed' or 'in_transit'.
                if key == "status" and isinstance(value, str):
                    try:
                        value = TrainStatus(value)
                    except ValueError:
                        logger.warning(f"Unknown status value '{value}' for train {train_id} — keeping as-is")
                setattr(state, key, value)

            # last_updated is automatically set by onupdate
            self.session.commit()

            logger.info(f"Updated train state for train {train_id}")

            result = {
                "train_id": str(state.train_id),
                "current_section_id": str(state.current_section_id) if state.current_section_id else None,
                "current_station_id": str(state.current_station_id) if state.current_station_id else None,
                "status": state.status.value,
                "actual_arrival": state.actual_arrival.isoformat() if state.actual_arrival else None,
                "actual_departure": state.actual_departure.isoformat() if state.actual_departure else None,
                "accumulated_delay_minutes": state.accumulated_delay_minutes,
                "last_updated": state.last_updated.isoformat(),
            }

            return result

        except (ValueError, IntegrityError) as e:
            self.session.rollback()
            logger.warning(f"Update failed for train {train_id}: {str(e)}")
            raise
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Database error updating train state for {train_id}: {str(e)}")
            raise Exception(f"Failed to update train state: {str(e)}")

    def bulk_update_train_states(
        self,
        list_of_updates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Atomically update multiple train states in a single transaction.

        Each update dict should contain 'train_id' and other fields to update.
        If any update fails, the entire transaction is rolled back.

        Args:
            list_of_updates: List of update dicts, each containing:
                - 'train_id': UUID of train to update
                - Other fields: values to update (same as update_train_state)

        Returns:
            Dictionary with keys:
            - 'successful': List of successfully updated train IDs
            - 'failed': List of failed update dicts with error messages
            - 'summary': Counter info

        Raises:
            Exception: If transaction cannot be completed
        """
        successful = []
        failed = []

        try:
            for update_dict in list_of_updates:
                try:
                    if "train_id" not in update_dict:
                        failed.append({
                            "update": update_dict,
                            "error": "Missing 'train_id' field",
                        })
                        continue

                    train_id = update_dict["train_id"]
                    if isinstance(train_id, str):
                        train_id = UUID(train_id)

                    state = self.session.query(TrainState).filter(TrainState.train_id == train_id).first()
                    if not state:
                        failed.append({
                            "train_id": str(train_id),
                            "error": "Train state not found",
                        })
                        continue

                    # Extract update fields (everything except train_id)
                    fields_to_update = {k: v for k, v in update_dict.items() if k != "train_id"}

                    # Validate fields
                    valid_fields = {
                        "current_section_id",
                        "current_station_id",
                        "status",
                        "actual_arrival",
                        "actual_departure",
                        "accumulated_delay_minutes",
                    }
                    invalid_fields = set(fields_to_update.keys()) - valid_fields
                    if invalid_fields:
                        failed.append({
                            "train_id": str(train_id),
                            "error": f"Invalid fields: {invalid_fields}",
                        })
                        continue

                    # Apply updates
                    for key, value in fields_to_update.items():
                        setattr(state, key, value)

                    successful.append(str(train_id))

                except (ValueError, IntegrityError) as e:
                    failed.append({
                        "train_id": str(update_dict.get("train_id", "unknown")),
                        "error": str(e),
                    })

            # Commit all changes atomically
            self.session.commit()
            logger.info(f"Bulk update completed: {len(successful)} successful, {len(failed)} failed")

            return {
                "successful": successful,
                "failed": failed,
                "summary": {
                    "total": len(list_of_updates),
                    "successful_count": len(successful),
                    "failed_count": len(failed),
                },
            }

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Database error in bulk update: {str(e)}")
            raise Exception(f"Bulk update transaction failed: {str(e)}")

    def get_train_by_id(self, train_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single train by ID with basic information.

        Args:
            train_id: UUID of the train

        Returns:
            Train dictionary or None if not found

        Raises:
            Exception: Database query error
        """
        try:
            train = self.session.query(Train).filter(Train.id == train_id).first()
            if not train:
                return None

            return {
                "id": str(train.id),
                "train_number": train.train_number,
                "priority_weight": train.priority_weight,
                "train_type": train.train_type,
                "max_speed_kmph": train.max_speed_kmph,
                "rake_length": train.rake_length,
            }

        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving train {train_id}: {str(e)}")
            raise Exception(f"Failed to retrieve train: {str(e)}")

    def get_trains_by_status(self, status: TrainStatus) -> List[Dict[str, Any]]:
        """
        Retrieve all trains with a specific status.

        Args:
            status: TrainStatus enum value to filter by

        Returns:
            List of train dictionaries with current status

        Raises:
            Exception: Database query error
        """
        try:
            trains = (
                self.session.query(Train, TrainState)
                .outerjoin(TrainState)
                .filter(TrainState.status == status)
                .all()
            )

            result = []
            for train, state in trains:
                result.append({
                    "id": str(train.id),
                    "train_number": train.train_number,
                    "priority_weight": train.priority_weight,
                    "train_type": train.train_type,
                    "max_speed_kmph": train.max_speed_kmph,
                    "rake_length": train.rake_length,
                    "status": state.status.value if state else status.value,
                    "accumulated_delay_minutes": state.accumulated_delay_minutes if state else 0.0,
                })

            return result

        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving trains by status {status}: {str(e)}")
            raise Exception(f"Failed to retrieve trains by status: {str(e)}")

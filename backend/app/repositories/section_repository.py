import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.models import Section, Station


logger = logging.getLogger(__name__)


class SectionRepository:
    """
    Repository for section-related database operations.

    Provides clean data access abstraction for railway sections/segments.
    """

    def __init__(self, session: Session):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy session instance
        """
        self.session = session

    def get_all_sections(self) -> List[Dict[str, Any]]:
        """
        Retrieve all sections in the network with station details.

        Returns:
            List of section dictionaries with fields: id, from_station_id, to_station_id,
            from_station (name, zone), to_station (name, zone), capacity, headway_minutes,
            travel_time_minutes, signalling_type

        Raises:
            Exception: Database query error
        """
        try:
            sections = self.session.query(Section).all()

            result = []
            for section in sections:
                result.append({
                    "id": str(section.id),
                    "from_station_id": str(section.from_station_id),
                    "to_station_id": str(section.to_station_id),
                    "from_station": {
                        "name": section.station_from.name,
                        "zone": section.station_from.zone,
                    },
                    "to_station": {
                        "name": section.station_to.name,
                        "zone": section.station_to.zone,
                    },
                    "capacity": section.capacity,
                    "headway_minutes": section.headway_minutes,
                    "travel_time_minutes": section.travel_time_minutes,
                    "signalling_type": section.signalling_type.value if hasattr(section.signalling_type, 'value') else section.signalling_type,
                })

            return result

        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving all sections: {str(e)}")
            raise Exception(f"Failed to retrieve sections: {str(e)}")

    def get_section_by_id(self, section_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single section by ID.

        Args:
            section_id: UUID of the section

        Returns:
            Section dictionary or None if not found

        Raises:
            Exception: Database query error
        """
        try:
            section = self.session.query(Section).filter(Section.id == section_id).first()
            if not section:
                return None

            return {
                "id": str(section.id),
                "from_station_id": str(section.from_station_id),
                "to_station_id": str(section.to_station_id),
                "from_station": {
                    "name": section.station_from.name,
                    "zone": section.station_from.zone,
                },
                "to_station": {
                    "name": section.station_to.name,
                    "zone": section.station_to.zone,
                },
                "capacity": section.capacity,
                "headway_minutes": section.headway_minutes,
                "travel_time_minutes": section.travel_time_minutes,
                    "signalling_type": section.signalling_type.value if hasattr(section.signalling_type, 'value') else section.signalling_type,
            }

        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving section {section_id}: {str(e)}")
            raise Exception(f"Failed to retrieve section: {str(e)}")

    def get_sections_from_station(self, station_id: UUID) -> List[Dict[str, Any]]:
        """
        Retrieve all sections starting from a given station.

        Args:
            station_id: UUID of the station

        Returns:
            List of outgoing section dictionaries

        Raises:
            Exception: Database query error
        """
        try:
            sections = self.session.query(Section).filter(Section.from_station_id == station_id).all()

            result = []
            for section in sections:
                result.append({
                    "id": str(section.id),
                    "from_station_id": str(section.from_station_id),
                    "to_station_id": str(section.to_station_id),
                    "to_station_name": section.station_to.name,
                    "capacity": section.capacity,
                    "headway_minutes": section.headway_minutes,
                    "travel_time_minutes": section.travel_time_minutes,
                        "signalling_type": section.signalling_type.value if hasattr(section.signalling_type, 'value') else section.signalling_type,
                })

            return result

        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving sections from {station_id}: {str(e)}")
            raise Exception(f"Failed to retrieve sections: {str(e)}")

    def get_sections_to_station(self, station_id: UUID) -> List[Dict[str, Any]]:
        """
        Retrieve all sections ending at a given station.

        Args:
            station_id: UUID of the station

        Returns:
            List of incoming section dictionaries

        Raises:
            Exception: Database query error
        """
        try:
            sections = self.session.query(Section).filter(Section.to_station_id == station_id).all()

            result = []
            for section in sections:
                result.append({
                    "id": str(section.id),
                    "from_station_id": str(section.from_station_id),
                    "from_station_name": section.station_from.name,
                    "to_station_id": str(section.to_station_id),
                    "capacity": section.capacity,
                    "headway_minutes": section.headway_minutes,
                    "travel_time_minutes": section.travel_time_minutes,
                        "signalling_type": section.signalling_type.value if hasattr(section.signalling_type, 'value') else section.signalling_type,
                })

            return result

        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving sections to {station_id}: {str(e)}")
            raise Exception(f"Failed to retrieve sections: {str(e)}")

    def get_section_route(self, from_station_id: UUID, to_station_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Retrieve the section for a specific route.

        Args:
            from_station_id: UUID of origin station
            to_station_id: UUID of destination station

        Returns:
            Section dictionary or None if no direct connection exists

        Raises:
            Exception: Database query error
        """
        try:
            section = (
                self.session.query(Section)
                .filter(
                    Section.from_station_id == from_station_id,
                    Section.to_station_id == to_station_id,
                )
                .first()
            )

            if not section:
                return None

            return {
                "id": str(section.id),
                "from_station_id": str(section.from_station_id),
                "to_station_id": str(section.to_station_id),
                "capacity": section.capacity,
                "headway_minutes": section.headway_minutes,
                "travel_time_minutes": section.travel_time_minutes,
                "signalling_type": section.signalling_type.value if hasattr(section.signalling_type, 'value') else section.signalling_type,
            }

        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving section route {from_station_id}->{to_station_id}: {str(e)}")
            raise Exception(f"Failed to retrieve section: {str(e)}")

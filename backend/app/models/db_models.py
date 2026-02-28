from datetime import datetime
from uuid import uuid4
from typing import Optional
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    Enum as SQLEnum,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
import enum


Base = declarative_base()


class TrainStatus(str, enum.Enum):
    """Enumeration of possible train statuses"""
    SCHEDULED = "scheduled"
    IN_TRANSIT = "in_transit"
    STOPPED = "stopped"
    DELAYED = "delayed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class SignallingType(str, enum.Enum):
    """Train signalling/control system types"""
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    MIXED = "mixed"


class Station(Base):
    """
    Represents a railway station in the network.

    Attributes:
        id: Unique UUID identifier
        name: Station name
        zone: Zone/area identifier for grouping
        latitude: GPS latitude coordinate
        longitude: GPS longitude coordinate
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated
    """
    __tablename__ = "stations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False)
    name = Column(String(255), nullable=False, index=True)
    zone = Column(String(100), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    sections_from = relationship(
        "Section",
        foreign_keys="Section.from_station_id",
        back_populates="station_from",
        cascade="all, delete-orphan",
    )
    sections_to = relationship(
        "Section",
        foreign_keys="Section.to_station_id",
        back_populates="station_to",
        cascade="all, delete-orphan",
    )
    trains_originating = relationship(
        "Train",
        foreign_keys="Train.origin_id",
        back_populates="origin_station",
    )
    trains_destinating = relationship(
        "Train",
        foreign_keys="Train.destination_id",
        back_populates="destination_station",
    )
    schedules = relationship(
        "TrainSchedule",
        back_populates="station",
        cascade="all, delete-orphan",
    )
    train_states = relationship(
        "TrainState",
        back_populates="current_station",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("zone", "name", name="uq_station_zone_name"),
        Index("idx_station_zone_name", "zone", "name"),
    )


class Section(Base):
    """
    Represents a railway section/segment between two stations.

    Attributes:
        id: Unique UUID identifier
        from_station_id: UUID of origin station (foreign key)
        to_station_id: UUID of destination station (foreign key)
        capacity: Number of trains that can be in this section concurrently
        headway_minutes: Minimum time between trains (minutes)
        travel_time_minutes: Standard travel time through section (minutes)
        signalling_type: Type of signalling system used
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated
    """
    __tablename__ = "sections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False)
    from_station_id = Column(
        UUID(as_uuid=True),
        ForeignKey("stations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_station_id = Column(
        UUID(as_uuid=True),
        ForeignKey("stations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    capacity = Column(Integer, nullable=False, default=1)
    headway_minutes = Column(Float, nullable=False, default=5.0)
    travel_time_minutes = Column(Float, nullable=False, default=10.0)
    signalling_type = Column(SQLEnum(SignallingType), nullable=False, default=SignallingType.AUTOMATIC)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    station_from = relationship(
        "Station",
        foreign_keys=[from_station_id],
        back_populates="sections_from",
    )
    station_to = relationship(
        "Station",
        foreign_keys=[to_station_id],
        back_populates="sections_to",
    )
    train_states = relationship(
        "TrainState",
        back_populates="current_section",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("from_station_id", "to_station_id", name="uq_section_route"),
        Index("idx_section_route", "from_station_id", "to_station_id"),
    )


class Train(Base):
    """
    Represents a train in the network.

    Attributes:
        id: Unique UUID identifier
        train_number: Human-readable train identifier (e.g., "IC101")
        priority_weight: Priority score for scheduling (higher = more important)
        origin_id: UUID of origin station (foreign key)
        destination_id: UUID of destination station (foreign key)
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated
    """
    __tablename__ = "trains"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False)
    train_number = Column(String(50), nullable=False, unique=True, index=True)
    priority_weight = Column(Float, nullable=False, default=1.0)
    origin_id = Column(
        UUID(as_uuid=True),
        ForeignKey("stations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    destination_id = Column(
        UUID(as_uuid=True),
        ForeignKey("stations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    origin_station = relationship(
        "Station",
        foreign_keys=[origin_id],
        back_populates="trains_originating",
    )
    destination_station = relationship(
        "Station",
        foreign_keys=[destination_id],
        back_populates="trains_destinating",
    )
    schedules = relationship(
        "TrainSchedule",
        back_populates="train",
        cascade="all, delete-orphan",
    )
    state = relationship(
        "TrainState",
        back_populates="train",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_train_number", "train_number"),
    )


class TrainSchedule(Base):
    """
    Represents a scheduled stop for a train at a station.

    Attributes:
        id: Unique UUID identifier
        train_id: UUID of train (foreign key)
        station_id: UUID of station (foreign key)
        scheduled_arrival: Scheduled arrival time at station
        scheduled_departure: Scheduled departure time from station
        sequence: Order of this stop in the train's itinerary
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated
    """
    __tablename__ = "train_schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False)
    train_id = Column(
        UUID(as_uuid=True),
        ForeignKey("trains.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    station_id = Column(
        UUID(as_uuid=True),
        ForeignKey("stations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scheduled_arrival = Column(DateTime, nullable=False)
    scheduled_departure = Column(DateTime, nullable=False)
    sequence = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    train = relationship("Train", back_populates="schedules")
    station = relationship("Station", back_populates="schedules")

    __table_args__ = (
        UniqueConstraint("train_id", "station_id", "sequence", name="uq_train_schedule"),
        Index("idx_train_schedule_train_stop", "train_id", "sequence"),
        Index("idx_train_schedule_times", "scheduled_arrival", "scheduled_departure"),
    )


class TrainState(Base):
    """
    Represents the real-time operational state of a train.

    Attributes:
        id: Unique UUID identifier
        train_id: UUID of train (foreign key)
        current_section_id: UUID of current section (nullable, foreign key)
        current_station_id: UUID of current station (nullable, foreign key)
        status: Current operational status (scheduled, in_transit, stopped, etc.)
        actual_arrival: Actual arrival time at current location
        actual_departure: Actual departure time from current location
        accumulated_delay_minutes: Total delay accumulated so far (minutes)
        last_updated: Timestamp of last status update
        created_at: Timestamp when record was created
    """
    __tablename__ = "train_states"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False)
    train_id = Column(
        UUID(as_uuid=True),
        ForeignKey("trains.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    current_section_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    current_station_id = Column(
        UUID(as_uuid=True),
        ForeignKey("stations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status = Column(SQLEnum(TrainStatus), nullable=False, default=TrainStatus.SCHEDULED, index=True)
    actual_arrival = Column(DateTime, nullable=True)
    actual_departure = Column(DateTime, nullable=True)
    accumulated_delay_minutes = Column(Float, nullable=False, default=0.0)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    train = relationship("Train", back_populates="state")
    current_section = relationship("Section", back_populates="train_states")
    current_station = relationship("Station", back_populates="train_states")

    __table_args__ = (
        Index("idx_train_state_status", "status"),
        Index("idx_train_state_updated", "last_updated"),
    )


class OptimizationLog(Base):
    """
    Records results and metrics from each optimization run.

    Attributes:
        id: Unique UUID identifier
        timestamp: When optimization was executed
        objective_value: Total objective function value from solver
        total_weighted_delay: Sum of weighted delays across all trains (minutes)
        conflicts_detected: Number of conflicts discovered in solution
        solver_runtime: Actual time spent by solver (seconds)
        notes: Optional notes/metadata about the run
        created_at: Timestamp when record was created
    """
    __tablename__ = "optimization_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True, default=datetime.utcnow)
    objective_value = Column(Float, nullable=False)
    total_weighted_delay = Column(Float, nullable=False)
    conflicts_detected = Column(Integer, nullable=False, default=0)
    solver_runtime = Column(Float, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_optimization_log_timestamp", "timestamp"),
        Index("idx_optimization_log_created", "created_at"),
    )

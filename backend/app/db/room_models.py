"""Room domain metadata; migration 0004 is reserved for this module."""
from datetime import date, datetime
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.models import Base

class Facility(Base):
    __tablename__ = 'facilities'
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    label: Mapped[str] = mapped_column(String(100))

class Record:
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    version: Mapped[int] = mapped_column(Integer)
    source_label: Mapped[str] = mapped_column(String(100))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class Room(Record, Base):
    __tablename__ = 'rooms'
    __table_args__ = (
        CheckConstraint('capacity > 0', name='room_positive_capacity'),
        CheckConstraint('version > 0', name='room_positive_version'),
        CheckConstraint("status IN ('active','archived')", name='room_status'),
        CheckConstraint('(coverage_start IS NULL) = (coverage_end IS NULL)', name='room_coverage_pair'),
        CheckConstraint('coverage_end IS NULL OR coverage_end > coverage_start', name='room_coverage_interval'),
        CheckConstraint('NOT coverage_complete OR coverage_start IS NOT NULL', name='room_complete_bounds'),
    )
    code: Mapped[str] = mapped_column(String(80), unique=True)
    building_id: Mapped[str] = mapped_column(ForeignKey('buildings.id'), index=True)
    capacity: Mapped[int] = mapped_column(Integer)
    timezone: Mapped[str] = mapped_column(String(80))
    opening_hours: Mapped[list | None] = mapped_column(JSONB, nullable=False)
    coverage_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    coverage_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    coverage_complete: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[str] = mapped_column(String(20))

class RoomFacility(Base):
    __tablename__ = 'room_facilities'
    room_id: Mapped[str] = mapped_column(ForeignKey('rooms.id', ondelete='CASCADE'), primary_key=True)
    facility_id: Mapped[str] = mapped_column(ForeignKey('facilities.id'), primary_key=True)

class Booking(Record, Base):
    __tablename__ = 'bookings'
    __table_args__ = (
        CheckConstraint('ends_at > starts_at', name='booking_interval'),
        CheckConstraint('version > 0', name='booking_version'),
        CheckConstraint("status IN ('active','cancelled','archived')", name='booking_status'),
        CheckConstraint("(recurrence = 'none' AND recurrence_until IS NULL) OR (recurrence = 'weekly' AND recurrence_until IS NOT NULL)", name='booking_recurrence'),
    )
    room_id: Mapped[str] = mapped_column(ForeignKey('rooms.id'), index=True)
    purpose: Mapped[str] = mapped_column(String(200))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recurrence: Mapped[str] = mapped_column(String(10))
    recurrence_until: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20))

class BookingException(Record, Base):
    __tablename__ = 'booking_exceptions'
    __table_args__ = (
        CheckConstraint('version > 0', name='booking_exception_version'),
        CheckConstraint("status IN ('active','archived')", name='booking_exception_status'),
        CheckConstraint("(action = 'cancel' AND replacement_start IS NULL AND replacement_end IS NULL) OR (action = 'replace' AND replacement_start IS NOT NULL AND replacement_end IS NOT NULL AND replacement_end > replacement_start)", name='booking_exception_action'),
        Index('ix_booking_exception_active_occurrence', 'booking_id', 'occurrence_date', unique=True, postgresql_where=text("status = 'active'")),
    )
    booking_id: Mapped[str] = mapped_column(ForeignKey('bookings.id', ondelete='CASCADE'), index=True)
    occurrence_date: Mapped[date] = mapped_column(Date)
    action: Mapped[str] = mapped_column(String(10))
    replacement_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replacement_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20))

class RoomClosure(Record, Base):
    __tablename__ = 'room_closures'
    __table_args__ = (
        CheckConstraint('ends_at > starts_at', name='room_closure_interval'),
        CheckConstraint('version > 0', name='room_closure_version'),
        CheckConstraint("status IN ('active','archived')", name='room_closure_status'),
    )
    room_id: Mapped[str] = mapped_column(ForeignKey('rooms.id'), index=True)
    reason: Mapped[str] = mapped_column(String(300))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20))

class RoomAudit(Base):
    __tablename__ = 'room_audit'
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    room_id: Mapped[str] = mapped_column(ForeignKey('rooms.id', ondelete='CASCADE'), index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    resource: Mapped[str] = mapped_column(String(30))
    record_id: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(20))
    version: Mapped[int] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

"""Person 1 faculty-domain metadata; revision 0005."""
from datetime import date,datetime
from sqlalchemy import Boolean,CheckConstraint,Date,DateTime,ForeignKey,Index,Integer,String,text
from sqlalchemy.orm import Mapped,mapped_column
from app.db.models import Base
from app.db.room_models import Record

class Faculty(Record,Base):
    __tablename__='faculty'
    __table_args__=(CheckConstraint('version > 0',name='faculty_version'),
        CheckConstraint("status IN ('active','archived')",name='faculty_status'),
        CheckConstraint('(office_hours_coverage_start IS NULL) = (office_hours_coverage_end IS NULL)',name='faculty_coverage_pair'),
        CheckConstraint('office_hours_coverage_end IS NULL OR office_hours_coverage_end >= office_hours_coverage_start',name='faculty_coverage_order'),
        CheckConstraint('NOT office_hours_complete OR office_hours_coverage_start IS NOT NULL',name='faculty_complete_bounds'))
    name: Mapped[str]=mapped_column(String(200))
    normalized_name: Mapped[str]=mapped_column(String(200),index=True)
    department_id: Mapped[str]=mapped_column(ForeignKey('departments.id'),index=True)
    location: Mapped[str]=mapped_column(String(200))
    email: Mapped[str | None]=mapped_column(String(254))
    timezone: Mapped[str]=mapped_column(String(80))
    office_hours_coverage_start: Mapped[date | None]=mapped_column(Date)
    office_hours_coverage_end: Mapped[date | None]=mapped_column(Date)
    office_hours_complete: Mapped[bool]=mapped_column(Boolean)
    status: Mapped[str]=mapped_column(String(20))

class FacultyAlias(Record,Base):
    __tablename__='faculty_aliases'
    __table_args__=(CheckConstraint('version > 0',name='faculty_alias_version'),
        CheckConstraint("status IN ('active','archived')",name='faculty_alias_status'),
        CheckConstraint("entity_type = 'faculty'",name='faculty_alias_entity'),
        Index('ix_faculty_alias_active_target','canonical_id','normalized_alias',unique=True,postgresql_where=text("status = 'active'")))
    entity_type: Mapped[str]=mapped_column(String(20))
    canonical_id: Mapped[str]=mapped_column(ForeignKey('faculty.id',ondelete='CASCADE'),index=True)
    alias: Mapped[str]=mapped_column(String(200))
    normalized_alias: Mapped[str]=mapped_column(String(200),index=True)
    status: Mapped[str]=mapped_column(String(20))

class OfficeHour(Record,Base):
    __tablename__='office_hours'
    __table_args__=(CheckConstraint('version > 0',name='office_hour_version'),
        CheckConstraint('weekday BETWEEN 0 AND 6',name='office_hour_weekday'),
        CheckConstraint('effective_until >= effective_from',name='office_hour_dates'),
        CheckConstraint("status IN ('active','cancelled','archived')",name='office_hour_status'))
    faculty_id: Mapped[str]=mapped_column(ForeignKey('faculty.id'),index=True)
    location: Mapped[str]=mapped_column(String(200))
    weekday: Mapped[int]=mapped_column(Integer)
    start_time: Mapped[str]=mapped_column(String(5))
    end_time: Mapped[str]=mapped_column(String(5))
    effective_from: Mapped[date]=mapped_column(Date)
    effective_until: Mapped[date]=mapped_column(Date)
    timezone: Mapped[str]=mapped_column(String(80))
    status: Mapped[str]=mapped_column(String(20))

class OfficeHourException(Record,Base):
    __tablename__='office_hour_exceptions'
    __table_args__=(CheckConstraint('version > 0',name='office_hour_exception_version'),
        CheckConstraint("status IN ('active','archived')",name='office_hour_exception_status'),
        CheckConstraint("(action = 'cancel' AND replacement_start IS NULL AND replacement_end IS NULL) OR (action = 'replace' AND replacement_start IS NOT NULL AND replacement_end IS NOT NULL AND replacement_end > replacement_start)",name='office_hour_exception_action'),
        Index('ix_office_hour_exception_active_date','office_hour_id','occurrence_date',unique=True,postgresql_where=text("status = 'active'")))
    office_hour_id: Mapped[str]=mapped_column(ForeignKey('office_hours.id',ondelete='CASCADE'),index=True)
    occurrence_date: Mapped[date]=mapped_column(Date)
    action: Mapped[str]=mapped_column(String(10))
    replacement_start: Mapped[datetime | None]=mapped_column(DateTime(timezone=True))
    replacement_end: Mapped[datetime | None]=mapped_column(DateTime(timezone=True))
    note: Mapped[str]=mapped_column(String(500))
    status: Mapped[str]=mapped_column(String(20))

class FacultyAudit(Base):
    __tablename__='faculty_audit'
    id: Mapped[str]=mapped_column(String(80),primary_key=True)
    faculty_id: Mapped[str]=mapped_column(ForeignKey('faculty.id',ondelete='CASCADE'),index=True)
    actor_id: Mapped[str | None]=mapped_column(ForeignKey('users.id',ondelete='SET NULL'))
    resource: Mapped[str]=mapped_column(String(30))
    record_id: Mapped[str]=mapped_column(String(80))
    action: Mapped[str]=mapped_column(String(20))
    version: Mapped[int]=mapped_column(Integer)
    occurred_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))

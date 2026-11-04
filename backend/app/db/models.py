from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, Integer, String, ForeignKey, Boolean, UniqueConstraint, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class DemoEvent(Base):
    __tablename__ = "demo_events"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="valid_interval"),
        CheckConstraint("cost_minor IS NULL OR cost_minor >= 0", name="nonnegative_cost"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cost_minor: Mapped[int | None] = mapped_column(Integer)
    source_label: Mapped[str] = mapped_column(String(100))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    label: Mapped[str] = mapped_column(String(100))

class Building(Base):
    __tablename__ = "buildings"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    label: Mapped[str] = mapped_column(String(100))

class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    label: Mapped[str] = mapped_column(String(100))

class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('student', 'admin')", name="valid_user_role"),)
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(10))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class StudentProfile(Base):
    __tablename__ = "student_profiles"
    __table_args__ = (CheckConstraint("year IS NULL OR year BETWEEN 1 AND 4", name="valid_profile_year"),)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"))
    year: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(16))

class ProfileInterest(Base):
    __tablename__ = "profile_interests"
    user_id: Mapped[str] = mapped_column(ForeignKey("student_profiles.user_id", ondelete="CASCADE"), primary_key=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id"), primary_key=True)

class WebSession(Base):
    __tablename__ = "web_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class AuthRateLimit(Base):
    __tablename__ = "auth_rate_limits"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="event_valid_interval"),
        CheckConstraint("cost_minor IS NULL OR cost_minor >= 0", name="event_nonnegative_cost"),
        CheckConstraint("registration_deadline IS NULL OR registration_deadline <= starts_at", name="event_deadline"),
        CheckConstraint("status IN ('draft','published','cancelled','archived')", name="event_status"),
        CheckConstraint("version > 0", name="event_version"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(String(30))
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id"))
    venue: Mapped[str] = mapped_column(String(200))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cost_minor: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    registration_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    eligibility_rules: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), index=True)
    source_label: Mapped[str] = mapped_column(String(100))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer)

class EventAudit(Base):
    __tablename__ = "event_audit"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(20))
    version: Mapped[int] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    state: Mapped[dict] = mapped_column(JSONB,default=dict,server_default='{}')
    state_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer,default=1,server_default='1')

class AssistantTurn(Base):
    __tablename__ = "assistant_turns"
    __table_args__ = (UniqueConstraint("user_id", "client_request_id", name="turn_user_request_unique"),UniqueConstraint("conversation_id","sequence",name="turn_conversation_sequence_unique"))
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    client_request_id: Mapped[str] = mapped_column(String(128))
    sequence: Mapped[int] = mapped_column(Integer)
    payload_hash: Mapped[str] = mapped_column(String(64))
    question: Mapped[str] = mapped_column(String(1000))
    response: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    model_version: Mapped[str] = mapped_column(String(40))

class DeletedRequest(Base):
    """Text-free retry tombstones prevent deleted history being recreated by a delayed retry."""
    __tablename__ = 'deleted_requests'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'),primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64),primary_key=True)

class SavedRecord(Base):
    __tablename__ = 'saved_records'
    __table_args__ = (
        UniqueConstraint('user_id','kind','record_id',name='saved_user_target_unique'),
        CheckConstraint("(kind='event' AND event_id IS NOT NULL AND event_id=record_id AND room_id IS NULL AND faculty_id IS NULL) OR (kind='room' AND room_id IS NOT NULL AND room_id=record_id AND event_id IS NULL AND faculty_id IS NULL) OR (kind='faculty' AND faculty_id IS NOT NULL AND faculty_id=record_id AND event_id IS NULL AND room_id IS NULL)",name='saved_target_kind'),
    )
    id: Mapped[str] = mapped_column(String(80),primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True)
    saved_version: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))
    record_id: Mapped[str] = mapped_column(String(80))
    event_id: Mapped[str | None] = mapped_column(ForeignKey('events.id',ondelete='CASCADE'))
    room_id: Mapped[str | None] = mapped_column(ForeignKey('rooms.id',ondelete='CASCADE'))
    faculty_id: Mapped[str | None] = mapped_column(ForeignKey('faculty.id',ondelete='CASCADE'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

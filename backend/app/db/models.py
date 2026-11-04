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

class AssistantTurn(Base):
    __tablename__ = "assistant_turns"
    __table_args__ = (UniqueConstraint("user_id", "client_request_id", name="turn_user_request_unique"),)
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    client_request_id: Mapped[str] = mapped_column(String(128))
    payload_hash: Mapped[str] = mapped_column(String(64))
    question: Mapped[str] = mapped_column(String(1000))
    response: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    model_version: Mapped[str] = mapped_column(String(40))

"""Events, audit records and retry-safe minimal assistant turns."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("events",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("topic_id", sa.String(80), sa.ForeignKey("topics.id"), nullable=False),
        sa.Column("venue", sa.String(200), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cost_minor", sa.Integer()), sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("registration_deadline", sa.DateTime(timezone=True)),
        sa.Column("eligibility_rules", JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("source_label", sa.String(100), nullable=False), sa.Column("source_url", sa.String(1000)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name="event_valid_interval"),
        sa.CheckConstraint("cost_minor IS NULL OR cost_minor >= 0", name="event_nonnegative_cost"),
        sa.CheckConstraint("registration_deadline IS NULL OR registration_deadline <= starts_at", name="event_deadline"),
        sa.CheckConstraint("status IN ('draft','published','cancelled','archived')", name="event_status"),
        sa.CheckConstraint("version > 0", name="event_version"))
    op.create_index("ix_events_starts_at", "events", ["starts_at"])
    op.create_index("ix_events_status", "events", ["status"])
    op.create_table("event_audit",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("event_id", sa.String(80), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.String(80), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(20), nullable=False), sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_event_audit_event_id", "event_audit", ["event_id"])
    op.create_table("conversations", sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("owner_id", sa.String(80), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_conversations_owner_id", "conversations", ["owner_id"])
    op.create_table("assistant_turns",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("conversation_id", sa.String(80), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(80), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_request_id", sa.String(128), nullable=False), sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("question", sa.String(1000), nullable=False), sa.Column("response", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("model_version", sa.String(40), nullable=False),
        sa.UniqueConstraint("user_id", "client_request_id", name="turn_user_request_unique"))
    op.create_index("ix_assistant_turns_conversation_id", "assistant_turns", ["conversation_id"])

def downgrade():
    for name in ("assistant_turns", "conversations", "event_audit", "events"):
        op.drop_table(name)

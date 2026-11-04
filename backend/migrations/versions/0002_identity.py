"""Server-side sessions, users, profiles, reference data and auth rate counters."""
from alembic import op
import sqlalchemy as sa
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade():
    for name in ("departments", "buildings", "topics"):
        op.create_table(name, sa.Column("id", sa.String(80), primary_key=True), sa.Column("label", sa.String(100), nullable=False))
    op.create_table("users",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("username", sa.String(80), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(300), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.CheckConstraint("role IN ('student', 'admin')", name="valid_user_role"))
    op.create_table("student_profiles",
        sa.Column("user_id", sa.String(80), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("department_id", sa.String(80), sa.ForeignKey("departments.id")),
        sa.Column("year", sa.Integer()), sa.Column("section", sa.String(16)),
        sa.CheckConstraint("year IS NULL OR year BETWEEN 1 AND 4", name="valid_profile_year"))
    op.create_table("profile_interests",
        sa.Column("user_id", sa.String(80), sa.ForeignKey("student_profiles.user_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("topic_id", sa.String(80), sa.ForeignKey("topics.id"), primary_key=True))
    op.create_table("web_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(80), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("csrf_token", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)))
    op.create_index("ix_web_sessions_user_id", "web_sessions", ["user_id"])
    op.create_index("ix_web_sessions_expires_at", "web_sessions", ["expires_at"])
    op.create_table("auth_rate_limits", sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_auth_rate_limits_expires_at", "auth_rate_limits", ["expires_at"])

def downgrade():
    for name in ("auth_rate_limits", "web_sessions", "profile_interests", "student_profiles", "users", "topics", "buildings", "departments"):
        op.drop_table(name)

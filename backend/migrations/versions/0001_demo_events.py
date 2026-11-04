"""Initial isolated demo fixture storage; domain event tables arrive in Phase 2."""
from alembic import op
import sqlalchemy as sa
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("demo_events",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cost_minor", sa.Integer(), nullable=True),
        sa.Column("source_label", sa.String(100), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name="valid_interval"),
        sa.CheckConstraint("cost_minor IS NULL OR cost_minor >= 0", name="nonnegative_cost"))

def downgrade():
    op.drop_table("demo_events")

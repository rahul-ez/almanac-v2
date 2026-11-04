"""Person A: rooms and bounded scheduling. Reserved revision 0004."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None

def record():
    return [sa.Column('id',sa.String(80),primary_key=True),sa.Column('version',sa.Integer(),nullable=False),
            sa.Column('source_label',sa.String(100),nullable=False),sa.Column('source_url',sa.String(1000)),
            sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False)]

def upgrade():
    op.create_table('facilities',sa.Column('id',sa.String(80),primary_key=True),sa.Column('label',sa.String(100),nullable=False))
    op.create_table('rooms',*record(),sa.Column('code',sa.String(80),nullable=False,unique=True),
        sa.Column('building_id',sa.String(80),sa.ForeignKey('buildings.id'),nullable=False),
        sa.Column('capacity',sa.Integer(),nullable=False),sa.Column('timezone',sa.String(80),nullable=False),
        sa.Column('opening_hours',JSONB(),nullable=False),sa.Column('coverage_start',sa.DateTime(timezone=True)),
        sa.Column('coverage_end',sa.DateTime(timezone=True)),sa.Column('coverage_complete',sa.Boolean(),nullable=False),
        sa.Column('status',sa.String(20),nullable=False),
        sa.CheckConstraint('capacity > 0',name='room_positive_capacity'),sa.CheckConstraint('version > 0',name='room_positive_version'),
        sa.CheckConstraint("status IN ('active','archived')",name='room_status'),
        sa.CheckConstraint('(coverage_start IS NULL) = (coverage_end IS NULL)',name='room_coverage_pair'),
        sa.CheckConstraint('coverage_end IS NULL OR coverage_end > coverage_start',name='room_coverage_interval'),
        sa.CheckConstraint('NOT coverage_complete OR coverage_start IS NOT NULL',name='room_complete_bounds'))
    op.create_index('ix_rooms_building_id','rooms',['building_id'])
    op.create_table('room_facilities',sa.Column('room_id',sa.String(80),sa.ForeignKey('rooms.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('facility_id',sa.String(80),sa.ForeignKey('facilities.id'),primary_key=True))
    op.create_table('bookings',*record(),sa.Column('room_id',sa.String(80),sa.ForeignKey('rooms.id'),nullable=False),
        sa.Column('purpose',sa.String(200),nullable=False),sa.Column('starts_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('ends_at',sa.DateTime(timezone=True),nullable=False),sa.Column('recurrence',sa.String(10),nullable=False),
        sa.Column('recurrence_until',sa.Date()),sa.Column('status',sa.String(20),nullable=False),
        sa.CheckConstraint('ends_at > starts_at',name='booking_interval'),sa.CheckConstraint('version > 0',name='booking_version'),
        sa.CheckConstraint("status IN ('active','cancelled','archived')",name='booking_status'),
        sa.CheckConstraint("(recurrence = 'none' AND recurrence_until IS NULL) OR (recurrence = 'weekly' AND recurrence_until IS NOT NULL)",name='booking_recurrence'))
    op.create_index('ix_bookings_room_id','bookings',['room_id']); op.create_index('ix_bookings_starts_at','bookings',['starts_at'])
    op.create_table('booking_exceptions',*record(),sa.Column('booking_id',sa.String(80),sa.ForeignKey('bookings.id',ondelete='CASCADE'),nullable=False),
        sa.Column('occurrence_date',sa.Date(),nullable=False),sa.Column('action',sa.String(10),nullable=False),
        sa.Column('replacement_start',sa.DateTime(timezone=True)),sa.Column('replacement_end',sa.DateTime(timezone=True)),
        sa.Column('note',sa.String(500),nullable=False),sa.Column('status',sa.String(20),nullable=False),
        sa.CheckConstraint('version > 0',name='booking_exception_version'),
        sa.CheckConstraint("status IN ('active','archived')",name='booking_exception_status'),
        sa.CheckConstraint("(action = 'cancel' AND replacement_start IS NULL AND replacement_end IS NULL) OR (action = 'replace' AND replacement_start IS NOT NULL AND replacement_end IS NOT NULL AND replacement_end > replacement_start)",name='booking_exception_action'))
    op.create_index('ix_booking_exceptions_booking_id','booking_exceptions',['booking_id'])
    op.create_index('ix_booking_exception_active_occurrence','booking_exceptions',['booking_id','occurrence_date'],unique=True,postgresql_where=sa.text("status = 'active'"))
    op.create_table('room_closures',*record(),sa.Column('room_id',sa.String(80),sa.ForeignKey('rooms.id'),nullable=False),
        sa.Column('reason',sa.String(300),nullable=False),sa.Column('starts_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('ends_at',sa.DateTime(timezone=True),nullable=False),sa.Column('status',sa.String(20),nullable=False),
        sa.CheckConstraint('ends_at > starts_at',name='room_closure_interval'),sa.CheckConstraint('version > 0',name='room_closure_version'),
        sa.CheckConstraint("status IN ('active','archived')",name='room_closure_status'))
    op.create_index('ix_room_closures_room_id','room_closures',['room_id']); op.create_index('ix_room_closures_starts_at','room_closures',['starts_at'])
    op.create_table('room_audit',sa.Column('id',sa.String(80),primary_key=True),
        sa.Column('room_id',sa.String(80),sa.ForeignKey('rooms.id',ondelete='CASCADE'),nullable=False),
        sa.Column('actor_id',sa.String(80),sa.ForeignKey('users.id',ondelete='SET NULL')),
        sa.Column('resource',sa.String(30),nullable=False),sa.Column('record_id',sa.String(80),nullable=False),
        sa.Column('action',sa.String(20),nullable=False),sa.Column('version',sa.Integer(),nullable=False),
        sa.Column('occurred_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_room_audit_room_id','room_audit',['room_id'])

def downgrade():
    for name in ('room_audit','room_closures','booking_exceptions','bookings','room_facilities','rooms','facilities'):
        op.drop_table(name)

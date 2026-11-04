"""Faculty, exact aliases, published office hours and dated exceptions. Person 1."""
from alembic import op
import sqlalchemy as sa
revision='0005'
down_revision='0004'
branch_labels=None
depends_on=None

def record():
    return [sa.Column('id',sa.String(80),primary_key=True),sa.Column('version',sa.Integer(),nullable=False),
            sa.Column('source_label',sa.String(100),nullable=False),sa.Column('source_url',sa.String(1000)),
            sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False)]

def upgrade():
    op.create_table('faculty',*record(),sa.Column('name',sa.String(200),nullable=False),sa.Column('normalized_name',sa.String(200),nullable=False),
        sa.Column('department_id',sa.String(80),sa.ForeignKey('departments.id'),nullable=False),sa.Column('location',sa.String(200),nullable=False),
        sa.Column('email',sa.String(254)),sa.Column('timezone',sa.String(80),nullable=False),
        sa.Column('office_hours_coverage_start',sa.Date()),sa.Column('office_hours_coverage_end',sa.Date()),
        sa.Column('office_hours_complete',sa.Boolean(),nullable=False),sa.Column('status',sa.String(20),nullable=False),
        sa.CheckConstraint('version > 0',name='faculty_version'),sa.CheckConstraint("status IN ('active','archived')",name='faculty_status'),
        sa.CheckConstraint('(office_hours_coverage_start IS NULL) = (office_hours_coverage_end IS NULL)',name='faculty_coverage_pair'),
        sa.CheckConstraint('office_hours_coverage_end IS NULL OR office_hours_coverage_end >= office_hours_coverage_start',name='faculty_coverage_order'),
        sa.CheckConstraint('NOT office_hours_complete OR office_hours_coverage_start IS NOT NULL',name='faculty_complete_bounds'))
    op.create_index('ix_faculty_normalized_name','faculty',['normalized_name']);op.create_index('ix_faculty_department_id','faculty',['department_id'])
    op.create_table('faculty_aliases',*record(),sa.Column('entity_type',sa.String(20),nullable=False),
        sa.Column('canonical_id',sa.String(80),sa.ForeignKey('faculty.id',ondelete='CASCADE'),nullable=False),sa.Column('alias',sa.String(200),nullable=False),
        sa.Column('normalized_alias',sa.String(200),nullable=False),sa.Column('status',sa.String(20),nullable=False),
        sa.CheckConstraint('version > 0',name='faculty_alias_version'),sa.CheckConstraint("status IN ('active','archived')",name='faculty_alias_status'),
        sa.CheckConstraint("entity_type = 'faculty'",name='faculty_alias_entity'))
    op.create_index('ix_faculty_aliases_canonical_id','faculty_aliases',['canonical_id']);op.create_index('ix_faculty_aliases_normalized_alias','faculty_aliases',['normalized_alias'])
    op.create_index('ix_faculty_alias_active_target','faculty_aliases',['canonical_id','normalized_alias'],unique=True,postgresql_where=sa.text("status = 'active'"))
    op.create_table('office_hours',*record(),sa.Column('faculty_id',sa.String(80),sa.ForeignKey('faculty.id'),nullable=False),
        sa.Column('location',sa.String(200),nullable=False),sa.Column('weekday',sa.Integer(),nullable=False),sa.Column('start_time',sa.String(5),nullable=False),
        sa.Column('end_time',sa.String(5),nullable=False),sa.Column('effective_from',sa.Date(),nullable=False),sa.Column('effective_until',sa.Date(),nullable=False),
        sa.Column('timezone',sa.String(80),nullable=False),sa.Column('status',sa.String(20),nullable=False),
        sa.CheckConstraint('version > 0',name='office_hour_version'),sa.CheckConstraint('weekday BETWEEN 0 AND 6',name='office_hour_weekday'),
        sa.CheckConstraint('effective_until >= effective_from',name='office_hour_dates'),sa.CheckConstraint("status IN ('active','cancelled','archived')",name='office_hour_status'))
    op.create_index('ix_office_hours_faculty_id','office_hours',['faculty_id'])
    op.create_table('office_hour_exceptions',*record(),sa.Column('office_hour_id',sa.String(80),sa.ForeignKey('office_hours.id',ondelete='CASCADE'),nullable=False),
        sa.Column('occurrence_date',sa.Date(),nullable=False),sa.Column('action',sa.String(10),nullable=False),
        sa.Column('replacement_start',sa.DateTime(timezone=True)),sa.Column('replacement_end',sa.DateTime(timezone=True)),
        sa.Column('note',sa.String(500),nullable=False),sa.Column('status',sa.String(20),nullable=False),
        sa.CheckConstraint('version > 0',name='office_hour_exception_version'),sa.CheckConstraint("status IN ('active','archived')",name='office_hour_exception_status'),
        sa.CheckConstraint("(action = 'cancel' AND replacement_start IS NULL AND replacement_end IS NULL) OR (action = 'replace' AND replacement_start IS NOT NULL AND replacement_end IS NOT NULL AND replacement_end > replacement_start)",name='office_hour_exception_action'))
    op.create_index('ix_office_hour_exceptions_office_hour_id','office_hour_exceptions',['office_hour_id'])
    op.create_index('ix_office_hour_exception_active_date','office_hour_exceptions',['office_hour_id','occurrence_date'],unique=True,postgresql_where=sa.text("status = 'active'"))
    op.create_table('faculty_audit',sa.Column('id',sa.String(80),primary_key=True),sa.Column('faculty_id',sa.String(80),sa.ForeignKey('faculty.id',ondelete='CASCADE'),nullable=False),
        sa.Column('actor_id',sa.String(80),sa.ForeignKey('users.id',ondelete='SET NULL')),sa.Column('resource',sa.String(30),nullable=False),
        sa.Column('record_id',sa.String(80),nullable=False),sa.Column('action',sa.String(20),nullable=False),sa.Column('version',sa.Integer(),nullable=False),
        sa.Column('occurred_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_faculty_audit_faculty_id','faculty_audit',['faculty_id'])

def downgrade():
    for name in ('faculty_audit','office_hour_exceptions','office_hours','faculty_aliases','faculty'):
        op.drop_table(name)

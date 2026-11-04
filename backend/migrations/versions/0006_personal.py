"""Authoritative dialogue state, text-free deleted retry receipts and owned saves."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision='0006'
down_revision='0005'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('conversations',sa.Column('state',JSONB,nullable=False,server_default=sa.text("'{}'::jsonb")))
    op.add_column('conversations',sa.Column('state_expires_at',sa.DateTime(timezone=True)))
    op.add_column('conversations',sa.Column('version',sa.Integer(),nullable=False,server_default='1'))
    op.add_column('assistant_turns',sa.Column('sequence',sa.Integer()))
    op.execute("WITH numbered AS (SELECT id,row_number() OVER (PARTITION BY conversation_id ORDER BY created_at,id) AS n FROM assistant_turns) UPDATE assistant_turns SET sequence=numbered.n FROM numbered WHERE assistant_turns.id=numbered.id")
    op.alter_column('assistant_turns','sequence',nullable=False)
    op.create_unique_constraint('turn_conversation_sequence_unique','assistant_turns',['conversation_id','sequence'])
    op.execute("UPDATE conversations SET version=greatest(1,(SELECT count(*) FROM assistant_turns WHERE conversation_id=conversations.id))")
    op.create_table('deleted_requests',sa.Column('user_id',sa.String(80),sa.ForeignKey('users.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('request_hash',sa.String(64),primary_key=True))
    op.create_table('saved_records',sa.Column('id',sa.String(80),primary_key=True),
        sa.Column('user_id',sa.String(80),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('saved_version',sa.Integer(),nullable=False),sa.Column('kind',sa.String(20),nullable=False),sa.Column('record_id',sa.String(80),nullable=False),
        sa.Column('event_id',sa.String(80),sa.ForeignKey('events.id',ondelete='CASCADE')),
        sa.Column('room_id',sa.String(80),sa.ForeignKey('rooms.id',ondelete='CASCADE')),
        sa.Column('faculty_id',sa.String(80),sa.ForeignKey('faculty.id',ondelete='CASCADE')),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('user_id','kind','record_id',name='saved_user_target_unique'),
        sa.CheckConstraint("(kind='event' AND event_id IS NOT NULL AND event_id=record_id AND room_id IS NULL AND faculty_id IS NULL) OR (kind='room' AND room_id IS NOT NULL AND room_id=record_id AND event_id IS NULL AND faculty_id IS NULL) OR (kind='faculty' AND faculty_id IS NOT NULL AND faculty_id=record_id AND event_id IS NULL AND room_id IS NULL)",name='saved_target_kind'))
    op.create_index('ix_saved_records_user_id','saved_records',['user_id'])

def downgrade():
    op.drop_table('saved_records');op.drop_table('deleted_requests')
    op.drop_constraint('turn_conversation_sequence_unique','assistant_turns',type_='unique')
    op.drop_column('assistant_turns','sequence')
    op.drop_column('conversations','version');op.drop_column('conversations','state_expires_at');op.drop_column('conversations','state')

from alembic import context
from app.config import Settings
from app.db.connection import make_engine
from app.db.models import Base

with make_engine(Settings()).connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()

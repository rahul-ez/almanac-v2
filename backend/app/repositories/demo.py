from sqlalchemy import select
from app.db.models import DemoEvent

def get_demo_event(connection):
    return connection.execute(select(DemoEvent.__table__).where(
        DemoEvent.id == "demo-event-ml-workshop")).mappings().first()

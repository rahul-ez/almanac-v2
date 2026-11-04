import json
import argparse
from datetime import datetime
from pathlib import Path
from sqlalchemy import make_url, delete
from sqlalchemy.dialects.postgresql import insert
from app.config import Settings
from app.db.connection import make_engine
from app.db.models import DemoEvent

def seed(reset=False):
    settings = Settings()
    if make_url(settings.database_url.get_secret_value()).database not in {"almanac_demo", "almanac_test"}:
        raise SystemExit("Seed is restricted to almanac_demo or almanac_test")
    rows = json.loads(Path("/workspace/data/demo/events.json").read_text())
    for row in rows:
        for key in ("starts_at", "ends_at", "updated_at"):
            row[key] = datetime.fromisoformat(row[key])
    engine = make_engine(settings)
    try:
        with engine.begin() as conn:
            if reset:
                conn.execute(delete(DemoEvent).where(DemoEvent.id.in_([row["id"] for row in rows])))
            conn.execute(insert(DemoEvent).values(rows).on_conflict_do_nothing(index_elements=["id"]))
    finally:
        engine.dispose()
    print("Demo seed v1 applied; existing records preserved.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--confirm-demo-only", action="store_true")
    args = parser.parse_args()
    if args.reset and not args.confirm_demo_only:
        parser.error("Reset requires --confirm-demo-only")
    seed(reset=args.reset)

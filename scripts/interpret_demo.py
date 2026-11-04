"""Inspect pure meanings with a fixed campus clock and the actual maintained catalog."""
import json
import sys
from datetime import datetime
from pathlib import Path
from app.config import Settings
from app.db.connection import make_engine
from app.nlp.catalog import load_catalog
from app.nlp.interpreter import interpret

CASES = {
    'events': 'Any ML workshops for second years this week?',
    'rooms': 'Rooms in B block tomorrow from 2 to 3pm with projector',
    'faculty': 'Professor Anita Rao office hours tomorrow',
    'missing': 'Find rooms',
    'ambiguous': 'Professor Rao office hours tomorrow',
    'unsupported': 'Events and rooms tomorrow',
}
clock = datetime.fromisoformat('2026-11-04T10:00:00+05:30')
settings = Settings()
engine = make_engine(settings)
try:
    with engine.connect() as conn:
        catalog = load_catalog(conn)
    reports = {name: interpret(text, catalog=catalog, now=clock,
        campus_timezone=settings.campus_timezone).model_dump(mode='json')
        for name, text in CASES.items()}
    for name in ('events', 'rooms', 'faculty'):
        assert reports[name]['status']=='ready', f'{name} demo requires its campus seed: {reports[name]["message"]}'
    if '--write-fixtures' in sys.argv:
        target = Path('/workspace/contracts/interpretation-fixtures')
        target.mkdir(exist_ok=True)
        for name, report in reports.items():
            (target / (name + '.json')).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'synthetic_demo': True, 'reference_clock': clock.isoformat(),
        'questions': CASES, 'interpretations': reports}, indent=2))
finally:
    engine.dispose()

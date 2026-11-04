import json
from datetime import datetime
from app.nlp.event_baseline import parse_event_question, VERSION
query, provenance = parse_event_question('Any ML workshops for second years this week?',datetime.fromisoformat('2026-11-04T10:00:00+05:30'),'Asia/Kolkata')
print(json.dumps({'model_version':VERSION,'reference_clock':'2026-11-04T10:00:00+05:30','query':query.model_dump(mode='json'),'provenance':provenance},indent=2))

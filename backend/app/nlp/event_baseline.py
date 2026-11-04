"""Conservative Phase 2 grammar. No training, SQL, database access or dialogue state."""
import re
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from app.schemas.events import EventSearch

VERSION = 'events-rules-v1'

class UnsupportedQuestion(ValueError):
    pass


def parse_event_question(text, now, timezone, context=None):
    text = re.sub(r'[?!,.]', ' ', text.casefold())
    text = re.sub(r'\s+', ' ', text).strip()
    values, origins = {}, {}
    if re.search(r'\b(room|rooms|faculty|professor|placement|placements|book|reserve)\b', text):
        raise UnsupportedQuestion('This checkpoint supports event questions only.')

    def consume(pattern, field, value, flags=0):
        nonlocal text
        matches = list(re.finditer(pattern, text, flags))
        if not matches:
            return False
        if field in values or len(matches) > 1:
            raise UnsupportedQuestion('Use one value for each filter in this baseline.')
        values[field] = value(matches[0]) if callable(value) else value
        origins[field] = 'explicit_question'
        text = re.sub(pattern, ' ', text, flags=flags)
        return True

    domain = bool(re.search(r'\b(events?|workshops?|seminars?|hackathons?|lectures?)\b', text))
    if not domain:
        raise UnsupportedQuestion('Ask for events, workshops, seminars, hackathons or lectures.')
    for kind in ('workshop', 'seminar', 'hackathon', 'lecture'):
        consume(r'\b'+kind+r's?\b', 'event_type', kind)
    text = re.sub(r'\bevents?\b', ' ', text)
    for alias, canonical in [('aiml','aiml'), ('cse','cse')]:
        consume(r'\b'+alias+r'\b', 'department_id', canonical)
    for alias, canonical in [('machine learning|ml','machine_learning'), ('artificial intelligence|ai','artificial_intelligence'), ('web development','web_development')]:
        consume(r'\b(?:'+alias+r')\b', 'topic_id', canonical)
    for pattern, year in [(r'\b(?:first|1st)[ -]years?\b',1),(r'\b(?:second|2nd)[ -]years?\b',2),(r'\b(?:third|3rd)[ -]years?\b',3),(r'\b(?:fourth|4th)[ -]years?\b',4)]:
        consume(pattern, 'student_year', year)
    consume(r'\byear\s+([1-4])\b', 'student_year', lambda m:int(m[1]))
    consume(r'\bfree\b', 'max_cost_minor', 0)
    wants_eligible = bool(re.search(r'\b(?:for me|can i attend|eligible)\b', text))
    text = re.sub(r'\b(?:for me|can i attend|eligible)\b', ' ', text)
    local = now.astimezone(ZoneInfo(timezone))
    midnight = datetime.combine(local.date(), time.min, tzinfo=local.tzinfo)
    windows = {'today':(midnight, midnight+timedelta(days=1)), 'tomorrow':(midnight+timedelta(days=1),midnight+timedelta(days=2))}
    monday = midnight-timedelta(days=local.weekday())
    windows['this week'] = (monday, monday+timedelta(days=7))
    windows['next week'] = (monday+timedelta(days=7),monday+timedelta(days=14))
    for name, window in windows.items():
        consume(r'\b'+name+r'\b', 'window', window)
    for index, day in enumerate(('monday','tuesday','wednesday','thursday','friday','saturday','sunday')):
        start = midnight+timedelta(days=(index-local.weekday())%7)
        consume(r'\b'+day+r'\b', 'window', (start,start+timedelta(days=1)))
    def date_window(match):
        try:
            start = datetime.combine(datetime.strptime(match[0], '%Y-%m-%d').date(), time.min, tzinfo=local.tzinfo)
        except ValueError:
            raise UnsupportedQuestion('Use a valid YYYY-MM-DD date.') from None
        return start,start+timedelta(days=1)
    consume(r'\b\d{4}-\d{2}-\d{2}\b', 'window', date_window)
    remaining = re.sub(r'\b(any|show|find|list|what|which|are|is|there|happening|upcoming|the|on|in|for|please|only|a|an)\b', ' ', text)
    if remaining.strip():
        raise UnsupportedQuestion('This baseline could not interpret every constraint. Try “free ML workshops this week” or “events on YYYY-MM-DD”.')
    start,end = values.pop('window', (now, now+timedelta(days=30)))
    origins['interval'] = origins.pop('window','default')
    context = context or {}
    for field in ('student_year','department_id'):
        if field not in values and context.get(field) is not None:
            values[field] = context[field]
            origins[field] = context.get(field+'_origin','profile')
    values['eligible_only'] = wants_eligible or origins.get('student_year') == 'explicit_question' or origins.get('department_id') == 'explicit_question'
    return EventSearch(from_at=start,to_at=end,limit=20,**values), origins

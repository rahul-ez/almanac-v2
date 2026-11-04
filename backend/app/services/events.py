"""Typed event semantics shared by HTTP, local CLI and the rule baseline."""
import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from pydantic import ValidationError
from sqlalchemy import select, insert, update, and_, or_, case, false
from app.api.errors import ApiError
from app.db.models import Event, EventAudit, Topic, Department
from app.schemas.events import EventData, EventView, EventList, EventSearch


def eligibility(rules, year, department):
    if rules['mode'] == 'unknown':
        return 'unknown', 'Eligibility has not been supplied'
    if rules['mode'] == 'unrestricted':
        return 'eligible', 'Explicitly open to all students'
    missing = False
    for allowed, actual in ((rules.get('years'), year), (rules.get('departments'), department)):
        if allowed is not None:
            if actual is None:
                missing = True
            elif actual not in allowed:
                return 'ineligible', 'Student context does not satisfy the published restrictions'
    if missing:
        return 'unknown', 'Student context is incomplete for these restrictions'
    return 'eligible', 'Student context satisfies the published restrictions'


def eligibility_expression(year, department):
    rules = Event.eligibility_rules
    mismatch, missing = [], []
    for key, actual in (('years', year), ('departments', department)):
        present = rules[key].astext.is_not(None)
        if actual is None:
            missing.append(present)
        else:
            mismatch.append(and_(present, ~rules[key].contains([actual])))
    return case((rules['mode'].astext == 'unrestricted', 'eligible'),
                (rules['mode'].astext == 'unknown', 'unknown'),
                (or_(*mismatch, false()), 'ineligible'),
                (or_(*missing, false()), 'unknown'), else_='eligible')


def view(row, now, year=None, department=None):
    result, reason = eligibility(row['eligibility_rules'], year, department)
    deadline = row['registration_deadline']
    registration = 'closed' if row['status'] in {'cancelled', 'archived'} or row['ends_at'] <= now else (
        'unknown' if deadline is None else ('open' if now < deadline else 'closed'))
    return EventView(**dict(row), eligibility=result, eligibility_reason=reason, registration_status=registration)


def references(conn, values):
    if conn.execute(select(Topic.id).where(Topic.id == values['topic_id'])).first() is None:
        raise ApiError(422, 'validation_error', 'Unknown event topic', [{'field':'body.topic_id','message':'Choose a reference topic'}])
    departments = values['eligibility_rules'].get('departments') or []
    found = set(conn.execute(select(Department.id).where(Department.id.in_(departments))).scalars())
    if found != set(departments):
        raise ApiError(422, 'validation_error', 'Unknown eligibility department')


def db_values(model):
    values = model.model_dump()
    values['source_url'] = str(model.source_url) if model.source_url else None
    return values


def audit(conn, event_id, actor_id, action, version, now):
    conn.execute(insert(EventAudit).values(id=str(uuid4()), event_id=event_id, actor_id=actor_id,
                                         action=action, version=version, occurred_at=now))


def create_event(conn, payload, actor_id, now):
    values = db_values(payload)
    if values['status'] == 'archived':
        raise ApiError(422, 'validation_error', 'Create an active or draft event before archiving')
    references(conn, values)
    row = conn.execute(insert(Event).values(**values, id=str(uuid4()), version=1, updated_at=now)
                       .returning(*Event.__table__.c)).mappings().one()
    audit(conn, row['id'], actor_id, 'create', 1, now)
    return view(row, now)


def get_event(conn, event_id, now, admin=False, year=None, department=None, lock=False):
    query = select(Event.__table__).where(Event.id == event_id)
    if not admin:
        query = query.where(Event.status.in_(['published', 'cancelled']))
    if lock:
        query = query.with_for_update()
    row = conn.execute(query).mappings().first()
    if row is None:
        raise ApiError(404, 'not_found', 'Event not found')
    return view(row, now, year, department)


def patch_event(conn, event_id, payload, actor_id, now):
    existing = get_event(conn, event_id, now, admin=True, lock=True)
    if existing.version != payload.version:
        raise ApiError(409, 'version_conflict', 'Event changed; reload it before editing')
    if existing.status == 'archived':
        raise ApiError(409, 'event_archived', 'Archived events cannot be edited')
    merged = {key:getattr(existing, key) for key in EventData.model_fields}
    merged.update(payload.model_dump(exclude_unset=True, exclude={'version'}))
    try:
        data = EventData.model_validate(merged)
    except ValidationError:
        raise ApiError(422, 'validation_error', 'Invalid event fields or time interval') from None
    values = db_values(data)
    references(conn, values)
    row = conn.execute(update(Event).where(Event.id == event_id).values(**values, version=existing.version+1, updated_at=now)
                       .returning(*Event.__table__.c)).mappings().one()
    audit(conn, event_id, actor_id, 'archive' if data.status == 'archived' else 'update', row['version'], now)
    return view(row, now)


def search_events(conn, filters: EventSearch, now, year=None, department=None, admin=False):
    year = filters.student_year if filters.student_year is not None else year
    department = filters.department_id if filters.department_id is not None else department
    if filters.topic_id is not None and conn.execute(select(Topic.id).where(Topic.id == filters.topic_id)).first() is None:
        raise ApiError(422, 'validation_error', 'Unknown topic')
    if department is not None and conn.execute(select(Department.id).where(Department.id == department)).first() is None:
        raise ApiError(422, 'validation_error', 'Unknown department')
    # Stable calendar-day default so a continuation cursor does not drift with each request.
    start = filters.from_at or now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end = filters.to_at or start + timedelta(days=366)
    conditions = [Event.starts_at < end, Event.ends_at > start]
    if filters.from_at is None:
        conditions.append(Event.ends_at > now)
    conditions.append(Event.status != 'archived' if admin else Event.status == 'published')
    for field, value in ((Event.event_type, filters.event_type), (Event.topic_id, filters.topic_id), (Event.venue, filters.venue)):
        if value is not None:
            conditions.append(field == value)
    if filters.q is not None:
        conditions.append(Event.title.icontains(filters.q, autoescape=True))
    if filters.max_cost_minor is not None:
        conditions.append(Event.cost_minor <= filters.max_cost_minor)
    warnings = []
    if filters.eligible_only:
        expression = eligibility_expression(year, department)
        if conn.execute(select(Event.id).where(*conditions, expression == 'unknown').limit(1)).first():
            warnings.append('Some matching events have unknown eligibility and were excluded from eligible-only results.')
        conditions.append(expression == 'eligible')
    fingerprint = hashlib.sha256(json.dumps({**filters.model_dump(mode='json', exclude={'cursor'}),
        'start':start.isoformat(), 'end':end.isoformat(), 'year':year, 'department':department, 'admin':admin}, sort_keys=True).encode()).hexdigest()
    if filters.cursor:
        try:
            stamp, record_id, prior = json.loads(base64.urlsafe_b64decode(filters.cursor.encode()))
            after = datetime.fromisoformat(stamp)
            if prior != fingerprint or after.tzinfo is None or not isinstance(record_id, str):
                raise ValueError()
        except (ValueError, TypeError, UnicodeError):
            raise ApiError(422, 'invalid_cursor', 'Cursor does not match this query') from None
        conditions.append(or_(Event.starts_at > after, and_(Event.starts_at == after, Event.id > record_id)))
    rows = list(conn.execute(select(Event.__table__).where(*conditions).order_by(Event.starts_at, Event.id).limit(filters.limit+1)).mappings())
    cursor = None
    if len(rows) > filters.limit:
        last = rows[filters.limit-1]
        cursor = base64.urlsafe_b64encode(json.dumps([last['starts_at'].isoformat(), last['id'], fingerprint]).encode()).decode()
    return EventList(items=[view(row, now, year, department) for row in rows[:filters.limit]], next_cursor=cursor, warnings=warnings)

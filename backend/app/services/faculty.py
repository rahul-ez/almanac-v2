import base64
import hashlib
import json
import re
import unicodedata
from datetime import date,datetime,timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo
from pydantic import ValidationError
from sqlalchemy import select,insert,update,or_,func
from sqlalchemy.exc import IntegrityError
from app.api.errors import ApiError
from app.db.models import Department
from app.db.faculty_models import Faculty,FacultyAlias,OfficeHour,OfficeHourException,FacultyAudit
from app.schemas.faculty import (FacultyData,FacultyView,AliasData,AliasView,OfficeHourData,OfficeHourView,
    OfficeExceptionData,OfficeExceptionView,FacultyResolution,OfficeHoursResult,OfficeHourSlot)
from app.schemas.rooms import RequestedInterval
from app.services.rooms import row,values,cursor_state,next_cursor
from app.services.faculty_time import effective_office_slots,check_office_conflicts

RESOURCES={'faculty':(Faculty,FacultyData,FacultyView),'aliases':(FacultyAlias,AliasData,AliasView),
           'office-hours':(OfficeHour,OfficeHourData,OfficeHourView),'office-hour-exceptions':(OfficeHourException,OfficeExceptionData,OfficeExceptionView)}


def normalize_name(value):
    result=' '.join(unicodedata.normalize('NFKC',value).casefold().split())
    result=re.sub(r'^(?:(?:professor|prof|dr)\.?\s+)+','',result)
    if not 1 <= len(result) <= 200:
        raise ApiError(422,'validation_error','Name cannot be normalized safely')
    return result


def matching_query(key,department_id=None):
    alias_ids=select(FacultyAlias.canonical_id).where(FacultyAlias.normalized_alias == key,FacultyAlias.status == 'active')
    query=select(Faculty.__table__).where(Faculty.status == 'active',or_(Faculty.normalized_name == key,Faculty.id.in_(alias_ids)))
    return query.where(Faculty.department_id == department_id) if department_id else query


def validate_department(conn,department):
    if department and not conn.execute(select(Department.id).where(Department.id == department)).first():
        raise ApiError(422,'validation_error','Unknown department')


def faculty_view(conn,record):
    data={key:record[key] for key in FacultyData.model_fields}
    aliases=list(conn.execute(select(FacultyAlias.alias).where(FacultyAlias.canonical_id == record['id'],FacultyAlias.status == 'active').order_by(FacultyAlias.alias)).scalars())
    return FacultyView(**data,id=record['id'],version=record['version'],updated_at=record['updated_at'],timezone=record['timezone'],aliases=aliases)


def detail(conn,resource,record_id,public=False):
    model,_,schema=RESOURCES[resource];record=row(conn,model,record_id)
    if public and record['status'] == 'archived': raise ApiError(404,'not_found','Faculty not found')
    if model is Faculty: return faculty_view(conn,record)
    if model is FacultyAlias:
        count=conn.execute(select(func.count()).select_from(matching_query(record['normalized_alias']).subquery())).scalar_one()
        data={key:record[key] for key in AliasData.model_fields}
        return AliasView(**data,id=record['id'],version=record['version'],updated_at=record['updated_at'],matching_faculty_count=count)
    return schema.model_validate(record)


def lock_faculty(conn,ids,share=False):
    found=list(conn.execute(select(Faculty.__table__).where(Faculty.id.in_(sorted(set(ids)))).order_by(Faculty.id).with_for_update(read=share)).mappings())
    if len(found) != len(set(ids)): raise ApiError(422,'validation_error','Unknown faculty member')
    return {r['id']:dict(r) for r in found}


def exceptions_for(conn,rule_id):
    return [dict(r) for r in conn.execute(select(OfficeHourException.__table__).where(OfficeHourException.office_hour_id == rule_id)).mappings()]


def validate_plan(conn,faculty,rule,exceptions):
    proposed=effective_office_slots(rule,exceptions);existing=[]
    for other in conn.execute(select(OfficeHour.__table__).where(OfficeHour.faculty_id == faculty['id'],OfficeHour.id != rule['id'],OfficeHour.status == 'active')).mappings():
        existing.extend(effective_office_slots(other,exceptions_for(conn,other['id'])))
    check_office_conflicts(proposed,existing)


def audit(conn,faculty_id,resource,record_id,actor,action,version,now):
    conn.execute(insert(FacultyAudit).values(id=str(uuid4()),faculty_id=faculty_id,resource=resource,record_id=record_id,
        actor_id=actor,action=action,version=version,occurred_at=now))


def write(conn,resource,payload,actor,now,campus_timezone,record_id=None):
    model,schema,_=RESOURCES[resource];existing=None
    if record_id:
        if model is OfficeHourException:
            before=row(conn,model,record_id);row(conn,OfficeHour,before['office_hour_id'],lock=True)
        elif model is FacultyAlias:
            before=row(conn,model,record_id);lock_faculty(conn,[before['canonical_id']])
        existing=row(conn,model,record_id,lock=True)
        if existing['version'] != payload.version: raise ApiError(409,'version_conflict','Record changed; reload before editing')
        if existing['status'] == 'archived': raise ApiError(409,'record_archived','Archived records cannot be edited')
        merged={key:existing[key] for key in schema.model_fields}
        merged.update(payload.model_dump(exclude_unset=True,exclude={'version'}))
        try: data=values(schema.model_validate(merged))
        except ValidationError: raise ApiError(422,'validation_error','Invalid faculty or office-hour fields') from None
    else:
        data=values(payload);record_id=str(uuid4())
        if data['status'] == 'archived': raise ApiError(422,'validation_error','Create a record before archiving it')
    version=existing['version']+1 if existing else 1
    parent=None;alias_faculty=None
    if model is Faculty:
        validate_department(conn,data['department_id']);data['normalized_name']=normalize_name(data['name'])
        data['timezone']=existing['timezone'] if existing else campus_timezone;faculty_id=record_id
    elif model is FacultyAlias:
        if existing and data['canonical_id'] != existing['canonical_id']:
            raise ApiError(422,'validation_error','Archive and recreate an alias to change its target')
        alias_faculty=lock_faculty(conn,[data['canonical_id']])[data['canonical_id']]
        if alias_faculty['status'] == 'archived' and data['status'] == 'active': raise ApiError(409,'faculty_archived','Faculty is archived')
        data['normalized_alias']=normalize_name(data['alias']);faculty_id=data['canonical_id']
    elif model is OfficeHour:
        ids=[data['faculty_id']]+([existing['faculty_id']] if existing else [])
        faculty=lock_faculty(conn,ids)[data['faculty_id']]
        if faculty['status'] == 'archived' and data['status'] == 'active': raise ApiError(409,'faculty_archived','Faculty is archived')
        data['timezone']=data['timezone'] or faculty['timezone']
        if data['timezone'] != faculty['timezone']: raise ApiError(422,'validation_error','Rule timezone must match its faculty campus timezone')
        validate_plan(conn,faculty,dict(data,id=record_id),exceptions_for(conn,record_id) if existing else [])
        faculty_id=data['faculty_id']
    else:
        if existing and data['office_hour_id'] != existing['office_hour_id']: raise ApiError(422,'validation_error','An exception cannot change its parent rule')
        parent=row(conn,OfficeHour,data['office_hour_id'],lock=True)
        faculty=lock_faculty(conn,[parent['faculty_id']])[parent['faculty_id']]
        if faculty['status'] == 'archived' and data['status'] == 'active': raise ApiError(409,'faculty_archived','Faculty is archived')
        current=[e for e in exceptions_for(conn,parent['id']) if e['id'] != record_id]
        validate_plan(conn,faculty,parent,current+[dict(data,id=record_id)]);faculty_id=parent['faculty_id']
    try:
        with conn.begin_nested():
            if existing: conn.execute(update(model).where(model.id == record_id).values(**data,version=version,updated_at=now))
            else: conn.execute(insert(model).values(**data,id=record_id,version=version,updated_at=now))
    except IntegrityError:
        raise ApiError(409,'record_conflict','This target alias or active occurrence exception already exists') from None
    if parent:
        conn.execute(update(OfficeHour).where(OfficeHour.id == parent['id']).values(version=parent['version']+1,updated_at=now))
        audit(conn,faculty_id,'office-hours',parent['id'],actor,'exception_change',parent['version']+1,now)
    if alias_faculty:
        conn.execute(update(Faculty).where(Faculty.id == faculty_id).values(version=alias_faculty['version']+1,updated_at=now))
        audit(conn,faculty_id,'faculty',faculty_id,actor,'alias_change',alias_faculty['version']+1,now)
    audit(conn,faculty_id,resource,record_id,actor,'archive' if data['status'] == 'archived' else 'update' if existing else 'create',version,now)
    return detail(conn,resource,record_id)


def inventory(conn,resource,query,public=False):
    model,_,_=RESOURCES[resource];after,signature=cursor_state(query,resource+(':public' if public else ':admin'))
    conditions=[model.status != 'archived']
    if after: conditions.append(model.id > after)
    if query.department_id:
        validate_department(conn,query.department_id)
        if model is Faculty: conditions.append(Faculty.department_id == query.department_id)
        else:
            ids=select(Faculty.id).where(Faculty.department_id == query.department_id)
            field=OfficeHour.faculty_id if model is OfficeHour else FacultyAlias.canonical_id if model is FacultyAlias else None
            conditions.append(field.in_(ids) if field is not None else OfficeHourException.office_hour_id.in_(select(OfficeHour.id).where(OfficeHour.faculty_id.in_(ids))))
    if query.faculty_id:
        if model is Faculty: conditions.append(model.id == query.faculty_id)
        elif model is FacultyAlias: conditions.append(model.canonical_id == query.faculty_id)
        elif model is OfficeHour: conditions.append(model.faculty_id == query.faculty_id)
        else: conditions.append(model.office_hour_id.in_(select(OfficeHour.id).where(OfficeHour.faculty_id == query.faculty_id)))
    if query.search:
        field=Faculty.name if model is Faculty else FacultyAlias.alias if model is FacultyAlias else OfficeHour.location if model is OfficeHour else OfficeHourException.note
        conditions.append(field.icontains(query.search,autoescape=True))
    records=list(conn.execute(select(model.__table__).where(*conditions).order_by(model.id).limit(query.limit+1)).mappings())
    more=len(records)>query.limit;records=records[:query.limit]
    return {'items':[detail(conn,resource,r['id']) for r in records],'next_cursor':next_cursor(records[-1],signature) if more else None}


def resolve_faculty(conn,query):
    validate_department(conn,query.department_id)
    key=normalize_name(query.name)
    records=list(conn.execute(matching_query(key,query.department_id).order_by(Faculty.id).limit(21).with_for_update(read=True)).mappings())
    count=len(records);warnings=[]
    if count>1: warnings.append('Name is ambiguous. Select a canonical faculty ID before querying office hours.')
    if count>20: warnings.append('Candidates truncated to 20; narrow the name or department before selecting.')
    return FacultyResolution(status='resolved' if count==1 else 'clarification_required' if count>1 else 'no_results',
        candidates=[faculty_view(conn,r) for r in records[:20]],warnings=warnings)


def office_hours(conn,faculty_id,query,now):
    if query.from_at < now or query.to_at > now+timedelta(days=30): raise ApiError(422,'query_horizon','Office-hour queries must lie within the next 30 days')
    faculty=row(conn,Faculty,faculty_id,lock='share')
    if faculty['status'] == 'archived': raise ApiError(404,'not_found','Faculty not found')
    signature=hashlib.sha256(json.dumps({'faculty_id':faculty_id,**query.model_dump(mode='json',exclude={'cursor'})},sort_keys=True).encode()).hexdigest()
    after=None
    if query.cursor:
        try:
            after,prior=json.loads(base64.urlsafe_b64decode(query.cursor.encode()))
            if prior != signature or not isinstance(after,list) or len(after)!=3 or not all(isinstance(x,str) for x in after): raise ValueError()
            if not 1 <= len(after[1]) <= 80: raise ValueError()
            date.fromisoformat(after[2])
            instant=datetime.fromisoformat(after[0])
            if instant.tzinfo is None: raise ValueError()
            after=(instant,after[1],after[2])
        except (ValueError,TypeError,UnicodeError): raise ApiError(422,'invalid_cursor','Cursor does not match this office-hour query') from None
    slots=[]
    for rule in conn.execute(select(OfficeHour.__table__).where(OfficeHour.faculty_id == faculty_id,OfficeHour.status == 'active')).mappings():
        for slot in effective_office_slots(rule,exceptions_for(conn,rule['id'])):
            if slot['starts_at'] >= query.to_at or slot['ends_at'] <= query.from_at: continue
            exception=slot['exception'];source=exception or rule
            slots.append(OfficeHourSlot(faculty_id=faculty_id,office_hour_id=rule['id'],occurrence_date=slot['occurrence_date'],
                starts_at=slot['starts_at'],ends_at=slot['ends_at'],location=rule['location'],timezone=rule['timezone'],
                exception_id=exception['id'] if exception else None,exception_note=exception['note'] if exception else None,
                source_label=source['source_label'],source_url=source['source_url'],record_updated_at=max(rule['updated_at'],faculty['updated_at'],source['updated_at'])))
    key=lambda slot:(slot.starts_at,slot.office_hour_id,slot.occurrence_date.isoformat())
    slots.sort(key=key)
    if after: slots=[slot for slot in slots if key(slot)>after]
    more=len(slots)>query.limit;page=slots[:query.limit];cursor=None
    if more:
        last=page[-1];cursor=base64.urlsafe_b64encode(json.dumps([[last.starts_at.isoformat(),last.office_hour_id,last.occurrence_date.isoformat()],signature]).encode()).decode()
    zone=ZoneInfo(faculty['timezone']);start_day=query.from_at.astimezone(zone).date();end_day=(query.to_at-timedelta(microseconds=1)).astimezone(zone).date()
    complete=bool(faculty['office_hours_complete'] and faculty['office_hours_coverage_start'] is not None and start_day >= faculty['office_hours_coverage_start'] and end_day <= faculty['office_hours_coverage_end'])
    warnings=['Only published office hours and recorded exceptions are used; class timetables do not establish meeting availability.']
    if not complete: warnings.append('Published office-hour coverage is incomplete or unavailable for this window.')
    if more: warnings.append('This is a result page; continue with next_cursor for more slots.')
    return OfficeHoursResult(status='answered' if page else 'no_results' if complete else 'information_unavailable',faculty=faculty_view(conn,faculty),items=page,
        requested_interval=RequestedInterval(start=query.from_at,end=query.to_at),data_coverage='complete' if complete else 'partial' if page else 'unknown',next_cursor=cursor,warnings=warnings)

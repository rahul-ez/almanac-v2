"""Pure bounded office-hour expansion; no class-timetable inference."""
from datetime import datetime,time,timedelta,timezone
from zoneinfo import ZoneInfo
from app.api.errors import ApiError
from app.schemas.rooms import minutes
from app.services.room_time import local_instant,ensure_no_conflicts


def base_office_slots(rule):
    first=rule['effective_from']+timedelta(days=(rule['weekday']-rule['effective_from'].weekday())%7)
    end=rule['effective_until'];zone=ZoneInfo(rule['timezone'])
    if first > end or not 0 <= (end-rule['effective_from']).days <= 366:
        raise ApiError(422,'validation_error','Office hours need a matching weekday within bounded effective dates')
    result=[]
    for offset in range(0,(end-first).days+1,7):
        day=first+timedelta(days=offset);midnight=datetime.combine(day,time.min)
        result.append((day,local_instant(midnight+timedelta(minutes=minutes(rule['start_time'])),zone),
                       local_instant(midnight+timedelta(minutes=minutes(rule['end_time'])),zone)))
    return result


def effective_office_slots(rule,exceptions):
    base=base_office_slots(rule);dates={day for day,_,_ in base};active={}
    zone=ZoneInfo(rule['timezone'])
    for exception in exceptions:
        if exception['status'] != 'active': continue
        day=exception['occurrence_date']
        if day not in dates:
            raise ApiError(422,'validation_error','Exception must target an original local office-hour date')
        if day in active:
            raise ApiError(409,'exception_conflict','An active exception already exists for this occurrence')
        if exception['action'] == 'replace' and abs((exception['replacement_start'].astimezone(zone).date()-day).days)>7:
            raise ApiError(422,'validation_error','Replacement must be within seven local dates of its original occurrence')
        active[day]=exception
    if rule['status'] != 'active': return []
    result=[]
    for day,start,end in base:
        exception=active.get(day)
        if exception:
            if exception['action'] == 'cancel': continue
            start=exception['replacement_start'].astimezone(timezone.utc)
            end=exception['replacement_end'].astimezone(timezone.utc)
        result.append({'occurrence_date':day,'starts_at':start,'ends_at':end,'exception':exception})
    return result


def check_office_conflicts(proposed,existing):
    try:
        ensure_no_conflicts([(s['starts_at'],s['ends_at']) for s in proposed],[(s['starts_at'],s['ends_at']) for s in existing])
    except ApiError as exc:
        if exc.status != 409: raise
        raise ApiError(409,'office_hour_conflict','Published office-hour intervals would overlap for this faculty member') from None

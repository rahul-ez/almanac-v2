"""Pure, bounded scheduling calculations. No HTTP, SQL or application clock access."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from app.api.errors import ApiError
from app.schemas.rooms import minutes

UTC = timezone.utc

def local_instant(naive, zone):
    """Reject nonexistent/ambiguous wall times rather than silently guessing a fold."""
    candidates = {naive.replace(tzinfo=zone,fold=fold).astimezone(UTC) for fold in (0,1)
                  if naive.replace(tzinfo=zone,fold=fold).astimezone(UTC).astimezone(zone).replace(tzinfo=None) == naive}
    if len(candidates) != 1:
        raise ApiError(422,'ambiguous_schedule_time','Schedule contains an ambiguous or nonexistent local time')
    return candidates.pop()


def base_occurrences(booking, zone_name):
    start,end = booking['starts_at'],booking['ends_at']
    zone = ZoneInfo(zone_name)
    first = start.astimezone(zone)
    if booking['recurrence'] == 'none':
        return [(first.date(),start.astimezone(UTC),end.astimezone(UTC))]
    until = booking['recurrence_until']
    if until is None or not 0 <= (until-first.date()).days <= 366:
        raise ApiError(422,'validation_error','Weekly recurrence must end within 366 days of its first local date')
    naive_start = first.replace(tzinfo=None)
    naive_end = end.astimezone(zone).replace(tzinfo=None)
    result=[]
    for offset in range(0,(until-first.date()).days+1,7):
        day = first.date()+timedelta(days=offset)
        a = local_instant(naive_start+timedelta(days=offset),zone)
        b = local_instant(naive_end+timedelta(days=offset),zone)
        if b <= a:
            raise ApiError(422,'validation_error','Invalid recurring occurrence')
        result.append((day,a,b))
    return result


def effective_occurrences(booking, exceptions, zone_name):
    base = base_occurrences(booking,zone_name)
    valid_dates = {day for day,_,_ in base}
    active = {}
    for exception in exceptions:
        if exception['status'] != 'active':
            continue
        day = exception['occurrence_date']
        if day not in valid_dates:
            raise ApiError(422,'validation_error','Exception date must name an original booking occurrence')
        if day in active:
            raise ApiError(409,'exception_conflict','An active exception already exists for this occurrence')
        if exception['action'] == 'replace':
            moved = exception['replacement_start'].astimezone(ZoneInfo(zone_name)).date()
            if abs((moved-day).days) > 7:
                raise ApiError(422,'validation_error','Replacement must be within seven local dates of its original occurrence')
        active[day]=exception
    if booking['status'] != 'active':
        return []
    result=[]
    for day,start,end in base:
        exception = active.get(day)
        if exception:
            if exception['action'] == 'cancel':
                continue
            start,end = exception['replacement_start'].astimezone(UTC),exception['replacement_end'].astimezone(UTC)
        result.append((start,end))
    return sorted(result)


def overlaps(a,b):
    return a[0] < b[1] and a[1] > b[0]


def ensure_no_conflicts(candidate, existing):
    ordered = sorted(candidate)
    for prior,current in zip(ordered,ordered[1:]):
        if overlaps(prior,current):
            raise ApiError(409,'booking_conflict','Occurrences of this booking overlap each other')
    occupied = sorted(existing)
    i=0
    for slot in ordered:
        while i < len(occupied) and occupied[i][1] <= slot[0]:
            i+=1
        if i < len(occupied) and overlaps(slot,occupied[i]):
            raise ApiError(409,'booking_conflict','Room has an overlapping scheduled booking')


def within_opening_hours(room,start,end):
    zone = ZoneInfo(room['timezone'])
    first,last = start.astimezone(zone).date(),end.astimezone(zone).date()
    intervals=[]
    for offset in range((last-first).days+1):
        day = first+timedelta(days=offset)
        for entry in room['opening_hours']:
            if entry['weekday'] == day.weekday():
                midnight = datetime.combine(day,time.min)
                intervals.append((local_instant(midnight+timedelta(minutes=minutes(entry['start'])),zone),
                                  local_instant(midnight+timedelta(minutes=minutes(entry['end'])),zone)))
    covered = start.astimezone(UTC)
    for a,b in sorted(intervals):
        if b <= covered:
            continue
        if a > covered:
            return False
        covered=max(covered,b)
        if covered >= end.astimezone(UTC):
            return True
    return False

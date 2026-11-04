"""Allowlisted typed execution. No text, SQL or uncertain meanings are executed."""
from app.api.errors import ApiError
from app.schemas.contracts import EventCard,RoomCard,OfficeHoursCard,Interval
from app.services.events import search_events
from app.services.rooms import available_rooms
from app.services.faculty import office_hours


def execute_interpretation(conn,report,catalog,now):
    if report.status!='ready' or report.execution is None:
        raise ApiError(422,'unsafe_interpretation','An uncertain interpretation cannot execute')
    labels={(entry.kind,entry.id):entry.label for entry in catalog.entries}
    cards=[];warnings=list(report.warnings);coverage='complete'
    execution=report.execution
    if execution.kind=='event':
        found=search_events(conn,execution.query,now)
        for item in found.items:
            cards.append(EventCard(kind='event',record_id=item.id,title=item.title,source_label=item.source_label,source_url=item.source_url,
                record_updated_at=item.updated_at,interval=Interval(start=item.starts_at,end=item.ends_at),venue=item.venue,topic=item.topic_id,
                event_type=item.event_type,cost_minor=item.cost_minor,currency=item.currency,eligibility=item.eligibility,eligibility_rules=item.eligibility_rules,
                registration_deadline=item.registration_deadline,cancelled=False,registration_status=item.registration_status))
        warnings.extend(found.warnings)
        if found.next_cursor: warnings.append('Results truncated to 20 events; narrow the question. Chat pagination is not implemented.')
        status='answered' if cards else 'information_unavailable' if found.warnings else 'no_results'
        message=f'Found {len(cards)} matching event(s).' if cards else 'Eligibility is unknown for matching events.' if found.warnings else 'No matching published events.'
    elif execution.kind=='room':
        found=available_rooms(conn,execution.query,now,room_id=execution.room_id)
        if execution.room_id:
            available=[found] if found.availability=='available' else []
            status='answered' if available else 'information_unavailable' if found.availability=='unknown' else 'no_results'
            coverage='unknown' if found.availability=='unknown' else 'complete'
            warnings.append('Room '+found.room.code+': '+', '.join(found.reasons)+'.')
            warnings.append('Availability is based on maintained schedules, not physical occupancy.')
        else:
            available=found.items;status=found.status;coverage=found.data_coverage;warnings.extend(found.warnings)
            if found.next_cursor:
                warnings.append('Only the first 100 matching room candidates were checked; narrow the filters for a complete search.')
                coverage='partial'
                if not available: status='information_unavailable'
        for item in available[:20]:
            room=item.room
            cards.append(RoomCard(kind='room_availability',record_id=room.id,title=room.code,source_label=room.source_label,source_url=room.source_url,
                record_updated_at=room.updated_at,building=labels.get(('building',room.building_id),room.building_id),capacity=room.capacity,
                facilities=[labels.get(('facility',key),key) for key in room.facility_ids],requested_interval=item.requested_interval.model_dump(),
                schedule_coverage='complete',availability_basis='scheduled_bookings'))
        if len(available)>20: warnings.append('Results truncated to 20 available rooms; narrow the filters. Chat pagination is not implemented.')
        message=f'Found {len(cards)} room(s) with no scheduled conflict.' if cards else 'Room schedule information is incomplete.' if status=='information_unavailable' else 'No confirmed scheduled room availability for this interval and filters.'
    elif execution.kind=='office_hours':
        found=office_hours(conn,execution.faculty_id,execution.query,now);coverage=found.data_coverage;status=found.status;warnings.extend(found.warnings)
        for item in found.items:
            cards.append(OfficeHoursCard(kind='office_hours',record_id=found.faculty.id,title=found.faculty.name+' office hours',source_label=item.source_label,
                source_url=item.source_url,record_updated_at=item.record_updated_at,faculty_id=found.faculty.id,faculty_name=found.faculty.name,location=item.location,
                interval=Interval(start=item.starts_at,end=item.ends_at),exception=item.exception_note))
        if found.next_cursor: warnings.append('Office-hour results truncated to 20 slots; narrow the date window. Chat pagination is not implemented.')
        message=f'Found {len(cards)} published office-hour slot(s).' if cards else 'Published office-hour coverage is incomplete or unavailable.' if status=='information_unavailable' else 'No matching published office-hour slots in the covered window.'
    else:
        raise ApiError(422,'unsafe_interpretation','Unsupported typed execution kind')
    return cards,status,message,coverage,warnings

import hashlib
import json
from uuid import uuid4
from sqlalchemy import select, insert, text
from app.api.errors import ApiError
from app.db.models import Conversation, AssistantTurn
from app.nlp.event_baseline import parse_event_question, UnsupportedQuestion, VERSION
from app.repositories.profiles import read_profile
from app.services.events import search_events
from app.schemas.contracts import AssistantResponse, EventCard, Meaning, Filters, Interval, ContextValue


def answer_event_question(conn, payload, user_id, request_id, now, campus_timezone):
    canonical = payload.model_dump(mode='json')
    fingerprint = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
    key = user_id+':'+payload.client_request_id
    conn.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))'), {'key':key})
    prior = conn.execute(select(AssistantTurn.__table__).where(AssistantTurn.user_id == user_id,
        AssistantTurn.client_request_id == payload.client_request_id)).mappings().first()
    if prior:
        if prior['payload_hash'] != fingerprint:
            raise ApiError(409, 'request_conflict', 'Request ID was already used for a different payload')
        return AssistantResponse.model_validate(prior['response'])
    conversation_id = payload.conversation_id
    if conversation_id:
        owned = conn.execute(select(Conversation.id).where(Conversation.id == conversation_id,
            Conversation.owner_id == user_id).with_for_update()).first()
        if not owned:
            raise ApiError(404, 'not_found', 'Conversation not found')
    else:
        conversation_id = str(uuid4())
        conn.execute(insert(Conversation).values(id=conversation_id, owner_id=user_id, created_at=now))
    turn_id = str(uuid4())
    warnings = ['Phase 2 rule baseline; only documented event question patterns are supported.']
    cards, meaning, applied = [], None, []
    status, intent, coverage = 'unsupported', None, 'not_applicable'
    message = 'Follow-ups and clarification replies are not supported yet. Start a new event question.'
    if payload.conversation_id is None and payload.clarification is None:
        profile = read_profile(conn, user_id)
        overrides = payload.context_overrides.model_dump(exclude_unset=True)
        context = {'student_year':profile['year'], 'department_id':profile['department_id']}
        for key, field in (('year','student_year'),('department_id','department_id')):
            if key in overrides:
                context[field] = overrides[key]
                context[field+'_origin'] = 'override'
        try:
            query, origins = parse_event_question(payload.text, now, campus_timezone, context)
            found = search_events(conn, query, now)
            interval = Interval(start=query.from_at, end=query.to_at)
            meaning = Meaning(intent='find_events', filters=Filters(event_type=query.event_type, topic=query.topic_id,
                student_year=query.student_year, department_id=query.department_id, interval=interval,
                max_cost_minor=query.max_cost_minor, eligible_only=query.eligible_only))
            for field, value in (('event_type',query.event_type),('topic_id',query.topic_id),('student_year',query.student_year),
                                 ('department_id',query.department_id),('max_cost_minor',query.max_cost_minor)):
                if value is not None:
                    applied.append(ContextValue(field=field,value=value,origin=origins.get(field,'default')))
            applied.append(ContextValue(field='interval',value=[query.from_at.isoformat(),query.to_at.isoformat()],origin=origins['interval']))
            for item in found.items:
                cards.append(EventCard(kind='event',record_id=item.id,title=item.title,source_label=item.source_label,
                    source_url=item.source_url,record_updated_at=item.updated_at,interval=Interval(start=item.starts_at,end=item.ends_at),
                    venue=item.venue,topic=item.topic_id,event_type=item.event_type,cost_minor=item.cost_minor,currency=item.currency,
                    eligibility=item.eligibility,eligibility_rules=item.eligibility_rules,registration_deadline=item.registration_deadline,
                    cancelled=False, registration_status=item.registration_status))
            warnings.extend(found.warnings)
            if found.next_cursor:
                warnings.append('Results truncated to 20 events; narrow the question to see more. Chat pagination is not implemented.')
            intent, coverage = 'find_events', 'complete'
            status = 'answered' if cards else ('information_unavailable' if found.warnings else 'no_results')
            message = f'Found {len(cards)} matching event(s).' if cards else ('Eligibility is unknown for matching events.' if found.warnings else 'No matching published events.')
        except UnsupportedQuestion as exc:
            message = str(exc)
    result = AssistantResponse(conversation_id=conversation_id,turn_id=turn_id,request_id=request_id,status=status,intent=intent,
        message=message,interpreted_query=meaning,applied_context=applied,results=cards,clarification=None,answered_at=now,
        campus_timezone=campus_timezone,warnings=warnings,data_coverage=coverage,next_cursor=None)
    conn.execute(insert(AssistantTurn).values(id=turn_id, conversation_id=conversation_id,user_id=user_id,
        client_request_id=payload.client_request_id,payload_hash=fingerprint,question=payload.text,response=result.model_dump(mode='json'),
        created_at=now,model_version=VERSION))
    return result

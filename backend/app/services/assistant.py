"""Retry-safe assistant orchestration. Interpretation/execution remain separate services."""
import hashlib
import json
from uuid import uuid4
from sqlalchemy import select,insert,text,update
from app.api.errors import ApiError
from app.db.models import Conversation,AssistantTurn,DeletedRequest,SavedRecord
from app.schemas.contracts import AssistantResponse,Clarification
from app.services.interpretation import interpret_question
from app.services.execute_meaning import execute_interpretation
from app.nlp.interpreter import VERSION
from app.services.dialogue import prepare,TTL
from app.repositories.profiles import read_profile


def canonical_payload(payload):
    canonical=payload.model_dump(mode='json')
    if canonical.get('conversation_version') is None: canonical.pop('conversation_version',None)
    # Preserve Phase 2–4 request hashes when newly added optional overrides are absent.
    for field in list(canonical['context_overrides']):
        if field not in {'year','department_id'} and canonical['context_overrides'][field] is None:
            del canonical['context_overrides'][field]
    cleared = sorted(field for field in payload.context_overrides.model_fields_set
                     if getattr(payload.context_overrides, field) is None)
    if cleared:
        canonical['_explicit_null_context'] = cleared
    return canonical


def answer_question(conn,payload,user_id,request_id,now,campus_timezone,*,nlp_mode='baseline',intent_model=None,now_minutes=30,horizon_days=30):
    fingerprint=hashlib.sha256(json.dumps(canonical_payload(payload),sort_keys=True).encode()).hexdigest()
    conn.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))'),{'key':'assistant-owner:'+user_id})
    deleted=conn.execute(select(DeletedRequest.user_id).where(DeletedRequest.user_id==user_id,DeletedRequest.request_hash==hashlib.sha256(payload.client_request_id.encode()).hexdigest())).first()
    if deleted: raise ApiError(410,'history_deleted','This request belonged to deleted history; use a new request ID')
    prior=conn.execute(select(AssistantTurn.__table__).where(AssistantTurn.user_id==user_id,AssistantTurn.client_request_id==payload.client_request_id)).mappings().first()
    if prior:
        if prior['payload_hash']!=fingerprint: raise ApiError(409,'request_conflict','Request ID was already used for a different payload')
        return prior['response']  # Exact historical snapshot, including snapshots from earlier schema versions.
    if payload.clarification is not None and payload.conversation_id is None:
        raise ApiError(422,'conversation_required','A clarification reply requires its conversation ID')
    conversation_id=payload.conversation_id
    state={};expires_at=None;version=1
    if conversation_id:
        owned=conn.execute(select(Conversation.__table__).where(Conversation.id==conversation_id,Conversation.owner_id==user_id).with_for_update()).mappings().first()
        if not owned: raise ApiError(404,'not_found','Conversation not found')
        if payload.conversation_version is not None and payload.conversation_version!=owned['version']:
            raise ApiError(409,'conversation_conflict','Conversation changed; reload before sending another turn')
        if owned['version']>=200: raise ApiError(409,'conversation_limit','This conversation reached its 200-turn limit; start a new conversation')
        state=owned['state'];expires_at=owned['state_expires_at'];version=owned['version']+1
    else:
        if payload.conversation_version is not None: raise ApiError(422,'conversation_required','A conversation version requires its ID')
        conversation_id=str(uuid4());conn.execute(insert(Conversation).values(id=conversation_id,owner_id=user_id,created_at=now))
    prepared,prior_meaning,selected,context_warnings=prepare(payload,state,expires_at,now)
    report,catalog=interpret_question(conn,prepared,user_id,now,campus_timezone,nlp_mode=nlp_mode,intent_model=intent_model,
        prior_meaning=prior_meaning,selected_intent=selected,now_minutes=now_minutes,horizon_days=horizon_days)
    status=report.status;intent=report.intent;meaning=report.meaning;applied=report.applied_context;message=report.message
    cards=[];clarification=None;coverage='not_applicable'
    warnings=['Prototype trained intent with deterministic semantic checks.' if nlp_mode=='hybrid' else 'Deterministic cross-domain rules.']+context_warnings+report.warnings
    next_state={'meaning':prior_meaning.model_dump(mode='json') if prior_meaning else None}
    if report.status=='ready':
        cards,status,message,coverage,execution_warnings=execute_interpretation(conn,report,catalog,now,interests=read_profile(conn,user_id)['interests'])
        warnings=warnings[:1]+context_warnings+execution_warnings
        next_state={'meaning':meaning.model_dump(mode='json')}
    elif report.status=='clarification_required':
        issue=report.ambiguities[0]
        clarification=Clarification(id=str(uuid4()),field=issue.field,prompt=issue.prompt,options=issue.options)
        next_state['pending']={'id':clarification.id,'field':issue.field,'options':[o.model_dump() for o in issue.options],'prompt':issue.prompt,
            'text':prepared.text,'overrides':prepared.context_overrides.model_dump(exclude_unset=True),'intent':report.intent,
            'prior':prior_meaning.model_dump(mode='json') if prior_meaning else None,'entities':[entity.model_dump(mode='json') for entity in report.entities]}
    conn.execute(update(Conversation).where(Conversation.id==conversation_id).values(state=next_state,state_expires_at=now+TTL,version=version))
    if cards:
        saved=set(conn.execute(select(SavedRecord.kind,SavedRecord.record_id).where(SavedRecord.user_id==user_id,SavedRecord.record_id.in_([card.record_id for card in cards]))).all())
        for card in cards: card.saved=({'event':'event','room_availability':'room','office_hours':'faculty'}[card.kind],card.record_id) in saved
    turn_id=str(uuid4())
    answer=AssistantResponse(conversation_version=version,conversation_id=conversation_id,turn_id=turn_id,request_id=request_id,status=status,intent=intent,message=message,
        interpreted_query=meaning,applied_context=applied,results=cards,clarification=clarification,answered_at=now,campus_timezone=campus_timezone,
        warnings=warnings,data_coverage=coverage,next_cursor=None)
    body=answer.model_dump(mode='json')
    conn.execute(insert(AssistantTurn).values(id=turn_id,conversation_id=conversation_id,user_id=user_id,client_request_id=payload.client_request_id,
        sequence=version,payload_hash=fingerprint,question=payload.text,response=body,created_at=now,model_version=intent_model.version+'+rules-v1' if nlp_mode=='hybrid' and intent_model is not None else VERSION))
    return body

# Compatibility name for callers; the legacy rule baseline stays in nlp/event_baseline.py for evaluation.
answer_event_question=answer_question

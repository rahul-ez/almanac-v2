"""Private snapshots and current saved references; no caller-supplied owner IDs."""
import hashlib
from uuid import uuid4
from sqlalchemy import select,insert,delete,func,text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.api.errors import ApiError
from app.db.models import Conversation,AssistantTurn,DeletedRequest,SavedRecord,Event
from app.db.room_models import Room
from app.db.faculty_models import Faculty
from app.schemas.personal import ConversationSummary,ConversationDetail,ConversationPage,SavedView,SavedPage
from app.services.rooms import room_value
from app.services.faculty import faculty_view
from app.services.events import get_event
from app.schemas.rooms import RoomView
from app.repositories.profiles import read_profile


def summary(conn,record):
    turns=AssistantTurn.__table__
    count,last=conn.execute(select(func.count(),func.max(turns.c.created_at)).where(turns.c.conversation_id==record['id'])).one()
    first=conn.execute(select(turns.c.question).where(turns.c.conversation_id==record['id']).order_by(turns.c.sequence).limit(1)).scalar_one_or_none()
    return ConversationSummary(id=record['id'],title=(first or 'Conversation')[:100],created_at=record['created_at'],last_turn_at=last,
        turn_count=count,version=record['version'],state_expires_at=record['state_expires_at'])


def conversations(conn,user_id,limit,offset):
    records=list(conn.execute(select(Conversation.__table__).where(Conversation.owner_id==user_id)
        .order_by(Conversation.created_at.desc(),Conversation.id.desc()).limit(limit+1).offset(offset)).mappings())
    return ConversationPage(items=[summary(conn,r) for r in records[:limit]],next_offset=offset+limit if len(records)>limit else None)


def owned(conn,user_id,conversation_id):
    found=conn.execute(select(Conversation.__table__).where(Conversation.id==conversation_id,Conversation.owner_id==user_id)).mappings().first()
    if found is None: raise ApiError(404,'not_found','Conversation not found')
    return found


def conversation(conn,user_id,conversation_id,now,limit,offset):
    record=owned(conn,user_id,conversation_id)
    turns=list(conn.execute(select(AssistantTurn.__table__).where(AssistantTurn.conversation_id==conversation_id)
        .order_by(AssistantTurn.sequence).limit(limit+1).offset(offset)).mappings())
    active=record['state'].get('pending') if record['state_expires_at'] and record['state_expires_at']>now else None
    return ConversationDetail(conversation=summary(conn,record),active_clarification={k:active[k] for k in ('id','field','options')}|{'prompt':active['prompt']} if active else None,
        turns=[dict(id=r['id'],question=r['question'],created_at=r['created_at'],response=r['response']) for r in turns[:limit]],
        next_offset=offset+limit if len(turns)>limit else None)


def delete_conversation(conn,user_id,conversation_id):
    conn.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,0))'),{'key':'assistant-owner:'+user_id})
    owned(conn,user_id,conversation_id)
    requests=conn.execute(select(AssistantTurn.client_request_id).where(AssistantTurn.conversation_id==conversation_id)).scalars()
    for request_id in requests:
        conn.execute(pg_insert(DeletedRequest).values(user_id=user_id,request_hash=hashlib.sha256(request_id.encode()).hexdigest()).on_conflict_do_nothing())
    conn.execute(delete(Conversation).where(Conversation.id==conversation_id,Conversation.owner_id==user_id))
    return {'id':conversation_id,'deleted':True}

MODELS={'event':Event,'room':Room,'faculty':Faculty}

def saved_view(conn,record,user_id,now):
    model=MODELS[record['kind']]
    target=conn.execute(select(model.__table__).where(model.id==record['record_id'])).mappings().one()
    current=None
    if target['status'] not in {'archived','draft'}:
        if record['kind']=='event':
            profile=read_profile(conn,user_id)
            current=get_event(conn,target['id'],now,year=profile['year'],department=profile['department_id'])
        elif record['kind']=='room': current=RoomView.model_validate(room_value(conn,target))
        else: current=faculty_view(conn,target)
    return SavedView(kind=record['kind'],record_id=record['record_id'],saved_at=record['created_at'],record_status=target['status'],
        changed=target['version']!=record['saved_version'],current=current)


def saved(conn,user_id,now,limit,offset):
    records=list(conn.execute(select(SavedRecord.__table__).where(SavedRecord.user_id==user_id)
        .order_by(SavedRecord.created_at.desc(),SavedRecord.id.desc()).limit(limit+1).offset(offset)).mappings())
    return SavedPage(items=[saved_view(conn,r,user_id,now) for r in records[:limit]],next_offset=offset+limit if len(records)>limit else None)


def save(conn,user_id,kind,record_id,now):
    conn.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,0))'),{'key':'saved-owner:'+user_id})
    existing=conn.execute(select(SavedRecord.__table__).where(SavedRecord.user_id==user_id,SavedRecord.kind==kind,SavedRecord.record_id==record_id)).mappings().first()
    if existing: return saved_view(conn,existing,user_id,now)
    model=MODELS[kind]
    target=conn.execute(select(model.__table__).where(model.id==record_id).with_for_update(read=True)).mappings().first()
    if target is None or target['status'] in {'archived','draft'}: raise ApiError(404,'not_found','Record not found')
    values={'id':str(uuid4()),'user_id':user_id,'kind':kind,'record_id':record_id,'saved_version':target['version'],
        'created_at':now,'event_id':None,'room_id':None,'faculty_id':None}
    values[kind+'_id']=record_id
    conn.execute(insert(SavedRecord).values(**values))
    stored=conn.execute(select(SavedRecord.__table__).where(SavedRecord.id==values['id'])).mappings().one()
    return saved_view(conn,stored,user_id,now)


def remove_save(conn,user_id,kind,record_id):
    conn.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,0))'),{'key':'saved-owner:'+user_id})
    conn.execute(delete(SavedRecord).where(SavedRecord.user_id==user_id,SavedRecord.kind==kind,SavedRecord.record_id==record_id))
    return {'kind':kind,'record_id':record_id,'saved':False}

from typing import Annotated
from fastapi import APIRouter,Query,Request
from app.auth.dependencies import Db,Student,CsrfSession
from app.auth.sessions import rate_limit
from app.schemas.contracts import ErrorResponse
from app.schemas.personal import ConversationPage,ConversationDetail,DeletedConversation,SavedPage,SavedView,RemovedSave,SavedKind
from app.schemas.rooms import ID
from app.services import personal
router=APIRouter(prefix='/api/v1',responses={code:{'model':ErrorResponse} for code in (401,403,404,409,410,422,429,503)})
Limit=Annotated[int,Query(ge=1,le=50)]
Offset=Annotated[int,Query(ge=0,le=100000)]

@router.get('/conversations',response_model=ConversationPage,tags=['history'])
def conversations(request:Request,conn:Db,user:Student,limit:Limit=20,offset:Offset=0):
    rate_limit(request,'personal-read',user['id'],60)
    return personal.conversations(conn,user['id'],limit,offset)

@router.get('/conversations/{conversation_id}',response_model=ConversationDetail,tags=['history'])
def conversation(conversation_id:ID,request:Request,conn:Db,user:Student,limit:Limit=20,offset:Offset=0):
    rate_limit(request,'personal-read',user['id'],60)
    return personal.conversation(conn,user['id'],conversation_id,request.app.state.now(),limit,offset)

@router.delete('/conversations/{conversation_id}',response_model=DeletedConversation,tags=['history'])
def delete_conversation(conversation_id:ID,request:Request,conn:Db,user:Student,session:CsrfSession):
    rate_limit(request,'personal-write',user['id'],60)
    return personal.delete_conversation(conn,user['id'],conversation_id)

@router.get('/me/saved',response_model=SavedPage,tags=['saved'])
def saved(request:Request,conn:Db,user:Student,limit:Limit=20,offset:Offset=0):
    rate_limit(request,'personal-read',user['id'],60)
    return personal.saved(conn,user['id'],request.app.state.now(),limit,offset)

@router.put('/me/saved/{kind}/{record_id}',response_model=SavedView,tags=['saved'])
def save(kind:SavedKind,record_id:ID,request:Request,conn:Db,user:Student,session:CsrfSession):
    rate_limit(request,'personal-write',user['id'],60)
    return personal.save(conn,user['id'],kind,record_id,request.app.state.now())

@router.delete('/me/saved/{kind}/{record_id}',response_model=RemovedSave,tags=['saved'])
def remove_save(kind:SavedKind,record_id:ID,request:Request,conn:Db,user:Student,session:CsrfSession):
    rate_limit(request,'personal-write',user['id'],60)
    return personal.remove_save(conn,user['id'],kind,record_id)

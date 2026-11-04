from typing import Annotated
from fastapi import APIRouter, Query, Request
from app.auth.dependencies import Db, CurrentUser, Student, Admin, CsrfSession
from app.auth.sessions import rate_limit
from app.schemas.contracts import ErrorResponse, AssistantResponse
from app.schemas.events import EventCreate, EventPatch, EventView, EventList, EventSearch, AssistantRequest
from app.services.events import create_event, patch_event, get_event, search_events
from app.services.assistant import answer_event_question
from app.repositories.profiles import read_profile

router = APIRouter(prefix='/api/v1', responses={code:{'model':ErrorResponse} for code in (401,403,404,409,413,422,429,503)})
Search = Annotated[EventSearch, Query()]

def context(conn, user):
    profile = read_profile(conn,user['id']) if user['role'] == 'student' else {'year':None,'department_id':None}
    return {'year':profile['year'],'department':profile['department_id']}

@router.get('/events', response_model=EventList, tags=['events'])
def events(filters: Search, request: Request, conn: Db, user: CurrentUser):
    return search_events(conn, filters, request.app.state.now(), **context(conn,user))

@router.get('/events/{event_id}', response_model=EventView, tags=['events'])
def event(event_id: str, request: Request, conn: Db, user: CurrentUser):
    return get_event(conn,event_id,request.app.state.now(),**context(conn,user))

@router.get('/admin/events', response_model=EventList, tags=['admin events'])
def admin_events(filters: Search, request: Request, conn: Db, user: Admin):
    return search_events(conn,filters,request.app.state.now(),admin=True)

@router.get('/admin/events/{event_id}', response_model=EventView, tags=['admin events'])
def admin_event(event_id: str, request: Request, conn: Db, user: Admin):
    return get_event(conn,event_id,request.app.state.now(),admin=True)

@router.post('/admin/events', response_model=EventView, status_code=201, tags=['admin events'])
def create(payload: EventCreate, request: Request, conn: Db, user: Admin, session: CsrfSession):
    return create_event(conn,payload,user['id'],request.app.state.now())

@router.patch('/admin/events/{event_id}', response_model=EventView, tags=['admin events'])
def patch(event_id: str, payload: EventPatch, request: Request, conn: Db, user: Admin, session: CsrfSession):
    return patch_event(conn,event_id,payload,user['id'],request.app.state.now())

@router.delete('/admin/events/{event_id}', response_model=EventView, tags=['admin events'])
def archive(event_id: str, version: Annotated[int,Query(ge=1)], request: Request, conn: Db, user: Admin, session: CsrfSession):
    return patch_event(conn,event_id,EventPatch(version=version,status='archived'),user['id'],request.app.state.now())

@router.post('/assistant/query', response_model=AssistantResponse, tags=['assistant'])
def assistant(payload: AssistantRequest, request: Request, conn: Db, user: Student, session: CsrfSession):
    rate_limit(request,'assistant',user['id'],30)
    return answer_event_question(conn,payload,user['id'],request.state.request_id,request.app.state.now(),request.app.state.settings.campus_timezone)

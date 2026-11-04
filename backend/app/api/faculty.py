from typing import Annotated
from fastapi import APIRouter,Query,Request
from app.auth.dependencies import Db,CurrentUser,Admin,CsrfSession
from app.auth.sessions import rate_limit
from app.schemas.contracts import ErrorResponse
from app.schemas.rooms import ID
from app.schemas.faculty import (FacultyData,FacultyPatch,FacultyView,FacultyPage,AliasData,AliasPatch,AliasView,AliasPage,
    OfficeHourData,OfficeHourPatch,OfficeHourView,OfficeHourPage,OfficeExceptionData,OfficeExceptionPatch,OfficeExceptionView,OfficeExceptionPage,
    FacultyQuery,ResolveQuery,FacultyResolution,OfficeHoursQuery,OfficeHoursResult)
from app.services.faculty import inventory,detail,write,resolve_faculty,office_hours

router=APIRouter(prefix='/api/v1',responses={code:{'model':ErrorResponse} for code in (401,403,404,409,413,422,429,503)})
Inventory=Annotated[FacultyQuery,Query()]
Resolve=Annotated[ResolveQuery,Query()]
Hours=Annotated[OfficeHoursQuery,Query()]

@router.get('/faculty/resolve',response_model=FacultyResolution,tags=['faculty'])
def resolve(query: Resolve,request: Request,conn: Db,user: CurrentUser):
    rate_limit(request,'faculty-query',user['id'],60)
    return resolve_faculty(conn,query)

@router.get('/faculty',response_model=FacultyPage,tags=['faculty'])
def faculty_list(query: Inventory,conn: Db,user: CurrentUser):
    return inventory(conn,'faculty',query,public=True)

@router.get('/faculty/{record_id}/office-hours',response_model=OfficeHoursResult,tags=['faculty'])
def published_hours(record_id: ID,query: Hours,request: Request,conn: Db,user: CurrentUser):
    rate_limit(request,'faculty-query',user['id'],60)
    return office_hours(conn,record_id,query,request.app.state.now())

@router.get('/faculty/{record_id}',response_model=FacultyView,tags=['faculty'])
def faculty_detail(record_id: ID,conn: Db,user: CurrentUser):
    return detail(conn,'faculty',record_id,public=True)


def register_admin(resource,data_schema,patch_schema,view_schema,page_schema):
    prefix='/admin/'+resource;tags=['admin '+resource]
    def listing(query: Inventory,conn: Db,user: Admin): return inventory(conn,resource,query)
    def get(record_id: ID,conn: Db,user: Admin): return detail(conn,resource,record_id)
    def create(payload: data_schema,request: Request,conn: Db,user: Admin,session: CsrfSession):
        return write(conn,resource,payload,user['id'],request.app.state.now(),request.app.state.settings.campus_timezone)
    def patch(record_id: ID,payload: patch_schema,request: Request,conn: Db,user: Admin,session: CsrfSession):
        return write(conn,resource,payload,user['id'],request.app.state.now(),request.app.state.settings.campus_timezone,record_id)
    def archive(record_id: ID,version: Annotated[int,Query(ge=1)],request: Request,conn: Db,user: Admin,session: CsrfSession):
        return write(conn,resource,patch_schema(version=version,status='archived'),user['id'],request.app.state.now(),request.app.state.settings.campus_timezone,record_id)
    for method,path,endpoint,schema,status in [('GET',prefix,listing,page_schema,200),('GET',prefix+'/{record_id}',get,view_schema,200),
        ('POST',prefix,create,view_schema,201),('PATCH',prefix+'/{record_id}',patch,view_schema,200),('DELETE',prefix+'/{record_id}',archive,view_schema,200)]:
        router.add_api_route(path,endpoint,methods=[method],response_model=schema,status_code=status,tags=tags,
                             operation_id='faculty_'+resource.replace('-','_')+'_'+endpoint.__name__)

for args in [('faculty',FacultyData,FacultyPatch,FacultyView,FacultyPage),('aliases',AliasData,AliasPatch,AliasView,AliasPage),
    ('office-hours',OfficeHourData,OfficeHourPatch,OfficeHourView,OfficeHourPage),('office-hour-exceptions',OfficeExceptionData,OfficeExceptionPatch,OfficeExceptionView,OfficeExceptionPage)]:
    register_admin(*args)

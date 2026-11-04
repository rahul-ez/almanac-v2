from typing import Annotated
from fastapi import APIRouter, Query, Request
from app.auth.dependencies import Db,CurrentUser,Admin,CsrfSession
from app.auth.sessions import rate_limit
from app.schemas.contracts import ErrorResponse
from app.schemas.rooms import (RoomData,RoomPatch,RoomView,RoomPage,BookingData,BookingPatch,BookingView,BookingPage,
    ExceptionData,ExceptionPatch,ExceptionView,ExceptionPage,ClosureData,ClosurePatch,ClosureView,ClosurePage,
    InventoryQuery,AvailabilityQuery,AvailabilityPage,RoomAvailability,ID)
from app.services.rooms import detail,inventory,write,available_rooms

router=APIRouter(prefix='/api/v1',responses={code:{'model':ErrorResponse} for code in (401,403,404,409,413,422,429,503)})
Inventory = Annotated[InventoryQuery,Query()]
Availability = Annotated[AvailabilityQuery,Query()]

# Static routes precede /rooms/{record_id}.
@router.get('/rooms/availability',response_model=AvailabilityPage,tags=['rooms'])
def availability(query: Availability,request: Request,conn: Db,user: CurrentUser):
    rate_limit(request,'room-availability',user['id'],60)
    return available_rooms(conn,query,request.app.state.now())

@router.get('/rooms',response_model=RoomPage,tags=['rooms'])
def rooms(query: Inventory,conn: Db,user: CurrentUser):
    return inventory(conn,'rooms',query,public=True)

@router.get('/rooms/{record_id}/availability',response_model=RoomAvailability,tags=['rooms'])
def room_availability(record_id: ID,query: Availability,request: Request,conn: Db,user: CurrentUser):
    rate_limit(request,'room-availability',user['id'],60)
    return available_rooms(conn,query,request.app.state.now(),room_id=record_id)

@router.get('/rooms/{record_id}',response_model=RoomView,tags=['rooms'])
def room(record_id: ID,conn: Db,user: CurrentUser):
    return detail(conn,'rooms',record_id,student=True)


def register_admin(resource,data_schema,patch_schema,view_schema,page_schema):
    tag=['admin '+resource]
    prefix='/admin/'+resource
    def listing(query: Inventory,conn: Db,user: Admin):
        return inventory(conn,resource,query)
    def get(record_id: ID,conn: Db,user: Admin):
        return detail(conn,resource,record_id)
    def create(payload: data_schema,request: Request,conn: Db,user: Admin,session: CsrfSession):
        return write(conn,resource,payload,user['id'],request.app.state.now(),request.app.state.settings.campus_timezone)
    def patch(record_id: ID,payload: patch_schema,request: Request,conn: Db,user: Admin,session: CsrfSession):
        return write(conn,resource,payload,user['id'],request.app.state.now(),request.app.state.settings.campus_timezone,record_id)
    def archive(record_id: ID,version: Annotated[int,Query(ge=1)],request: Request,conn: Db,user: Admin,session: CsrfSession):
        return write(conn,resource,patch_schema(version=version,status='archived'),user['id'],request.app.state.now(),request.app.state.settings.campus_timezone,record_id)
    for method,path,endpoint,schema,status in [('GET',prefix,listing,page_schema,200),('GET',prefix+'/{record_id}',get,view_schema,200),
          ('POST',prefix,create,view_schema,201),('PATCH',prefix+'/{record_id}',patch,view_schema,200),('DELETE',prefix+'/{record_id}',archive,view_schema,200)]:
        router.add_api_route(path,endpoint,methods=[method],response_model=schema,status_code=status,tags=tag,
                             operation_id=resource.replace('-','_')+'_'+endpoint.__name__)

for args in [('rooms',RoomData,RoomPatch,RoomView,RoomPage),('bookings',BookingData,BookingPatch,BookingView,BookingPage),
             ('booking-exceptions',ExceptionData,ExceptionPatch,ExceptionView,ExceptionPage),('room-closures',ClosureData,ClosurePatch,ClosureView,ClosurePage)]:
    register_admin(*args)

from datetime import date, timedelta
from typing import Annotated, Literal
from pydantic import AwareDatetime, Field, HttpUrl, field_validator, model_validator
from app.schemas.contracts import StrictModel

ID = Annotated[str,Field(min_length=1,max_length=80)]
Clock = Annotated[str,Field(pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')]
EndClock = Annotated[str,Field(pattern=r'^(?:(?:[01]\d|2[0-3]):[0-5]\d|24:00)$')]

def minutes(value):
    hour,minute = map(int,value.split(':'))
    return hour*60+minute

class OpeningHour(StrictModel):
    weekday: int = Field(strict=True,ge=0,le=6)
    start: Clock
    end: EndClock

    @model_validator(mode='after')
    def interval(self):
        if minutes(self.end) <= minutes(self.start):
            raise ValueError('Opening intervals must end after start; split overnight hours across days')
        return self

class Source(StrictModel):
    source_label: str = Field(min_length=1,max_length=100)
    source_url: HttpUrl | None = Field(default=None,max_length=1000)

    @field_validator('source_label')
    @classmethod
    def nonblank(cls,value):
        if not value.strip():
            raise ValueError('Nonblank source label required')
        return value.strip()

    @field_validator('source_url')
    @classmethod
    def safe_link(cls,value):
        if value and (value.username or value.password):
            raise ValueError('Source links cannot contain credentials')
        return value

class RoomData(Source):
    code: str = Field(min_length=1,max_length=80)
    building_id: ID
    capacity: int = Field(strict=True,gt=0,le=100000)
    facility_ids: list[ID] = Field(default_factory=list,max_length=30)
    opening_hours: list[OpeningHour] | None = Field(default=None,max_length=50)
    coverage_start: AwareDatetime | None = None
    coverage_end: AwareDatetime | None = None
    coverage_complete: bool = False
    status: Literal['active','archived'] = 'active'

    @field_validator('code')
    @classmethod
    def canonical_code(cls,value):
        if not value.strip():
            raise ValueError('Nonblank room code required')
        return value.strip().upper()

    @model_validator(mode='after')
    def schedules(self):
        if len(set(self.facility_ids)) != len(self.facility_ids):
            raise ValueError('Facilities must be unique')
        if (self.coverage_start is None) != (self.coverage_end is None):
            raise ValueError('Supply both coverage bounds or neither')
        if self.coverage_complete and self.coverage_start is None:
            raise ValueError('Complete coverage requires explicit bounds')
        if self.coverage_start and self.coverage_end <= self.coverage_start:
            raise ValueError('Coverage end must follow start')
        previous = {}
        for opening in sorted(self.opening_hours or [],key=lambda x:(x.weekday,x.start)):
            if minutes(opening.start) < previous.get(opening.weekday,-1):
                raise ValueError('Opening hours must not overlap')
            previous[opening.weekday] = minutes(opening.end)
        return self

class RoomView(RoomData):
    id: str
    version: int
    updated_at: AwareDatetime
    timezone: str

class BookingData(Source):
    room_id: ID
    purpose: str = Field(min_length=1,max_length=200)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    recurrence: Literal['none','weekly'] = 'none'
    recurrence_until: date | None = None
    status: Literal['active','cancelled','archived'] = 'active'

    @model_validator(mode='after')
    def bounded(self):
        if not self.purpose.strip():
            raise ValueError('Nonblank purpose required')
        if not timedelta(0) < self.ends_at-self.starts_at <= timedelta(days=1):
            raise ValueError('Booking duration must be positive and at most 24 hours')
        if (self.recurrence == 'weekly') != (self.recurrence_until is not None):
            raise ValueError('Only weekly recurrence requires an inclusive recurrence_until date')
        return self

class BookingView(BookingData):
    id: str
    version: int
    updated_at: AwareDatetime

class ExceptionData(Source):
    booking_id: ID
    occurrence_date: date
    action: Literal['cancel','replace']
    replacement_start: AwareDatetime | None = None
    replacement_end: AwareDatetime | None = None
    note: str = Field(default='',max_length=500)
    status: Literal['active','archived'] = 'active'

    @model_validator(mode='after')
    def replacements(self):
        if self.action == 'cancel':
            if self.replacement_start is not None or self.replacement_end is not None:
                raise ValueError('Cancellation has no replacement interval')
        elif self.replacement_start is None or self.replacement_end is None or not timedelta(0) < self.replacement_end-self.replacement_start <= timedelta(days=1):
            raise ValueError('Replacement requires a positive interval of at most 24 hours')
        return self

class ExceptionView(ExceptionData):
    id: str
    version: int
    updated_at: AwareDatetime

class ClosureData(Source):
    room_id: ID
    reason: str = Field(min_length=1,max_length=300)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    status: Literal['active','archived'] = 'active'

    @model_validator(mode='after')
    def interval(self):
        if not self.reason.strip() or not timedelta(0) < self.ends_at-self.starts_at <= timedelta(days=366):
            raise ValueError('Closure needs a reason and a positive interval of at most 366 days')
        return self

class ClosureView(ClosureData):
    id: str
    version: int
    updated_at: AwareDatetime

# PATCH fields are optional, but version is mandatory. Whole merged records are revalidated.
def patch_schema(name,data):
    from pydantic import create_model
    fields = {key:(field.annotation | None,Field(default=None)) for key,field in data.model_fields.items()}
    return create_model(name,__base__=StrictModel,version=(Annotated[int,Field(strict=True,ge=1)],...),**fields)

RoomPatch = patch_schema('RoomPatch',RoomData)
BookingPatch = patch_schema('BookingPatch',BookingData)
ExceptionPatch = patch_schema('ExceptionPatch',ExceptionData)
ClosurePatch = patch_schema('ClosurePatch',ClosureData)

class InventoryQuery(StrictModel):
    room_id: str | None = Field(default=None,max_length=80)
    search: str | None = Field(default=None,max_length=100)
    limit: int = Field(default=20,ge=1,le=100)
    cursor: str | None = Field(default=None,max_length=1024)

class AvailabilityQuery(StrictModel):
    from_at: AwareDatetime
    to_at: AwareDatetime
    building_id: str | None = Field(default=None,max_length=80)
    min_capacity: int = Field(default=1,ge=1,le=100000)
    facility_ids: list[ID] = Field(default_factory=list,max_length=30)
    limit: int = Field(default=20,ge=1,le=100)
    cursor: str | None = Field(default=None,max_length=1024)

    @model_validator(mode='after')
    def interval(self):
        if not timedelta(0) < self.to_at-self.from_at <= timedelta(days=30):
            raise ValueError('Interval must be positive and at most 30 days')
        return self

class RequestedInterval(StrictModel):
    start: AwareDatetime
    end: AwareDatetime

class RoomAvailability(StrictModel):
    room: RoomView
    availability: Literal['available','unavailable','unknown']
    reasons: list[str]
    requested_interval: RequestedInterval
    availability_basis: Literal['scheduled_bookings'] = 'scheduled_bookings'

class AvailabilityPage(StrictModel):
    status: Literal['answered','no_results','information_unavailable']
    items: list[RoomAvailability]
    unknown_rooms: list[RoomAvailability]
    checked_count: int
    next_cursor: str | None
    data_coverage: Literal['complete','partial','unknown']
    warnings: list[str]
    availability_basis: Literal['scheduled_bookings'] = 'scheduled_bookings'

class RoomPage(StrictModel):
    items: list[RoomView]
    next_cursor: str | None

class BookingPage(StrictModel):
    items: list[BookingView]
    next_cursor: str | None

class ExceptionPage(StrictModel):
    items: list[ExceptionView]
    next_cursor: str | None

class ClosurePage(StrictModel):
    items: list[ClosureView]
    next_cursor: str | None

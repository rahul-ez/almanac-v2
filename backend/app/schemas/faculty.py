from datetime import date,timedelta
from typing import Literal
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from pydantic import AwareDatetime,Field,field_validator,model_validator
from app.schemas.contracts import StrictModel
from app.schemas.rooms import Source,ID,Clock,EndClock,minutes,patch_schema,RequestedInterval

class FacultyData(Source):
    name: str=Field(min_length=1,max_length=200)
    department_id: ID
    location: str=Field(default='',max_length=200)
    email: str | None=Field(default=None,max_length=254,pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    office_hours_coverage_start: date | None=None
    office_hours_coverage_end: date | None=None
    office_hours_complete: bool=False
    status: Literal['active','archived']='active'

    @field_validator('name')
    @classmethod
    def nonblank_name(cls,value):
        if not value.strip(): raise ValueError('Faculty name must be nonblank')
        return value.strip()

    @model_validator(mode='after')
    def coverage(self):
        if (self.office_hours_coverage_start is None) != (self.office_hours_coverage_end is None):
            raise ValueError('Supply both coverage dates or neither')
        if self.office_hours_complete and self.office_hours_coverage_start is None:
            raise ValueError('Complete publication requires explicit coverage dates')
        if self.office_hours_coverage_start and not 0 <= (self.office_hours_coverage_end-self.office_hours_coverage_start).days <= 366:
            raise ValueError('Coverage dates must be ordered and within 366 days')
        return self

class FacultyView(FacultyData):
    id: str
    version: int
    updated_at: AwareDatetime
    timezone: str
    aliases: list[str]

class AliasData(Source):
    entity_type: Literal['faculty']='faculty'
    canonical_id: ID
    alias: str=Field(min_length=1,max_length=200)
    status: Literal['active','archived']='active'

    @field_validator('alias')
    @classmethod
    def nonblank_alias(cls,value):
        if not value.strip(): raise ValueError('Alias must be nonblank')
        return value.strip()

class AliasView(AliasData):
    id: str
    version: int
    updated_at: AwareDatetime
    matching_faculty_count: int

class OfficeHourData(Source):
    faculty_id: ID
    location: str=Field(min_length=1,max_length=200)
    weekday: int=Field(strict=True,ge=0,le=6)
    start_time: Clock
    end_time: EndClock
    effective_from: date
    effective_until: date
    timezone: str | None=Field(default=None,min_length=1,max_length=80)
    status: Literal['active','cancelled','archived']='active'

    @field_validator('location')
    @classmethod
    def nonblank_location(cls,value):
        if not value.strip(): raise ValueError('Published meeting location is required')
        return value.strip()

    @field_validator('timezone')
    @classmethod
    def valid_timezone(cls,value):
        if value:
            try: ZoneInfo(value)
            except (ZoneInfoNotFoundError,ValueError): raise ValueError('Unknown timezone') from None
        return value

    @model_validator(mode='after')
    def bounded(self):
        if minutes(self.end_time) <= minutes(self.start_time):
            raise ValueError('Office hours end must follow start on the local day')
        if not 0 <= (self.effective_until-self.effective_from).days <= 366:
            raise ValueError('Effective dates must be ordered and within 366 days')
        if self.effective_from+timedelta(days=(self.weekday-self.effective_from.weekday())%7) > self.effective_until:
            raise ValueError('Effective dates must include a matching weekday')
        return self

class OfficeHourView(OfficeHourData):
    id: str
    version: int
    updated_at: AwareDatetime
    timezone: str

class OfficeExceptionData(Source):
    office_hour_id: ID
    occurrence_date: date
    action: Literal['cancel','replace']
    replacement_start: AwareDatetime | None=None
    replacement_end: AwareDatetime | None=None
    note: str=Field(default='',max_length=500)
    status: Literal['active','archived']='active'

    @model_validator(mode='after')
    def replacement(self):
        if self.action == 'cancel':
            if self.replacement_start is not None or self.replacement_end is not None:
                raise ValueError('Cancellation has no replacement interval')
        elif self.replacement_start is None or self.replacement_end is None or not timedelta(0) < self.replacement_end-self.replacement_start <= timedelta(days=1):
            raise ValueError('Replacement needs a positive interval of at most 24 hours')
        return self

class OfficeExceptionView(OfficeExceptionData):
    id: str
    version: int
    updated_at: AwareDatetime

FacultyPatch=patch_schema('FacultyPatch',FacultyData)
AliasPatch=patch_schema('AliasPatch',AliasData)
OfficeHourPatch=patch_schema('OfficeHourPatch',OfficeHourData)
OfficeExceptionPatch=patch_schema('OfficeExceptionPatch',OfficeExceptionData)

class FacultyQuery(StrictModel):
    search: str | None=Field(default=None,max_length=100)
    faculty_id: str | None=Field(default=None,max_length=80)
    department_id: str | None=Field(default=None,max_length=80)
    limit: int=Field(default=20,ge=1,le=100)
    cursor: str | None=Field(default=None,max_length=1024)

class ResolveQuery(StrictModel):
    name: str=Field(min_length=1,max_length=200)
    department_id: str | None=Field(default=None,max_length=80)

class FacultyResolution(StrictModel):
    status: Literal['resolved','clarification_required','no_results']
    candidates: list[FacultyView]
    warnings: list[str]

class OfficeHoursQuery(StrictModel):
    from_at: AwareDatetime
    to_at: AwareDatetime
    limit: int=Field(default=20,ge=1,le=100)
    cursor: str | None=Field(default=None,max_length=1024)

    @model_validator(mode='after')
    def ordered(self):
        if not timedelta(0) < self.to_at-self.from_at <= timedelta(days=30):
            raise ValueError('Office-hour window must be positive and at most 30 days')
        return self

class OfficeHourSlot(StrictModel):
    faculty_id: str
    office_hour_id: str
    occurrence_date: date
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    location: str
    timezone: str
    exception_id: str | None
    exception_note: str | None
    source_label: str
    source_url: str | None
    record_updated_at: AwareDatetime

class OfficeHoursResult(StrictModel):
    status: Literal['answered','no_results','information_unavailable']
    faculty: FacultyView
    items: list[OfficeHourSlot]
    requested_interval: RequestedInterval
    data_coverage: Literal['complete','partial','unknown']
    next_cursor: str | None
    warnings: list[str]

class FacultyPage(StrictModel):
    items: list[FacultyView]
    next_cursor: str | None
class AliasPage(StrictModel):
    items: list[AliasView]
    next_cursor: str | None
class OfficeHourPage(StrictModel):
    items: list[OfficeHourView]
    next_cursor: str | None
class OfficeExceptionPage(StrictModel):
    items: list[OfficeExceptionView]
    next_cursor: str | None

from datetime import timedelta
from typing import Annotated, Literal
from pydantic import AwareDatetime, Field, HttpUrl, field_validator, model_validator
from app.schemas.contracts import StrictModel, EligibilityRules

EventType = Literal['workshop', 'seminar', 'hackathon', 'lecture']
EventStatus = Literal['draft', 'published', 'cancelled', 'archived']

class EventData(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=4000)
    event_type: EventType
    topic_id: str = Field(min_length=1, max_length=80)
    venue: str = Field(min_length=1, max_length=200)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    cost_minor: int | None = Field(default=None, strict=True, ge=0, le=100000000)
    currency: Literal['INR'] = 'INR'
    registration_deadline: AwareDatetime | None = None
    eligibility_rules: EligibilityRules = Field(default_factory=lambda: EligibilityRules(mode='unknown'))
    status: EventStatus = 'draft'
    source_label: str = Field(min_length=1, max_length=100)
    source_url: HttpUrl | None = Field(default=None, max_length=1000)

    @field_validator('title', 'venue', 'source_label')
    @classmethod
    def trim_required(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('A nonblank value is required')
        return value

    @field_validator('source_url')
    @classmethod
    def no_url_credentials(cls, value):
        if value and (value.username or value.password):
            raise ValueError('Source URLs cannot contain credentials')
        return value

    @model_validator(mode='after')
    def valid_time(self):
        if self.ends_at <= self.starts_at:
            raise ValueError('Event end must follow start')
        if self.registration_deadline and self.registration_deadline > self.starts_at:
            raise ValueError('Deadline must not follow event start')
        return self

class EventCreate(EventData):
    pass

class EventPatch(StrictModel):
    version: int = Field(strict=True, ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    event_type: EventType | None = None
    topic_id: str | None = Field(default=None, min_length=1, max_length=80)
    venue: str | None = Field(default=None, min_length=1, max_length=200)
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    cost_minor: int | None = Field(default=None, strict=True, ge=0, le=100000000)
    currency: Literal['INR'] | None = None
    registration_deadline: AwareDatetime | None = None
    eligibility_rules: EligibilityRules | None = None
    status: EventStatus | None = None
    source_label: str | None = Field(default=None, min_length=1, max_length=100)
    source_url: HttpUrl | None = Field(default=None, max_length=1000)

class EventView(EventData):
    id: str
    version: int
    updated_at: AwareDatetime
    eligibility: Literal['eligible', 'ineligible', 'unknown']
    eligibility_reason: str
    registration_status: Literal['open', 'closed', 'unknown']

class EventSearch(StrictModel):
    from_at: AwareDatetime | None = None
    to_at: AwareDatetime | None = None
    event_type: EventType | None = None
    topic_id: str | None = Field(default=None, max_length=80)
    venue: str | None = Field(default=None, max_length=200)
    q: str | None = Field(default=None, max_length=100)
    max_cost_minor: int | None = Field(default=None, ge=0, le=100000000)
    eligible_only: bool = False
    student_year: int | None = Field(default=None, ge=1, le=4)
    department_id: str | None = Field(default=None, max_length=80)
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=1024)

    @model_validator(mode='after')
    def valid_window(self):
        if (self.from_at is None) != (self.to_at is None):
            raise ValueError('Supply both from_at and to_at')
        if self.from_at and not timedelta(0) < self.to_at - self.from_at <= timedelta(days=366):
            raise ValueError('Search interval must be positive and at most 366 days')
        return self

class EventList(StrictModel):
    items: list[EventView]
    next_cursor: str | None
    warnings: list[str] = Field(default_factory=list)

class ContextOverrides(StrictModel):
    year: int | None = Field(default=None, strict=True, ge=1, le=4)
    department_id: str | None = Field(default=None, max_length=80)

    building_id: str | None = Field(default=None,max_length=80)
    room_id: str | None = Field(default=None,max_length=80)
    faculty_id: str | None = Field(default=None,max_length=80)
    capacity: int | None = Field(default=None,strict=True,ge=1,le=100000)
    facility_ids: list[Annotated[str,Field(max_length=80)]] | None = Field(default=None,max_length=30)

class ClarificationReply(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    option_id: str | None = Field(default=None, max_length=80)

class AssistantRequest(StrictModel):
    text: str = Field(min_length=1, max_length=1000)
    client_request_id: str = Field(min_length=1, max_length=128)
    conversation_id: str | None = Field(default=None, max_length=80)
    context_overrides: ContextOverrides = Field(default_factory=ContextOverrides)
    clarification: ClarificationReply | None = None
    conversation_version: int | None = Field(default=None,strict=True,ge=1)

    @field_validator('text')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Question must not be blank')
        return value

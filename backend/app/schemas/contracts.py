from typing import Annotated, Literal
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class FieldError(StrictModel):
    field: str
    message: str

class ErrorDetail(StrictModel):
    code: str
    message: str
    field_errors: list[FieldError] = Field(default_factory=list)
    request_id: str

class ErrorResponse(StrictModel):
    error: ErrorDetail

class LiveResponse(StrictModel):
    status: Literal["alive"] = "alive"

class ReadyResponse(StrictModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, Literal["ok", "unavailable"]]
    nlp_mode: Literal["baseline"] = "baseline"
    request_id: str

class DemoEventResponse(StrictModel):
    demo: Literal[True] = True
    seed_version: Literal["v1"] = "v1"
    id: str
    title: str
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    cost_minor: int | None = Field(ge=0)
    source_label: str
    updated_at: AwareDatetime

class Interval(StrictModel):
    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def valid(self):
        if self.end <= self.start:
            raise ValueError("Interval end must follow start")
        return self

class Card(StrictModel):
    record_id: str
    title: str
    source_label: str
    source_url: HttpUrl | None = None
    record_updated_at: AwareDatetime
    saved: bool = False

class EligibilityRules(StrictModel):
    mode: Literal['unknown', 'unrestricted', 'restricted']
    years: list[Annotated[int, Field(strict=True, ge=1, le=4)]] | None = Field(default=None, max_length=4)
    departments: list[Annotated[str, Field(max_length=80)]] | None = Field(default=None, max_length=20)

    @model_validator(mode='after')
    def explicit_rules(self):
        for values in (self.years, self.departments):
            if values is not None and (not values or len(set(values)) != len(values)):
                raise ValueError('Restrictions must be nonempty and unique or null')
        if self.mode != 'restricted' and (self.years is not None or self.departments is not None):
            raise ValueError('Only restricted eligibility has constraints')
        if self.mode == 'restricted' and self.years is None and self.departments is None:
            raise ValueError('Restricted eligibility requires at least one constraint')
        return self

class EventCard(Card):
    kind: Literal["event"]
    interval: Interval
    venue: str
    topic: str
    event_type: str
    cost_minor: int | None = Field(ge=0)
    currency: str = "INR"
    eligibility: Literal["eligible", "ineligible", "unknown"]
    eligibility_rules: EligibilityRules
    registration_deadline: AwareDatetime | None
    cancelled: bool
    registration_status: Literal["open", "closed", "unknown"] = "unknown"

class RoomCard(Card):
    kind: Literal["room_availability"]
    building: str
    capacity: int = Field(gt=0)
    facilities: list[str]
    requested_interval: Interval
    schedule_coverage: Literal["complete"]
    availability_basis: Literal["scheduled_bookings"]

class OfficeHoursCard(Card):
    kind: Literal["office_hours"]
    faculty_id: str
    faculty_name: str
    location: str
    interval: Interval
    exception: str | None

ResultCard = Annotated[EventCard | RoomCard | OfficeHoursCard, Field(discriminator="kind")]
Intent = Literal["find_events", "find_available_rooms", "find_faculty_office_hours"]

class Filters(StrictModel):
    event_type: str | None = None
    topic: str | None = None
    student_year: int | None = Field(default=None, ge=1, le=8)
    department_id: str | None = None
    building_id: str | None = None
    faculty_id: str | None = None
    room_id: str | None = None
    interval: Interval | None = None
    capacity: int | None = Field(default=None, gt=0)
    eligible_only: bool = False
    max_cost_minor: int | None = Field(default=None, ge=0)

class Meaning(StrictModel):
    intent: Intent
    filters: Filters

class ContextValue(StrictModel):
    field: str
    value: str | int | list[str]
    origin: Literal["explicit_question", "override", "prior_turn", "profile", "default"]

class Option(StrictModel):
    id: str
    label: str

class Clarification(StrictModel):
    id: str
    field: str
    prompt: str
    options: list[Option]

class AssistantResponse(StrictModel):
    conversation_id: str
    turn_id: str
    request_id: str
    status: Literal["answered", "no_results", "clarification_required", "unsupported", "information_unavailable"]
    intent: Intent | None
    message: str
    interpreted_query: Meaning | None
    applied_context: list[ContextValue]
    results: list[ResultCard]
    clarification: Clarification | None
    answered_at: AwareDatetime
    campus_timezone: str
    warnings: list[str]
    data_coverage: Literal["complete", "partial", "unknown", "not_applicable"]
    next_cursor: None = None

    @model_validator(mode="after")
    def consistent(self):
        if (self.status == "clarification_required") != (self.clarification is not None):
            raise ValueError("Clarification must match status")
        if (self.status == "answered") != bool(self.results):
            raise ValueError("Only answered responses contain results")
        expected = {"find_events": "event", "find_available_rooms": "room_availability", "find_faculty_office_hours": "office_hours"}
        if any(card.kind != expected.get(self.intent) for card in self.results):
            raise ValueError("Result kind must match intent")
        if self.interpreted_query and self.interpreted_query.intent != self.intent:
            raise ValueError("Meaning must match intent")
        return self

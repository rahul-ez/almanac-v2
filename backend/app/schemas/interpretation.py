"""Stable interpreter boundary: pure input/catalog -> safe meaning or uncertainty."""
from typing import Annotated,Literal
from pydantic import Field,model_validator
from app.schemas.contracts import StrictModel,Meaning,ContextValue,Intent,Option
from app.schemas.events import EventSearch
from app.schemas.rooms import AvailabilityQuery
from app.schemas.faculty import OfficeHoursQuery

EntityKind=Literal['department','topic','building','room','facility','faculty','venue','event_keyword']

class CatalogEntry(StrictModel):
    kind: EntityKind
    id: str
    label: str
    aliases: list[str]=Field(default_factory=list)
    department_id: str | None=None

class CampusCatalog(StrictModel):
    entries: list[CatalogEntry]=Field(default_factory=list,max_length=20000)
    version: str='campus-catalog-v1'

class ExtractedEntity(StrictModel):
    label: str
    start: int=Field(ge=0)
    end: int=Field(gt=0)
    text: str
    normalized: str | int | None
    canonical_id: str | None=None
    candidate_ids: list[str]=Field(default_factory=list)

class Ambiguity(StrictModel):
    field: str
    prompt: str
    options: list[Option]=Field(default_factory=list)

class EventExecution(StrictModel):
    kind: Literal['event']='event'
    query: EventSearch
class RoomExecution(StrictModel):
    kind: Literal['room']='room'
    query: AvailabilityQuery
    room_id: str | None=None
class FacultyExecution(StrictModel):
    kind: Literal['office_hours']='office_hours'
    query: OfficeHoursQuery
    faculty_id: str

Execution=Annotated[EventExecution | RoomExecution | FacultyExecution,Field(discriminator='kind')]

class Interpretation(StrictModel):
    status: Literal['ready','clarification_required','unsupported']
    intent: Intent | None
    meaning: Meaning | None
    execution: Execution | None
    entities: list[ExtractedEntity]
    applied_context: list[ContextValue]
    missing_fields: list[str]=Field(default_factory=list)
    ambiguities: list[Ambiguity]=Field(default_factory=list)
    unsupported_constraints: list[str]=Field(default_factory=list)
    message: str
    warnings: list[str]=Field(default_factory=list)
    intent_source: Literal['rules','model']='rules'
    interpreter_version: str='campus-rules-v1'
    model_version: str | None=None
    intent_confidence: float | None=Field(default=None,ge=0,le=1)

    @model_validator(mode='after')
    def execution_guard(self):
        if (self.status=='ready') != (self.execution is not None):
            raise ValueError('Only a ready interpretation has executable typed queries')
        if self.status=='ready' and (self.meaning is None or self.missing_fields or self.ambiguities or self.unsupported_constraints):
            raise ValueError('Uncertainty must never reach execution')
        return self

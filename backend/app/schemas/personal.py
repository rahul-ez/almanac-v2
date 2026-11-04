from typing import Literal, Any
from pydantic import AwareDatetime, Field
from app.schemas.contracts import StrictModel, Clarification
from app.schemas.events import EventView
from app.schemas.rooms import RoomView
from app.schemas.faculty import FacultyView

SavedKind=Literal['event','room','faculty']
class ConversationSummary(StrictModel):
    id: str
    title: str
    created_at: AwareDatetime
    last_turn_at: AwareDatetime | None
    turn_count: int
    version: int
    state_expires_at: AwareDatetime | None
class ConversationPage(StrictModel):
    items: list[ConversationSummary]
    next_offset: int | None
class HistoryTurn(StrictModel):
    id: str
    question: str
    created_at: AwareDatetime
    response: dict[str,Any]  # Exact versioned historical snapshot; never filled with new defaults.
class ConversationDetail(StrictModel):
    conversation: ConversationSummary
    active_clarification: Clarification | None
    turns: list[HistoryTurn]
    next_offset: int | None
class DeletedConversation(StrictModel):
    id: str
    deleted: Literal[True]=True
class SavedView(StrictModel):
    kind: SavedKind
    record_id: str
    saved_at: AwareDatetime
    record_status: Literal['published','cancelled','draft','active','archived']
    changed: bool
    current: EventView | RoomView | FacultyView | None
class SavedPage(StrictModel):
    items: list[SavedView]
    next_offset: int | None
class RemovedSave(StrictModel):
    kind: SavedKind
    record_id: str
    saved: Literal[False]=False

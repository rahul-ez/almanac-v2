"""Export runtime OpenAPI separately from future assistant response fixtures."""
import json
import sys
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
from app.config import Settings
from app.main import create_app
from app.schemas.contracts import AssistantResponse, ErrorResponse
from app.schemas.identity import LoginRequest, LoginResponse, Identity, Profile, ProfilePatch, ReferenceData, CsrfResponse

from app.schemas.events import EventCreate, EventPatch, EventView, EventList, EventSearch, AssistantRequest
from app.schemas.rooms import RoomData,RoomPatch,RoomView,BookingData,BookingPatch,BookingView,ExceptionData,ExceptionPatch,ExceptionView,ClosureData,ClosurePatch,ClosureView,AvailabilityQuery,AvailabilityPage,RoomAvailability

from app.schemas.faculty import (FacultyData,FacultyPatch,FacultyView,AliasData,AliasPatch,AliasView,OfficeHourData,OfficeHourPatch,OfficeHourView,
    OfficeExceptionData,OfficeExceptionPatch,OfficeExceptionView,OfficeHoursQuery,OfficeHoursResult,FacultyResolution)

from app.schemas.interpretation import Interpretation
from app.schemas.personal import ConversationPage,ConversationDetail,DeletedConversation,SavedPage,SavedView,RemovedSave

root = Path("/workspace")
settings = Settings(database_url="postgresql+psycopg://unused:unused@localhost/almanac_test")
outputs = {"openapi.json": create_app(settings).openapi(),
           "assistant-response.schema.json": AssistantResponse.model_json_schema(),
           "error.schema.json": ErrorResponse.model_json_schema(),
           "interpretation.schema.json": Interpretation.model_json_schema()}
identity_models = {'login-request': LoginRequest, 'login-response': LoginResponse,
                   'identity': Identity, 'profile': Profile, 'profile-patch': ProfilePatch,
                   'reference-data': ReferenceData, 'csrf-response': CsrfResponse}
event_models = {'event-create':EventCreate,'event-patch':EventPatch,'event-view':EventView,'event-list':EventList,'event-search':EventSearch,'assistant-request':AssistantRequest}
room_models={'room-create':RoomData,'room-patch':RoomPatch,'room-view':RoomView,'booking-create':BookingData,'booking-patch':BookingPatch,
             'booking-view':BookingView,'booking-exception-create':ExceptionData,'booking-exception-patch':ExceptionPatch,'booking-exception-view':ExceptionView,
             'room-closure-create':ClosureData,'room-closure-patch':ClosurePatch,'room-closure-view':ClosureView,
             'availability-query':AvailabilityQuery,'availability-page':AvailabilityPage,'room-availability':RoomAvailability}
faculty_models={'faculty-create':FacultyData,'faculty-patch':FacultyPatch,'faculty-view':FacultyView,'alias-create':AliasData,'alias-patch':AliasPatch,'alias-view':AliasView,
    'office-hour-create':OfficeHourData,'office-hour-patch':OfficeHourPatch,'office-hour-view':OfficeHourView,'office-hour-exception-create':OfficeExceptionData,
    'office-hour-exception-patch':OfficeExceptionPatch,'office-hour-exception-view':OfficeExceptionView,'office-hours-query':OfficeHoursQuery,
    'office-hours-result':OfficeHoursResult,'faculty-resolution':FacultyResolution}
personal_models={'conversation-page':ConversationPage,'conversation-detail':ConversationDetail,'deleted-conversation':DeletedConversation,'saved-page':SavedPage,'saved-view':SavedView,'removed-save':RemovedSave}
for name, model in (identity_models | event_models | room_models | faculty_models | personal_models).items():
    outputs[name + '.schema.json'] = model.model_json_schema()
for name, schema in outputs.items():
    path = root / "contracts" / name
    serialized = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    if "--write" in sys.argv:
        path.write_text(serialized)
    elif not path.exists() or path.read_text() != serialized:
        raise SystemExit(f"Contract drift: {name}; run make contract-export and review the diff")
count = 0
for path in sorted((root / "contracts/fixtures").glob("*.json")):
    payload = json.loads(path.read_text())
    model = ErrorResponse if "error" in payload else AssistantResponse
    model.model_validate(payload)
    Draft202012Validator(model.model_json_schema(), format_checker=FormatChecker()).validate(payload)
    count += 1
print(f"Contracts match; {count} fixtures validated by Pydantic and JSON Schema")

for path in sorted((root / 'contracts/identity-fixtures').glob('*.json')):
    model = identity_models[path.stem]
    payload = json.loads(path.read_text())
    model.model_validate(payload)
    Draft202012Validator(model.model_json_schema(), format_checker=FormatChecker()).validate(payload)
    count += 1
print(f'All contracts match; {count} total fixtures validated')

for path in sorted((root / 'contracts/event-fixtures').glob('*.json')):
    model = event_models[path.stem]
    payload = json.loads(path.read_text())
    model.model_validate(payload)
    Draft202012Validator(model.model_json_schema(), format_checker=FormatChecker()).validate(payload)
    count += 1
print(f'Contracts including events match; {count} total fixtures validated')

for path in sorted((root / 'contracts/room-fixtures').glob('*.json')):
    model=room_models[path.stem.split('--')[0]]
    payload=json.loads(path.read_text())
    model.model_validate(payload)
    Draft202012Validator(model.model_json_schema(),format_checker=FormatChecker()).validate(payload)
    count+=1
print(f'Room contracts match; {count} total fixtures validated')

for path in sorted((root / 'contracts/faculty-fixtures').glob('*.json')):
    model=faculty_models[path.stem.split('--')[0]]
    payload=json.loads(path.read_text())
    model.model_validate(payload)
    Draft202012Validator(model.model_json_schema(),format_checker=FormatChecker()).validate(payload)
    count+=1
print(f'Faculty contracts match; {count} total fixtures validated')

for path in sorted((root / 'contracts/interpretation-fixtures').glob('*.json')):
    payload=json.loads(path.read_text())
    Interpretation.model_validate(payload)
    Draft202012Validator(Interpretation.model_json_schema(),format_checker=FormatChecker()).validate(payload)
    count+=1
print(f'Interpretation contracts match; {count} total fixtures validated')

for path in sorted((root / 'contracts/personal-fixtures').glob('*.json')):
    model=personal_models[path.stem.split('--')[0]]
    payload=json.loads(path.read_text())
    model.model_validate(payload)
    Draft202012Validator(model.model_json_schema(),format_checker=FormatChecker()).validate(payload)
    count+=1
print(f'Personal contracts match; {count} total fixtures validated')

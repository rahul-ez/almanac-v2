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

root = Path("/workspace")
settings = Settings(database_url="postgresql+psycopg://unused:unused@localhost/almanac_test")
outputs = {"openapi.json": create_app(settings).openapi(),
           "assistant-response.schema.json": AssistantResponse.model_json_schema(),
           "error.schema.json": ErrorResponse.model_json_schema()}
identity_models = {'login-request': LoginRequest, 'login-response': LoginResponse,
                   'identity': Identity, 'profile': Profile, 'profile-patch': ProfilePatch,
                   'reference-data': ReferenceData, 'csrf-response': CsrfResponse}
event_models = {'event-create':EventCreate,'event-patch':EventPatch,'event-view':EventView,'event-list':EventList,'event-search':EventSearch,'assistant-request':AssistantRequest}
for name, model in (identity_models | event_models).items():
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

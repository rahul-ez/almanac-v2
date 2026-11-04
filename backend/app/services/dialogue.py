"""Owned, bounded dialogue preparation. State is server-authored and expires after 30 minutes."""
from datetime import timedelta
import re
from app.api.errors import ApiError
from app.schemas.contracts import Meaning
from app.schemas.events import AssistantRequest
from app.nlp.text import normalized

TTL = timedelta(minutes=30)


def prepare(payload, state, expires_at, now):
    expired=expires_at is None or expires_at<=now
    if payload.clarification is not None:
        pending=state.get('pending')
        if expired or not pending or payload.clarification.id!=pending['id']:
            raise ApiError(409,'stale_clarification','Clarification is expired or no longer active; ask a complete question')
        overrides={**pending['overrides'],**payload.context_overrides.model_dump(exclude_unset=True)}
        selected=pending.get('intent')
        text=pending['text']
        if payload.clarification.option_id is not None:
            options={option['id']:option for option in pending['options']}
            option=options.get(payload.clarification.option_id)
            if option is None: raise ApiError(422,'invalid_option','Choose an option from the active clarification')
            if normalized(payload.text) not in {normalized(option['id']),normalized(option['label'])}:
                raise ApiError(422,'invalid_option_text','An option reply must contain its label or ID; send additional constraints in a later turn')
            if pending['field']=='intent': selected=option['id']
            else:
                names={'student_year':'year'}
                overrides[names.get(pending['field'],pending['field'])]=option['id']
        else:
            labels={'faculty_id':{'faculty'},'date':{'date'},'time_interval':{'time_interval'},'date_and_time_interval':{'date','time_interval'}}.get(pending['field'],set())
            masked=list(text)
            for entity in pending.get('entities',[]):
                if entity['label'] in labels: masked[entity['start']:entity['end']]=' '*(entity['end']-entity['start'])
            text=''.join(masked)
            if pending['field'] in {'time_interval','date_and_time_interval'}:
                text=re.sub(r'(?<!\w)(?:from\s+|between\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*(?:to|[-–—]|and)\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)?(?!\w)',' ',text,flags=re.I)
            text+=' '+payload.text
        if len(text)>1000: raise ApiError(422,'dialogue_text_limit','Combined clarification exceeds 1000 characters; ask a new complete question')
        prepared=AssistantRequest(text=text,client_request_id=payload.client_request_id,context_overrides=overrides)
        prior=Meaning.model_validate(pending['prior']) if pending.get('prior') else None
        return prepared,prior,selected,[]
    prior=Meaning.model_validate(state['meaning']) if not expired and state.get('meaning') else None
    warnings=['Conversation context expired; this question is interpreted independently.'] if expired and state else []
    return payload,prior,None,warnings

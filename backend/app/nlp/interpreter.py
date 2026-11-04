"""Pure conservative cross-domain interpreter. A model may supply an intent, never SQL."""
import re
from datetime import datetime,time,timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
from pydantic import ValidationError
from app.schemas.contracts import Meaning,Filters,Interval,ContextValue,Option
from app.schemas.interpretation import Interpretation,ExtractedEntity,Ambiguity,EventExecution,RoomExecution,FacultyExecution
from app.schemas.events import EventSearch
from app.schemas.rooms import AvailabilityQuery
from app.schemas.faculty import OfficeHoursQuery
from app.services.room_time import local_instant
from app.api.errors import ApiError
from app.nlp.text import TextView,normalized

VERSION='campus-rules-v1'
FIELDS={'department':'department_id','topic':'topic','building':'building_id','room':'room_id','facility':'facility_ids','faculty':'faculty_id','venue':'venue'}
ALLOWED={'find_events':{'department','topic','venue'},'find_available_rooms':{'room','building','facility'},'find_faculty_office_hours':{'faculty','department'}}

class Problem(Exception):
    def __init__(self,message,status='unsupported',field=None,options=None,constraint=None):
        self.message=message;self.status=status;self.field=field;self.options=options or [];self.constraint=constraint


def catalog_matches(view,catalog):
    found={}
    for entry in catalog.entries:
        for alias in {normalized(value) for value in [entry.label,*entry.aliases] if value.strip()}:
            if alias in {'today','tomorrow','now','right now','this week','next week','monday','tuesday','wednesday','thursday','friday','saturday','sunday','free','available','room','rooms','event','events','faculty'} or re.fullmatch(r'\d{4}-\d{2}-\d{2}',alias):
                continue  # Reserved syntax cannot be swallowed by an entity alias. Use canonical overrides for such names.
            for match in re.finditer(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',view.text):
                key=(match.start(),match.end(),entry.kind)
                found.setdefault(key,{})[entry.id]=entry
    return [(a,b,kind,list(entries.values())) for (a,b,kind),entries in found.items()]


def choose_intent(view,matches,selected):
    masked=list(view.text)
    for a,b,kind,_ in matches:
        if kind=='building': masked[a:b]=' '*(b-a)
    text=''.join(masked);cues=set()
    if re.search(r'\b(events?|workshops?|seminars?|hackathons?|lectures?)\b',text): cues.add('find_events')
    if re.search(r'\b(rooms?|classrooms?)\b',text): cues.add('find_available_rooms')
    if re.search(r'\b(office hours?|meet|professor|prof|dr|faculty)\b',text): cues.add('find_faculty_office_hours')
    if not cues and re.search(r'\b(free|available)\b',text) and any(kind=='room' for _,_,kind,_ in matches): cues.add('find_available_rooms')
    if len(cues)>1: raise Problem('Ask about one domain at a time; this question combines domains.',constraint='multiple_domains')
    if selected is not None:
        if selected not in ALLOWED: raise Problem('The selected intent is not supported.',constraint='unknown_intent')
        if cues and selected not in cues: raise Problem('The intent prediction contradicts the explicit domain.',constraint='intent_conflict')
        return selected
    if cues: return cues.pop()
    if re.search(r'\bfree\b',text):
        raise Problem('Does free mean a zero-cost event or an unbooked room?',status='clarification_required',field='intent',options=[Option(id='find_events',label='Zero-cost events'),Option(id='find_available_rooms',label='Scheduled room availability')])
    raise Problem('Ask about events, available rooms, or published faculty office hours.',constraint='missing_supported_intent')


def interpret(text,*,catalog,now,campus_timezone,profile=None,overrides=None,selected_intent=None,prior_meaning=None):
    """Only injected catalog/context/clock inputs; no database, network or persistence."""
    view=TextView(text);entities=[];values={};origins={};ambiguities=[];warnings=[];intent=None;meaning=None
    profile=profile or {};overrides=overrides or {};date_window=None;time_window=None
    entries={(entry.kind,entry.id):entry for entry in catalog.entries}
    intent_source='model' if selected_intent is not None else 'rules'
    def entity(a,b,label,value=None,canonical=None,candidates=None):
        # Patterns may consume whitespace masking an already extracted adjacent entity.
        while a<b and (view.used[a] or view.text[a].isspace()): a+=1
        while b>a and (view.used[b-1] or view.text[b-1].isspace()): b-=1
        start,end,original=view.original_span(a,b)
        entities.append(ExtractedEntity(label=label,start=start,end=end,text=original,normalized=value,canonical_id=canonical,candidate_ids=candidates or []))
        view.reserve(a,b)
    def assign(field,value):
        if field=='facility_ids': values.setdefault(field,[]).extend(value);values[field]=sorted(set(values[field]))
        elif field=='max_cost_minor': values[field]=min(values.get(field,value),value)
        elif field in values and values[field]!=value: raise Problem('Use one value for '+field.replace('_',' ')+'.',constraint='contradictory_'+field)
        else: values[field]=value
        origins[field]='explicit_question'
    def consume(pattern,label,field=None,convert=None):
        matches=list(re.finditer(pattern,view.available()))
        for match in matches:
            value=convert(match) if callable(convert) else convert
            if field: assign(field,value)
            entity(match.start(),match.end(),label,value)
        return matches
    def context_value(field,value,origin):
        if value is not None: return ContextValue(field=field,value=value,origin=origin)
    try:
        clear=re.fullmatch(r'\s*(?:clear|remove)\s+(?:the\s+)?(topic|event type|year|department|price|building|room|faculty|capacity|facilities)(?:\s+filter)?[.!?]?\s*',view.text)
        if clear and prior_meaning is not None:
            field={'topic':'topic','event type':'event_type','year':'student_year','department':'department_id','price':'max_cost_minor','building':'building_id','room':'room_id','faculty':'faculty_id','capacity':'capacity','facilities':'facility_ids'}[clear[1]]
            values[field]=[] if field=='facility_ids' else None;origins[field]='explicit_question'
            view.reserve(0,len(view.text))
        matches=catalog_matches(view,catalog)
        try: intent=choose_intent(view,matches,selected_intent)
        except Problem as issue:
            if prior_meaning is not None and (issue.constraint=='missing_supported_intent' or (issue.field=='intent' and prior_meaning.intent in {'find_events','find_available_rooms'})): intent=prior_meaning.intent
            else: raise
        prior=prior_meaning.filters if prior_meaning is not None and prior_meaning.intent==intent else None
        # Longest original span wins; all candidates for that same span remain candidates.
        for a,b,kind,candidates in sorted(matches,key=lambda item:(-(item[1]-item[0]),item[0],item[2])):
            if kind not in ALLOWED[intent] or any(view.used[a:b]): continue
            field=FIELDS[kind]
            ids=sorted({entry.id for entry in candidates})
            if len(ids)>1:
                ambiguities.append(Ambiguity(field=field,prompt='Which '+kind+' do you mean?',options=[Option(id=e.id,label=e.label) for e in sorted(candidates,key=lambda e:e.id)]))
                entity(a,b,kind,None,candidates=ids)
            else:
                value=ids if kind=='facility' else ids[0];assign(field,value)
                entity(a,b,kind,ids[0],canonical=ids[0])
        for kind in ('workshop','seminar','hackathon','lecture'):
            consume(r'\b'+kind+r's?\b','event_type','event_type',kind)
        for pattern,year in [(r'\b(?:first|1st)[ -]years?\b',1),(r'\b(?:second|2nd)[ -]years?\b',2),(r'\b(?:third|3rd)[ -]years?\b',3),(r'\b(?:fourth|4th)[ -]years?\b',4)]:
            consume(pattern,'student_year','student_year',year)
        consume(r'\byear\s+([1-4])\b','student_year','student_year',lambda m:int(m[1]))
        consume(r'\b(?:for\s+|at least\s+|capacity\s+)?(\d{1,6})\s*(?:students|people|seats)\b','capacity','capacity',lambda m:int(m[1]))
        consume(r'\bcapacity\s+(\d{1,6})\b','capacity','capacity',lambda m:int(m[1]))
        money=r'\b(under|below|less than|up to|at most)\s*(?:(?:rs\.?|inr)\s*|₹\s*)(\d+(?:\.\d{1,2})?)(?:\s*(?:rupees|rs|inr))?'
        def cost(match):
            amount=int(Decimal(match[2])*100)-(1 if match[1] in {'under','below','less than'} else 0)
            if not 0<=amount<=100000000: raise Problem('Price constraint is outside supported bounds.',constraint='invalid_cost')
            return amount
        consume(money,'cost','max_cost_minor',cost)
        consume(r'\b(under|below|less than|up to|at most)\s*(\d+(?:\.\d{1,2})?)\s*(?:rupees|rs\.?|inr)\b','cost','max_cost_minor',cost)
        if intent=='find_events': consume(r'\bfree\b','cost','max_cost_minor',0)
        local=now.astimezone(ZoneInfo(campus_timezone));midnight=datetime.combine(local.date(),time.min,tzinfo=local.tzinfo)
        monday=midnight-timedelta(days=local.weekday())
        date_hits=[]
        for phrase,window in [('today',(midnight,midnight+timedelta(days=1))),('tomorrow',(midnight+timedelta(days=1),midnight+timedelta(days=2))),
                              ('this week',(monday,monday+timedelta(days=7))),('next week',(monday+timedelta(days=7),monday+timedelta(days=14)))]:
            for match in list(re.finditer(r'\b'+phrase+r'\b',view.available())):
                date_hits.append((window,phrase));entity(match.start(),match.end(),'date',window[0].isoformat()+'/'+window[1].isoformat())
        for match in list(re.finditer(r'\b\d{4}-\d{2}-\d{2}\b',view.available())):
            try: day=datetime.strptime(match[0],'%Y-%m-%d').date()
            except ValueError: raise Problem('Use a valid YYYY-MM-DD date.',constraint='invalid_date') from None
            start=datetime.combine(day,time.min,tzinfo=local.tzinfo);window=(start,start+timedelta(days=1))
            date_hits.append((window,'date'));entity(match.start(),match.end(),'date',window[0].isoformat()+'/'+window[1].isoformat())
        weekdays=[]
        for index,day in enumerate(('monday','tuesday','wednesday','thursday','friday','saturday','sunday')):
            for match in list(re.finditer(r'\b'+day+r'\b',view.available())):
                weekdays.append((index,match.start(),match.end()))
        if len(date_hits)>1 or len(weekdays)>1: raise Problem('Use one unambiguous date range.',constraint='contradictory_dates')
        if weekdays:
            index,a,b=weekdays[0]
            if date_hits:
                window,phrase=date_hits[0]
                if phrase not in {'this week','next week'}: raise Problem('Date expressions conflict.',constraint='contradictory_dates')
                start=window[0]+timedelta(days=index)
            elif prior and prior.interval and prior.interval.end-prior.interval.start==timedelta(days=7) and prior.interval.start.astimezone(local.tzinfo).weekday()==0:
                start=prior.interval.start.astimezone(local.tzinfo)+timedelta(days=index)
            else: start=midnight+timedelta(days=(index-local.weekday())%7)
            date_window=(start,start+timedelta(days=1));entity(a,b,'date',date_window[0].isoformat()+'/'+date_window[1].isoformat())
        elif date_hits: date_window=date_hits[0][0]
        now_matches=list(re.finditer(r'\b(?:right now|now)\b',view.available()))
        if len(now_matches)>1 or (now_matches and date_window): raise Problem('Now conflicts with the supplied date.',constraint='contradictory_dates')
        now_query=bool(now_matches)
        for match in now_matches: entity(match.start(),match.end(),'date',now.isoformat())
        def clock(raw,meridiem,twenty_four=False):
            hour,minute=(map(int,raw.split(':')) if ':' in raw else (int(raw),0))
            if minute>59: raise Problem('Minutes must be between 00 and 59.',constraint='invalid_time')
            if meridiem:
                if not 1<=hour<=12: raise Problem('AM/PM hours must be 1–12.',constraint='invalid_time')
                hour=hour%12+(12 if meridiem=='pm' else 0)
            elif not twenty_four: raise Problem('Use explicit AM/PM or 24-hour HH:MM for both endpoints.',status='clarification_required',field='time_interval')
            if hour>24 or (hour==24 and minute): raise Problem('Invalid 24-hour time.',constraint='invalid_time')
            return hour*60+minute
        pattern=r'(?<!\w)(?:from\s+|between\s+)?(\d{1,2}(?::\d{2})?)\s*(am|pm)?\s*(?:to|[-–—]|and)\s*(\d{1,2}(?::\d{2})?)\s*(am|pm)?(?!\w)'
        time_hits=list(re.finditer(pattern,view.available()))
        if len(time_hits)>1 or (time_hits and now_query): raise Problem('Use one requested time interval.',constraint='contradictory_times')
        if time_hits:
            match=time_hits[0];left,right=match[1],match[3];ap,bp=match[2],match[4]
            if ap or bp: ap=ap or bp;bp=bp or ap
            use24=':' in left or ':' in right or int(left.split(':')[0])>12 or int(right.split(':')[0])>12
            a,b=clock(left,ap,use24),clock(right,bp,use24)
            if a>=1440 or b<=a: raise Problem('Use an increasing same-day interval with explicit AM/PM; overnight requests need separate dates.',status='clarification_required',field='time_interval')
            time_window=(a,b);entity(match.start(),match.end(),'time_interval',f'{a//60:02}:{a%60:02}/{b//60:02}:{b%60:02}')
        wants_eligible=bool(re.search(r'\b(?:for me|can i attend|eligible)\b',view.available()))
        # Remove known grammar only. Any remaining constraint blocks execution.
        remaining=view.available()
        grammar=r"\b(?:any|show|find|list|what|which|are|is|there|happening|upcoming|the|on|in|for|please|only|a|an|events?|rooms?|classrooms?|available|free|with|when|can|i|meet|professor|prof|dr|faculty|office|hours?|me|attend|eligible|at)\b"
        remaining=re.sub(grammar,' ',remaining)
        remaining=re.sub(r"(?:'s|’s)\b",' ',remaining)
        if intent=='find_available_rooms' and len(values.get('facility_ids',[]))>1: remaining=re.sub(r'\band\b',' ',remaining)
        remaining=re.sub(r'[?!.,;]',' ',remaining).strip()
        if remaining: raise Problem('This interpreter could not safely interpret every constraint. Rephrase using supported dates, times and campus names.',constraint=remaining)
        explicit=set(values)
        allowed_fields={'find_events':{'event_type','topic','department_id','venue','student_year','max_cost_minor'},
                        'find_available_rooms':{'room_id','building_id','facility_ids','capacity'},
                        'find_faculty_office_hours':{'faculty_id','department_id'}}[intent]
        if set(values)-allowed_fields: raise Problem('Some constraints do not apply to this domain.',constraint='invalid_domain_filters')
        override_map={'year':'student_year','department_id':'department_id','faculty_id':'faculty_id','room_id':'room_id','building_id':'building_id','capacity':'capacity','facility_ids':'facility_ids'}
        for name,field in override_map.items():
            if name in overrides and overrides[name] is not None and field not in allowed_fields:
                raise Problem('A request override does not apply to this domain.',constraint='invalid_override_'+name)
            if field in allowed_fields and field not in values:
                if name in overrides: values[field]=overrides[name];origins[field]='override'
                elif prior is not None:
                    values[field]=getattr(prior,field);origins[field]='prior_turn'
                elif intent=='find_events' and field in {'student_year','department_id'} and profile.get(field) is not None:
                    values[field]=profile[field];origins[field]='profile'
        if prior is not None:
            for field in allowed_fields:
                if field not in values:
                    values[field]=getattr(prior,field);origins[field]='prior_turn'
        for field,kind in [('department_id','department'),('topic','topic'),('building_id','building'),('room_id','room'),('faculty_id','faculty'),('venue','venue')]:
            if values.get(field) is not None and (kind,values[field]) not in entries: raise Problem('Unknown canonical '+kind+' in context.',constraint='unknown_'+field)
        if any(('facility',value) not in entries for value in (values.get('facility_ids') or [])): raise Problem('Unknown facility in request context.',constraint='unknown_facility')
        # A supplied canonical ID can disambiguate a matching explicit name, but cannot contradict it.
        pending=[]
        for ambiguity in ambiguities:
            candidates=[option for option in ambiguity.options if ambiguity.field!='faculty_id' or not values.get('department_id') or entries[('faculty',option.id)].department_id==values['department_id']]
            selected=values.get(ambiguity.field)
            if selected:
                if selected not in [option.id for option in candidates]: raise Problem('Selected ID contradicts the named entity.',constraint='conflicting_canonical_id')
            elif len(candidates)==1: values[ambiguity.field]=candidates[0].id;origins[ambiguity.field]='explicit_question'
            else: pending.append(Ambiguity(field=ambiguity.field,prompt=ambiguity.prompt,options=candidates))
        ambiguities=pending
        if intent=='find_faculty_office_hours' and values.get('faculty_id') and values.get('department_id') and entries[('faculty',values['faculty_id'])].department_id!=values['department_id']:
            raise Problem('The named faculty does not match the department constraint.',constraint='faculty_department_conflict')
        if ambiguities:
            issue=ambiguities[0];raise Problem(issue.prompt,status='clarification_required',field=issue.field,options=issue.options)
        if intent=='find_faculty_office_hours' and not values.get('faculty_id'):
            raise Problem('Which faculty member do you mean?',status='clarification_required',field='faculty_id')
        if time_window and date_window is None and prior and prior.interval and prior.interval.end.astimezone(local.tzinfo).date()==prior.interval.start.astimezone(local.tzinfo).date():
            base=datetime.combine(prior.interval.start.astimezone(local.tzinfo).date(),time.min,tzinfo=local.tzinfo)
            date_window=(base,base+timedelta(days=1))
        if date_window and not time_window and prior and prior.interval and intent=='find_available_rooms':
            old_start=prior.interval.start.astimezone(local.tzinfo);old_end=prior.interval.end.astimezone(local.tzinfo)
            if old_start.date()==old_end.date() and date_window[1]-date_window[0]==timedelta(days=1):
                time_window=(old_start.hour*60+old_start.minute,old_end.hour*60+old_end.minute)
        if now_query:
            start,end=now,now+timedelta(minutes=30);origin='explicit_question';warnings.append('“Now” is interpreted as the next 30 minutes.')
        elif time_window:
            if date_window is None: raise Problem('Which date is the requested time interval on?',status='clarification_required',field='date')
            if date_window[1]-date_window[0]>timedelta(days=1): raise Problem('Use one date with a daily time interval.',status='clarification_required',field='date')
            naive=datetime.combine(date_window[0].date(),time.min)
            try:
                start=local_instant(naive+timedelta(minutes=time_window[0]),local.tzinfo)
                end=local_instant(naive+timedelta(minutes=time_window[1]),local.tzinfo)
            except ApiError: raise Problem('This local time is ambiguous or nonexistent; provide another interval.',status='clarification_required',field='time_interval') from None
            origin='explicit_question'
        elif date_window is None and prior and prior.interval:
            start,end=prior.interval.start,prior.interval.end;origin='prior_turn'
        elif intent=='find_available_rooms':
            raise Problem('Supply a date and start/end time, or say “right now”.',status='clarification_required',field='time_interval' if date_window else 'date_and_time_interval')
        elif date_window:
            start,end=date_window;origin='explicit_question'
        else:
            start,end=now,now+timedelta(days=30 if intent=='find_events' else 7);origin='default'
            warnings.append('No date supplied; using the next '+('30' if intent=='find_events' else '7')+' days.')
        if intent!='find_events':
            if end<=now or (time_window and start<now): raise Problem('Use a future interval within the next 30 days.',status='clarification_required',field='date_and_time_interval')
            if start<now:
                start=now;warnings.append('Only the remaining portion of this date range is queried from the current server time.')
            if end>now+timedelta(days=30): raise Problem('Use a window within the next 30 days.',status='clarification_required',field='date')
        interval=Interval(start=start,end=end);origins['interval']=origin
        if intent=='find_events': values['eligible_only']=wants_eligible or 'student_year' in explicit or 'department_id' in explicit or bool(prior and prior.eligible_only)
        if intent=='find_available_rooms':
            values['capacity']=values.get('capacity') or 1;origins.setdefault('capacity','default');values['facility_ids']=values.get('facility_ids') or []
        filters=Filters(**values,interval=interval);meaning=Meaning(intent=intent,filters=filters)
        if intent=='find_events': execution=EventExecution(query=EventSearch(from_at=start,to_at=end,event_type=filters.event_type,topic_id=filters.topic,venue=filters.venue,
            student_year=filters.student_year,department_id=filters.department_id,max_cost_minor=filters.max_cost_minor,eligible_only=filters.eligible_only,limit=20))
        elif intent=='find_available_rooms': execution=RoomExecution(query=AvailabilityQuery(from_at=start,to_at=end,building_id=filters.building_id,min_capacity=filters.capacity,
            facility_ids=filters.facility_ids,limit=100),room_id=filters.room_id)
        else: execution=FacultyExecution(query=OfficeHoursQuery(from_at=start,to_at=end,limit=20),faculty_id=filters.faculty_id)
        applied=[value for field,val in values.items() if (value:=context_value(field,val,origins.get(field,'default'))) is not None]
        applied.append(ContextValue(field='interval',value=[start.isoformat(),end.isoformat()],origin=origin))
        return Interpretation(status='ready',intent=intent,meaning=meaning,execution=execution,entities=sorted(entities,key=lambda e:e.start),applied_context=applied,
            message='Validated '+intent.replace('_',' ')+'.',warnings=warnings,intent_source=intent_source)
    except Problem as issue:
        if issue.status=='clarification_required' and not ambiguities:
            ambiguities=[Ambiguity(field=issue.field,prompt=issue.message,options=issue.options)]
        return Interpretation(status=issue.status,intent=intent,meaning=None,execution=None,entities=sorted(entities,key=lambda e:e.start),applied_context=[],
            missing_fields=[issue.field] if issue.field and not issue.options else [],ambiguities=ambiguities if issue.status=='clarification_required' else [],
            unsupported_constraints=[issue.constraint] if issue.constraint else [],message=issue.message,warnings=warnings,intent_source=intent_source)
    except (ValidationError,ValueError) as exc:
        return Interpretation(status='unsupported',intent=intent,meaning=None,execution=None,entities=sorted(entities,key=lambda e:e.start),applied_context=[],
            unsupported_constraints=['invalid_normalized_constraints'],message='A normalized constraint is invalid or outside supported bounds.',warnings=warnings,intent_source=intent_source)

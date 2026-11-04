"""Frozen synthetic semantic/retrieval benchmark. Does not fit, tune or update an artifact."""
import hashlib
import json
import os
import platform
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from time import perf_counter
import numpy as np
from sklearn.metrics import classification_report,confusion_matrix
from app.nlp.interpreter import VERSION
from app.nlp.pipeline import interpret_catalog
from app.nlp.intent_model import LABELS,load_model
from app.schemas.contracts import Meaning
from app.schemas.interpretation import Interpretation
from app.services.execute_meaning import execute_interpretation


def source_digest(root):
    root=Path(root);digestor=hashlib.sha256()
    for path in sorted([*root.glob('backend/app/**/*.py'),*root.glob('scripts/*.py')]):
        digestor.update(path.relative_to(root).as_posix().encode()+b'\0'+path.read_bytes().replace(b'\r\n',b'\n')+b'\0')
    return digestor.hexdigest()

def digest(path): return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n',b'\n')).hexdigest()

def canonical(value):
    if isinstance(value,datetime): return value.astimezone(timezone.utc).isoformat()
    if isinstance(value,dict): return {k:canonical(v) for k,v in value.items()}
    if isinstance(value,list): return [canonical(v) for v in value]
    return value

def result_key(card):
    data=card.model_dump()
    return canonical({'kind':data['kind'],'record_id':data['record_id'],'interval':data.get('interval',data.get('requested_interval'))})

def expected_keys(case):
    return [canonical({**item,'interval':{key:datetime.fromisoformat(value) for key,value in item['interval'].items()}}) for item in case['results']]

def metrics(tp,fp,fn):
    precision=tp/(tp+fp) if tp+fp else 0.
    recall=tp/(tp+fn) if tp+fn else 0.
    return {'precision':precision,'recall':recall,'f1':2*precision*recall/(precision+recall) if precision+recall else 0.,'tp':tp,'fp':fp,'fn':fn}

def score_case(case,report,cards,answer_status):
    gold=Meaning.model_validate(case['meaning']) if case['meaning'] else None
    actual=report.meaning
    expected_status=case['expected_interpretation']
    interval_slots=[]
    if gold:
        for field in case['meaning']['filters']:
            interval_slots.append((field,actual is not None and canonical(actual.filters.model_dump()[field])==canonical(gold.filters.model_dump()[field])))
    expected_entities={(e['start'],e['end'],e['label']) for e in case['entities']} if case['entities'] is not None else None
    predicted_entities={(e.start,e.end,e.label) for e in report.entities}
    spans=None if expected_entities is None else {'tp':len(expected_entities & predicted_entities),'fp':len(predicted_entities-expected_entities),'fn':len(expected_entities-predicted_entities)}
    results=sorted([result_key(card) for card in cards],key=lambda x:json.dumps(x,sort_keys=True))
    expected=sorted(expected_keys(case),key=lambda x:json.dumps(x,sort_keys=True))
    clarify_ok=expected_status!='clarification_required' or (bool(report.ambiguities) and report.ambiguities[0].field==case['clarification_field'])
    answer_ok=answer_status==case['answer_status'] and results==expected and clarify_ok
    return {'id':case['id'],'text':case['text'],'expected_meaning':canonical(gold.model_dump()) if gold else None,
        'actual_meaning':canonical(actual.model_dump()) if actual else None,'expected_entities':case['entities'],
        'actual_entities':[e.model_dump(mode='json') for e in report.entities],'intent_confidence':report.intent_confidence,
        'interpretation_correct':report.status==expected_status,'meaning_correct':actual==gold if gold else None,
        'normalization_slots':interval_slots,'entities':spans,'end_to_end_correct':answer_ok,
        'false_answer':case['answer_status']!='answered' and answer_status=='answered',
        'expected_status':case['answer_status'],'actual_status':answer_status,'expected_results':expected,'actual_results':results,
        'error_types':(['intent'] if case['intent']!=report.intent and expected_status!='unsupported' else [])+
            (['interpretation_status'] if report.status!=expected_status else [])+(['query_semantics'] if gold and actual!=gold else [])+
            (['extraction'] if spans and (spans['fp'] or spans['fn']) else [])+(['retrieval_or_interval'] if expected!=results else [])+
            (['clarification'] if not clarify_ok else [])}


def validate_suite(root):
    root=Path(root);manifest=json.loads((root/'data/evaluation/manifest.json').read_text())
    expected_files={'data/evaluation/semantic-smoke.json','data/demo/campus-events.json','data/demo/rooms.json','data/demo/faculty.json'}
    if set(manifest['files'])!=expected_files: raise ValueError('Unexpected evaluation manifest paths')
    for name,expected in manifest['files'].items():
        if digest(root/name)!=expected: raise ValueError('Frozen evaluation checksum mismatch: '+name)
    suite=json.loads((root/'data/evaluation/semantic-smoke.json').read_text())
    ids=set()
    for case in suite['cases']:
        if case['id'] in ids or not 1<=len(case['text'])<=1000: raise ValueError('Invalid or duplicate evaluation question')
        ids.add(case['id'])
        if case['meaning']: Meaning.model_validate(case['meaning'])
        if case['prior_meaning']: Meaning.model_validate(case['prior_meaning'])
        if case['entities'] is not None:
            for entity in case['entities']:
                if not 0<=entity['start']<entity['end']<=len(case['text']): raise ValueError('Gold entity span out of bounds')
    return suite,manifest


def evaluate(conn,catalog,root,model_path,repeats=3):
    if not 1<=repeats<=20: raise ValueError('Use 1–20 benchmark repeats')
    suite,manifest=validate_suite(root);clock=datetime.fromisoformat(suite['clock']);zone=suite['campus_timezone']
    start=perf_counter();model=load_model(model_path);model_load_ms=(perf_counter()-start)*1000
    outputs={}
    for mode in ('baseline','hybrid'):
        scored=[];times=[];y_true=[];y_pred=[]
        per_type={};reject_counts=Counter()
        for repeat in range(repeats+1):
            for case in suite['cases']:
                start=perf_counter();prior=Meaning.model_validate(case['prior_meaning']) if case['prior_meaning'] else None
                report=interpret_catalog(case['text'],catalog=catalog,now=clock,campus_timezone=zone,
                    nlp_mode=mode,intent_model=model if mode=='hybrid' else None,prior_meaning=prior)
                cards=[];answer_status=report.status
                if report.status=='ready': cards,answer_status,_,_,_=execute_interpretation(conn,report,catalog,clock)
                duration=(perf_counter()-start)*1000
                if repeat: times.append(duration);continue
                score=score_case(case,report,cards,answer_status);scored.append(score)
                if case['intent'] is not None or case['expected_interpretation']=='unsupported':
                    y_true.append(case['intent'] if case['expected_interpretation']!='unsupported' else 'unsupported')
                    y_pred.append(report.intent if report.status!='unsupported' and report.intent else 'unsupported')
                wanted=case['expected_interpretation']!='ready';predicted=report.status!='ready'
                reject_counts['tp' if wanted and predicted else 'fp' if predicted else 'fn' if wanted else 'tn']+=1
                if case['entities'] is not None:
                    gold={(e['start'],e['end'],e['label']) for e in case['entities']};actual={(e.start,e.end,e.label) for e in report.entities}
                    for label in {e[2] for e in gold|actual}:
                        counts=per_type.setdefault(label,Counter());g={e for e in gold if e[2]==label};a={e for e in actual if e[2]==label}
                        counts.update(tp=len(g&a),fp=len(a-g),fn=len(g-a))
        total=Counter()
        for counts in per_type.values(): total.update(counts)
        slots=[slot for score in scored for slot in score['normalization_slots']]
        ready=[s for s in scored if s['meaning_correct'] is not None]
        outputs[mode]={'case_count':len(scored),'intent':classification_report(y_true,y_pred,labels=LABELS,output_dict=True,zero_division=0),
            'intent_confusion':{'labels':list(LABELS),'counts':confusion_matrix(y_true,y_pred,labels=LABELS).tolist()},
            'entity_exact_span_type':{'scored_cases':sum(c['entities'] is not None for c in suite['cases']),'overall':metrics(total['tp'],total['fp'],total['fn']),
                'per_type':{k:metrics(v['tp'],v['fp'],v['fn']) for k,v in sorted(per_type.items())}},
            'normalization':{'correct':sum(ok for _,ok in slots),'gold_slot_count':len(slots),
                'by_field':{field:{'correct':sum(ok for name,ok in slots if name==field),'total':sum(name==field for name,_ in slots)} for field in sorted({name for name,_ in slots})}},
            'meaning_exact':{'correct':sum(s['meaning_correct'] for s in ready),'gold_ready_count':len(ready)},
            'end_to_end':{'correct':sum(s['end_to_end_correct'] for s in scored),'total':len(scored),'false_answers':sum(s['false_answer'] for s in scored)},
            'uncertain_input_detection':metrics(reject_counts['tp'],reject_counts['fp'],reject_counts['fn']),
            'warm_latency_ms':{'count':len(times),'median':float(np.median(times)),'p95':float(np.percentile(times,95)),'max':max(times)},
            'cases':scored}
    return {'suite_version':suite['version'],'clock':suite['clock'],'campus_timezone':zone,'synthetic':True,
        'limitations':['Author-written regression gold; not an independently reviewed or held-out student corpus.',
            'No model fitting or tuning occurs here. Prototype intent-training questions are a separate corpus.',
            'Entity scores use only cases with complete gold span lists; normalization uses explicitly specified gold slots.',
            'End-to-end checks status, complete result IDs and intervals, and requested clarification field against fixed PostgreSQL records.',
            'Prior-meaning cases test semantic transitions; active clarification/session/privacy transport is covered by HTTP acceptance and regression tests.',
            'Warm measurements include interpreter and typed retrieval on this small synthetic database; not a production load test.'],
        'manifest':manifest,'source_sha256':source_digest(root),'model_training_corpus_sha256':model.artifact.dataset_sha256,'interpreter_version':VERSION,'model_version':model.version,'model_sha256':digest(model_path),
        'requirements_sha256':digest(Path(root)/'backend/requirements.lock'),
        'runtime':{'python':platform.python_version(),'platform':platform.platform(),'machine':platform.machine(),'logical_cpus':os.cpu_count()},
        'artifact_load_ms':model_load_ms,'modes':outputs}

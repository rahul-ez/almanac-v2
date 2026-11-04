"""Creates and drops only a unique evaluation database. Existing demo data is untouched."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from app.config import Settings
from app.db.connection import make_engine
from app.nlp.catalog import load_catalog
from app.nlp.evaluation import evaluate,validate_suite
from app.nlp.evaluation_records import load_records
from datetime import datetime

parser=argparse.ArgumentParser()
parser.add_argument('--model',default='/workspace/.local/models/intent.json')
parser.add_argument('--output',default='/workspace/reports/phase-7/semantic-evaluation.json')
parser.add_argument('--check',action='store_true')
args=parser.parse_args()
root=Path('/workspace');suite,_=validate_suite(root)
url=make_url(Settings().database_url.get_secret_value())
name='almanac_eval_'+uuid4().hex
admin=create_engine(url.set(database='postgres'),isolation_level='AUTOCOMMIT')
created=False;engine=None
try:
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'));created=True
    target=url.set(database=name).render_as_string(hide_password=False)
    env=dict(os.environ,DATABASE_URL=target,NLP_MODE='baseline')
    migration=subprocess.run(['alembic','upgrade','head'],env=env,capture_output=True,text=True)
    if migration.returncode: raise SystemExit('Disposable evaluation database migration failed; no credentials printed')
    engine=make_engine(Settings(database_url=target))
    with engine.begin() as conn:
        load_records(conn,root,datetime.fromisoformat(suite['clock']),suite['campus_timezone'])
    with engine.connect() as conn:
        report=evaluate(conn,load_catalog(conn),root,args.model)
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n')
    for mode,data in report['modes'].items():
        print(json.dumps({'mode':mode,'end_to_end':data['end_to_end'],'meaning_exact':data['meaning_exact'],
            'entity_span_type':data['entity_exact_span_type']['overall'],'warm_latency_ms':data['warm_latency_ms']}))
    baseline=report['modes']['baseline']
    if args.check and (baseline['end_to_end']['correct']!=baseline['end_to_end']['total'] or
        baseline['meaning_exact']['correct']!=baseline['meaning_exact']['gold_ready_count'] or
        baseline['entity_exact_span_type']['overall']['fp'] or baseline['entity_exact_span_type']['overall']['fn'] or
        any(data['end_to_end']['false_answers'] for data in report['modes'].values())):
        raise SystemExit('Semantic regression gate failed; inspect the saved per-case errors')
finally:
    if engine is not None: engine.dispose()
    if created:
        with admin.connect() as conn: conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
    admin.dispose()

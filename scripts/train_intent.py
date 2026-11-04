"""Explicit offline training; never executed during application startup or requests."""
import argparse
import json
from app.nlp.training import train
parser=argparse.ArgumentParser()
parser.add_argument('--dataset',default='/workspace/data/annotations/prototype/intent-pilot.jsonl')
parser.add_argument('--output',default='/workspace/.local/models/intent.json')
parser.add_argument('--reports',default='/workspace/reports/phase-5')
args=parser.parse_args()
report=train(args.dataset,args.output,args.reports)
print(json.dumps({'model_version':report['model_version'],'synthetic_only':report['synthetic_only'],
    'partitions':report['partitions'],'selection':report['selection'],'holdout':report['holdout'],
    'limitations':report['limitations']},indent=2))

"""Offline group-aware training. Holdout results never participate in selection."""
import hashlib
import json
import random
from collections import Counter
from pathlib import Path
import numpy as np
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.pipeline import Pipeline
from app.nlp.intent_model import Artifact, IntentModel, LABELS
from app.nlp.text import normalized


def grouped_split(rows, seed=42):
    if not rows or len(rows)>100000:
        raise ValueError('Dataset must contain 1–100000 questions')
    ids = set(); parent = list(range(len(rows))); seen = {}; text_labels = {}
    def find(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]]; i=parent[i]
        return i
    for i,row in enumerate(rows):
        if not isinstance(row.get('id'),str) or not row['id'] or row['id'] in ids:
            raise ValueError('Question IDs must be unique nonempty strings')
        ids.add(row['id'])
        if row.get('intent') not in LABELS or not isinstance(row.get('text'),str) or not 1<=len(row['text'])<=1000 or not row['text'].strip():
            raise ValueError('Each question needs bounded text and a supported intent label')
        family=row.get('paraphrase_family_id')
        if not isinstance(family,str) or not family:
            raise ValueError('Every question requires a paraphrase family')
        canonical_text=normalized(row['text'])
        if canonical_text in text_labels and text_labels[canonical_text]!=row['intent']:
            raise ValueError('Normalized duplicate questions have conflicting intent labels')
        text_labels[canonical_text]=row['intent']
        keys=[('family',family),('text',canonical_text)]
        conversation=row.get('conversation_group_id')
        if conversation is not None:
            if not isinstance(conversation,str) or not conversation:
                raise ValueError('Conversation groups must be nonempty strings or null')
            keys.append(('conversation',conversation))
        for key in keys:
            if key in seen: parent[find(i)]=find(seen[key])
            else: seen[key]=i
    groups={}
    for i in range(len(rows)): groups.setdefault(find(i),[]).append(i)
    groups=sorted(groups.values(),key=lambda group:min(rows[i]['id'] for i in group))
    if any(sum(any(rows[i]['intent']==label for i in group) for group in groups)<3 for label in LABELS):
        raise ValueError('Each class needs at least three independent connected groups')
    rng=random.Random(seed); best=None
    # Group membership is immutable. Search only for class coverage and partition sizes, never model scores.
    for _ in range(5000):
        shuffled=list(groups);rng.shuffle(shuffled)
        n_test=max(4,round(len(groups)*.15));n_val=max(4,round(len(groups)*.15))
        if n_test+n_val>=len(groups): continue
        parts={'test':shuffled[:n_test],'validation':shuffled[n_test:n_test+n_val],'train':shuffled[n_test+n_val:]}
        split={name:sorted(i for group in values for i in group) for name,values in parts.items()}
        if any({rows[i]['intent'] for i in indices}!=set(LABELS) for indices in split.values()): continue
        error=sum(abs(len(split[name])/len(rows)-target) for name,target in [('train',.7),('validation',.15),('test',.15)])
        if best is None or error<best[0]: best=(error,split)
    if best is None: raise ValueError('Cannot split connected groups with all classes in every partition')
    return best[1]


def train(dataset, output, report_dir):
    raw=Path(dataset).read_bytes().replace(b'\r\n',b'\n');digest=hashlib.sha256(raw).hexdigest()
    report_dir=Path(report_dir)
    manifest_path=report_dir/'intent-split.json'
    if manifest_path.exists() and json.loads(manifest_path.read_text()).get('dataset_sha256')!=digest:
        raise ValueError('Existing split is frozen for a different dataset; select a new report directory')
    rows=[json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    split=grouped_split(rows)
    def texts(name): return [normalized(rows[i]['text']) for i in split[name]]
    def labels(name): return [rows[i]['intent'] for i in split[name]]
    best=None
    for strength in (.5,1.,2.):
        pipeline=Pipeline([('tfidf',TfidfVectorizer(ngram_range=(1,2),lowercase=False,max_features=20000)),
            ('classifier',LogisticRegression(C=strength,random_state=42,max_iter=1000))])
        pipeline.fit(texts('train'),labels('train'))
        probabilities=pipeline.predict_proba(texts('validation'));classes=pipeline.classes_
        for threshold in (.35,.45,.55,.65,.75):
            predicted=[classes[int(p.argmax())] if p.max()>=threshold else 'unsupported' for p in probabilities]
            score=f1_score(labels('validation'),predicted,labels=LABELS,average='macro',zero_division=0)
            rank=(score,threshold,-strength)
            if best is None or rank>best[0]: best=(rank,pipeline,strength,threshold)
    rank,pipeline,strength,threshold=best
    vectorizer=pipeline.named_steps['tfidf'];classifier=pipeline.named_steps['classifier']
    payload=dict(format='almanac-intent-v1',sklearn_version=sklearn.__version__,dataset_sha256=digest,
        classes=classifier.classes_.tolist(),vocabulary={k:int(v) for k,v in vectorizer.vocabulary_.items()},
        idf=vectorizer.idf_.tolist(),coefficients=classifier.coef_.tolist(),intercept=classifier.intercept_.tolist(),confidence_threshold=threshold)
    version=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()[:12]
    artifact=Artifact(**payload,model_version='tfidf-'+version);runtime=IntentModel(artifact)
    # Export parity is a numerical invariant, not a model-quality score or selection criterion.
    assert np.allclose(runtime.probabilities(texts('test')),pipeline.predict_proba(texts('test')),rtol=1e-10,atol=1e-12)
    predicted=[runtime.predict(rows[i]['text'])[0] for i in split['test']]
    from app.nlp.interpreter import choose_intent, Problem
    from app.nlp.text import TextView
    baseline=[]
    for i in split['test']:
        try: baseline.append(choose_intent(TextView(rows[i]['text']), [], None))
        except Problem: baseline.append('unsupported')
    report=dict(model_version=artifact.model_version,dataset_sha256=digest,synthetic_only=all(r.get('synthetic') is True for r in rows),
        limitations=['Small synthetic prototype; not a student-data accuracy claim.','Paraphrase/conversation/duplicate connected groups remain intact.',
            'Actual split fractions differ from 70/15/15 because class coverage requires whole groups.','Final independent test corpus must be frozen before production tuning.'],
        selection={'C':strength,'threshold':threshold,'validation_macro_f1':rank[0]},
        partitions={name:{'count':len(indices),'fraction':len(indices)/len(rows),'class_counts':dict(Counter(rows[i]['intent'] for i in indices))} for name,indices in split.items()},
        keyword_baseline_holdout=classification_report(labels('test'),baseline,labels=LABELS,output_dict=True,zero_division=0),
        holdout=classification_report(labels('test'),predicted,labels=LABELS,output_dict=True,zero_division=0),
        confusion_matrix={'labels':list(LABELS),'counts':confusion_matrix(labels('test'),predicted,labels=LABELS).tolist()})
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    encoded=(artifact.model_dump_json(indent=2)+'\n').encode()
    output.write_bytes(encoded);output.with_suffix('.sha256').write_text(hashlib.sha256(encoded).hexdigest()+'\n')
    report_dir=Path(report_dir);report_dir.mkdir(parents=True,exist_ok=True)
    manifest={'dataset_sha256':digest,'seed':42,'partitions':{name:[rows[i]['id'] for i in indices] for name,indices in split.items()}}
    (report_dir/'intent-split.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (report_dir/'intent-evaluation.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

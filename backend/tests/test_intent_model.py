import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from app.config import Settings
from app.main import create_app
from app.nlp.intent_model import Artifact, IntentModel, LABELS, load_model
from app.nlp.text import normalized
from app.nlp.training import grouped_split, train
from test_identity import env, headers


def examples():
    # Every family is independent; strings are deliberately distinct, including the label token.
    return [dict(id=f'{label}-{group}-{i}',text=f'{label} question family{group} variant{i}',intent=label,
        paraphrase_family_id=f'{label}-{group}',conversation_group_id=None,synthetic=True)
        for label in LABELS for group in range(4) for i in range(2)]


def test_split_keeps_transitive_conversation_family_and_duplicates_together():
    rows=examples()
    rows[2]['conversation_group_id']='linked-conversation'
    rows[4]['conversation_group_id']='linked-conversation'
    # Different families now connected by a normalized duplicate as well.
    rows[5]['text']=rows[0]['text'].upper()
    # Add enough groups for the merged class to retain train/validation/test support.
    rows.extend([dict(id=f'extra-{i}',text=f'event extra group{i}',intent='find_events',
        paraphrase_family_id=f'extra-{i}',conversation_group_id=None) for i in range(3)])
    split=grouped_split(rows)
    assert split==grouped_split(rows)
    where={index:name for name,indices in split.items() for index in indices}
    assert len({where[i] for i in range(6)})==1
    assert len(where)==len(rows)
    for indices in split.values(): assert {rows[i]['intent'] for i in indices}==set(LABELS)


def test_dataset_rejects_duplicate_ids_and_insufficient_independent_groups():
    rows=examples();rows[1]['id']=rows[0]['id']
    with pytest.raises(ValueError,match='IDs'): grouped_split(rows)
    rows=examples()
    for row in rows: row['paraphrase_family_id']=row['intent']
    with pytest.raises(ValueError,match='three independent'): grouped_split(rows)


@pytest.fixture
def fitted():
    rows=examples();texts=[normalized(r['text']) for r in rows];labels=[r['intent'] for r in rows]
    pipeline=Pipeline([('tfidf',TfidfVectorizer(ngram_range=(1,2),lowercase=False)),('classifier',LogisticRegression(max_iter=1000))]).fit(texts,labels)
    vectorizer=pipeline.named_steps['tfidf'];classifier=pipeline.named_steps['classifier']
    import sklearn
    artifact=Artifact(format='almanac-intent-v1',sklearn_version=sklearn.__version__,model_version='tfidf-'+'a'*12,
        dataset_sha256='b'*64,classes=classifier.classes_.tolist(),vocabulary=vectorizer.vocabulary_,idf=vectorizer.idf_.tolist(),
        coefficients=classifier.coef_.tolist(),intercept=classifier.intercept_.tolist(),confidence_threshold=.35)
    return pipeline,artifact


def test_export_inference_matches_pipeline_and_validates_artifacts(fitted,tmp_path):
    pipeline,artifact=fitted
    texts=['find_events question family1','unknown completely different words','ＦＩＮＤ＿ＥＶＥＮＴＳ question']
    assert np.allclose(IntentModel(artifact).probabilities(texts),pipeline.predict_proba([normalized(t) for t in texts]),atol=1e-12)
    path=tmp_path/'intent.json';encoded=artifact.model_dump_json().encode();path.write_bytes(encoded)
    path.with_suffix('.sha256').write_text(hashlib.sha256(encoded).hexdigest())
    assert load_model(path).version==artifact.model_version
    path.write_bytes(encoded+b' ')
    with pytest.raises(ValueError,match='checksum'): load_model(path)
    for changes in ({'sklearn_version':'wrong'},{'idf':[1.]},{'coefficients':[[float('nan')]]*4},{'classes':['unsupported']*4}):
        with pytest.raises(ValueError): Artifact.model_validate({**artifact.model_dump(),**changes})


def test_offline_training_reproducible_and_train_only_vocabulary(tmp_path):
    rows=examples();split=grouped_split(rows)
    # This token is unique to the immutable held-out group and must not enter the vocabulary.
    for i in split['test']: rows[i]['text']+=' forbiddenholdouttoken'
    source=tmp_path/'data.jsonl';source.write_text('\n'.join(json.dumps(r) for r in rows))
    report=train(source,tmp_path/'intent.json',tmp_path/'reports')
    model=load_model(tmp_path/'intent.json')
    assert 'forbiddenholdouttoken' not in model.artifact.vocabulary
    source.write_bytes(source.read_bytes().replace(b'\n',b'\r\n'))  # Windows checkout newline parity.
    again=train(source,tmp_path/'again.json',tmp_path/'reports-again')
    assert again==report
    assert (tmp_path/'intent.json').read_bytes()==(tmp_path/'again.json').read_bytes()


def test_missing_hybrid_model_is_not_ready_but_liveness_survives(tmp_path):
    app=create_app(Settings(nlp_mode='hybrid',intent_model_path=str(tmp_path/'missing.json')))
    with TestClient(app) as client:
        assert client.get('/api/v1/health/live').status_code==200
        result=client.get('/api/v1/health/ready')
        assert result.status_code==503 and result.json()['checks']['nlp']=='unavailable'
        assert result.json()['nlp_mode']=='hybrid'


def test_hybrid_cannot_bypass_semantics_or_fallback_when_missing(env):
    e=env;student,token=e['login']();app=e['app']
    app.state.settings.nlp_mode='hybrid'
    payload={'text':'events tomorrow','client_request_id':'hybrid-missing'}
    missing=student.post('/api/v1/assistant/query',json=payload,headers=headers(token))
    assert missing.status_code==503 and missing.json()['error']['code']=='model_unavailable'
    class Predictor:
        version='tfidf-'+'a'*12
        def predict(self,text): return 'find_events',.99
    app.state.intent_model=Predictor()
    answered=student.post('/api/v1/assistant/query',json=payload,headers=headers(token))
    assert answered.status_code==200 and answered.json()['status']!='unsupported'
    app.state.intent_model=None
    replay=student.post('/api/v1/assistant/query',json=payload,headers=headers(token))
    assert replay.json()==answered.json()  # A completed snapshot needs no new inference.
    app.state.intent_model=Predictor()
    response=student.post('/api/v1/assistant/interpret',json={'text':'rooms tomorrow from 2 to 3pm','client_request_id':'conflict'},headers=headers(token))
    assert response.status_code==200 and response.json()['status']=='unsupported'
    assert response.json()['execution'] is None and response.json()['model_version']==Predictor.version
    class Rejector(Predictor):
        def predict(self,text): return 'unsupported',.31
    app.state.intent_model=Rejector()
    response=student.post('/api/v1/assistant/interpret',json=payload,headers=headers(token))
    assert response.json()['status']=='unsupported' and response.json()['execution'] is None


def test_valid_artifact_loads_at_startup(fitted,tmp_path):
    _,artifact=fitted
    path=tmp_path/'intent.json';raw=artifact.model_dump_json().encode();path.write_bytes(raw)
    path.with_suffix('.sha256').write_text(hashlib.sha256(raw).hexdigest())
    with TestClient(create_app(Settings(nlp_mode='hybrid',intent_model_path=str(path)))) as client:
        ready=client.get('/api/v1/health/ready')
        assert ready.status_code==200 and ready.json()['checks']['nlp']=='ok'
        assert ready.json()['nlp_mode']=='hybrid'


def test_training_does_not_replace_a_different_frozen_dataset(tmp_path):
    report_dir=tmp_path/'reports';report_dir.mkdir()
    (report_dir/'intent-split.json').write_text(json.dumps({'dataset_sha256':'wrong'}))
    source=tmp_path/'dataset.jsonl';source.write_text('{}')
    with pytest.raises(ValueError,match='frozen'): train(source,tmp_path/'model.json',report_dir)


def test_duplicate_questions_cannot_have_conflicting_labels():
    rows=examples();rows[8]['text']=rows[0]['text'].upper()
    with pytest.raises(ValueError,match='conflicting intent'): grouped_split(rows)

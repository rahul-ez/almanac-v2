from copy import deepcopy
from pathlib import Path
import pytest
from app.nlp.evaluation import score_case,validate_suite
from app.schemas.interpretation import Interpretation,RoomExecution
from app.schemas.contracts import Meaning
from app.schemas.rooms import AvailabilityQuery


def test_frozen_suite_identity_and_manually_annotated_gold():
    suite,manifest=validate_suite('/workspace')
    assert len(suite['cases'])==24
    assert len({case['id'] for case in suite['cases']})==24
    assert suite['synthetic'] is True
    # Frozen fixtures include outcomes requiring data-aware reasoning, not just intent labels.
    assert {'answered','no_results','information_unavailable','clarification_required','unsupported'}<={c['answer_status'] for c in suite['cases']}


def test_scoring_penalizes_extra_filters_and_false_answers():
    suite,_=validate_suite('/workspace')
    case=next(c for c in suite['cases'] if c['id']=='room-available')
    meaning=Meaning.model_validate(case['meaning'])
    query=AvailabilityQuery(from_at=meaning.filters.interval.start,to_at=meaning.filters.interval.end)
    report=Interpretation(status='ready',intent=meaning.intent,meaning=meaning,execution=RoomExecution(query=query,room_id=meaning.filters.room_id),
        entities=[],applied_context=[],message='Test')
    correct=score_case(case,report,[],'no_results')
    assert correct['meaning_correct'] and not correct['end_to_end_correct']
    report.meaning.filters.facility_ids=['unrequested-facility']
    assert not score_case(case,report,[],'no_results')['meaning_correct']
    uncertain=next(c for c in suite['cases'] if c['id']=='missing-room-time')
    assert score_case(uncertain,report,[],'answered')['false_answer']


def test_frozen_suite_rejects_changed_records(tmp_path):
    import shutil
    for name in ('data/evaluation/manifest.json','data/evaluation/semantic-smoke.json','data/demo/campus-events.json','data/demo/rooms.json','data/demo/faculty.json'):
        target=tmp_path/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(Path('/workspace')/name,target)
    (tmp_path/'data/demo/rooms.json').write_text('{}')
    with pytest.raises(ValueError,match='checksum mismatch'): validate_suite(tmp_path)

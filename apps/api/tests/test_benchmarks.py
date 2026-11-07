import importlib
import io
import json
import sys
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).parents[1]))
from benchmarks import BenchmarkService,RunInput,grid
from datasets import DatasetInput
from test_pipeline import controlled

@pytest.fixture
def app(tmp_path,monkeypatch):
    monkeypatch.setenv('RAGLAB_DATA_DIR',str(tmp_path))
    for key in ['LLM_MODEL','LLM_API_KEY','OPENAI_API_KEY','LLM_REQUIRE_KEY']:monkeypatch.delenv(key,raising=False)
    import main
    importlib.reload(main)
    yield main,TestClient(main.app)
    main.benchmark_service.shutdown();main.engine.shutdown()

def dataset(app,reviewed=True):
    main,c=app
    text='The library lends energy meters. Return the meters within seven days. The garden collects rainwater.'
    d=c.post('/documents',files={'file':('evidence.txt',text.encode())}).json()
    payload={'name':'Controlled test judgments','document_ids':[d['id']], 'questions':[
        {'id':'q1','question':'Where can I borrow energy meters?','reference_answer':'The library.','answerability':'answerable',
         'human_reviewed':reviewed,'reviewer':'test fixture' if reviewed else '',
         'relevant_spans':[{'document_id':d['id'],'quote':'The library lends energy meters.'}]},
        {'id':'q2','question':'What are the Sunday closing hours?','answerability':'unanswerable','human_reviewed':reviewed,'reviewer':'test fixture' if reviewed else ''}
    ]}
    r=c.post('/datasets',json=payload);assert r.status_code==201,r.text
    return r.json(),d,payload

def test_grid_has_18_comparable_unique_configurations():
    values=grid(RunInput(dataset_id='d'))
    assert len(values)==18
    assert len({(c['model_id'],c['strategy'],c['budget']) for c in values})==18
    assert {c['budget'] for c in values}=={64,128,256}
    assert all(c['overlap']==0 for c in values if c['strategy']!='fixed')

def test_dataset_review_rules_offsets_import_and_revision(app):
    main,c=app;d,doc,payload=dataset(app,reviewed=False)
    assert d['reviewed_count']==0
    assert c.post('/benchmarks/runs',json={'dataset_id':d['id']}).status_code==422
    bad={**payload,'questions':[{**payload['questions'][0],'human_reviewed':True,'reviewer':''}]}
    assert c.post('/datasets',json=bad).status_code==422
    q=d['questions'][0];span=q['relevant_spans'][0]
    assert doc['text'][span['start']:span['end']]==span['quote']
    assert span['source_sha256']
    exported=c.get('/datasets/'+d['id']+'/export?format=csv')
    imported=c.post('/datasets/import',files={'file':('questions.csv',exported.content)},data={'document_ids':json.dumps([doc['id']])})
    assert imported.status_code==201,imported.text
    assert imported.json()['questions'][0]['relevant_spans'][0]['quote']==span['quote']
    assert imported.json()['questions'][0]['human_reviewed'] is False
    snapshot=main.dataset_store.snapshot(d['id'],True)
    updated=c.put('/datasets/'+d['id'],json={**d,'name':'Edited','expected_revision':d['revision']})
    assert updated.status_code==200 and updated.json()['revision']==2
    assert snapshot['revision']==1 and snapshot['name']==d['name']
    assert c.put('/datasets/'+d['id'],json={**d,'expected_revision':1}).status_code==409

@pytest.mark.parametrize('change',[
 {'relevant_spans':[{'document_name':'evidence.txt','start':0,'end':5,'quote':'wrong'}]},
 {'relevant_spans':[{'document_name':'evidence.txt','start':0,'end':99999}]},
 {'answerability':'unanswerable','relevant_spans':[{'document_name':'evidence.txt','quote':'The library lends energy meters.'}]},
 {'human_reviewed':True,'reviewer':'test fixture','relevant_spans':[]},
])
def test_invalid_dataset_evidence_rejected(app,change):
    _,c=app;_,doc,payload=dataset(app)
    payload['questions']=[{**payload['questions'][0],**change}]
    assert c.post('/datasets',json=payload).status_code==422

def test_unicode_offsets_and_json_import_validation(app):
    _,c=app
    doc=c.post('/documents',files={'file':('unicode.txt','🌱 The library lends meters.'.encode())}).json()
    body={'name':'Unicode','document_ids':[doc['id']],'questions':[{'question':'What is lent?','reference_answer':'meters','relevant_spans':[{'document_id':doc['id'],'quote':'The library lends meters.'}]}]}
    r=c.post('/datasets/import',files={'file':('data.json',json.dumps(body).encode())});assert r.status_code==201,r.text
    assert r.json()['questions'][0]['relevant_spans'][0]['start']==2
    assert c.post('/datasets/import',files={'file':('data.exe',b'x')}).status_code==415
    assert c.post('/datasets/import',files={'file':('data.json',b'{')}).status_code==422
    assert c.post('/datasets/import',files={'file':('data.csv',b'not_questions\nvalue')}).status_code==422
    assert c.post('/datasets/import',files={'file':('data.json',b'x'*(2*1024*1024+1))}).status_code==413

def test_actual_runner_persistence_exports_and_immutable_snapshot(app,controlled):
    main,c=app;d,_,_=dataset(app)
    run=main.benchmark_service.start(RunInput(dataset_id=d['id'],repetitions=1),asynchronous=False)
    assert run['status']=='completed',[(x['config'],x['error']) for x in run['configs'] if x['error']]
    assert run['completed_configs']==18 and run['completed_measurements']==36
    measurements=c.get(f"/benchmarks/runs/{run['id']}/measurements").json()
    assert len(measurements)==36
    assert all(m['latency_ms']>=0 for m in measurements)
    assert all(m['metrics']['answer_exact_match'] is None and m['metrics']['groundedness'] is None for m in measurements)
    assert all(m['metrics']['precision_at_k'] is None for m in measurements if m['answerability']=='unanswerable')
    ranked=c.get(f"/benchmarks/runs/{run['id']}/leaderboard?objective=accuracy").json()['ranked']
    assert len(ranked)==18 and ranked[0]['metrics']['unique_answerable_questions']==1
    assert all(c['indexing_time_ms'] is not None for c in run['configs'])
    csv=c.get(f"/benchmarks/runs/{run['id']}/export?format=csv")
    assert csv.status_code==200 and len(csv.text.splitlines())==37
    exported=c.get(f"/benchmarks/runs/{run['id']}/export").json()
    assert len(exported['measurements'])==36
    assert c.get(f"/benchmarks/runs/{run['id']}/leaderboard?objective=invented").status_code==422
    before=run['snapshot']['fingerprint']
    d['name']='Edited after benchmark';c.put('/datasets/'+d['id'],json={**d,'expected_revision':d['revision']})
    assert c.get('/benchmarks/runs/'+run['id']).json()['snapshot']['fingerprint']==before
    recovered=BenchmarkService(main.connect,main.engine,main.dataset_store)
    assert recovered.get(run['id'])['completed_measurements']==36
    recovered.shutdown()

def test_cancel_resume_keeps_completed_measurements(app,controlled,monkeypatch):
    main,c=app;d,_,_=dataset(app);original=main.engine.retrieve;cancelled=False
    def retrieve(q,persist=True):
        nonlocal cancelled
        result=original(q,persist=persist)
        if persist and not cancelled:
            cancelled=True
            with main.connect() as db:run_id=db.execute('SELECT id FROM benchmark_runs ORDER BY rowid DESC').fetchone()[0]
            main.benchmark_service.cancel(run_id)
        return result
    monkeypatch.setattr(main.engine,'retrieve',retrieve)
    run=main.benchmark_service.start(RunInput(dataset_id=d['id'],repetitions=1),asynchronous=False)
    assert run['status']=='cancelled' and run['completed_measurements']==1
    first=main.benchmark_service.measurements(run['id'])[0]['id']
    resumed=main.benchmark_service.resume(run['id'],asynchronous=False)
    assert resumed['status']=='completed' and resumed['completed_measurements']==36
    assert resumed['resume_count']==1
    assert first in {r['id'] for r in main.benchmark_service.measurements(run['id'])}

def test_failed_configs_are_not_zeros_and_can_resume_after_restart(app,controlled,monkeypatch):
    main,c=app;d,_,_=dataset(app);original=main.engine.retrieve;fail=True
    def retrieve(q,persist=True):
        nonlocal fail
        if fail:fail=False;raise RuntimeError('controlled temporary failure')
        return original(q,persist=persist)
    monkeypatch.setattr(main.engine,'retrieve',retrieve)
    run=main.benchmark_service.start(RunInput(dataset_id=d['id'],repetitions=1),asynchronous=False)
    assert run['status']=='completed_with_errors' and run['completed_configs']==17
    assert len(main.benchmark_service.leaderboard(run['id'])['ranked'])==17
    failed=[c for c in run['configs'] if c['status']=='failed'][0]
    assert failed['metrics']=={} and 'temporary failure' in failed['error']
    with main.connect() as db:db.execute("UPDATE benchmark_runs SET status='running' WHERE id=?",(run['id'],))
    recovered=BenchmarkService(main.connect,main.engine,main.dataset_store)
    assert recovered.get(run['id'])['status']=='interrupted'
    final=recovered.resume(run['id'],asynchronous=False)
    assert final['status']=='completed' and final['completed_configs']==18
    recovered.shutdown()

def test_missing_generation_provider_rejected_and_sample_is_unreviewed(app):
    main,c=app;d,_,_=dataset(app)
    assert c.post('/benchmarks/runs',json={'dataset_id':d['id'],'generate_answers':True}).status_code==422
    sample=c.post('/datasets/sample');assert sample.status_code==201,sample.text
    assert sample.json()['sample'] and sample.json()['question_count']==6 and sample.json()['reviewed_count']==0
    assert c.post('/benchmarks/runs',json={'dataset_id':sample.json()['id']}).status_code==422
    assert c.post('/benchmarks/runs',json={'dataset_id':d['id'],'budgets':[64,64,128]}).status_code==422


def test_csv_repeated_question_metadata_must_agree(app):
    _,c=app;d,doc,payload=dataset(app)
    csv='question_id,question,reference_answer,document_id,quote\nq,Where?,Library,'+doc['id']+',The library lends energy meters.\nq,Where?,Garden,'+doc['id']+',Return the meters within seven days.\n'
    result=c.post('/datasets/import',files={'file':('bad.csv',csv.encode())})
    assert result.status_code==422 and 'consistent' in result.json()['detail']


def test_cancelled_inflight_index_is_not_reused_by_immediate_resume(app,controlled,monkeypatch):
    import embeddings,threading
    from pipeline import Build
    main,c=app;d,doc,_=dataset(app);entered=threading.Event();release=threading.Event()
    def load(_):entered.set();assert release.wait(5)
    monkeypatch.setattr(embeddings,'load_model',load)
    config=Build(document_ids=[doc['id']],budget=64,overlap=9)
    first=main.engine.create(config)
    assert entered.wait(5)
    main.engine.cancel(first['id'])
    second=main.engine.create(config)
    assert second['id']!=first['id'] and not second['cache_reused']
    release.set();deadline=time.monotonic()+10
    while main.engine.row(second['id'])['status'] in ('queued','running') and time.monotonic()<deadline:time.sleep(.01)
    assert main.engine.row(first['id'])['status']=='cancelled'
    assert main.engine.row(second['id'])['status']=='ready'

"""Controlled source fixtures are synthetic unit tests, not research results."""
import json
import pytest
from fastapi import HTTPException
from test_benchmarks import app,controlled
from adaptive import Objective,SearchInput,analyse,uncertainty
from datasets import DatasetInput,SplitInput,assign_splits,validate_split_isolation


def split_dataset(app):
    main,c=app
    text='Meters are lent by the library. Rainwater is stored by the garden. The solar panels generate electricity. Food waste becomes compost. The buses use electric batteries. Trees provide shade.'
    d=c.post('/documents',files={'file':('independent.txt',text.encode())}).json()
    statements=text.split('. ')
    questions=[]
    for i,sentence in enumerate(statements):
        # Independent source spans; deliberately unreviewed research fixtures.
        questions.append({'id':f'q{i}','question':f'What does source fact number {i} say?', 'reference_answer':sentence,'split':['validation','test','train'][i%3],
                          'relevant_spans':[{'document_id':d['id'],'quote':sentence}]})
    response=c.post('/datasets',json={'name':'Unreviewed isolation fixture','document_ids':[d['id']],'questions':questions})
    assert response.status_code==201,response.text
    return response.json()


def test_group_splits_roundtrip_and_leakage_guard(app):
    main,c=app;d=split_dataset(app)
    validate_split_isolation(d['questions'])
    copy=[{**q} for q in d['questions']];copy[1]['group_id']=copy[0]['group_id']='related'
    with pytest.raises(HTTPException):validate_split_isolation(copy)
    duplicate=[{**q} for q in d['questions']];duplicate[1]['question']=duplicate[0]['question']
    with pytest.raises(HTTPException):validate_split_isolation(duplicate)
    overlapping=[{**q} for q in d['questions']];overlapping[1]['relevant_spans']=overlapping[0]['relevant_spans']
    with pytest.raises(HTTPException):validate_split_isolation(overlapping)
    r=c.post(f"/datasets/{d['id']}/split",json={'expected_revision':1,'seed':7})
    assert r.status_code==200,r.text
    assert {q['split'] for q in r.json()['questions']}=={'train','validation','test'}
    assert not any(q['human_reviewed'] for q in r.json()['questions'])
    assert c.post(f"/datasets/{d['id']}/split",json={'expected_revision':1}).status_code==409
    raw=c.get(f"/datasets/{d['id']}/export?format=csv").content
    imported=c.post('/datasets/import',files={'file':('split.csv',raw)})
    assert imported.status_code==201,imported.text
    assert [q['split'] for q in imported.json()['questions']]==[q['split'] for q in r.json()['questions']]


def test_uncertainty_groups_repetitions_and_is_repeatable():
    def m(q,v):return {'question_id':q,'latency_ms':10+v,'metrics':{'precision_at_k':v,'recall_at_k':v,'mrr':v}}
    records=[m('a',0),m('a',0),m('b',1),m('b',1)]
    u=uncertainty(records)
    assert u==uncertainty(records)
    assert u['intervals']['recall_at_k']['unique_questions']==2
    assert u['intervals']['recall_at_k']['ci95']==[0,1]
    assert u['repeatability']['quality_consistent'] is True
    assert uncertainty(records[:2])['intervals']['recall_at_k']['ci95'] is None
    assert uncertainty(records[:1])['repeatability']['quality_consistent'] is None
    assert uncertainty([m('a',0),m('a',1)])['repeatability']['quality_consistent'] is False


def test_pareto_constraints_weights_and_no_unmeasured_candidates():
    def config(id,q,latency,status='completed'):
        return {'id':id,'config':{},'status':status,'metrics':{'precision_at_k':q,'recall_at_k':q,'mrr':q,'latency_mean_ms':latency}}
    run={'configs':[config('fast',.5,10),config('accurate',1,100),config('dominated',.4,20),config('failed',1,1,'failed')],
         'snapshot':{'provisional':True,'split':'validation'},'settings':{'seed':7}}
    a=analyse(run,[],Objective(accuracy_weight=1))
    assert set(a['pareto_config_ids'])=={'fast','accurate'}
    assert a['ranked'][0]['config_id']=='accurate'
    assert analyse(run,[],Objective(accuracy_weight=0))['ranked'][0]['config_id']=='fast'
    assert analyse(run,[],Objective(max_latency_ms=5))['ranked']==[]
    assert analyse(run,[],Objective(max_latency_ms=50))['excluded_by_latency']==1
    with pytest.raises(ValueError):Objective(recall_weight=0,mrr_weight=0,precision_weight=0)


def test_automatic_search_freezes_selection_then_evaluates_one_test_config(app,controlled):
    main,c=app;d=split_dataset(app)
    search=main.adaptive_service.start(SearchInput(dataset_id=d['id'],include_unreviewed=True,repetitions=2,budgets=[8,16,24]),asynchronous=False)
    assert search['status']=='completed',search.get('error')
    validation=main.benchmark_service.get(search['selection_run_id']);test=main.benchmark_service.get(search['test_run_id'])
    assert len(validation['configs'])==18 and len(test['configs'])==1
    assert validation['completed_measurements']==72 and test['completed_measurements']==4
    assert {q['id'] for q in validation['snapshot']['questions']}.isdisjoint(q['id'] for q in test['snapshot']['questions'])
    assert test['configs'][0]['config']==search['frozen_selection']['config']
    assert test['settings']['adaptive_provenance']['frozen_selection']['sha256']==search['frozen_selection']['sha256']
    assert search['held_out']['provisional'] is True
    assert search['held_out']['uncertainty']['intervals']['recall_at_k']['unique_questions']==2
    assert c.post('/adaptive/analyse/'+test['id'],json={}).status_code==422
    assert c.post('/adaptive/analyse/'+validation['id'],json={'max_latency_ms':10000}).status_code==200
    assert c.post('/adaptive/searches/'+search['id']+'/resume').status_code==409
    assert c.post('/adaptive/searches',json={'dataset_id':d['id'],'include_unreviewed':True}).status_code==409
    from adaptive import AdaptiveService
    reopened=AdaptiveService(main.connect,main.benchmark_service,main.dataset_store)
    assert reopened.get(search['id'])['frozen_selection']==search['frozen_selection'];reopened.shutdown()
    # Historical immutable snapshots survive later dataset edits.
    c.put('/datasets/'+d['id'],json={**d,'name':'Edited later','expected_revision':1})
    assert main.adaptive_service.get(search['id'])['selection_snapshot']['revision']==1
    main.adaptive_service.shutdown()


def test_search_rejects_unassigned_review_and_impossible_constraint(app,controlled):
    main,c=app;d=split_dataset(app)
    assert c.post('/adaptive/searches',json={'dataset_id':d['id']}).status_code==422
    # No feasible candidate: no test run must exist.
    s=main.adaptive_service.start(SearchInput(dataset_id=d['id'],include_unreviewed=True,repetitions=1,budgets=[8,16,24],objective=Objective(max_latency_ms=.000001)),asynchronous=False)
    assert s['status']=='failed' and s['test_run_id'] is None and s['frozen_selection'] is None
    assert 'latency constraint' in s['error']
    main.adaptive_service.shutdown()


def test_pdf_report_contains_actual_metrics_and_provenance(app,controlled):
    import fitz
    main,c=app;d=split_dataset(app)
    run=main.benchmark_service.start(__import__('benchmarks').RunInput(dataset_id=d['id'],include_unreviewed=True,repetitions=1,budgets=[8,16,24]),asynchronous=False)
    response=c.get(f"/benchmarks/runs/{run['id']}/export?format=pdf")
    assert response.status_code==200 and response.headers['content-type']=='application/pdf'
    doc=fitz.open(stream=response.content,filetype='pdf');text='\n'.join(page.get_text() for page in doc)
    assert len(doc)>=3 and 'PROVISIONAL' in text and run['snapshot']['fingerprint'] in text
    assert 'Not evaluated' in text and 'Methodology and limitations' in text and 'minilm' in text
    assert str(round(run['configs'][0]['metrics']['latency_mean_ms'],2)) in text
    assert c.get(f"/benchmarks/runs/{run['id']}/export?format=invalid").status_code==422


def test_adaptive_cancel_and_resume_preserve_reserved_test_and_completed_work(app,controlled,monkeypatch):
    main,c=app;d=split_dataset(app)
    pending=[]
    monkeypatch.setattr(main.benchmark_service.executor,'submit',lambda *args:pending.append(args))
    monkeypatch.setattr(main.adaptive_service.executor,'submit',lambda *args:pending.append(args))
    s=main.adaptive_service.start(SearchInput(dataset_id=d['id'],include_unreviewed=True,repetitions=1,budgets=[8,16,24]))
    main.adaptive_service.cancel(s['id'])
    main.benchmark_service.execute(s['selection_run_id']);main.adaptive_service.execute(s['id'])
    assert main.adaptive_service.get(s['id'])['status']=='cancelled'
    main.adaptive_service.resume(s['id']);main.benchmark_service.execute(s['selection_run_id'])
    main.adaptive_service.execute(s['id'],synchronous=True)
    completed=main.adaptive_service.get(s['id']);assert completed['status']=='completed',completed['error']
    assert completed['selection_run_id']==s['selection_run_id']
    assert main.benchmark_service.get(completed['test_run_id'])['completed_measurements']==2
    main.adaptive_service.shutdown()


def test_adaptive_interruption_and_frozen_selection_tamper_fail_closed(app,controlled,monkeypatch):
    from adaptive import AdaptiveService
    main,c=app;d=split_dataset(app)
    monkeypatch.setattr(main.benchmark_service.executor,'submit',lambda *args:None)
    monkeypatch.setattr(main.adaptive_service.executor,'submit',lambda *args:None)
    s=main.adaptive_service.start(SearchInput(dataset_id=d['id'],include_unreviewed=True,repetitions=1,budgets=[8,16,24]))
    restarted=AdaptiveService(main.connect,main.benchmark_service,main.dataset_store)
    assert restarted.get(s['id'])['status']=='interrupted'
    restarted.resume(s['id']);main.benchmark_service.execute(s['selection_run_id'])
    # Corrupt a selection seal: test queries must never execute.
    record=restarted.get(s['id']);record['frozen_selection']={'sha256':'invalid'};restarted.save(record)
    restarted.execute(s['id'],synchronous=True)
    result=restarted.get(s['id']);assert result['status']=='failed' and result['test_run_id'] is None
    assert 'integrity check' in result['error']
    restarted.shutdown();main.adaptive_service.shutdown()


def test_adaptive_sample_has_real_anchors_and_no_review_claims(app):
    main,c=app;r=c.post('/datasets/sample/adaptive');assert r.status_code==201
    d=r.json();assert len(d['questions'])==12 and d['reviewed_count']==0
    for split in ['train','validation','test']:
        snap=main.dataset_store.snapshot(d['id'],True,split)
        assert len(snap['questions'])==4 and snap['provisional']
    validate_split_isolation(d['questions'])


def test_cancellation_at_selection_seal_never_launches_test_queries(app,controlled,monkeypatch):
    main,c=app;d=split_dataset(app);service=main.adaptive_service
    save=service.save;triggered=False
    def cancel_at_seal(data,**kwargs):
        nonlocal triggered
        save(data,**kwargs)
        if data.get('frozen_selection') and not data.get('test_run_id') and not triggered:
            triggered=True;service.cancel(data['id'])
    monkeypatch.setattr(service,'save',cancel_at_seal)
    result=service.start(SearchInput(dataset_id=d['id'],include_unreviewed=True,repetitions=1,budgets=[8,16,24]),asynchronous=False)
    assert triggered and result['status']=='cancelled' and result['test_run_id'] is None
    assert result['frozen_selection'] is not None
    service.shutdown()

"""Synthetic fixtures test mechanics only; never used as claimed human study evidence."""
import json
from unittest.mock import Mock
import httpx
import numpy as np
import pytest
from test_benchmarks import app,controlled,dataset
from benchmarks import RunInput
from datasets import DatasetInput
from answer_reviews import AnswerReviewInput
from generation import generate,probe


def test_review_decisions_history_and_backend_edit_revocation(app):
    main,c=app;d,doc,payload=dataset(app,reviewed=False);qid=d['questions'][0]['id'];base=f"/datasets/{d['id']}"
    assert c.post(base+f'/questions/{qid}/review',json={'expected_revision':1,'action':'approve','reviewer':' '}).status_code==422
    r=c.post(base+f'/questions/{qid}/review',json={'expected_revision':1,'action':'approve','reviewer':'Unit-test reviewer','notes':'Controlled fixture only.'});assert r.status_code==200,r.text
    approved=r.json();assert approved['questions'][0]['review_status']=='reviewed'
    assert c.post(base+f'/questions/{qid}/review',json={'expected_revision':1,'action':'reject','reviewer':'fixture'}).status_code==409
    edited={**approved,'expected_revision':2};edited['questions'][0]['reference_answer']='Changed reference';edited['questions'][0]['reference_answers']=[]
    changed=c.put(base,json=edited).json();assert not changed['questions'][0]['human_reviewed'] and changed['questions'][0]['review_status']=='unreviewed'
    rejected=c.post(base+f'/questions/{qid}/review',json={'expected_revision':3,'action':'reject','reviewer':'Unit-test reviewer'}).json()
    assert rejected['questions'][0]['review_status']=='rejected'
    # Rejected answerable question cannot re-enter a provisional benchmark.
    assert c.post('/benchmarks/runs',json={'dataset_id':d['id'],'include_unreviewed':True}).status_code==422
    reopened=c.post(base+f'/questions/{qid}/review',json={'expected_revision':4,'action':'reopen','reviewer':'Unit-test reviewer'}).json()
    assert reopened['questions'][0]['review_status']=='unreviewed'
    events=c.get(base+'/history').json();assert {'created','approved','edited_approval_revoked','rejected','reopened'}<=set(e['action'] for e in events)
    assert any(e['before_json'] and e['before_json']['human_reviewed'] for e in events)
    # Review flags in an import are never a new review in this workspace.
    imported=c.post('/datasets/import',files={'file':('reviewed.json',json.dumps(approved).encode())}).json()
    assert imported['reviewed_count']==0 and imported['questions'][0]['reviewer']==''
    assert all(e['actor'] is None for e in c.get('/datasets/'+imported['id']+'/history').json())


def test_human_answer_rubric_uses_only_explicit_attributed_judgments(app,controlled):
    main,c=app;d,doc,_=dataset(app)
    from pipeline import Build,Retrieval
    index=main.engine.create(Build(document_ids=[doc['id']],budget=8,overlap=1),asynchronous=False)
    retrieval=main.engine.retrieve(Retrieval(index_id=index['id'],query='Where are meters?'))
    # A stored controlled adapter fixture, not a live provider result.
    result={'id':'fixture-answer','status':'generated','answer':'The library lends meters. [1]','claims':[{'text':'The library lends meters.'}],'citations':[]}
    with main.connect() as db:db.execute('INSERT INTO answers VALUES(?,?,?,CURRENT_TIMESTAMP)',(result['id'],retrieval['id'],json.dumps(result)))
    base='/answers/fixture-answer/review'
    assert c.post(base,json={'reviewer':'fixture'}).status_code==422
    assert c.post(base,json={'reviewer':'fixture','attested':True,'correctness':'correct'}).status_code==422
    assert c.post(base,json={'reviewer':'fixture','attested':True,'claim_ratings':['supported','supported']}).status_code==422
    review=c.post(base,json={'reviewer':'Unit-test reviewer','attested':True,'reference_answer':'The library.','correctness':'partial','claim_ratings':['supported']})
    assert review.status_code==201,review.text
    r=review.json();assert r['correctness_score']==.5 and r['groundedness_score']==1
    assert c.post(base,json={'reviewer':'fixture','attested':True}).status_code==409
    next=c.post(base,json={'reviewer':'Unit-test reviewer','attested':True,'claim_ratings':['uncertain'],'expected_latest_id':r['id']}).json()
    assert next['groundedness_score'] is None and next['correctness_score'] is None
    assert len(c.get(base).json()['reviews'])==2
    rollup=main.answer_review_store.rollup([{'generation':result}]);assert rollup['reviewed_answers']==1 and rollup['groundedness'] is None
    no_answer={**result,'id':'fixture-failure','status':'provider_error','answer':None}
    with main.connect() as db:db.execute('INSERT INTO answers VALUES(?,?,?,CURRENT_TIMESTAMP)',(no_answer['id'],retrieval['id'],json.dumps(no_answer)))
    assert c.post('/answers/fixture-failure/review',json={'reviewer':'fixture','attested':True}).status_code==422


def test_provider_probe_redacts_bodies_and_never_claims_generation(monkeypatch):
    monkeypatch.delenv('LLM_MODEL',raising=False);monkeypatch.delenv('OPENAI_API_KEY',raising=False);monkeypatch.delenv('LLM_API_KEY',raising=False)
    assert probe()['status']=='not_configured'
    monkeypatch.setenv('LLM_MODEL','test-model');monkeypatch.setenv('LLM_API_KEY','unit-test-secret')
    transport=httpx.MockTransport(lambda _:httpx.Response(200,json={'data':[{'id':'test-model'}]}))
    p=probe(transport);assert p['status']=='model_listed' and not p['generation_tested'] and 'unit-test-secret' not in json.dumps(p)
    p=probe(httpx.MockTransport(lambda _:httpx.Response(429,json={'secret':'unit-test-secret'})))
    assert p['http_status']==429 and 'unit-test-secret' not in json.dumps(p)
    assert probe(httpx.MockTransport(lambda _:httpx.Response(404)))['status']=='probe_unsupported'
    monkeypatch.setenv('LLM_API_BASE','https://user:password@example.test/v1')
    assert probe(transport)['status']=='invalid_configuration'
    for base in ['https://example.test:bad/v1','https://[invalid','ftp://example.test/v1']:
        monkeypatch.setenv('LLM_API_BASE',base)
        assert probe(transport)['status']=='invalid_configuration'
        assert generate('fixture question',[{'source_name':'fixture','page_numbers':[1],'text':'Fixture passage.'}],transport)['status']=='provider_error'


def test_bounded_429_retry_and_no_automatic_timeout_retry(monkeypatch):
    monkeypatch.setenv('LLM_MODEL','test-model');monkeypatch.setenv('LLM_API_KEY','fixture');monkeypatch.setenv('LLM_MAX_RETRIES','2')
    calls=[]
    def limited(request):calls.append(request);return httpx.Response(429,headers={'retry-after':'0'})
    hit={'source_name':'fixture','page_numbers':[1],'text':'Fixture passage.'}
    assert generate('q',[hit],httpx.MockTransport(limited))['status']=='provider_error' and len(calls)==3
    calls.clear()
    def timeout(request):calls.append(request);raise httpx.ReadTimeout('fixture')
    assert generate('q',[hit],httpx.MockTransport(timeout))['status']=='provider_error' and len(calls)==1


def test_request_bounds_origins_binary_disguise_and_filename_controls(app):
    main,c=app
    assert c.post('/documents',content=b'',headers={'content-length':str(13*1024**2)}).status_code==413
    assert c.post('/datasets/sample',headers={'Origin':'https://untrusted.example'}).status_code==403
    assert c.get('/health',headers={'Origin':'http://localhost:3000'}).headers['access-control-allow-origin']=='http://localhost:3000'
    for raw in [b'%PDF-1.7',b'PK\x03\x04rest',b'hello\x01world']:
        assert c.post('/documents',files={'file':('disguise.txt',raw)}).status_code==422
    r=c.post('/documents',files={'file':('../../\u202esafe.txt',b'Plain text.')});assert r.status_code==201 and r.json()['name']=='safe.txt'
    assert c.post('/documents',files={'file':('a'*181+'.txt',b'text')}).status_code==422
    from boundaries import allowed_origins
    with pytest.raises(ValueError):allowed_origins('*')
    with pytest.raises(ValueError):allowed_origins('https://*.example.test')
    with pytest.raises(ValueError):allowed_origins('https://example.test:invalid')
    with pytest.raises(ValueError):allowed_origins('https://user:key@host.test')


def test_pdf_worker_timeout_and_decompression_limits(app,monkeypatch):
    main,c=app
    import ingestion,subprocess,pymupdf
    old=ingestion.subprocess.run
    monkeypatch.setattr(ingestion.subprocess,'run',lambda *a,**k:(_ for _ in ()).throw(subprocess.TimeoutExpired('fixture',25)))
    r=c.post('/documents',files={'file':('slow.pdf',b'%PDF-1.7')});assert r.status_code==422 and '25 seconds' in r.text
    monkeypatch.setattr(ingestion.subprocess,'run',old)
    pdf=pymupdf.open();page=pdf.new_page();xref=pdf.get_new_xref();pdf.update_object(xref,'<<>>');pdf.update_stream(xref,b' '*(17*1024**2));page.set_contents(xref)
    r=c.post('/documents',files={'file':('compressed.pdf',pdf.tobytes(deflate=True))});assert r.status_code==422 and '16 MB' in r.text
    # Worker saturation rejects safely without starting a third parser.
    main.PDF_SLOTS.acquire();main.PDF_SLOTS.acquire()
    try:assert c.post('/documents',files={'file':('busy.pdf',b'%PDF-1.7')}).status_code==429
    finally:main.PDF_SLOTS.release();main.PDF_SLOTS.release()


def test_csv_formula_safety_and_benchmark_queue_backpressure(app,monkeypatch):
    main,c=app;d,_,_=dataset(app,reviewed=False)
    d['questions'][0]['question']='=HYPERLINK("http://example.test")'
    saved=c.put('/datasets/'+d['id'],json={**d,'expected_revision':1}).json()
    csv=c.get('/datasets/'+d['id']+'/export?format=csv').text;assert "'=HYPERLINK" in csv
    monkeypatch.setattr(main.benchmark_service.executor,'submit',lambda *a:None)
    for _ in range(3):assert c.post('/benchmarks/runs',json={'dataset_id':d['id'],'include_unreviewed':True}).status_code==202
    assert c.post('/benchmarks/runs',json={'dataset_id':d['id'],'include_unreviewed':True}).status_code==429


def test_reviewed_rerun_comparison_and_immutable_provisional_snapshot(app,controlled):
    main,c=app;d,_,_=dataset(app,reviewed=False)
    first=main.benchmark_service.start(RunInput(dataset_id=d['id'],include_unreviewed=True,repetitions=1,budgets=[8,16,24]),asynchronous=False)
    current=d
    for q in d['questions']:
        current=c.post(f"/datasets/{d['id']}/questions/{q['id']}/review",json={'action':'approve','reviewer':'Unit-test reviewer','expected_revision':current['revision']}).json()
    second=main.benchmark_service.start(RunInput(dataset_id=d['id'],repetitions=1,budgets=[8,16,24]),asynchronous=False)
    compared=c.get(f"/benchmarks/compare?left={first['id']}&right={second['id']}").json()
    assert compared['compatible'] and len(compared['rows'])==18
    assert compared['left_provisional'] and not compared['right_provisional']
    assert all(row['delta']['recall_at_k']==0 for row in compared['rows'])
    assert main.benchmark_service.get(first['id'])['snapshot']['provisional'] is True
    broken={**second['settings'],'top_k':4}
    with main.connect() as db:db.execute('UPDATE benchmark_runs SET settings=? WHERE id=?',(json.dumps(broken),second['id']))
    assert not c.get(f"/benchmarks/compare?left={first['id']}&right={second['id']}").json()['compatible']
    assert c.get('/dashboard').json()['reviewed_questions']==2
    assert c.get('/storage').json()['sqlite_integrity']=='ok'
    assert c.post('/storage/check-indexes').json()['invalid_ids']==[]


def test_optimizer_exact_ties_use_stable_configuration_specifications():
    from evaluation import optimize
    from adaptive import analyse,Objective
    from test_evaluation import config
    rows=[{**config('random-a',1,10),'config':{'budget':64}}, {**config('random-z',1,10),'config':{'budget':32}}]
    assert optimize(rows)[0]['config']['budget']==32
    run={'configs':rows,'snapshot':{'provisional':True},'settings':{'seed':7}}
    assert analyse(run,[],Objective())['ranked'][0]['config']['budget']==32
    rows[0]['id'],rows[1]['id']=rows[1]['id'],rows[0]['id']
    assert optimize(rows)[0]['config']['budget']==32
    assert analyse(run,[],Objective())['ranked'][0]['config']['budget']==32


def test_streaming_body_limit_without_truthful_content_length(app):
    main,c=app
    r=c.post('/datasets',content=b'x'*(12*1024*1024+1),headers={'Content-Length':'0','Content-Type':'application/json'})
    assert r.status_code==413,r.text


def test_resumed_jobs_share_the_same_atomic_queue_capacity(app,monkeypatch):
    main,c=app;d,_,_=dataset(app,reviewed=False)
    monkeypatch.setattr(main.benchmark_service.executor,'submit',lambda *a:None)
    stopped=[]
    for _ in range(4):
        run=main.benchmark_service.start(RunInput(dataset_id=d['id'],include_unreviewed=True))
        main.benchmark_service.cancel(run['id']);main.benchmark_service.execute(run['id']);stopped.append(run['id'])
    for id in stopped[:3]:assert c.post('/benchmarks/runs/'+id+'/resume').status_code==202
    assert c.post('/benchmarks/runs/'+stopped[3]+'/resume').status_code==429


def test_reviewer_reassignment_requires_an_explicit_fresh_decision(app):
    main,c=app;d,_,_=dataset(app,reviewed=True);qid=d['questions'][0]['id'];base='/datasets/'+d['id']
    body={**d,'expected_revision':1};body['questions'][0]['reviewer']='Another fixture identity'
    changed=c.put(base,json=body).json();assert not changed['questions'][0]['human_reviewed']
    approved=c.post(base+f'/questions/{qid}/review',json={'expected_revision':2,'action':'approve','reviewer':'Explicit fixture identity'}).json()
    assert approved['questions'][0]['human_reviewed'] and approved['questions'][0]['reviewer']=='Explicit fixture identity'
    c.post(base+f'/questions/{qid}/review',json={'expected_revision':3,'action':'approve','reviewer':'Explicit fixture identity'})
    decisions=[e for e in c.get(base+'/history').json() if e['question_id']==qid and e['action']=='approved']
    assert len(decisions)==2 and all(e['actor']=='Explicit fixture identity' for e in decisions)

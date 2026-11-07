"""Deterministic boundary tests. Real-model integration is in smoke_pipeline.py."""
import importlib
import json
import sys
import threading
import time
from pathlib import Path
import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).parents[1]))
import embeddings
from pipeline import Build, Retrieval, Engine, pages_for
from generation import generate, INSUFFICIENT

@pytest.fixture
def service(tmp_path,monkeypatch):
    monkeypatch.setenv('RAGLAB_DATA_DIR',str(tmp_path))
    monkeypatch.delenv('LLM_API_KEY',raising=False)
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    monkeypatch.delenv('LLM_MODEL',raising=False)
    monkeypatch.delenv('LLM_REQUIRE_KEY',raising=False)
    import main
    importlib.reload(main)
    yield main,TestClient(main.app)
    main.engine.shutdown()

@pytest.fixture
def controlled(monkeypatch):
    calls=[]
    monkeypatch.setattr(embeddings,'load_model',lambda _:None)
    monkeypatch.setattr(embeddings,'split_for_model',lambda text,_:iter([(0,len(text),len(text.split()))]))
    def encode(texts,model_id='minilm',query=False):
        calls.append((list(texts),model_id,query))
        values=[]
        for text in texts:
            v=np.zeros(384,dtype='float32');v[0]=1 if 'meter' in text.lower() else .01
            v[1]=1 if 'garden' in text.lower() else .01
            v/=np.linalg.norm(v);values.append(v)
        return np.array(values)
    monkeypatch.setattr(embeddings,'encode',encode)
    return calls

def add(client,name='energy.txt',text='The library lends energy meters. Return meters within seven days.'):
    r=client.post('/documents',files={'file':(name,text.encode())});assert r.status_code==201,r.text
    return r.json()['id']

def build(main,client,**kwargs):
    id=add(client)
    config=Build(document_ids=[id],budget=12,overlap=2,**kwargs)
    row=main.engine.create(config,asynchronous=False)
    assert row['status']=='ready',row
    return row

def test_persisted_faiss_load_and_cache_reuse(service,controlled):
    main,c=service;row=build(main,c)
    assert (main.engine.root/row['id']/'index.faiss').is_file()
    assert row['stats']['norm_min']==pytest.approx(1)
    count=len(controlled)
    restarted=Engine(main.connect,main.DATA)
    result=restarted.retrieve(Retrieval(index_id=row['id'],query='energy meters',min_score=-1))
    assert len(controlled)==count+1 and controlled[-1][2] is True  # query only, no document re-embedding
    assert result['hits'][0]['source_name']=='energy.txt'
    assert result['hits'][0]['page_numbers']==[1]
    duplicate=restarted.create(Build(**row['config']),asynchronous=False)
    assert duplicate['cache_reused'] and duplicate['id']==row['id']
    rebuilt=restarted.create(Build(**{**row['config'],'rebuild':True}),asynchronous=False)
    assert rebuilt['id']!=row['id'] and rebuilt['stats']['cache_hits']==rebuilt['stats']['vectors']
    restarted.shutdown()

def test_collection_mapping_visualization_and_delete_invalidation(service,controlled):
    main,c=service;a=add(c);b=add(c,'garden.md','The community garden collects rainwater in covered tanks. Volunteers water plants early.')
    row=main.engine.create(Build(document_ids=[a,b],budget=12,overlap=0),asynchronous=False)
    result=main.engine.retrieve(Retrieval(index_id=row['id'],query='energy meters',top_k=2,min_score=-1))
    hit=result['hits'][0];assert hit['document_id']==a
    source=c.get(hit['source_url']);assert source.status_code==200
    page=source.json()['pages'][0]
    assert page['text'][page['highlight_start']:page['highlight_end']]==hit['text']
    projection=c.get('/indexes/'+row['id']+'/visualization').json()
    assert len(projection['points'])==row['stats']['vectors']
    assert all(np.isfinite(p['x']) for p in projection['points'])
    assert c.delete('/documents/'+a).status_code==204
    assert main.engine.row(row['id'])['status']=='invalidated'
    assert c.post('/retrieve',json={'index_id':row['id'],'query':'meters'}).status_code==409
    assert c.post('/answers',json={'retrieval_id':result['id']}).status_code==404

def test_missing_provider_keeps_retrieval_and_no_context(service,controlled):
    main,c=service;row=build(main,c)
    result=c.post('/rag',json={'index_id':row['id'],'query':'energy meters','min_score':-1})
    assert result.status_code==200,result.text
    assert result.json()['retrieval']['hits']
    assert result.json()['generation']['status']=='provider_unconfigured'
    assert result.json()['generation']['answer'] is None
    assert generate('unknown',[])['answer']==INSUFFICIENT
    assert c.get('/provider').json()['configured'] is False

def test_corruption_and_failed_job(service,controlled,monkeypatch):
    main,c=service;row=build(main,c)
    (main.engine.root/row['id']/'index.faiss').write_bytes(b'damaged')
    result=c.post('/retrieve',json={'index_id':row['id'],'query':'meters'})
    assert result.status_code==409 and 'damaged' in result.json()['detail']
    assert main.engine.row(row['id'])['status']=='failed'
    monkeypatch.setattr(embeddings,'load_model',lambda _:(_ for _ in ()).throw(RuntimeError('offline fixture')))
    failed=main.engine.create(Build(**{**row['config'],'rebuild':True}),asynchronous=False)
    assert failed['status']=='failed' and 'offline fixture' in failed['error']

def test_cancellation_and_restart_recovery(service,controlled,monkeypatch):
    main,c=service;id=add(c);entered=threading.Event();release=threading.Event()
    def loading(_):entered.set();assert release.wait(5)
    monkeypatch.setattr(embeddings,'load_model',loading)
    row=c.post('/indexes',json={'document_ids':[id]}).json()
    assert entered.wait(5)
    assert c.post('/indexes/'+row['id']+'/cancel').json()['cancel_requested']==1
    release.set()
    deadline=time.monotonic()+5
    while main.engine.row(row['id'])['status'] in ('queued','running') and time.monotonic()<deadline:time.sleep(.01)
    assert main.engine.row(row['id'])['status']=='cancelled'
    with main.connect() as db:
        db.execute("UPDATE vector_indexes SET status='running',cancel_requested=0 WHERE id=?",(row['id'],))
    recovered=Engine(main.connect,main.DATA)
    assert recovered.row(row['id'])['status']=='failed'
    assert 'restarted' in recovered.row(row['id'])['error']
    recovered.shutdown()

def test_validation(service):
    _,c=service
    assert c.post('/indexes',json={'document_ids':[]}).status_code==422
    assert c.post('/indexes',json={'document_ids':['x'],'model_id':'invented'}).status_code==422
    assert c.post('/indexes',json={'document_ids':['missing']}).status_code==404
    assert c.post('/retrieve',json={'index_id':'x','query':' '}).status_code==422
    assert c.post('/retrieve',json={'index_id':'x','query':'valid','top_k':21}).status_code==422
    assert pages_for(['abc','def'],2,6)==[1,2]
    assert pages_for(['abc','def'],5,8)==[2]

def provider_env(monkeypatch):
    monkeypatch.setenv('LLM_API_BASE','https://provider.test/v1')
    monkeypatch.setenv('LLM_API_KEY','test-key-never-echo')
    monkeypatch.setenv('LLM_MODEL','test-contract-model')

def completion(value):
    return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(value)}}]})

def test_provider_request_and_citation_mapping(service,controlled,monkeypatch):
    main,c=service;row=build(main,c);r=main.engine.retrieve(Retrieval(index_id=row['id'],query='meters',min_score=-1))
    provider_env(monkeypatch)
    hit=r['hits'][0];quote='library lends energy meters'
    def handler(request):
        payload=json.loads(request.content)
        assert request.url.path=='/v1/chat/completions'
        assert request.headers['Authorization']=='Bearer test-key-never-echo'
        assert payload['model']=='test-contract-model'
        assert json.loads(payload['messages'][1]['content'])['sources'][0]['text']==hit['text']
        return completion({'insufficient_context':False,'claims':[{'text':'Energy meters can be borrowed from the library.','citations':[{'source_id':1,'quote':quote}]}]})
    answer=main.engine.answer(r['id'],transport=httpx.MockTransport(handler))
    assert answer['status']=='generated' and answer['answer'].endswith('[1]')
    citation=answer['citations'][0]
    original=c.get('/documents/'+hit['document_id']).json()['text']
    assert original[citation['start']:citation['end']]==quote
    assert 'test-key-never-echo' not in json.dumps(c.get('/provider').json())
    with main.connect() as db:assert db.execute('SELECT count(*) FROM answers').fetchone()[0]==1

@pytest.mark.parametrize('value',[
 {'insufficient_context':False,'claims':[{'text':'Unsupported','citations':[{'source_id':999,'quote':'fabricated quote'}]}]},
 {'insufficient_context':False,'claims':[{'text':'Unsupported','citations':[{'source_id':1,'quote':'fabricated quote'}]}]},
 {'insufficient_context':False,'claims':[{'text':'Unsupported','citations':[]}]},
 {'claims':[]},
])
def test_invalid_citations_fail_closed(value,monkeypatch):
    provider_env(monkeypatch)
    hit={'id':'c','document_id':'d','source_name':'notes','page_numbers':[1],'start':0,'text':'The library lends energy meters.'}
    result=generate('meters',[hit],httpx.MockTransport(lambda _:completion(value)))
    assert result['status']=='invalid_provider_answer' and result['answer'] is None

@pytest.mark.parametrize('status',[401,403,429,500])
def test_provider_http_failures_keep_sources(status,monkeypatch):
    provider_env(monkeypatch)
    hit={'source_name':'notes','page_numbers':[1],'text':'Evidence.'}
    result=generate('question',[hit],httpx.MockTransport(lambda _:httpx.Response(status,json={'error':'private fixture'})))
    assert result['status']=='provider_error' and result['answer'] is None
    assert 'private fixture' not in result['message'] and 'test-key' not in result['message']

def test_provider_timeout_insufficient_and_bad_json(monkeypatch):
    provider_env(monkeypatch);hit={'source_name':'notes','page_numbers':[1],'text':'Evidence.'}
    def timeout(request):raise httpx.ReadTimeout('timeout',request=request)
    assert 'timed out' in generate('q',[hit],httpx.MockTransport(timeout))['message']
    result=generate('q',[hit],httpx.MockTransport(lambda _:completion({'insufficient_context':True,'claims':[]})))
    assert result['answer']==INSUFFICIENT
    result=generate('q',[hit],httpx.MockTransport(lambda _:httpx.Response(200,json={'choices':[]})))
    assert result['status']=='invalid_provider_answer'

@pytest.mark.parametrize('model_id',['minilm','bge-small'])
def test_model_specific_formatting_and_normalization(model_id,monkeypatch):
    recorded=[]
    class StubModel:
        def tokenizer(self,text,**kwargs):return {'input_ids':[1,2,3]}
        def encode(self,texts,**kwargs):
            recorded.append((texts,kwargs))
            return np.array([[2.]+[0.]*383 for _ in texts],dtype='float32')
    monkeypatch.setattr(embeddings,'load_model',lambda _:StubModel())
    doc=embeddings.encode(['passage'],model_id)
    q=embeddings.encode(['question'],model_id,query=True)
    assert recorded[0][0]==['passage']
    assert recorded[1][0]==[embeddings.MODELS[model_id]['query_prefix']+'question']
    assert recorded[1][1]['prompt']=='' and recorded[1][1]['normalize_embeddings'] is True
    assert np.linalg.norm(doc[0])==pytest.approx(1) and q.shape==(1,384)

def test_model_revision_separation_and_damaged_cache(service,controlled,monkeypatch):
    main,c=service;row=build(main,c)
    other=main.engine.create(Build(**{**row['config'],'model_id':'bge-small'}),asynchronous=False)
    assert other['id']!=row['id'] and other['model_revision']!=row['model_revision']
    assert other['stats']['cache_hits']==0
    with main.connect() as db:
        db.execute("UPDATE embedding_cache SET vector=? WHERE model_id='minilm'",(np.zeros(384,dtype='float32').tobytes(),))
    rebuilt=main.engine.create(Build(**{**row['config'],'rebuild':True}),asynchronous=False)
    assert rebuilt['status']=='ready' and rebuilt['stats']['cache_hits']==0
    monkeypatch.setitem(embeddings.MODELS,'minilm',{**embeddings.MODELS['minilm'],'revision':'test-new-revision'})
    changed=main.engine.create(Build(**row['config']),asynchronous=False)
    assert changed['id']!=row['id'] and changed['model_revision']=='test-new-revision'
    assert changed['stats']['cache_hits']==0

def test_report_contains_saved_retrieval_and_answer_states(service,controlled):
    main,c=service;row=build(main,c)
    result=c.post('/rag',json={'index_id':row['id'],'query':'meters','min_score':-1})
    assert result.status_code==200
    report=c.get('/pipeline/report').json()
    assert report['totals']=={'retrievals':1,'answers':1}
    assert report['indexes'][0]['id']==row['id']
    assert report['retrievals'][0]['hits'] and report['answers'][0]['status']=='provider_unconfigured'

import json
import os
import sqlite3
import time
import asyncio
import threading
from boundaries import RequestBoundary,allowed_origins
PDF_SLOTS=threading.BoundedSemaphore(2)
from ingestion import safe_name,extract_pages
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
from pathlib import Path
from uuid import uuid4
import pymupdf as fitz
import numpy as np
from fastapi import FastAPI, UploadFile, HTTPException
from contextlib import asynccontextmanager
from pipeline import Engine, Build, Retrieval, Answer
import embeddings
from generation import public_configuration,probe
from datasets import DatasetStore, router as dataset_router
from benchmarks import BenchmarkService, router as benchmark_router
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field, model_validator
from chunking import chunk_text

DATA = Path(os.getenv('RAGLAB_DATA_DIR', './data'))
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / 'raglab.sqlite3'
DEFAULT_MODEL = next((key for key,value in embeddings.MODELS.items() if os.getenv('EMBEDDING_MODEL') in (key,value['repository'])), 'minilm')
MODEL = embeddings.MODELS[DEFAULT_MODEL]['repository']

def connect(path=DB):
    db = sqlite3.connect(path, timeout=30)
    db.execute('PRAGMA journal_mode=WAL')
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db

with connect() as db:
    db.executescript('''CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,name TEXT,text TEXT,pages TEXT,bytes INTEGER,created TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS experiments(id TEXT PRIMARY KEY,document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,name TEXT,config TEXT,chunks TEXT,metrics TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1),value TEXT);''')
engine = Engine(connect, DATA)
dataset_store = DatasetStore(connect)
benchmark_service = BenchmarkService(connect, engine, dataset_store)
from adaptive import AdaptiveService, router as adaptive_router
adaptive_service = AdaptiveService(connect, benchmark_service, dataset_store)
from answer_reviews import AnswerReviewStore,router as answer_review_router
answer_review_store=AnswerReviewStore(connect)
benchmark_service.answer_reviews=answer_review_store

@asynccontextmanager
async def lifespan(app):
    yield
    adaptive_service.shutdown()
    benchmark_service.shutdown()
    engine.shutdown()

app = FastAPI(title='RAGLab API', lifespan=lifespan)
app.include_router(dataset_router(dataset_store))
app.include_router(benchmark_router(benchmark_service))
app.include_router(adaptive_router(adaptive_service))
app.include_router(answer_review_router(answer_review_store,benchmark_service))
ORIGINS=allowed_origins(os.getenv('CORS_ORIGINS','http://localhost:3000,http://127.0.0.1:3000'))
app.add_middleware(CORSMiddleware,allow_origins=ORIGINS,allow_methods=['GET','POST','PUT','DELETE','OPTIONS'],allow_headers=['Content-Type'])
app.add_middleware(RequestBoundary,origins=ORIGINS)

def encode(texts):
    try:
        return embeddings.encode_untruncated(texts, DEFAULT_MODEL)
    except Exception as exc:
        raise HTTPException(503, 'Embedding model unavailable. Check model downloads/cache. '+str(exc)[:180])

def document(id):
    with connect() as db:
        row = db.execute('SELECT * FROM documents WHERE id=?',(id,)).fetchone()
    if row is None:
        raise HTTPException(404,'Document not found')
    return dict(row)

@app.get('/health')
def health():
    return {'status':'ok','embedding_model':MODEL,'model_loaded':embeddings.load_model.cache_info().currsize > 0,'models':list(embeddings.MODELS.values()),'llm':public_configuration()}

@app.get('/documents')
def documents():
    with connect() as db:
        return [dict(r) for r in db.execute('SELECT id,name,bytes,created,json_array_length(pages) AS pages,length(text) AS characters FROM documents ORDER BY created DESC')]

@app.get('/documents/{id}')
def get_document(id: str):
    d = document(id)
    d['pages'] = json.loads(d['pages'])
    return d

@app.post('/documents',status_code=201)
async def upload(file: UploadFile):
    try:name=safe_name(file.filename)
    except ValueError as exc:raise HTTPException(422,str(exc))
    ext = Path(name).suffix.lower()
    if ext not in {'.pdf','.txt','.md'}:
        raise HTTPException(415,'Choose a PDF, UTF-8 TXT, or Markdown file.')
    raw = await file.read(10*1024*1024+1)
    if len(raw)>10*1024*1024:
        raise HTTPException(413,'File exceeds the 10 MB limit.')
    try:
        if ext=='.pdf':
            if not PDF_SLOTS.acquire(blocking=False):raise HTTPException(429,'Two PDF extractions are active. Retry after one finishes.',headers={'Retry-After':'5'})
            try:pages=await asyncio.to_thread(extract_pages,raw,ext)
            finally:PDF_SLOTS.release()
        else:pages=await asyncio.to_thread(extract_pages,raw,ext)
    except HTTPException:raise
    except Exception as e:
        raise HTTPException(422,'Could not extract text: '+str(e)[:180])
    text = '\n\n'.join(pages)
    if len(text)>2_000_000:
        raise HTTPException(413,'Extracted text exceeds 2 million characters. Split this document before uploading.')
    if not text.strip():
        raise HTTPException(422,'No selectable text found. OCR scanned PDFs before uploading.')
    id = str(uuid4())
    with connect() as db:
        db.execute('INSERT INTO documents(id,name,text,pages,bytes) VALUES(?,?,?,?,?)',(id,name,text,json.dumps(pages),len(raw)))
    return get_document(id)

@app.delete('/documents/{id}',status_code=204)
def delete_document(id: str):
    document(id)
    engine.invalidate_document(id)
    with connect() as db:
        db.execute('DELETE FROM documents WHERE id=?',(id,))
    return Response(status_code=204)

class Config(BaseModel):
    document_id: str
    strategy: str = 'fixed'
    budget: int = Field(120,ge=8,le=2048)
    overlap: int = Field(20,ge=0)
    threshold: float = Field(.55,ge=-1,le=1)
    name: str = Field('Untitled experiment',min_length=1,max_length=120)
    @model_validator(mode='after')
    def valid(self):
        if self.strategy not in ['fixed','sentence','semantic']:
            raise ValueError('Unknown chunking strategy')
        if self.overlap>=self.budget:
            raise ValueError('Overlap must be smaller than chunk size')
        return self

def run(c):
    start = time.perf_counter()
    text = document(c.document_id)['text']
    chunks = chunk_text(text,c.strategy,c.budget,c.overlap,c.threshold,encode)
    sizes = [x['tokens'] for x in chunks]
    metrics = {'chunks':len(chunks),'avg_tokens':round(float(np.mean(sizes)),1),'min_tokens':min(sizes),'max_tokens':max(sizes),'latency_ms':round((time.perf_counter()-start)*1000,2),'total_tokens':sum(sizes)}
    return chunks, metrics

@app.post('/chunks/preview')
def preview(c: Config):
    chunks,metrics=run(c)
    return {'chunks':chunks,'metrics':metrics}

@app.post('/experiments',status_code=201)
def experiment(c: Config):
    chunks,metrics=run(c)
    id=str(uuid4())
    with connect() as db:
        db.execute('INSERT INTO experiments(id,document_id,name,config,chunks,metrics) VALUES(?,?,?,?,?,?)',(id,c.document_id,c.name,json.dumps(c.model_dump()),json.dumps(chunks),json.dumps(metrics)))
    return {'id':id,'chunks':chunks,'metrics':metrics}

@app.get('/experiments')
def experiments():
    with connect() as db:
        rows=db.execute('SELECT * FROM experiments ORDER BY created DESC').fetchall()
    return [{**dict(r),'config':json.loads(r['config']),'chunks':json.loads(r['chunks']),'metrics':json.loads(r['metrics'])} for r in rows]

class Query(BaseModel):
    experiment_id: str
    query: str = Field(min_length=1,max_length=2000)
    top_k: int = Field(3,ge=1,le=10)
    expected: str = Field('',max_length=2000)

@app.post('/search')
def search(q: Query):
    # Backward-compatible Phase 1 endpoint, now backed by a persistent index.
    with connect() as db:
        row=db.execute('SELECT * FROM experiments WHERE id=?',(q.experiment_id,)).fetchone()
    if not row:
        raise HTTPException(404,'Choose a saved experiment')
    saved=json.loads(row['config'])
    config=Build(document_ids=[row['document_id']],model_id=DEFAULT_MODEL,strategy=saved['strategy'],budget=saved['budget'],
                 overlap=saved['overlap'],threshold=saved['threshold'])
    index=engine.create(config,asynchronous=False)
    if index['status']!='ready':
        raise HTTPException(409,index.get('error') or 'Index is still being built. Try again when ready.')
    result=engine.retrieve(Retrieval(index_id=index['id'],query=q.query,top_k=q.top_k,expected=q.expected,min_score=-1))
    return {**result,'answer':'\n\n'.join(h['text'] for h in result['hits']),
            'answer_mode':'extractive: retrieved passages, no generative LLM'}

@app.get('/models')
def models():
    return list(embeddings.MODELS.values())

@app.get('/provider')
def provider():
    return public_configuration()

@app.post('/provider/check')
def provider_check():return probe()

@app.get('/storage')
def storage():
    indexes=engine.list()
    with connect() as db:
        integrity=db.execute('PRAGMA quick_check').fetchone()[0]
        counts={name:db.execute('SELECT count(*) FROM '+name).fetchone()[0] for name in ['documents','benchmark_runs','retrievals','answers']}
    return {'counts':counts,'database_bytes':DB.stat().st_size,'sqlite_integrity':integrity,'indexes':len(indexes),'ready_indexes':sum(i['status']=='ready' for i in indexes),'active_indexes':sum(i['status'] in ('queued','running') for i in indexes),'artifact_bytes':sum(i['stats'].get('disk_bytes',0) for i in indexes),'scope':'Local single-process storage. Back up while stopped; never publish private exports.'}

@app.post('/storage/check-indexes')
def check_indexes():
    rows=engine.list();return {'checked':sum(i['status']=='ready' for i in rows),'invalid_ids':[i['id'] for i in rows if i['status']=='ready' and not engine.artifacts_valid(i)]}

@app.get('/indexes')
def indexes():
    return engine.list()

@app.post('/indexes',status_code=202)
def create_index(c: Build):
    return engine.create(c)

@app.get('/indexes/{id}')
def get_index(id: str):
    return engine.row(id)

@app.post('/indexes/{id}/cancel')
def cancel_index(id: str):
    return engine.cancel(id)

@app.post('/indexes/{id}/rebuild',status_code=202)
def rebuild_index(id: str):
    c=Build(**{**engine.row(id)['config'],'rebuild':True})
    return engine.create(c)

@app.get('/indexes/{id}/visualization')
def visualization(id: str):
    return engine.visualization(id)

@app.get('/indexes/{id}/chunks/{ordinal}/source')
def source(id: str,ordinal: int):
    return engine.source(id,ordinal)

@app.post('/retrieve')
def retrieve(q: Retrieval):
    return engine.retrieve(q)

@app.post('/answers')
def answer(q: Answer):
    return engine.answer(q.retrieval_id)

@app.post('/rag')
def rag(q: Retrieval):
    retrieval=engine.retrieve(q)
    return {'retrieval':retrieval,'generation':engine.answer(retrieval['retrieval_id'])}

@app.get('/settings')
def settings():
    with connect() as db:
        row=db.execute('SELECT value FROM settings WHERE id=1').fetchone()
    return json.loads(row['value']) if row else {'project_name':'University research','dark_mode':False}

class Settings(BaseModel):
    project_name: str = Field(min_length=1,max_length=100)
    dark_mode: bool = False
    motion: str = Field('system',pattern='^(system|reduced)$')

@app.put('/settings')
def save_settings(s: Settings):
    with connect() as db:
        db.execute('INSERT OR REPLACE INTO settings VALUES(1,?)',(s.model_dump_json(),))
    return s


@app.get('/pipeline/report')
def pipeline_report():
    with connect() as db:
        retrieval_rows=db.execute('SELECT result FROM retrievals ORDER BY rowid DESC LIMIT 500').fetchall()
        answer_rows=db.execute('SELECT result FROM answers ORDER BY rowid DESC LIMIT 500').fetchall()
        retrieval_count=db.execute('SELECT count(*) FROM retrievals').fetchone()[0]
        answer_count=db.execute('SELECT count(*) FROM answers').fetchone()[0]
    return {'indexes':engine.list(),'retrievals':[json.loads(r[0]) for r in retrieval_rows],
            'answers':[json.loads(r[0]) for r in answer_rows],
            'totals':{'retrievals':retrieval_count,'answers':answer_count},'history_limit':500,
            'provider':public_configuration()}


@app.get('/dashboard')
def dashboard():
    with connect() as db:
        counts={table:db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ['documents','experiments','vector_indexes','benchmark_runs','retrievals']}
        ids=[r[0] for r in db.execute('SELECT id FROM benchmark_runs ORDER BY rowid DESC LIMIT 5')]
    runs=[];recommendation=None
    for id in ids:
        run=benchmark_service.get(id)
        runs.append({k:run[k] for k in ['id','name','status','created','completed_configs','total_configs','completed_measurements','total_measurements'] }|{'provisional':run['snapshot']['provisional'],'dataset_name':run['snapshot']['name']})
        if recommendation is None and run['status']=='completed' and run['snapshot'].get('split')!='test':
            ranked=benchmark_service.leaderboard(id)['ranked']
            if ranked:recommendation={'run_id':id,'config':ranked[0]['config'],'score':ranked[0]['optimizer']['score'],'explanation':ranked[0]['optimizer']['explanation'],'sample_size':ranked[0]['optimizer']['sample_size'],'provisional':run['snapshot']['provisional']}
    datasets=dataset_store.list()
    return {'counts':counts,'recent_runs':runs,'recommendation':recommendation,'reviewed_questions':sum(d['reviewed_count'] for d in datasets),'total_questions':sum(d['question_count'] for d in datasets),'provider':public_configuration()}

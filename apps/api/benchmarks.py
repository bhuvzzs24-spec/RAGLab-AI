"""Repeatable 18-configuration benchmarks over immutable dataset snapshots."""
import csv
import io
import json
import platform
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version, PackageNotFoundError
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field, model_validator
import embeddings
from datasets import sha
from evaluation import METHOD_VERSION, METHODOLOGY, evaluate_retrieval, aggregate, exact_match, optimize
from generation import public_configuration
from pipeline import Build, Retrieval

class RunInput(BaseModel):
    dataset_id:str
    name:str=Field('Retrieval benchmark',min_length=1,max_length=120)
    budgets:list[int]=Field(default_factory=lambda:[64,128,256],min_length=3,max_length=3)
    top_k:int=Field(3,ge=1,le=20)
    repetitions:int=Field(2,ge=1,le=5)
    min_score:float=Field(.2,ge=-1,le=1)
    evidence_overlap:float=Field(.5,gt=0,le=1)
    semantic_threshold:float=Field(.55,ge=-1,le=1)
    overlap_ratio:float=Field(.15,ge=0,lt=.5)
    seed:int=Field(7,ge=0,le=2**31-1)
    include_unreviewed:bool=False
    generate_answers:bool=False
    rebuild_indexes:bool=True
    evaluation_split:Literal['all','train','validation','test']='all'
    @model_validator(mode='after')
    def valid(self):
        if len(set(self.budgets))!=3 or any(b<8 or b>2048 for b in self.budgets):raise ValueError('Choose exactly three distinct word budgets between 8 and 2048.')
        if not self.name.strip():raise ValueError('Run name cannot be blank.')
        self.budgets=sorted(self.budgets)
        return self


def grid(settings):
    return [{'profile':f'{budget} words','model_id':model,'strategy':strategy,'budget':budget,
             'overlap':int(budget*settings.overlap_ratio) if strategy=='fixed' else 0,
             'threshold':settings.semantic_threshold}
            for strategy in ['fixed','sentence','semantic'] for model in ['minilm','bge-small'] for budget in settings.budgets]

class Stopped(Exception):pass

class BenchmarkService:
    def __init__(self,connect,engine,datasets):
        self.connect,self.engine,self.datasets=connect,engine,datasets
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='raglab-benchmark')
        self.lock=threading.Lock()
        with connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS benchmark_runs(id TEXT PRIMARY KEY,dataset_id TEXT,name TEXT,snapshot TEXT,settings TEXT,
                    status TEXT,phase TEXT,cancel_requested INTEGER DEFAULT 0,error TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated TEXT DEFAULT CURRENT_TIMESTAMP,resume_count INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS benchmark_configs(id TEXT PRIMARY KEY,run_id TEXT REFERENCES benchmark_runs(id) ON DELETE CASCADE,
                    ordinal INTEGER,config TEXT,status TEXT DEFAULT 'queued',index_id TEXT,indexing_time_ms REAL,
                    index_preparation_ms REAL,index_cache_reused INTEGER DEFAULT 0,cache_hits INTEGER DEFAULT 0,metrics TEXT DEFAULT '{}',error TEXT);
                CREATE TABLE IF NOT EXISTS benchmark_measurements(id TEXT PRIMARY KEY,run_id TEXT REFERENCES benchmark_runs(id) ON DELETE CASCADE,
                    config_id TEXT REFERENCES benchmark_configs(id) ON DELETE CASCADE,question_id TEXT,repetition INTEGER,payload TEXT,
                    UNIQUE(config_id,question_id,repetition));
            ''')
            db.execute("UPDATE benchmark_runs SET status='interrupted',phase='Server restarted',error='Interrupted by a server restart. Resume to continue missing measurements.' WHERE status IN ('queued','running')")
            db.execute("UPDATE benchmark_configs SET status='interrupted' WHERE status='running'")

    def shutdown(self):
        with self.connect() as db:db.execute("UPDATE benchmark_runs SET cancel_requested=1 WHERE status IN ('queued','running')")
        self.executor.shutdown(wait=True,cancel_futures=True)

    def update(self,id,**values):
        assert values.keys()<={'status','phase','cancel_requested','error','resume_count'}
        with self.connect() as db:db.execute('UPDATE benchmark_runs SET '+','.join(k+'=?' for k in values)+',updated=CURRENT_TIMESTAMP WHERE id=?',(*values.values(),id))

    def update_config(self,id,**values):
        assert values.keys()<={'status','index_id','indexing_time_ms','index_preparation_ms','index_cache_reused','cache_hits','metrics','error'}
        with self.connect() as db:db.execute('UPDATE benchmark_configs SET '+','.join(k+'=?' for k in values)+' WHERE id=?',(*values.values(),id))

    def config_rows(self,id):
        with self.connect() as db:rows=db.execute('SELECT * FROM benchmark_configs WHERE run_id=? ORDER BY ordinal',(id,)).fetchall()
        return [{**dict(r),'config':json.loads(r['config']),'metrics':json.loads(r['metrics'])} for r in rows]

    def get(self,id):
        with self.connect() as db:
            row=db.execute('SELECT * FROM benchmark_runs WHERE id=?',(id,)).fetchone()
            count=db.execute('SELECT count(*) FROM benchmark_measurements WHERE run_id=?',(id,)).fetchone()[0]
        if not row:raise HTTPException(404,'Benchmark run not found.')
        result=dict(row);result['snapshot']=json.loads(result['snapshot']);result['settings']=json.loads(result['settings'])
        configs=self.config_rows(id)
        result.update({'configs':configs,'completed_configs':sum(c['status']=='completed' for c in configs),
                       'failed_configs':sum(c['status']=='failed' for c in configs),'total_configs':len(configs),
                       'completed_measurements':count,'total_measurements':len(configs)*len(result['snapshot']['questions'])*result['settings']['repetitions'],
                       'methodology':METHODOLOGY,'provider':public_configuration()})
        return result

    def list(self):
        with self.connect() as db:ids=[r[0] for r in db.execute('SELECT id FROM benchmark_runs ORDER BY created DESC,rowid DESC LIMIT 100')]
        result=[]
        for id in ids:
            row=self.get(id)
            row['snapshot']={**{k:v for k,v in row['snapshot'].items() if k!='questions'},'question_count':len(row['snapshot']['questions'])}
            result.append({k:v for k,v in row.items() if k not in ('configs','methodology')})
        return result

    def source_check(self,snapshot):
        for source in snapshot['sources']:
            try:current=self.datasets.resolve_document(source['id'])
            except HTTPException:raise HTTPException(409,'A benchmark source was deleted. Historical results remain exportable; create a new dataset/run.')
            if sha(current['text'])!=source['sha256']:raise HTTPException(409,'Benchmark source changed. Restore the exact source or create a new run.')
        if snapshot.get('fingerprint'):
            body={k:v for k,v in snapshot.items() if k!='fingerprint'}
            if sha(json.dumps(body,sort_keys=True))!=snapshot['fingerprint']:raise HTTPException(409,'Dataset snapshot integrity check failed.')

    def start(self,settings,asynchronous=True,*,snapshot_override=None,configs_override=None,provenance=None):
        snapshot=snapshot_override or self.datasets.snapshot(settings.dataset_id,settings.include_unreviewed,settings.evaluation_split)
        if len(snapshot['questions'])>100:raise HTTPException(422,'Use at most 100 included questions per local benchmark run. Split larger datasets.')
        if settings.generate_answers and not public_configuration()['configured']:raise HTTPException(422,'LLM credentials/model are not configured. Disable answer generation; retrieval benchmarks work locally.')
        metadata={**settings.model_dump(),'model_registry':embeddings.MODELS,'evaluation_version':METHOD_VERSION,
                  'timing_mode':'one excluded query warm-up per config; shuffled seeded config/question order',
                  'runtime':{'python':platform.python_version(),'system':platform.system(),'machine':platform.machine()}}
        metadata['adaptive_provenance']=provenance
        metadata['packages']={}
        for package in ['sentence-transformers','faiss-cpu','numpy','torch']:
            try:metadata['packages'][package]=version(package)
            except PackageNotFoundError:metadata['packages'][package]='not-installed'
        id=str(uuid4())
        with self.connect() as db:
            db.execute('INSERT INTO benchmark_runs(id,dataset_id,name,snapshot,settings,status,phase) VALUES(?,?,?,?,?,?,?)',
                       (id,settings.dataset_id,settings.name.strip(),json.dumps(snapshot),json.dumps(metadata),'queued','Waiting for benchmark worker'))
            for ordinal,config in enumerate(configs_override if configs_override is not None else grid(settings)):
                db.execute('INSERT INTO benchmark_configs(id,run_id,ordinal,config) VALUES(?,?,?,?)',(str(uuid4()),id,ordinal,json.dumps(config)))
        if asynchronous:self.executor.submit(self.execute,id)
        else:self.execute(id)
        return self.get(id)

    def check_cancel(self,id):
        with self.connect() as db:row=db.execute('SELECT cancel_requested FROM benchmark_runs WHERE id=?',(id,)).fetchone()
        if not row or row[0]:raise Stopped()

    def cancel(self,id):
        row=self.get(id)
        if row['status'] in ('queued','running'):self.update(id,cancel_requested=1,phase='Cancellation requested; finishing current model call')
        return self.get(id)

    def resume(self,id,asynchronous=True):
        with self.lock:
            row=self.get(id)
            if row['status'] in ('queued','running'):raise HTTPException(409,'This benchmark is already queued or running.')
            if row['status']=='completed':raise HTTPException(409,'Completed benchmarks are immutable. Start a repeat run instead.')
            self.source_check(row['snapshot'])
            if row['settings']['model_registry']!=embeddings.MODELS:raise HTTPException(409,'Pinned model registry changed. Start a new run to avoid mixing model versions.')
            self.update(id,status='queued',phase='Resuming missing measurements',cancel_requested=0,error=None,resume_count=row['resume_count']+1)
            with self.connect() as db:db.execute("UPDATE benchmark_configs SET status='queued',error=NULL WHERE run_id=? AND status!='completed'",(id,))
            if asynchronous:self.executor.submit(self.execute,id)
            else:self.execute(id)
        return self.get(id)

    def measurements(self,id,config_id=None):
        self.get(id)
        sql='SELECT payload FROM benchmark_measurements WHERE run_id=?';params=[id]
        if config_id:sql+=' AND config_id=?';params.append(config_id)
        with self.connect() as db:rows=db.execute(sql+' ORDER BY rowid',params).fetchall()
        return [json.loads(r[0]) for r in rows]

    def execute(self,id):
        current_config=None;owned_index=None
        try:
            self.check_cancel(id);run=self.get(id);settings=run['settings'];snapshot=run['snapshot']
            self.source_check(snapshot);self.update(id,status='running',phase='Preparing configuration matrix',error=None)
            configs=self.config_rows(id);random.Random(settings['seed']).shuffle(configs)
            for c in configs:
                if c['status']=='completed':continue
                self.check_cancel(id);self.source_check(snapshot)
                current_config=c['id'];owned_index=None;cfg=c['config']
                label=f"{cfg['model_id']} / {cfg['strategy']} / {cfg['budget']} words"
                self.update_config(c['id'],status='running',error=None)
                try:
                    self.update(id,phase='Indexing '+label)
                    index=None;prepare=time.perf_counter()
                    if c['index_id']:
                        try:
                            old=self.engine.row(c['index_id'])
                            if old['status']=='ready' and self.engine.artifacts_valid(old):index={**old,'cache_reused':True}
                        except HTTPException:pass
                    if index is None:
                        index=self.engine.create(Build(document_ids=snapshot['document_ids'],model_id=cfg['model_id'],strategy=cfg['strategy'],
                            budget=cfg['budget'],overlap=cfg['overlap'],threshold=cfg['threshold'],rebuild=settings['rebuild_indexes']))
                        self.update_config(c['id'],index_id=index['id'])
                        if not index.get('cache_reused'):owned_index=index['id']
                    reused=index.get('cache_reused',False)
                    while index['status'] in ('queued','running'):
                        self.check_cancel(id)
                        self.update(id,phase=f"{label}: {index['phase']} ({index['progress']}/{index['total']} vectors)")
                        time.sleep(.15);index=self.engine.row(index['id'])
                    self.check_cancel(id)
                    if index['status']!='ready':raise RuntimeError(index.get('error') or 'Index did not become ready.')
                    self.update_config(c['id'],index_id=index['id'],indexing_time_ms=c['indexing_time_ms'] if c['indexing_time_ms'] is not None else (None if reused else index['stats']['build_ms']),
                        index_preparation_ms=(time.perf_counter()-prepare)*1000,index_cache_reused=int(reused),cache_hits=index['stats']['cache_hits'])
                    questions=snapshot['questions']
                    self.update(id,phase='Excluded warm-up: '+label)
                    self.engine.retrieve(Retrieval(index_id=index['id'],query=questions[0]['question'],top_k=settings['top_k'],min_score=settings['min_score']),persist=False)
                    schedule=[(rep,q) for rep in range(settings['repetitions']) for q in questions]
                    random.Random(settings['seed']+c['ordinal']).shuffle(schedule)
                    with self.connect() as db:done={(r[0],r[1]) for r in db.execute('SELECT question_id,repetition FROM benchmark_measurements WHERE config_id=?',(c['id'],))}
                    for rep,q in schedule:
                        if (q['id'],rep) in done:continue
                        self.check_cancel(id)
                        self.update(id,phase=f"Retrieving {label}: question {q['id']}, repetition {rep+1}/{settings['repetitions']}")
                        started=time.perf_counter()
                        result=self.engine.retrieve(Retrieval(index_id=index['id'],query=q['question'],top_k=settings['top_k'],min_score=settings['min_score']))
                        wall=(time.perf_counter()-started)*1000
                        metrics=evaluate_retrieval(result['hits'],q,settings['top_k'],settings['evidence_overlap'])
                        generation={'status':'disabled'};correctness=None
                        if settings['generate_answers']:
                            self.check_cancel(id);self.update(id,phase='Generating optional answer: '+label)
                            generation=self.engine.answer(result['retrieval_id'])
                            if generation['status']=='generated' and q['answerability']=='answerable':correctness=exact_match(generation['answer'],q['reference_answers'])
                        metrics.update({'answer_exact_match':correctness,'groundedness':None})
                        hits=[{key:h.get(key) for key in ['id','document_id','source_name','ordinal','chunk_index','part','start','end','score','page_numbers','source_url']} for h in result['hits']]
                        measurement={'id':str(uuid4()),'run_id':id,'config_id':c['id'],'index_id':index['id'],'retrieval_id':result['retrieval_id'],
                            'question_id':q['id'],'question':q['question'],'answerability':q['answerability'],'human_reviewed':q['human_reviewed'],
                            'repetition':rep,'latency_ms':result['latency_ms'],'wall_latency_ms':wall,'timings':result['timings'],
                            'metrics':metrics,'hits':hits,'generation_status':generation['status'],'generation':generation,
                            'model_revision':index['model_revision'],'evaluation_version':METHOD_VERSION}
                        with self.connect() as db:db.execute('INSERT OR IGNORE INTO benchmark_measurements VALUES(?,?,?,?,?,?)',
                            (measurement['id'],id,c['id'],q['id'],rep,json.dumps(measurement)))
                    self.check_cancel(id)
                    records=self.measurements(id,c['id'])
                    if len(records)!=len(schedule):raise RuntimeError('Incomplete measurement set; resume this configuration.')
                    self.update_config(c['id'],status='completed',metrics=json.dumps(aggregate(records)))
                except Stopped:raise
                except Exception as exc:
                    message=exc.detail if isinstance(exc,HTTPException) else str(exc)
                    self.update_config(c['id'],status='failed',error=str(message)[:500])
                owned_index=None;current_config=None
            final=self.get(id);count=final['completed_configs'];failed=final['failed_configs']
            self.update(id,status='completed' if failed==0 else ('completed_with_errors' if count else 'failed'),
                        phase='Completed' if failed==0 else f'Finished with {failed} failed configurations',
                        error=None if failed==0 else 'Failed configurations are excluded from ranking. Fix the reported cause and resume.')
        except Stopped:
            if owned_index:self.engine.cancel(owned_index)
            if current_config:self.update_config(current_config,status='cancelled')
            self.update(id,status='cancelled',phase='Cancelled; completed measurements preserved')
        except Exception as exc:
            message=exc.detail if isinstance(exc,HTTPException) else str(exc)
            if current_config:self.update_config(current_config,status='failed',error=str(message)[:500])
            self.update(id,status='failed',phase='Benchmark failed',error=str(message)[:500])

    def leaderboard(self,id,objective='balanced',model_id=None,strategy=None):
        run=self.get(id);configs=run['configs']
        if model_id:configs=[c for c in configs if c['config']['model_id']==model_id]
        if strategy:configs=[c for c in configs if c['config']['strategy']==strategy]
        try:ranked=optimize(configs,objective)
        except ValueError as exc:raise HTTPException(422,str(exc))
        from adaptive import analyse
        analysis=analyse(run,self.measurements(id))
        return {'analysis':analysis,'run_id':id,'dataset_fingerprint':run['snapshot']['fingerprint'],'provisional':run['snapshot']['provisional'],
                'objective':objective,'ranked':ranked,'methodology':{
                    'accuracy':'0.45 × Recall@k + 0.35 × MRR + 0.20 × Precision@k',
                    'speed':'1 - (mean latency - cohort minimum) / (cohort maximum - cohort minimum); 1 if equal.',
                    'balanced':'0.70 × retrieval accuracy score + 0.30 × speed score',
                    'scope':'Only complete configurations from this one immutable dataset/top-k/run. Speed is normalized within the selected filter cohort. Index timing is reported but excluded from speed because embedding caches affect build cost.',
                    'caution':'Point estimates, not statistical significance. Query repetitions do not increase the unique-question sample size. Treat small or provisional datasets as exploratory.'}}

    def export(self,id,format):
        run=self.get(id)
        if format=='json':
            body={**run,'measurements':self.measurements(id),'leaderboard':self.leaderboard(id)}
            return Response(json.dumps(body,indent=2),media_type='application/json',headers={'Content-Disposition':'attachment; filename="raglab-benchmark.json"'})
        if format=='pdf':
            from reports import benchmark_pdf
            return Response(benchmark_pdf(run,self.measurements(id)),media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="raglab-report.pdf"'})
        if format!='csv':raise HTTPException(422,'Choose csv, json or pdf.')
        configs={c['id']:c for c in run['configs']}
        out=io.StringIO();fields=['run_id','dataset_fingerprint','provisional','config_id','model_id','model_revision','strategy','budget','top_k','repetition','question_id','answerability','human_reviewed',
            'precision_at_k','recall_at_k','mrr','evidence_coverage','latency_ms','wall_latency_ms','indexing_time_ms','index_cache_reused','cache_hits','answer_exact_match','groundedness','generation_status']
        writer=csv.DictWriter(out,fieldnames=fields);writer.writeheader()
        for m in self.measurements(id):
            c=configs[m['config_id']]
            writer.writerow({'run_id':id,'dataset_fingerprint':run['snapshot']['fingerprint'],'provisional':run['snapshot']['provisional'],
                **{k:m.get(k) for k in ['config_id','model_revision','repetition','question_id','answerability','human_reviewed','latency_ms','wall_latency_ms','generation_status']},
                **{k:c['config'].get(k) for k in ['model_id','strategy','budget']},'top_k':run['settings']['top_k'],
                **{k:m['metrics'].get(k) for k in ['precision_at_k','recall_at_k','mrr','evidence_coverage','answer_exact_match','groundedness']},
                **{k:c.get(k) for k in ['indexing_time_ms','index_cache_reused','cache_hits']}})
        return Response(out.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="raglab-benchmark.csv"'})


def router(service):
    routes=APIRouter(prefix='/benchmarks',tags=['Benchmarks'])
    @routes.get('/methodology')
    def methodology():return METHODOLOGY
    @routes.get('/runs')
    def list_runs():return service.list()
    @routes.post('/runs',status_code=202)
    def start_run(data:RunInput):return service.start(data)
    @routes.get('/runs/{id}')
    def get_run(id:str):return service.get(id)
    @routes.post('/runs/{id}/cancel')
    def cancel(id:str):return service.cancel(id)
    @routes.post('/runs/{id}/resume',status_code=202)
    def resume(id:str):return service.resume(id)
    @routes.get('/runs/{id}/measurements')
    def measurements(id:str,config_id:str|None=None):return service.measurements(id,config_id)
    @routes.get('/runs/{id}/leaderboard')
    def leaderboard(id:str,objective:Literal['accuracy','speed','balanced']='balanced',model_id:str|None=None,strategy:str|None=None):return service.leaderboard(id,objective,model_id,strategy)
    @routes.get('/runs/{id}/export')
    def export(id:str,format:str='json'):return service.export(id,format)
    return routes

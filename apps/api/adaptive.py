"""Bounded automatic search with frozen validation selection and untouched test evaluation."""
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import numpy as np
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field,model_validator
from benchmarks import RunInput
from datasets import validate_split_isolation,sha

class Objective(BaseModel):
    accuracy_weight:float=Field(.7,ge=0,le=1)
    recall_weight:float=Field(.45,ge=0,le=1)
    mrr_weight:float=Field(.35,ge=0,le=1)
    precision_weight:float=Field(.2,ge=0,le=1)
    max_latency_ms:float|None=Field(None,gt=0,le=600000)
    @model_validator(mode='after')
    def weights(self):
        if self.recall_weight+self.mrr_weight+self.precision_weight<=0:raise ValueError('At least one retrieval quality weight must be positive.')
        return self


def quality(m,o):
    weights=[o.recall_weight,o.mrr_weight,o.precision_weight]
    return sum(w*m[key] for w,key in zip(weights,['recall_at_k','mrr','precision_at_k']))/sum(weights)


def uncertainty(records,seed=7):
    """Question-cluster bootstrap: repetitions collapse before resampling, not extra N."""
    result={};rng=np.random.default_rng(seed)
    for key in ['precision_at_k','recall_at_k','mrr','latency_ms']:
        grouped={}
        for m in records:
            value=m['latency_ms'] if key=='latency_ms' else m['metrics'].get(key)
            if value is not None:grouped.setdefault(m['question_id'],[]).append(value)
        values=np.array([np.mean(v) for _,v in sorted(grouped.items())]);n=len(values)
        ci=None
        if n>=2:
            means=np.mean(rng.choice(values,size=(1000,n),replace=True),axis=1)
            ci=[float(np.percentile(means,2.5)),float(np.percentile(means,97.5))]
        result[key]={'mean':float(values.mean()) if n else None,'ci95':ci,'unique_questions':n,
                     'status':'small_sample' if n<20 else 'exploratory',
                     'method':'1000 seeded percentile bootstrap draws over per-question means; repetitions grouped; unadjusted for multiple comparisons'}
    repeats={}
    for m in records:
        signature=json.dumps({k:m['metrics'].get(k) for k in ['precision_at_k','recall_at_k','mrr']},sort_keys=True)
        repeats.setdefault(m['question_id'],[]).append(signature)
    repeated=[v for v in repeats.values() if len(v)>1]
    return {'intervals':result,'repeatability':{'repeated_questions':len(repeated),
            'quality_consistent':all(len(set(v))==1 for v in repeated) if repeated else None,
            'scope':'Within-run retrieval metric repeatability; latency varies and repeated-run reproducibility is a separate check.'}}


def analyse(run,measurements,objective=None):
    o=objective or Objective();eligible=[]
    for c in run['configs']:
        m=c.get('metrics',{})
        if c['status']=='completed' and all(m.get(k) is not None for k in ['recall_at_k','mrr','precision_at_k','latency_mean_ms']):
            eligible.append({**c,'quality':quality(m,o)})
    frontier=[]
    for c in eligible:
        dominated=any(d['quality']>=c['quality'] and d['metrics']['latency_mean_ms']<=c['metrics']['latency_mean_ms'] and
                      (d['quality']>c['quality'] or d['metrics']['latency_mean_ms']<c['metrics']['latency_mean_ms']) for d in eligible)
        if not dominated:frontier.append(c['id'])
    allowed=[c for c in eligible if o.max_latency_ms is None or c['metrics']['latency_mean_ms']<=o.max_latency_ms]
    lo=min((c['metrics']['latency_mean_ms'] for c in allowed),default=0);hi=max((c['metrics']['latency_mean_ms'] for c in allowed),default=0)
    ranked=[]
    for c in allowed:
        latency=c['metrics']['latency_mean_ms'];speed=1 if hi==lo else 1-(latency-lo)/(hi-lo)
        records=[m for m in measurements if m['config_id']==c['id']]
        ranked.append({'config_id':c['id'],'config':c['config'],'quality':c['quality'],'latency_ms':latency,
                       'speed':speed,'score':o.accuracy_weight*c['quality']+(1-o.accuracy_weight)*speed,
                       'pareto':c['id'] in frontier,'uncertainty':uncertainty(records,run['settings']['seed'])})
    ranked.sort(key=lambda c:(-c['score'],-c['quality'],c['latency_ms'],c['config_id']))
    return {'objective':o.model_dump(),'ranked':ranked,'pareto_config_ids':frontier,'eligible_configs':len(eligible),
            'excluded_by_latency':len(eligible)-len(allowed),'provisional':run['snapshot']['provisional'],
            'selection_split':run['snapshot'].get('split','all'),
            'methodology':'Quality = normalized weighted recall/MRR/precision. Speed = inverse min-max mean latency in feasible cohort (1 if equal). Score = accuracy_weight*quality + (1-accuracy_weight)*speed. Pareto dominance maximizes this quality and minimizes latency over all complete configs before applying the latency constraint.',
            'caution':'Exploratory point estimates. Bootstrap intervals are not superiority tests; no multiple-comparison correction. Evidence groups/duplicates must remain in one split; manually check semantic paraphrases. Tiny or unreviewed samples cannot support general superiority claims.'}

class SearchInput(RunInput):
    name:str=Field('Adaptive validation search',min_length=1,max_length=120)
    objective:Objective=Field(default_factory=Objective)

class AdaptiveService:
    def __init__(self,connect,benchmarks,datasets):
        self.connect,self.benchmarks,self.datasets=connect,benchmarks,datasets
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='raglab-adaptive')
        self.stop=threading.Event();self.lock=threading.Lock()
        with connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS adaptive_searches(id TEXT PRIMARY KEY,payload TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP)')
            db.execute('CREATE TABLE IF NOT EXISTS adaptive_test_reservations(question_key TEXT PRIMARY KEY,search_id TEXT REFERENCES adaptive_searches(id))')
            rows=db.execute('SELECT id,payload FROM adaptive_searches').fetchall()
            for row in rows:
                data=json.loads(row['payload'])
                if data['status'] in ('queued','running'):
                    data.update(status='interrupted',phase='Server restarted; resume missing stages')
                    db.execute('UPDATE adaptive_searches SET payload=? WHERE id=?',(json.dumps(data),row['id']))
    def save(self,data,clear_cancel=False):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT payload FROM adaptive_searches WHERE id=?',(data['id'],)).fetchone()
            if old and not clear_cancel and json.loads(old[0]).get('cancel_requested'):data['cancel_requested']=True
            db.execute('INSERT INTO adaptive_searches(id,payload) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(data['id'],json.dumps(data)))
    def get(self,id):
        with self.connect() as db:r=db.execute('SELECT payload FROM adaptive_searches WHERE id=?',(id,)).fetchone()
        if not r:raise HTTPException(404,'Adaptive search not found.')
        return json.loads(r[0])
    def list(self):
        with self.connect() as db:ids=[r[0] for r in db.execute('SELECT id FROM adaptive_searches ORDER BY created DESC,rowid DESC LIMIT 100')]
        result=[]
        for id in ids:
            data=self.get(id)
            for key in ['selection_snapshot','test_snapshot']:
                snapshot=data[key];data[key]={**{k:v for k,v in snapshot.items() if k!='questions'},'question_count':len(snapshot['questions'])}
            if data.get('analysis'):data['analysis']=None
            result.append(data)
        return result
    def start(self,data,asynchronous=True):
        dataset=self.datasets.get(data.dataset_id)
        validate_split_isolation(dataset['questions'])
        selection=self.datasets.snapshot(data.dataset_id,data.include_unreviewed,'validation')
        test=self.datasets.snapshot(data.dataset_id,data.include_unreviewed,'test')
        settings=RunInput(**{**data.model_dump(),'evaluation_split':'validation'})
        id=str(uuid4())
        record={'id':id,'status':'queued','phase':'Validation search queued','settings':data.model_dump(),
                'selection_snapshot':selection,'test_snapshot':test,'selection_run_id':None,'test_run_id':None,
                'frozen_selection':None,'analysis':None,'held_out':None,'error':None,'cancel_requested':False}
        # Reserve test questions atomically, before candidate evaluation. Reusing exposed tests
        # for another tuning session is refused (resume this same search instead).
        from evaluation import normalize_answer
        keys=[sha(normalize_answer(q['question'])) for q in test['questions']]
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for key in keys:
                if db.execute('SELECT 1 FROM adaptive_test_reservations WHERE question_key=?',(key,)).fetchone():
                    raise HTTPException(409,'These test questions are already reserved/exposed by another search. Resume that search or supply genuinely new independent test questions; do not retune on exposed test results.')
            db.execute('INSERT INTO adaptive_searches(id,payload) VALUES(?,?)',(id,json.dumps(record)))
            for key in set(keys):db.execute('INSERT INTO adaptive_test_reservations VALUES(?,?)',(key,id))
        try:
            run=self.benchmarks.start(settings,asynchronous=asynchronous,snapshot_override=selection,provenance={'search_id':id,'stage':'validation'})
        except Exception:
            with self.connect() as db:
                db.execute('DELETE FROM adaptive_test_reservations WHERE search_id=?',(id,));db.execute('DELETE FROM adaptive_searches WHERE id=?',(id,))
            raise
        record['selection_run_id']=run['id'];self.save(record)
        if asynchronous:self.executor.submit(self.execute,id)
        else:self.execute(id,synchronous=True)
        return self.get(id)
    def wait_run(self,id,run_id):
        while True:
            record=self.get(id)
            if self.stop.is_set() or record['cancel_requested']:
                self.benchmarks.cancel(run_id);raise InterruptedError('Search cancelled; completed work preserved.')
            run=self.benchmarks.get(run_id)
            if run['status'] not in ('queued','running'):return run
            time.sleep(.2)
    def execute(self,id,synchronous=False):
        record=self.get(id)
        try:
            record.update(status='running',phase='Searching all 18 configurations on validation only',error=None);self.save(record)
            selection=self.wait_run(id,record['selection_run_id'])
            if selection['status']!='completed':raise RuntimeError('Validation matrix is incomplete. Resolve failures and resume; no test selection was made.')
            if not record['frozen_selection']:
                analysis=analyse(selection,self.benchmarks.measurements(selection['id']),Objective(**record['settings']['objective']))
                if not analysis['ranked']:raise RuntimeError('No complete configuration meets the latency constraint. Create a new search with a feasible constraint.')
                best=analysis['ranked'][0]
                record['analysis']=analysis
                record['frozen_selection']={'config':best['config'],'config_id':best['config_id'],'validation_score':best['score'],
                    'selection_fingerprint':selection['snapshot']['fingerprint'],'test_fingerprint':record['test_snapshot']['fingerprint'],
                    'rule':analysis['methodology']}
                record['frozen_selection']['sha256']=sha(json.dumps(record['frozen_selection'],sort_keys=True))
                record['phase']='Selection frozen; evaluating ONE configuration on held-out test';self.save(record)
            import embeddings
            if selection['settings']['model_registry']!=embeddings.MODELS:raise RuntimeError('Model registry changed after validation. Restore the pinned registry before resuming.')
            seal=record['frozen_selection']
            if sha(json.dumps({k:v for k,v in seal.items() if k!='sha256'},sort_keys=True))!=seal['sha256']:raise RuntimeError('Frozen selection integrity check failed.')
            if seal['test_fingerprint']!=record['test_snapshot']['fingerprint']:raise RuntimeError('Reserved test snapshot integrity check failed.')
            if self.stop.is_set() or self.get(id)['cancel_requested']:raise InterruptedError('Search cancelled before held-out queries; completed validation preserved.')
            if not record['test_run_id']:
                settings=RunInput(**{**record['settings'],'name':record['settings']['name']+' · held-out','evaluation_split':'test','rebuild_indexes':False})
                run=self.benchmarks.start(settings,asynchronous=not synchronous,snapshot_override=record['test_snapshot'],
                    configs_override=[record['frozen_selection']['config']],provenance={'search_id':id,'stage':'held_out_test','frozen_selection':record['frozen_selection']})
                record['test_run_id']=run['id'];self.save(record)
            test=self.wait_run(id,record['test_run_id'])
            if test['status']!='completed':raise RuntimeError('Held-out evaluation incomplete. Resolve failures and resume.')
            records=self.benchmarks.measurements(test['id'])
            record['held_out']={'metrics':test['configs'][0]['metrics'],'uncertainty':uncertainty(records,test['settings']['seed']),
                'provisional':test['snapshot']['provisional'],'unique_questions':len(test['snapshot']['questions']),
                'interpretation':'One frozen validation-selected configuration evaluated on reserved test questions. Never used to rank or retune candidates. Repeated searches against this test set compromise its hold-out status.'}
            record.update(status='completed',phase='Completed validation search and held-out evaluation');self.save(record)
        except Exception as exc:
            # Preserve concurrently requested cancellation instead of overwriting it.
            record['cancel_requested']=self.get(id)['cancel_requested']
            record.update(status='cancelled' if isinstance(exc,InterruptedError) else 'failed',error=str(exc)[:500],phase='Stopped; resume preserves completed stages');self.save(record)
    def cancel(self,id):
        with self.lock:
            data=self.get(id)
            if data['status'] in ('queued','running'):
                data['cancel_requested']=True;self.save(data)
                for key in ['selection_run_id','test_run_id']:
                    if data.get(key):self.benchmarks.cancel(data[key])
            return self.get(id)
    def resume(self,id):
        with self.lock:
            data=self.get(id)
            if data['status'] in ('completed','queued','running'):raise HTTPException(409,'Only stopped or interrupted searches can be resumed.')
            for snapshot in [data['selection_snapshot'],data['test_snapshot']]:self.benchmarks.source_check(snapshot)
            if not data.get('selection_run_id'):
                settings=RunInput(**{**data['settings'],'evaluation_split':'validation'})
                run=self.benchmarks.start(settings,snapshot_override=data['selection_snapshot'],provenance={'search_id':id,'stage':'validation'})
                data['selection_run_id']=run['id']
            for key in ['selection_run_id','test_run_id']:
                if data.get(key):
                    run=self.benchmarks.get(data[key])
                    if run['status'] not in ('completed','queued','running'):self.benchmarks.resume(run['id'])
            data.update(status='queued',cancel_requested=False,error=None);self.save(data,clear_cancel=True);self.executor.submit(self.execute,id)
            return data
    def shutdown(self):
        self.stop.set();self.executor.shutdown(wait=True,cancel_futures=True)


def router(service):
    routes=APIRouter(prefix='/adaptive',tags=['Adaptive optimization'])
    @routes.get('/searches')
    def list_searches():return service.list()
    @routes.post('/searches',status_code=202)
    def start(data:SearchInput):return service.start(data)
    @routes.get('/searches/{id}')
    def get(id:str):return service.get(id)
    @routes.post('/searches/{id}/cancel')
    def cancel(id:str):return service.cancel(id)
    @routes.post('/searches/{id}/resume',status_code=202)
    def resume(id:str):return service.resume(id)
    @routes.post('/analyse/{run_id}')
    def analysis(run_id:str,data:Objective):
        run=service.benchmarks.get(run_id)
        if run['snapshot'].get('split')=='test':raise HTTPException(422,'Held-out test results cannot be used for configuration selection. Analyse a validation run.')
        return analyse(run,service.benchmarks.measurements(run_id),data)
    return routes

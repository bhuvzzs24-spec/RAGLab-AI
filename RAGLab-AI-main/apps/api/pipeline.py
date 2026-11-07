"""Durable indexing jobs, embedding cache, FAISS artifacts and source provenance."""
import hashlib
import json
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
import numpy as np
from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator
from chunking import chunk_text
import embeddings
from generation import generate

ALGORITHM_VERSION = 'source-spans-v2'
ACTIVE = ('queued', 'running')

class Build(BaseModel):
    document_ids: list[str] = Field(min_length=1, max_length=50)
    model_id: str = 'minilm'
    strategy: str = 'fixed'
    budget: int = Field(120, ge=8, le=2048)
    overlap: int = Field(20, ge=0)
    threshold: float = Field(.55, ge=-1, le=1)
    rebuild: bool = False

    @model_validator(mode='after')
    def valid(self):
        if self.model_id not in embeddings.MODELS:
            raise ValueError('Choose minilm or bge-small.')
        if self.strategy not in ['fixed', 'sentence', 'semantic']:
            raise ValueError('Choose fixed, sentence or semantic chunking.')
        if self.overlap >= self.budget:
            raise ValueError('Overlap must be smaller than the chunk budget.')
        self.document_ids = sorted(set(self.document_ids))
        return self

class Retrieval(BaseModel):
    index_id: str
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(3, ge=1, le=20)
    min_score: float = Field(.2, ge=-1, le=1)
    expected: str = Field('', max_length=2000)

    @model_validator(mode='after')
    def valid(self):
        if not self.query.strip():
            raise ValueError('Enter a non-empty question.')
        return self

class Answer(BaseModel):
    retrieval_id: str

class Cancelled(Exception):
    pass


def digest(value):
    return hashlib.sha256(value).hexdigest()


def faiss_call(payload):
    try:
        worker = subprocess.run([sys.executable,str(Path(__file__).with_name('vector_search.py'))],
                                input=json.dumps(payload), text=True, capture_output=True,
                                check=True, timeout=90)
        return json.loads(worker.stdout)
    except (subprocess.SubprocessError, ValueError) as exc:
        raise RuntimeError('FAISS worker failed. Verify faiss-cpu is installed for this Python/platform; rebuild missing or damaged indexes.') from exc


def pages_for(pages, start, end):
    result, cursor = [], 0
    for i, text in enumerate(pages):
        if end > cursor and start < cursor+len(text):
            result.append(i+1)
        cursor += len(text)+2
    return result

class Engine:
    def __init__(self, connect, data):
        self.connect, self.root = connect, Path(data)/'indexes'
        self.root.mkdir(parents=True,exist_ok=True)
        self.executor = ThreadPoolExecutor(max_workers=1,thread_name_prefix='raglab-index')
        self.lock = threading.Lock()
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS vector_indexes(
                    id TEXT PRIMARY KEY,cache_key TEXT,model_id TEXT,model_revision TEXT,dimensions INTEGER,
                    config TEXT,status TEXT,phase TEXT,progress INTEGER DEFAULT 0,total INTEGER DEFAULT 0,
                    cancel_requested INTEGER DEFAULT 0,error TEXT,stats TEXT DEFAULT '{}',
                    created TEXT DEFAULT CURRENT_TIMESTAMP,updated TEXT DEFAULT CURRENT_TIMESTAMP);
                CREATE INDEX IF NOT EXISTS vector_cache_key ON vector_indexes(cache_key);
                CREATE TABLE IF NOT EXISTS index_documents(
                    index_id TEXT REFERENCES vector_indexes(id) ON DELETE CASCADE,
                    document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
                    PRIMARY KEY(index_id,document_id));
                CREATE TABLE IF NOT EXISTS index_chunks(
                    id TEXT PRIMARY KEY,index_id TEXT REFERENCES vector_indexes(id) ON DELETE CASCADE,
                    ordinal INTEGER,document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
                    source_name TEXT,chunk_index INTEGER,part INTEGER,start INTEGER,end INTEGER,
                    tokens INTEGER,model_tokens INTEGER,page_numbers TEXT,text TEXT,
                    UNIQUE(index_id,ordinal));
                CREATE TABLE IF NOT EXISTS embedding_cache(
                    key TEXT PRIMARY KEY,model_id TEXT,revision TEXT,dimensions INTEGER,vector BLOB);
                CREATE TABLE IF NOT EXISTS retrievals(
                    id TEXT PRIMARY KEY,index_id TEXT REFERENCES vector_indexes(id) ON DELETE CASCADE,
                    query TEXT,settings TEXT,result TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS answers(
                    id TEXT PRIMARY KEY,retrieval_id TEXT REFERENCES retrievals(id) ON DELETE CASCADE,
                    result TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
            ''')
            db.execute("UPDATE vector_indexes SET status='failed',phase='Interrupted',error='Server restarted during indexing. Rebuild to retry.' WHERE status IN ('queued','running')")

    def shutdown(self):
        with self.connect() as db:
            db.execute("UPDATE vector_indexes SET cancel_requested=1 WHERE status IN ('queued','running')")
        self.executor.shutdown(wait=True, cancel_futures=True)

    def row(self, id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM vector_indexes WHERE id=?',(id,)).fetchone()
        if row is None:
            raise HTTPException(404,'Index not found.')
        result = dict(row)
        result['config'], result['stats'] = json.loads(result['config']), json.loads(result['stats'])
        return result

    def list(self):
        with self.connect() as db:
            ids = [r[0] for r in db.execute('SELECT id FROM vector_indexes ORDER BY created DESC,rowid DESC')]
        return [self.row(id) for id in ids]

    def update(self,id,**values):
        allowed = {'status','phase','progress','total','error','stats','cancel_requested'}
        assert values.keys() <= allowed
        with self.connect() as db:
            db.execute('UPDATE vector_indexes SET '+','.join(k+'=?' for k in values)+',updated=CURRENT_TIMESTAMP WHERE id=?',(*values.values(),id))

    def check_cancel(self,id):
        row = self.row(id)
        if row['cancel_requested'] or row['status']=='invalidated':
            raise Cancelled()

    def create(self, config, asynchronous=True):
        s = embeddings.spec(config.model_id)
        with self.lock:
            documents = []
            with self.connect() as db:
                for id in config.document_ids:
                    d = db.execute('SELECT * FROM documents WHERE id=?',(id,)).fetchone()
                    if not d:
                        raise HTTPException(404,'A selected document no longer exists. Refresh your collection.')
                    documents.append(dict(d))
            params = config.model_dump(exclude={'rebuild'})
            # Canonicalize irrelevant settings so identical effective configurations reuse the cache.
            if config.strategy!='fixed': params['overlap']=0
            if config.strategy!='semantic': params['threshold']=None
            key = digest(json.dumps({'config':params,'sources':[(d['id'],digest(d['text'].encode())) for d in documents],
                       'revision':s['revision'],'format':embeddings.FORMAT_VERSION,'chunker':ALGORITHM_VERSION},sort_keys=True).encode())
            with self.connect() as db:
                existing = db.execute("SELECT id FROM vector_indexes WHERE cache_key=? AND cancel_requested=0 AND status IN ('ready','queued','running') ORDER BY rowid DESC LIMIT 1",(key,)).fetchone()
            if existing and (not config.rebuild or self.row(existing[0])['status'] in ACTIVE):
                current = self.row(existing[0])
                if current['status']!='ready' or self.artifacts_valid(current):
                    return {**current,'cache_reused':True}
                self.update(current['id'],status='failed',phase='Artifact missing',error='Persisted index files are missing or damaged. Rebuild the index.')
            id = str(uuid4())
            with self.connect() as db:
                db.execute('INSERT INTO vector_indexes(id,cache_key,model_id,model_revision,dimensions,config,status,phase) VALUES(?,?,?,?,?,?,?,?)',
                           (id,key,config.model_id,s['revision'],s['dimensions'],config.model_dump_json(),'queued','Waiting for worker'))
                db.executemany('INSERT INTO index_documents VALUES(?,?)',[(id,d['id']) for d in documents])
            if asynchronous:
                self.executor.submit(self.build,id,config,documents)
            else:
                self.build(id,config,documents)
            return {**self.row(id),'cache_reused':False}

    def artifacts_valid(self,row):
        folder = self.root/row['id']
        stats = row['stats']
        for file,key in [('vectors.npy','vectors_sha256'),('index.faiss','index_sha256')]:
            path = folder/file
            if not path.is_file() or not stats.get(key) or digest(path.read_bytes())!=stats[key]:
                return False
        return True

    def cached_vectors(self,id,texts,model_id):
        s=embeddings.spec(model_id)
        keys=[digest((model_id+s['revision']+embeddings.FORMAT_VERSION+text).encode()) for text in texts]
        result=[None]*len(texts)
        hits=0
        with self.connect() as db:
            for i,key in enumerate(keys):
                r=db.execute('SELECT vector,dimensions FROM embedding_cache WHERE key=?',(key,)).fetchone()
                if r and r['dimensions']==s['dimensions']:
                    value=np.frombuffer(r['vector'],dtype='float32').copy()
                    if value.shape==(s['dimensions'],) and np.isfinite(value).all() and abs(np.linalg.norm(value)-1)<1e-3:
                        result[i]=value;hits+=1
        missing=[i for i,v in enumerate(result) if v is None]
        for offset in range(0,len(missing),16):
            self.check_cancel(id)
            batch=missing[offset:offset+16]
            vectors=embeddings.encode([texts[i] for i in batch],model_id)
            with self.connect() as db:
                for i,vector in zip(batch,vectors):
                    result[i]=vector
                    db.execute('INSERT OR REPLACE INTO embedding_cache VALUES(?,?,?,?,?)',
                               (keys[i],model_id,s['revision'],s['dimensions'],vector.tobytes()))
            self.update(id,progress=hits+offset+len(batch),phase='Embedding passages')
        self.update(id,progress=len(texts))
        return np.stack(result).astype('float32'),hits

    def build(self,id,config,documents):
        folder = self.root/id
        started = time.perf_counter()
        try:
            self.check_cancel(id)
            self.update(id,status='running',phase='Loading pinned model')
            # Model downloads/individual inference calls cannot be interrupted safely.
            with embeddings.MODEL_LOCK:
                embeddings.load_model(config.model_id)
            self.check_cancel(id)
            self.update(id,phase='Computing chunk boundaries')
            records=[]; parents=0
            for document in documents:
                self.check_cancel(id)
                def semantic_encode(texts):
                    values=[]
                    for i in range(0,len(texts),16):
                        self.check_cancel(id)
                        values.extend(embeddings.encode_untruncated(texts[i:i+16],config.model_id))
                    return np.asarray(values)
                chunks=chunk_text(document['text'],config.strategy,config.budget,
                                  config.overlap,config.threshold,semantic_encode)
                pages=json.loads(document['pages'])
                for parent,chunk in enumerate(chunks):
                    self.check_cancel(id)
                    parents+=1
                    for part,(a,b,count) in enumerate(embeddings.split_for_model(chunk['text'],config.model_id)):
                        start,end=chunk['start']+a,chunk['start']+b
                        text=document['text'][start:end]
                        records.append({'id':str(uuid4()),'ordinal':len(records),'document_id':document['id'],
                                        'source_name':document['name'],'chunk_index':parent,'part':part,
                                        'start':start,'end':end,'tokens':len(text.split()),'model_tokens':count,
                                        'page_numbers':pages_for(pages,start,end),'text':text})
                        if len(records)>10000:
                            raise ValueError('This configuration exceeds 10,000 indexed passages. Use a smaller collection or a larger chunk budget.')
            if not records:
                raise ValueError('No indexable text was found in this collection.')
            self.update(id,total=len(records),phase='Checking embedding cache')
            vectors,hits=self.cached_vectors(id,[r['text'] for r in records],config.model_id)
            self.check_cancel(id)
            self.update(id,phase='Writing FAISS index')
            folder.mkdir(exist_ok=True)
            np.save(folder/'vectors.npy',vectors,allow_pickle=False)
            built=faiss_call({'action':'build','vectors_path':str(folder/'vectors.npy'),'index_path':str(folder/'index.faiss')})
            if built['count']!=len(records) or built['dimensions']!=embeddings.spec(config.model_id)['dimensions']:
                raise ValueError('FAISS index verification failed.')
            self.check_cancel(id)
            norms=np.linalg.norm(vectors,axis=1)
            stats={'vectors':len(records),'parent_chunks':parents,'documents':len(documents),'cache_hits':hits,
                   'dimensions':vectors.shape[1],'normalized':True,'norm_min':float(norms.min()),'norm_max':float(norms.max()),
                   'build_ms':round((time.perf_counter()-started)*1000,2),
                   'vectors_sha256':digest((folder/'vectors.npy').read_bytes()),'index_sha256':digest((folder/'index.faiss').read_bytes()),
                   'disk_bytes':sum(p.stat().st_size for p in folder.iterdir()),
                   'format_version':embeddings.FORMAT_VERSION,'algorithm_version':ALGORITHM_VERSION}
            with self.connect() as db:
                # Begin a write transaction before the final cancellation/deletion check.
                db.execute('BEGIN IMMEDIATE')
                current=db.execute('SELECT cancel_requested,status FROM vector_indexes WHERE id=?',(id,)).fetchone()
                count=db.execute('SELECT count(*) FROM index_documents WHERE index_id=?',(id,)).fetchone()[0]
                if not current or current['cancel_requested'] or current['status']=='invalidated' or count!=len(documents):
                    raise Cancelled()
                db.executemany('INSERT INTO index_chunks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    [(r['id'],id,r['ordinal'],r['document_id'],r['source_name'],r['chunk_index'],r['part'],r['start'],r['end'],
                      r['tokens'],r['model_tokens'],json.dumps(r['page_numbers']),r['text']) for r in records])
                db.execute("UPDATE vector_indexes SET status='ready',phase='Ready',stats=?,progress=total,updated=CURRENT_TIMESTAMP WHERE id=?",(json.dumps(stats),id))
        except Cancelled:
            shutil.rmtree(folder,ignore_errors=True)
            if self.row(id)['status']!='invalidated':
                self.update(id,status='cancelled',phase='Cancelled',error='Cancelled between batches. Completed vectors remain in the reusable cache.')
        except Exception as exc:
            shutil.rmtree(folder,ignore_errors=True)
            current=self.row(id)
            if current['status']=='invalidated':
                return
            if current['cancel_requested']:
                self.update(id,status='cancelled',phase='Cancelled',error='Cancelled during an indexing operation. Rebuild to retry.')
                return
            self.update(id,status='failed',phase='Failed',error='Indexing failed. '+str(exc)[:350]+'. Check model availability and rebuild.')

    def cancel(self,id):
        row=self.row(id)
        if row['status'] in ACTIVE:
            self.update(id,cancel_requested=1,phase='Cancellation requested')
        return self.row(id)

    def invalidate_document(self,document_id):
        with self.connect() as db:
            ids=[r[0] for r in db.execute('SELECT index_id FROM index_documents WHERE document_id=?',(document_id,))]
            for id in ids:
                db.execute("UPDATE vector_indexes SET status='invalidated',cancel_requested=1,phase='Source deleted',error='A source document was deleted. Create a new index.' WHERE id=?",(id,))
                db.execute('DELETE FROM index_chunks WHERE index_id=?',(id,))
                db.execute('DELETE FROM retrievals WHERE index_id=?',(id,))
        # Running builders observe invalidation and remove their staging files.
        for id in ids:
            shutil.rmtree(self.root/id,ignore_errors=True)

    def chunks(self,id):
        with self.connect() as db:
            rows=db.execute('SELECT * FROM index_chunks WHERE index_id=? ORDER BY ordinal',(id,)).fetchall()
        return [{**dict(r),'page_numbers':json.loads(r['page_numbers'])} for r in rows]

    def retrieve(self,q,persist=True):
        start=time.perf_counter()
        row=self.row(q.index_id)
        if row['status']!='ready':
            raise HTTPException(409,'Index is '+row['status']+'. Wait for indexing or rebuild a failed index.')
        if not self.artifacts_valid(row):
            self.update(row['id'],status='failed',phase='Artifact damaged',error='Index files are missing or checksum validation failed. Rebuild this configuration.')
            raise HTTPException(409,'Persisted index is missing or damaged. Rebuild it from Embeddings.')
        try:
            embedding_started=time.perf_counter()
            vector=embeddings.encode([q.query],row['model_id'],query=True)
            embedding_ms=(time.perf_counter()-embedding_started)*1000
            result=faiss_call({'action':'search','index_path':str(self.root/row['id']/'index.faiss'),
                               'query':vector.tolist(),'count':row['stats']['vectors'],'k':q.top_k})
        except ValueError as exc:
            raise HTTPException(422,str(exc))
        except Exception as exc:
            raise HTTPException(503,'Retrieval failed. Check the model cache and rebuild the index if necessary. '+str(exc)[:200])
        chunks=self.chunks(row['id'])
        if len(chunks)!=row['stats']['vectors'] or self.row(row['id'])['status']!='ready':
            raise HTTPException(409,'Sources changed during retrieval. Select a valid index and retry.')
        hits=[]
        for score,i in zip(result['scores'],result['indices']):
            if i>=0 and score>=q.min_score:
                c=chunks[i]
                hits.append({**c,'score':float(np.clip(score,-1,1)),'source_id':len(hits)+1,
                             'source_url':f"/indexes/{row['id']}/chunks/{c['ordinal']}/source"})
        id=str(uuid4())
        response={'id':id,'retrieval_id':id,'index_id':row['id'],'model_id':row['model_id'],
                  'model_revision':row['model_revision'],'query':q.query,'hits':hits,
                  'latency_ms':round((time.perf_counter()-start)*1000,2),
                  'timings':{'query_embedding_ms':round(embedding_ms,2),'search_and_load_ms':round((time.perf_counter()-start)*1000-embedding_ms,2)},
                  'expected_hit':any(q.expected.casefold() in h['text'].casefold() for h in hits) if q.expected else None,
                  'settings':q.model_dump(),'index_reused':True}
        if not persist:
            return response
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current=db.execute('SELECT status FROM vector_indexes WHERE id=?',(row['id'],)).fetchone()
            if not current or current['status']!='ready':
                raise HTTPException(409,'Sources changed during retrieval. Select a valid index and retry.')
            db.execute('INSERT INTO retrievals(id,index_id,query,settings,result) VALUES(?,?,?,?,?)',
                       (id,row['id'],q.query,q.model_dump_json(),json.dumps(response)))
        return response

    def answer(self,retrieval_id,transport=None):
        with self.connect() as db:
            row=db.execute('SELECT * FROM retrievals WHERE id=?',(retrieval_id,)).fetchone()
        if not row:
            raise HTTPException(404,'Retrieval not found. Run the question again.')
        if self.row(row['index_id'])['status']!='ready':
            raise HTTPException(409,'Sources are no longer valid. Retrieve from a ready index again.')
        retrieval=json.loads(row['result'])
        start=time.perf_counter()
        result=generate(row['query'],retrieval['hits'],transport=transport)
        result.update({'id':str(uuid4()),'retrieval_id':retrieval_id,'latency_ms':round((time.perf_counter()-start)*1000,2)})
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current=db.execute('SELECT v.status FROM retrievals r JOIN vector_indexes v ON v.id=r.index_id WHERE r.id=?',(retrieval_id,)).fetchone()
            if not current or current['status']!='ready':
                raise HTTPException(409,'Sources changed during answer generation. Retrieve from a valid index again.')
            db.execute('INSERT INTO answers VALUES(?,?,?,CURRENT_TIMESTAMP)',(result['id'],retrieval_id,json.dumps(result)))
        return result

    def source(self,id,ordinal):
        self.row(id)
        with self.connect() as db:
            chunk=db.execute('SELECT * FROM index_chunks WHERE index_id=? AND ordinal=?',(id,ordinal)).fetchone()
            if not chunk:
                raise HTTPException(404,'Source passage no longer exists.')
            document=db.execute('SELECT * FROM documents WHERE id=?',(chunk['document_id'],)).fetchone()
        if not document:
            raise HTTPException(404,'Source document was deleted.')
        pages=json.loads(document['pages']); cursor=0; result=[]
        for i,text in enumerate(pages):
            if chunk['end']>cursor and chunk['start']<cursor+len(text):
                left=max(0,chunk['start']-cursor-2500)
                right=min(len(text),chunk['end']-cursor+2500)
                result.append({'page':i+1,'text':text[left:right],'highlight_start':max(0,chunk['start']-cursor-left),
                               'highlight_end':min(right-left,chunk['end']-cursor-left),'offset':cursor+left,
                               'excerpted':left>0 or right<len(text)})
            cursor+=len(text)+2
        return {'document_id':document['id'],'name':document['name'],'chunk_id':chunk['id'],
                'start':chunk['start'],'end':chunk['end'],'text':chunk['text'],'pages':result}

    def visualization(self,id):
        row=self.row(id)
        if row['status']!='ready' or not self.artifacts_valid(row):
            raise HTTPException(409,'A valid, ready index is required for visualization.')
        vectors=np.load(self.root/id/'vectors.npy',allow_pickle=False)
        # Sample deterministically across the complete index, without fabricated points.
        selected=np.linspace(0,len(vectors)-1,min(500,len(vectors)),dtype=int)
        sample=vectors[selected].astype('float64')
        centered=sample-sample.mean(axis=0)
        if len(sample)>1 and np.linalg.norm(centered)>1e-12:
            u,s,vt=np.linalg.svd(centered,full_matrices=False)
            coordinates=u[:,:2]*s[:2]
            for axis in range(coordinates.shape[1]):
                if vt[axis,np.argmax(np.abs(vt[axis]))]<0:coordinates[:,axis]*=-1
            if coordinates.shape[1]<2: coordinates=np.pad(coordinates,((0,0),(0,1)))
            explained=(s[:2]**2/(s**2).sum()).tolist()
        else:
            coordinates=np.zeros((len(sample),2));explained=[0.,0.]
        chunks=self.chunks(id)
        return {'method':'PCA','sampled':len(sample),'total':len(vectors),'explained_variance':explained,
                'points':[{'x':float(xy[0]),'y':float(xy[1]),'ordinal':int(i),'document_id':chunks[i]['document_id'],
                           'stable_id':digest((chunks[i]['document_id']+':'+str(chunks[i]['start'])+':'+str(chunks[i]['end'])+':'+chunks[i]['text']).encode()),'start':chunks[i]['start'],'end':chunks[i]['end'],
                           'source_name':chunks[i]['source_name'],'tokens':chunks[i]['model_tokens'],
                           'page_numbers':chunks[i]['page_numbers']} for xy,i in zip(coordinates,selected)]}

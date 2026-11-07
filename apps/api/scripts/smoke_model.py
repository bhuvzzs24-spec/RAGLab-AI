import sys
import os
import tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
os.environ['RAGLAB_DATA_DIR']=tempfile.mkdtemp(prefix='raglab-smoke-')
sys.path.insert(0,str(root))
from fastapi.testclient import TestClient
from main import app
c=TestClient(app)
d=c.post('/documents',files={'file':('notes.md',(root/'samples/retrieval-notes.md').read_bytes(),'text/markdown')})
assert d.status_code==201,d.text
for strategy in ['fixed','sentence','semantic']:
 r=c.post('/experiments',json={'document_id':d.json()['id'],'strategy':strategy,'budget':60,'overlap':10,'threshold':.55,'name':'Real smoke '+strategy})
 assert r.status_code==201,r.text
 print(strategy,r.json()['metrics'])
 q=c.post('/search',json={'experiment_id':r.json()['id'],'query':'How does overlap affect index size?','expected':'index size'})
 assert q.status_code==200,q.text
 assert q.json()['expected_hit'],q.text
 print('REAL_FAISS',q.json()['hits'][0]['score'],'expected phrase hit',q.json()['expected_hit'])

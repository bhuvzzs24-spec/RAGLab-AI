import importlib
import sys
from pathlib import Path
import pytest
import pymupdf as fitz
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).parents[1]))
from chunking import chunk_text

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('RAGLAB_DATA_DIR',str(tmp_path))
    import main
    importlib.reload(main)
    return TestClient(main.app)

def add(client,text='One two three four five six seven eight nine ten. Second sentence follows here.'):
    r=client.post('/documents',files={'file':('notes.txt',text.encode(),'text/plain')})
    assert r.status_code==201,r.text
    return r.json()['id']

def test_fixed_overlap_and_source_boundaries():
    text='  '+' '.join(f'word{i}' for i in range(23))+'  '
    chunks=chunk_text(text,'fixed',8,3)
    assert [c['tokens'] for c in chunks]==[8,8,8,8]
    for a,b in zip(chunks,chunks[1:]):
        assert a['text'].split()[-3:]==b['text'].split()[:3]
    for c in chunks:
        assert text[c['start']:c['end']]==c['text']
    assert chunks[-1]['text'].endswith('word22')

def test_sentence_budget_and_coverage():
    text='First sentence here. Second sentence here! '+' '.join(['long']*25)+'.'
    chunks=chunk_text(text,'sentence',8,0)
    assert all(c['tokens']<=8 for c in chunks)
    assert ' '.join(c['text'] for c in chunks).split()==text.split()
    assert chunks[0]['text']=='First sentence here. Second sentence here!'

def test_semantic_boundaries():
    import numpy as np
    chunks=chunk_text('Cats sleep. Cats nap. Rockets fly.','semantic',20,0,.5,lambda _:np.array([[1.,0.],[1.,0.],[0.,1.]]))
    assert [x['text'] for x in chunks]==['Cats sleep. Cats nap.','Rockets fly.']

def test_upload_validation(client):
    assert client.post('/documents',files={'file':('bad.exe',b'code')}).status_code==415
    assert client.post('/documents',files={'file':('bad.pdf',b'not pdf')}).status_code==422
    assert client.post('/documents',files={'file':('bad.txt',b'\xff')}).status_code==422
    assert client.post('/documents',files={'file':('empty.md',b' ')}).status_code==422
    assert client.post('/documents',files={'file':('big.txt',b'a'*(10*1024*1024+1))}).status_code==413

def test_pdf_pages(client):
    pdf=fitz.open()
    for text in ['First page text','Second page text']:
        p=pdf.new_page();p.insert_text((72,72),text)
    r=client.post('/documents',files={'file':('../../sample.pdf',pdf.tobytes(),'application/pdf')})
    assert r.status_code==201
    d=r.json();assert d['name']=='sample.pdf';assert len(d['pages'])==2
    assert 'Second page text' in d['text']


def test_encrypted_pdf_rejected(client):
    pdf = fitz.open()
    pdf.new_page()

    encrypted = pdf.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw='owner',
        user_pw='user'
    )
    pdf.close()

    response = client.post(
        '/documents',
        files={'file': ('encrypted.pdf', encrypted, 'application/pdf')}
    )

    assert response.status_code == 422
    assert 'encrypted' in response.text.lower()


def test_persistence_and_cascade(client):
    id=add(client)
    config={'document_id':id,'budget':8,'overlap':2,'name':'test'}
    r=client.post('/experiments',json=config)
    assert r.status_code==201,r.text
    import main
    importlib.reload(main)
    new=TestClient(main.app)
    assert new.get('/documents/'+id).json()['text'].startswith('One two')
    assert new.get('/experiments').json()[0]['chunks']==r.json()['chunks']
    assert new.delete('/documents/'+id).status_code==204
    assert new.get('/experiments').json()==[]
    assert new.get('/documents/'+id).status_code==404

def test_config_validation_and_settings(client):
    id=add(client)
    assert client.post('/chunks/preview',json={'document_id':id,'budget':8,'overlap':8}).status_code==422
    assert client.post('/chunks/preview',json={'document_id':id,'strategy':'invalid'}).status_code==422
    assert client.put('/settings',json={'project_name':'Lab A','dark_mode':True}).status_code==200
    assert client.get('/settings').json()['dark_mode'] is True

def test_search_real_faiss_with_controlled_encoder(client,monkeypatch):
    import main
    import numpy as np
    id=add(client)
    r=client.post('/experiments',json={'document_id':id,'budget':8,'overlap':0}).json()
    import embeddings
    monkeypatch.setattr(embeddings,'load_model',lambda _:None)
    monkeypatch.setattr(embeddings,'split_for_model',lambda text,_:iter([(0,len(text),len(text.split()))]))
    monkeypatch.setattr(embeddings,'encode',lambda texts,*args,**kwargs:np.array([[1.]+[0.]*383 for _ in texts],dtype='float32'))
    result=client.post('/search',json={'experiment_id':r['id'],'query':'sentence','expected':'One two'})
    assert result.status_code==200,result.text
    assert result.json()['expected_hit'] is True
    assert result.json()['hits'][0]['score']==pytest.approx(1.)


def test_sentence_decimal_and_punctuation_preserved():
    for text in ['Version 1.0 is released. Next topic!', '...', 'Plain text without terminal punctuation']:
        chunks=chunk_text(text,'sentence',120,0)
        assert ' '.join(c['text'] for c in chunks).split()==text.split()
        assert all(text[c['start']:c['end']]==c['text'] for c in chunks)

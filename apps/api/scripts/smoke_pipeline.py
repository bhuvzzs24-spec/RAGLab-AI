"""Real-model integration: no synthetic embeddings, mocked retrieval, or AI answers."""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
import numpy as np
import pymupdf as fitz

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path)
parser.add_argument('--with-llm',action='store_true',help='Opt in to six real provider requests and verify grounded Q&A.')
args=parser.parse_args()

with tempfile.TemporaryDirectory(prefix='raglab-real-') as directory:
    os.environ['RAGLAB_DATA_DIR']=directory
    from fastapi.testclient import TestClient
    import main
    import embeddings
    from generation import public_configuration
    if args.with_llm and not public_configuration()['configured']:
        raise SystemExit('BLOCKED: configure LLM_MODEL and LLM_API_KEY (or a trusted local provider) before --with-llm.')
    from pipeline import Build, Retrieval, Engine
    client=TestClient(main.app)
    pdf=fitz.open()
    for text in [
        'The campus library lends energy meters to students. Borrowers can compare the electricity consumption of household appliances. Return meters to the library desk within seven days.',
        'The community garden collects rainwater in covered tanks. Volunteers water plants early in the morning to reduce evaporation. Compost bins accept fruit peels, dry leaves, and coffee grounds.'
    ]:
        page=pdf.new_page();page.insert_textbox(fitz.Rect(72,72,500,500),text,fontsize=12)
    response=client.post('/documents',files={'file':('campus.pdf',pdf.tobytes(),'application/pdf')})
    assert response.status_code==201,response.text
    document=response.json()
    notes=client.post('/documents',files={'file':('retrieval.md',(root/'samples/retrieval-notes.md').read_bytes())}).json()
    report=[]
    for model_id in embeddings.MODELS:
        vectors=embeddings.encode(['The library lends energy meters.','The garden collects rainwater.'],model_id)
        assert vectors.shape==(2,384)
        assert np.allclose(np.linalg.norm(vectors,axis=1),1,atol=1e-5)
        long_text='The library lends energy meters for research. '*100
        spans=list(embeddings.split_for_model(long_text,model_id))
        assert len(spans)>1 and all(tokens<=embeddings.spec(model_id)['max_tokens']-2 for _,_,tokens in spans)
        for strategy in ['fixed','sentence','semantic']:
            index=main.engine.create(Build(document_ids=[document['id'],notes['id']],model_id=model_id,
                strategy=strategy,budget=60,overlap=10,threshold=.55),asynchronous=False)
            assert index['status']=='ready',index
            # Fresh Engine + FAISS subprocess must load the persisted file.
            restarted=Engine(main.connect,main.DATA)
            result=restarted.retrieve(Retrieval(index_id=index['id'],query='Where can students borrow electricity consumption meters?',top_k=3,min_score=.1,expected='energy meters'))
            assert result['expected_hit'],result
            source_hits=[h for h in result['hits'] if h['document_id']==document['id'] and 1 in h['page_numbers']]
            assert source_hits,result
            h=source_hits[0]
            assert document['text'][h['start']:h['end']]==h['text']
            source=restarted.source(index['id'],h['ordinal'])
            assert source['pages'][0]['page']==1
            garden=restarted.retrieve(Retrieval(index_id=index['id'],query='How does the garden collect rainwater?',top_k=1,min_score=.1))
            assert garden['hits'] and garden['hits'][0]['document_id']==document['id'] and 2 in garden['hits'][0]['page_numbers'],garden
            reused=restarted.create(Build(**index['config']),asynchronous=False)
            assert reused['cache_reused'] and reused['id']==index['id']
            rebuilt=restarted.create(Build(**{**index['config'],'rebuild':True}),asynchronous=False)
            assert rebuilt['status']=='ready' and rebuilt['stats']['cache_hits']==rebuilt['stats']['vectors']
            projection=restarted.visualization(index['id'])
            assert len(projection['points'])==min(500,index['stats']['vectors'])
            answer=restarted.answer(result['id']) if args.with_llm or not public_configuration()['configured'] else {'status':'not_requested'}
            if args.with_llm:
                assert answer['status']=='generated' and answer['citations'],answer
                assert 'library' in answer['answer'].lower(),answer
                for citation in answer['citations']:
                    original=client.get('/documents/'+citation['document_id']).json()['text']
                    assert original[citation['start']:citation['end']]==citation['quote']
            entry={'model':model_id,'strategy':strategy,'revision':index['model_revision'],
                   'dimensions':index['dimensions'],'vectors':index['stats']['vectors'],
                   'cache_hits_on_rebuild':rebuilt['stats']['cache_hits'],
                   'energy_phrase_hit':result['expected_hit'],'garden_top1_page':garden['hits'][0]['page_numbers'],
                   'latency_ms':result['latency_ms'],'top_score':result['hits'][0]['score'],
                   'generation_status':answer['status'],'pca_points':projection['sampled']}
            print(json.dumps(entry),flush=True);report.append(entry)
            restarted.shutdown()
    main.engine.shutdown()
    if args.output: args.output.write_text(json.dumps(report,indent=2)+'\n')
    print('REAL_PIPELINE_SMOKE_PASSED: 2 models × 3 chunkers; persisted FAISS loads, relevance, page mapping, cache rebuilds, real PCA.',flush=True)

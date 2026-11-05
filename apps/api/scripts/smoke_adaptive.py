"""Real local-model adaptive evaluation; all included annotations remain unreviewed."""
import argparse,json,os,sys,tempfile,time
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('work/adaptive-evidence.json'));parser.add_argument('--pdf',type=Path,default=Path('work/adaptive-report.pdf'));args=parser.parse_args()
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory(prefix='raglab-adaptive-real-') as directory:
    os.environ['RAGLAB_DATA_DIR']=directory
    from fastapi.testclient import TestClient
    import main
    from benchmarks import RunInput
    with TestClient(main.app) as c:
        d=c.post('/datasets/sample/adaptive').json();assert len(d['questions'])==12 and d['reviewed_count']==0
        response=c.post('/adaptive/searches',json={'dataset_id':d['id'],'include_unreviewed':True,'repetitions':2,'seed':7})
        assert response.status_code==202,response.text
        id=response.json()['id'];deadline=time.monotonic()+900;last=''
        while time.monotonic()<deadline:
            s=c.get('/adaptive/searches/'+id).json()
            if s['phase']!=last:print(s['phase'],flush=True);last=s['phase']
            if s['status'] not in ('queued','running'):break
            time.sleep(.5)
        assert s['status']=='completed',s['error']
        validation=main.benchmark_service.get(s['selection_run_id']);test=main.benchmark_service.get(s['test_run_id'])
        assert validation['completed_configs']==18 and validation['completed_measurements']==144
        assert test['completed_configs']==1 and test['completed_measurements']==8
        assert s['held_out']['provisional'] and s['held_out']['metrics']['unique_answerable_questions']==3
        assert set(q['id'] for q in validation['snapshot']['questions']).isdisjoint(q['id'] for q in test['snapshot']['questions'])
        assert c.post('/adaptive/searches',json={'dataset_id':d['id'],'include_unreviewed':True}).status_code==409
        assert c.post('/adaptive/analyse/'+test['id'],json={}).status_code==422
        # Repeat validation only to check deterministic retrieval quality; never retune from test.
        repeat=main.benchmark_service.start(RunInput(dataset_id=d['id'],include_unreviewed=True,evaluation_split='validation',repetitions=2,name='Validation repeatability check'),asynchronous=False)
        assert repeat['status']=='completed' and repeat['completed_measurements']==144
        def quality(run):return {(x['config']['model_id'],x['config']['strategy'],x['config']['budget']):tuple(x['metrics'][k] for k in ['precision_at_k','recall_at_k','mrr']) for x in run['configs']}
        assert quality(validation)==quality(repeat)
        for config in validation['configs']:
            index=main.engine.row(config['index_id']);assert index['dimensions']==384 and main.engine.artifacts_valid(index)
        with main.connect() as db:
            assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
        vr=c.get('/benchmarks/runs/'+validation['id']+'/export?format=json').json();tr=c.get('/benchmarks/runs/'+test['id']+'/export?format=json').json()
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps({'search':s,'validation':vr,'held_out':tr,'verification':{'real_models':True,'mock_vectors':False,'reviewed_labels':False,'sqlite_integrity':'ok','foreign_keys':'ok','repeat_validation_run_id':repeat['id'],'repeat_measurements':144,'quality_reproduced':True,'test_reuse_rejected':True,'live_llm':'NOT TESTED - no provider credentials'}},indent=2)+'\n')
        args.output.with_suffix('.csv').write_text(c.get('/benchmarks/runs/'+validation['id']+'/export?format=csv').text)
        args.pdf.parent.mkdir(parents=True,exist_ok=True);pdf=c.get('/benchmarks/runs/'+test['id']+'/export?format=pdf');assert pdf.status_code==200;args.pdf.write_bytes(pdf.content)
        print(f'REAL_ADAPTIVE_PASS: search {id}; 18 validation configs / 144 measurements; 1 frozen test config / 8 measurements; repeat validation 144; no human-reviewed or live-LLM claims.',flush=True)

"""Execute all 18 configurations with real local models and public CC0 evidence.

No mocked vectors, retrievals, provider responses or human-review claims.
"""
import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,default=Path('work/benchmark-evidence.json'))
parser.add_argument('--repeat',action='store_true',help='Repeat the full run and verify retrieval-quality reproducibility.')
args=parser.parse_args()
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

with tempfile.TemporaryDirectory(prefix='raglab-real-benchmark-') as directory:
    os.environ['RAGLAB_DATA_DIR']=directory
    from fastapi.testclient import TestClient
    import main
    from benchmarks import RunInput
    with TestClient(main.app) as client:
        sample=client.post('/datasets/sample')
        assert sample.status_code==201,sample.text
        dataset=sample.json()
        assert dataset['question_count']==6 and dataset['reviewed_count']==0
        settings={'dataset_id':dataset['id'],'name':'Real CC0 provisional 18-config benchmark','top_k':3,
                  'repetitions':2,'seed':7,'include_unreviewed':True,'generate_answers':False}
        def execute():
            response=client.post('/benchmarks/runs',json=settings)
            assert response.status_code==202,response.text
            id=response.json()['id'];last=-1;deadline=time.monotonic()+900
            while time.monotonic()<deadline:
                run=client.get('/benchmarks/runs/'+id).json()
                if run['completed_configs']!=last:
                    last=run['completed_configs'];print(f"{id}: {last}/18 configs; {run['completed_measurements']}/{run['total_measurements']} actual measurements; {run['phase']}",flush=True)
                if run['status'] not in ('queued','running'):break
                time.sleep(.25)
            assert run['status']=='completed',[(c['config'],c['error']) for c in run['configs'] if c['error']]
            assert run['completed_configs']==18 and run['completed_measurements']==216
            assert run['snapshot']['provisional'] is True
            assert {c['config']['model_id'] for c in run['configs']}=={'minilm','bge-small'}
            assert len({c['index_id'] for c in run['configs']})==18
            records=client.get('/benchmarks/runs/'+id+'/measurements').json()
            assert len({(m['config_id'],m['question_id'],m['repetition']) for m in records})==216
            for measurement in records:
                assert measurement['generation_status']=='disabled'
                assert measurement['metrics']['answer_exact_match'] is None and measurement['metrics']['groundedness'] is None
                if measurement['answerability']=='answerable':
                    assert all(0<=measurement['metrics'][metric]<=1 for metric in ['precision_at_k','recall_at_k','mrr'])
                else:assert measurement['metrics']['recall_at_k'] is None
            assert any(m['metrics']['recall_at_k'] and m['question_id']=='sample-energy' for m in records)
            for config in run['configs']:
                assert config['metrics']['unique_answerable_questions']==4
                assert config['metrics']['measurements']==12
                assert config['indexing_time_ms'] is not None and config['indexing_time_ms']>0
                index=main.engine.row(config['index_id']);assert index['dimensions']==384 and main.engine.artifacts_valid(index)
                assert index['model_revision']==run['settings']['model_registry'][config['config']['model_id']]['revision']
            board=client.get('/benchmarks/runs/'+id+'/leaderboard').json()
            assert len(board['ranked'])==18
            assert len(client.get('/benchmarks/runs/'+id+'/leaderboard?model_id=minilm').json()['ranked'])==9
            csv=client.get('/benchmarks/runs/'+id+'/export?format=csv')
            assert len(csv.text.splitlines())==217
            return client.get('/benchmarks/runs/'+id+'/export?format=json').json(),csv.text
        exported,csv=execute()
        repeat_evidence=None
        if args.repeat:
            repeated,_=execute()
            def quality(run):
                return {(c['config']['model_id'],c['config']['strategy'],c['config']['budget']):
                    tuple(c['metrics'][metric] for metric in ['precision_at_k','recall_at_k','mrr']) for c in run['configs']}
            assert quality(exported)==quality(repeated),'Retrieval-quality scores changed across repeated identical configurations.'
            repeat_evidence={'run_id':repeated['id'],'configurations':repeated['completed_configs'],
                             'measurements':repeated['completed_measurements'],'quality_reproduced':True,
                             'total_cache_hits':sum(c['cache_hits'] for c in repeated['configs'])}
        exported['verification']={'real_models':True,'fixture_vectors':False,'human_reviewed':False,
                                  'provisional_sample':True,'repeat':repeat_evidence}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(exported,indent=2)+'\n')
        args.output.with_suffix('.csv').write_text(csv)
        print('REAL_BENCHMARK_PASS: 18 configs, 216 actual measurements, 4 unique answerable + 2 unanswerable questions, no generated-answer scores.',flush=True)

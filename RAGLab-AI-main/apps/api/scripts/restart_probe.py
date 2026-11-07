"""Probe an existing disposable benchmark database in a fresh Python process."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
p=argparse.ArgumentParser();p.add_argument('--search-id',required=True);args=p.parse_args()
from fastapi.testclient import TestClient
import main
with TestClient(main.app) as client:
    search=main.adaptive_service.get(args.search_id)
    assert search['status']=='completed' and search['frozen_selection']['sha256']
    run=main.benchmark_service.get(search['selection_run_id']);assert run['completed_measurements']==144
    dataset=main.dataset_store.get(run['dataset_id']);assert dataset['reviewed_count']==0
    history=main.dataset_store.history(dataset['id']);assert len(history)==12 and all(e['action']=='created' for e in history)
    for config in run['configs']:
        row=main.engine.row(config['index_id']);assert row['status']=='ready' and main.engine.artifacts_valid(row)
    config=run['configs'][0];q=run['snapshot']['questions'][0]
    result=client.post('/retrieve',json={'index_id':config['index_id'],'query':q['question'],'top_k':3,'min_score':.2})
    assert result.status_code==200 and result.json()['hits'],result.text
    with main.connect() as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    print('RESTART_PROBE_PASS '+json.dumps({'new_python_process':True,'persisted_configurations':18,'persisted_measurements':144,'persisted_review_events':len(history),'source_labels_still_unreviewed':True,'fresh_retrieval_hits':len(result.json()['hits']),'sqlite_integrity':'ok'}),flush=True)

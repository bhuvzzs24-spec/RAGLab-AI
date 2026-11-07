import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]))
from evaluation import evaluate_retrieval,merged_length,exact_match,optimize

def hit(a,b,document='d'):return {'document_id':document,'start':a,'end':b}
def question(*spans,answerability='answerable'):return {'answerability':answerability,'relevant_spans':[hit(a,b) for a,b in spans]}

def test_known_precision_recall_and_reciprocal_rank():
    value=evaluate_retrieval([hit(0,100,'wrong'),hit(10,20),hit(40,50)],question((10,20),(40,60)),3)
    assert value['precision_at_k']==pytest.approx(2/3)
    assert value['recall_at_k']==1
    assert value['mrr']==.5
    assert value['span_coverages']==[1.,.5]

def test_overlapping_chunks_do_not_inflate_evidence_recall():
    value=evaluate_retrieval([hit(0,7),hit(0,7),hit(0,7)],question((0,20)),3)
    assert value['precision_at_k']==pytest.approx(1/3)
    assert value['recall_at_k']==0
    assert value['evidence_coverage']==.35
    assert merged_length([(0,10),(5,15),(15,20)])==20

def test_original_ranks_retained_when_duplicates_occur():
    value=evaluate_retrieval([hit(0,5,'wrong'),hit(0,5,'wrong'),hit(10,20)],question((10,20)),3)
    assert value['mrr']==pytest.approx(1/3)
    assert value['precision_at_k']==pytest.approx(1/3)

def test_fixed_k_includes_missing_slots_and_boundary_touch_is_not_relevant():
    assert evaluate_retrieval([hit(10,20)],question((10,20)),3)['precision_at_k']==pytest.approx(1/3)
    value=evaluate_retrieval([hit(0,10),hit(20,30),hit(10,10)],question((10,20)),3)
    assert value['precision_at_k']==value['recall_at_k']==value['mrr']==0

def test_source_span_judgments_survive_chunk_splitting():
    q=question((10,30))
    combined=evaluate_retrieval([hit(0,40)],q,2)
    split=evaluate_retrieval([hit(10,20),hit(20,30)],q,2)
    assert combined['recall_at_k']==split['recall_at_k']==1
    assert combined['mrr']==split['mrr']==1
    assert split['evidence_coverage']==1

@pytest.mark.parametrize('answerability',['unknown','unanswerable'])
def test_no_invented_scores_for_unanswerable_or_unknown(answerability):
    value=evaluate_retrieval([],question(answerability=answerability),3)
    assert value['precision_at_k'] is value['recall_at_k'] is value['mrr'] is None
    assert value['retrieval_abstained'] is True

def test_exact_match_is_explicitly_strict_and_reference_based():
    assert exact_match('The Library. [1]',['library'])==1
    assert exact_match('Return meters within seven days. [1]',['seven days'])==0
    assert exact_match('Anything',[]) is None

def config(id,quality,latency,status='completed'):
    return {'id':id,'status':status,'metrics':{'precision_at_k':quality,'recall_at_k':quality,'mrr':quality,'latency_mean_ms':latency,'unique_answerable_questions':4,'measurements':12}}

def test_explainable_optimizer_objectives_and_partial_exclusion():
    rows=[config('accurate',1,100),config('fast',.4,10),config('failed',1,0,'failed')]
    assert optimize(rows,'accuracy')[0]['id']=='accurate'
    assert optimize(rows,'speed')[0]['id']=='fast'
    assert optimize(rows,'balanced')[0]['id']=='accurate'
    assert len(optimize(rows))==2
    assert optimize(rows)[0]['optimizer']['sample_size']==4
    assert optimize([config('a',1,10),config('b',.4,10)],'speed')[0]['optimizer']['speed_score']==1

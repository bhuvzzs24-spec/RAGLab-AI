"""Versioned, source-span retrieval judgments and transparent aggregation."""
import re
import string
import numpy as np

METHOD_VERSION = 'source-evidence-overlap-v1'
METHODOLOGY = {
    'version': METHOD_VERSION,
    'precision_at_k': 'Relevant unique retrieved passages / requested k; missing ranks count as nonrelevant.',
    'passage_relevance': 'Same source document/hash and intersection / min(passage length, gold span length) >= the fixed overlap threshold.',
    'recall_at_k': 'Fraction of distinct gold evidence spans with union coverage >= the fixed overlap threshold in the top k. Overlaps are merged before counting coverage.',
    'mrr': 'Reciprocal rank of the first relevant passage, averaged over answerable questions and repetitions; 0 when none is relevant.',
    'scope': 'Only answerable questions with validated source evidence enter P/R/MRR. Unanswerable questions have undefined retrieval P/R/MRR and a separately reported retrieval abstention rate.',
    'duplicates': 'Repeated identical document/start/end hits do not count twice; original ranks are retained. Different overlapping passages can both be relevant, but cannot inflate evidence recall.',
    'answer_correctness': 'Optional normalized exact match against reference answers, only for successfully generated, answerable outputs. Not a semantic correctness judge.',
    'groundedness': 'Not evaluated: no validated semantic or human claim evaluator is configured. Citation quote validation is provenance, not semantic groundedness.',
    'latency': 'Actual query embedding + index validation/load/search time after one excluded warm-up per configuration. Query repetitions are not independent questions.',
}


def merged_length(intervals):
    total=0; end=-1
    for a,b in sorted(intervals):
        if b<=a: continue
        total+=max(0,b-max(a,end)); end=max(end,b)
    return total


def evaluate_retrieval(hits, question, k, overlap_threshold=.5):
    seen=set(); unique=[]; ranks=[]
    for rank,hit in enumerate(hits[:k],1):
        key=(hit['document_id'],hit['start'],hit['end'])
        if key not in seen:
            seen.add(key);unique.append(hit);ranks.append(rank)
    gold=question.get('relevant_spans',[])
    if question['answerability']!='answerable' or not gold:
        return {'precision_at_k':None,'recall_at_k':None,'mrr':None,'evidence_coverage':None,
                'relevant_ranks':[], 'gold_spans':len(gold),'retrieved':len(unique),
                'retrieval_abstained':not bool(unique)}
    relevant=[]; coverages=[]
    for rank,hit in zip(ranks,unique):
        for span in gold:
            if hit['document_id']!=span['document_id']: continue
            # Caller validates the document hash against the immutable run snapshot.
            intersection=max(0,min(hit['end'],span['end'])-max(hit['start'],span['start']))
            denominator=min(hit['end']-hit['start'],span['end']-span['start'])
            if denominator>0 and intersection/denominator>=overlap_threshold:
                relevant.append(rank);break
    for span in gold:
        pieces=[(max(h['start'],span['start']),min(h['end'],span['end'])) for h in unique if h['document_id']==span['document_id']]
        coverages.append(merged_length(pieces)/(span['end']-span['start']))
    return {'precision_at_k':len(relevant)/k,
            'recall_at_k':sum(c>=overlap_threshold for c in coverages)/len(gold),
            'mrr':1/relevant[0] if relevant else 0.,'evidence_coverage':sum(coverages)/len(gold),
            'relevant_ranks':relevant,'gold_spans':len(gold),'retrieved':len(unique),
            'span_coverages':coverages,'retrieval_abstained':not bool(unique)}


def normalize_answer(text):
    text=re.sub(r'\[\d+\]','',text).lower()
    text=''.join(c for c in text if c not in string.punctuation)
    return ' '.join(re.sub(r'\b(a|an|the)\b',' ',text).split())


def exact_match(answer,references):
    if not references:return None
    value=normalize_answer(answer)
    return float(any(value==normalize_answer(ref) for ref in references))


def aggregate(measurements):
    def mean(name):
        values=[m['metrics'][name] for m in measurements if m['metrics'].get(name) is not None]
        return float(np.mean(values)) if values else None
    answerable=[m for m in measurements if m['answerability']=='answerable']
    unanswerable=[m for m in measurements if m['answerability']=='unanswerable']
    times=[m['latency_ms'] for m in measurements]
    return {**{name:mean(name) for name in ['precision_at_k','recall_at_k','mrr','evidence_coverage','answer_exact_match']},
            'latency_mean_ms':float(np.mean(times)) if times else None,
            'latency_p50_ms':float(np.median(times)) if times else None,
            'latency_p95_ms':float(np.percentile(times,95)) if times else None,
            'measurements':len(measurements),'answerable_measurements':len(answerable),
            'unique_questions':len({m['question_id'] for m in measurements}),
            'unique_answerable_questions':len({m['question_id'] for m in answerable}),
            'answer_evaluated_measurements':sum(m['metrics'].get('answer_exact_match') is not None for m in measurements),
            'unanswerable_measurements':len(unanswerable),
            'unanswerable_abstention_rate':float(np.mean([m['metrics']['retrieval_abstained'] for m in unanswerable])) if unanswerable else None,
            'groundedness':None,'groundedness_status':'not_evaluated',
            'generation_statuses':{status:sum(m.get('generation_status')==status for m in measurements) for status in sorted({m.get('generation_status','disabled') for m in measurements})}}


def optimize(configs,objective='balanced'):
    if objective not in ('accuracy','speed','balanced'):raise ValueError('Choose accuracy, speed or balanced.')
    eligible=[c for c in configs if c['status']=='completed' and c.get('metrics',{}).get('recall_at_k') is not None]
    if not eligible:return []
    low=min(c['metrics']['latency_mean_ms'] for c in eligible)
    high=max(c['metrics']['latency_mean_ms'] for c in eligible)
    result=[]
    for c in eligible:
        m=c['metrics'];quality=.45*m['recall_at_k']+.35*m['mrr']+.2*m['precision_at_k']
        speed=1. if high==low else 1-(m['latency_mean_ms']-low)/(high-low)
        score={'accuracy':quality,'speed':speed,'balanced':.7*quality+.3*speed}[objective]
        result.append({**c,'optimizer':{'score':score,'retrieval_accuracy_score':quality,'speed_score':speed,
                       'sample_size':m['unique_answerable_questions'],'measurements':m['measurements'],
                       'explanation':f"Recall {m['recall_at_k']:.3f}, MRR {m['mrr']:.3f}, precision {m['precision_at_k']:.3f}; mean retrieval {m['latency_mean_ms']:.2f} ms."}})
    result.sort(key=lambda c:(-c['optimizer']['score'],-c['metrics']['mrr'],c['metrics']['latency_mean_ms'],c['id']))
    return [{**c,'rank':i+1} for i,c in enumerate(result)]

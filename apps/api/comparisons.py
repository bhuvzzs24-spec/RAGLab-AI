"""Paired descriptive comparisons, refusing incompatible question/evidence cohorts."""
import json
from fastapi import HTTPException
from datasets import sha
from evaluation import aggregate

def compare(service,left_id,right_id):
    left,right=service.get(left_id),service.get(right_id)
    issues=[]
    for key in ['top_k','min_score','evidence_overlap','evaluation_version']:
        if left['settings'].get(key)!=right['settings'].get(key):issues.append(f'Different {key}')
    def content(run):
        return sha(json.dumps([{'id':q['id'],'question':q['question'],'answerability':q['answerability'],'spans':[(s['document_id'],s['source_sha256'],s['start'],s['end']) for s in q['relevant_spans']]} for q in sorted(run['snapshot']['questions'],key=lambda x:x['id'])],sort_keys=True))
    if content(left)!=content(right):issues.append('Different question/evidence cohort; changing approval status alone is permitted')
    if left['snapshot']['sources']!=right['snapshot']['sources']:issues.append('Different source content')
    if left['snapshot'].get('split','all')!=right['snapshot'].get('split','all'):issues.append('Different evaluation partitions')
    if left['status']!='completed' or right['status']!='completed':issues.append('Both runs must be complete')
    def config_key(c):return json.dumps(c['config'],sort_keys=True)
    rows=[]
    if not issues:
        paired={config_key(c):c for c in right['configs'] if c['status']=='completed'}
        for a in left['configs']:
            b=paired.get(config_key(a))
            if not b or a['status']!='completed':continue
            rows.append({'config':a['config'],'left_config_id':a['id'],'right_config_id':b['id'],
                'delta':{k:b['metrics'][k]-a['metrics'][k] if a['metrics'].get(k) is not None and b['metrics'].get(k) is not None else None for k in ['precision_at_k','recall_at_k','mrr','latency_mean_ms']},
                'unique_answerable_questions':b['metrics']['unique_answerable_questions']})
    return {'compatible':not issues,'issues':issues,'left_id':left_id,'right_id':right_id,'left_provisional':left['snapshot']['provisional'],'right_provisional':right['snapshot']['provisional'],
            'rows':rows,'method':'Right minus left for matched complete configurations, identical question/evidence cohort and retrieval settings. Descriptive deltas, not significance or universal superiority. Review revisions remain separately traceable.'}

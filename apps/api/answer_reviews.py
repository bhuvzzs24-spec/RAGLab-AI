"""Explicit, attributed human answer evaluation. Never an automatic semantic judge."""
import json
from datetime import datetime,timezone
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field

RUBRIC={
 'version':'human-answer-rubric-v1',
 'correctness':'Against the supplied human reference: incorrect=0, partial=0.5, correct=1. Not evaluated is null. Human judgment, not calibrated semantic equivalence.',
 'groundedness':'Judge every displayed answer claim against retrieved source passages. supported=1, unsupported=0. The mean is reported only if all claims are judged; any uncertain rating keeps the score null. Citation quote presence alone is not semantic support.',
 'abstention':'For an explicit insufficient-context answer, correctness may be judged against a reference; claim groundedness is inapplicable and remains null.',
 'identity':'Reviewer names are self-attestations in this local single-user application, not authenticated identities.'}

class AnswerReviewInput(BaseModel):
    reviewer:str=Field(min_length=1,max_length=100)
    notes:str=Field('',max_length=3000)
    reference_answer:str=Field('',max_length=10000)
    correctness:Literal['not_evaluated','incorrect','partial','correct']='not_evaluated'
    claim_ratings:list[Literal['supported','unsupported','uncertain']]=Field(default_factory=list,max_length=20)
    attested:bool=False
    expected_latest_id:str|None=None

class AnswerReviewStore:
    def __init__(self,connect):
        self.connect=connect
        with connect() as db:db.execute('''CREATE TABLE IF NOT EXISTS answer_reviews(
            id TEXT PRIMARY KEY,answer_id TEXT REFERENCES answers(id),payload TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP)''')
    def context(self,id):
        with self.connect() as db:
            row=db.execute('SELECT a.result,r.result AS retrieval FROM answers a JOIN retrievals r ON r.id=a.retrieval_id WHERE a.id=?',(id,)).fetchone()
        if not row:raise HTTPException(404,'Stored answer not found. Generate or retrieve again.')
        answer=json.loads(row['result']);retrieval=json.loads(row['retrieval'])
        claims=answer.get('claims') or ([{'text':text} for text in answer['answer'].split('\n\n')] if answer.get('status')=='generated' and answer.get('answer') else [])
        return {'answer':answer,'claims':claims,'retrieval':retrieval,'rubric':RUBRIC,'reviews':self.history(id)}
    def history(self,id):
        with self.connect() as db:rows=db.execute('SELECT payload FROM answer_reviews WHERE answer_id=? ORDER BY rowid DESC',(id,)).fetchall()
        return [json.loads(r[0]) for r in rows]
    def save(self,id,data):
        context=self.context(id);answer=context['answer'];claims=context['claims']
        if answer['status'] not in ('generated','insufficient_context'):raise HTTPException(422,'There is no generated answer or abstention to review. Provider failures cannot receive quality scores.')
        if not data.reviewer.strip() or not data.attested:raise HTTPException(422,'Name the reviewer and explicitly attest to inspecting the answer and source passages.')
        if data.correctness!='not_evaluated' and not data.reference_answer.strip():raise HTTPException(422,'Provide a human reference answer or expected abstention rationale before judging correctness.')
        if data.claim_ratings and len(data.claim_ratings)!=len(claims):raise HTTPException(422,'Rate every displayed claim, or leave claim evaluation empty.')
        correctness={'incorrect':0.,'partial':.5,'correct':1.}.get(data.correctness)
        groundedness=None
        if data.claim_ratings and 'uncertain' not in data.claim_ratings:groundedness=sum(r=='supported' for r in data.claim_ratings)/len(data.claim_ratings)
        result={**data.model_dump(exclude={'expected_latest_id'}),'id':str(uuid4()),'answer_id':id,'reviewer':data.reviewer.strip(),
                'correctness_score':correctness,'groundedness_score':groundedness,'claim_count':len(claims),'rubric_version':RUBRIC['version'],
                'method':'explicit_human_review','created':datetime.now(timezone.utc).isoformat()}
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            latest=db.execute('SELECT id FROM answer_reviews WHERE answer_id=? ORDER BY rowid DESC LIMIT 1',(id,)).fetchone()
            if (latest[0] if latest else None)!=data.expected_latest_id:raise HTTPException(409,'Answer review changed. Reload its history before submitting another judgment.')
            db.execute('INSERT INTO answer_reviews(id,answer_id,payload) VALUES(?,?,?)',(result['id'],id,json.dumps(result)))
        return result
    def rollup(self,measurements):
        selected=[];answer_ids={m.get('generation',{}).get('id') for m in measurements if m.get('generation',{}).get('id')}
        for id in sorted(answer_ids):
            history=self.history(id)
            if history:selected.append(history[0])
        by_answer={m.get('generation',{}).get('id'):m.get('question_id') for m in measurements}
        def unique_questions(key):return len({by_answer[r['answer_id']] for r in selected if r[key] is not None and by_answer.get(r['answer_id']) is not None})
        def mean(key):
            values=[r[key] for r in selected if r[key] is not None]
            return sum(values)/len(values) if values else None
        return {'method':'explicit_human_review_latest_per_answer','rubric':RUBRIC,'reviewed_answers':len(selected),'stored_answers':len(answer_ids),
                'correctness':mean('correctness_score'),'groundedness':mean('groundedness_score'),
                'correctness_unique_questions':unique_questions('correctness_score'),'groundedness_unique_questions':unique_questions('groundedness_score'),
                'correctness_n':sum(r['correctness_score'] is not None for r in selected),'groundedness_n':sum(r['groundedness_score'] is not None for r in selected),
                'review_ids':[r['id'] for r in selected],'as_of':datetime.now(timezone.utc).isoformat(),
                'limitation':'Post-run human judgments are separate from immutable automated metrics. Counts refer to answer judgments, not independent questions; repeated queries do not increase independent sample size. Small or selected review samples are not general quality estimates.'}

def router(store,benchmarks):
    routes=APIRouter(tags=['Human answer evaluation'])
    @routes.get('/answers/{id}/review')
    def context(id:str):return store.context(id)
    @routes.post('/answers/{id}/review',status_code=201)
    def review(id:str,data:AnswerReviewInput):return store.save(id,data)
    @routes.get('/benchmarks/runs/{id}/answer-reviews')
    def rollup(id:str):return store.rollup(benchmarks.measurements(id))
    return routes

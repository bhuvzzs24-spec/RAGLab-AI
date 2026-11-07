"""Editable source-grounded datasets. Human-review flags are explicit attestations."""
import csv
from ingestion import csv_safe
import hashlib
import io
import json
from pathlib import Path
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter, HTTPException, UploadFile, Form
from fastapi.responses import Response
from pydantic import BaseModel, Field
from pipeline import pages_for


def sha(text):return hashlib.sha256(text.encode()).hexdigest()

class EvidenceInput(BaseModel):
    id:str=Field(default_factory=lambda:str(uuid4()),max_length=100)
    document_id:str=''
    document_name:str=''
    start:int|None=Field(None,ge=0)
    end:int|None=Field(None,ge=1)
    quote:str=Field('',max_length=20000)
    source_sha256:str=''

class QuestionInput(BaseModel):
    id:str=Field(default_factory=lambda:str(uuid4()),min_length=1,max_length=100)
    question:str=Field(min_length=1,max_length=2000)
    reference_answer:str=Field('',max_length=10000)
    reference_answers:list[str]=Field(default_factory=list,max_length=10)
    answerability:Literal['answerable','unanswerable','unknown']='answerable'
    relevant_spans:list[EvidenceInput]=Field(default_factory=list,max_length=30)
    review_status:Literal['unreviewed','reviewed','rejected']|None=None
    human_reviewed:bool=False
    reviewer:str=Field('',max_length=100)
    review_notes:str=Field('',max_length=2000)
    split:Literal['unassigned','train','validation','test']='unassigned'
    group_id:str=Field('',max_length=120)
    annotation_origin:str=Field('user',max_length=50)

class DatasetInput(BaseModel):
    name:str=Field(min_length=1,max_length=120)
    description:str=Field('',max_length=3000)
    document_ids:list[str]=Field(default_factory=list,max_length=50)
    questions:list[QuestionInput]=Field(default_factory=list,max_length=500)
    expected_revision:int|None=None
    sample:bool=False
    editor:str=Field('',max_length=100)

class DatasetStore:
    def __init__(self,connect):
        self.connect=connect
        with connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS benchmark_datasets(id TEXT PRIMARY KEY,name TEXT,description TEXT,
                revision INTEGER,document_ids TEXT,questions TEXT,sample INTEGER DEFAULT 0,
                created TEXT DEFAULT CURRENT_TIMESTAMP,updated TEXT DEFAULT CURRENT_TIMESTAMP)''')

            db.execute('''CREATE TABLE IF NOT EXISTS dataset_review_history(
                id TEXT PRIMARY KEY,dataset_id TEXT REFERENCES benchmark_datasets(id),question_id TEXT,
                revision INTEGER,action TEXT,actor TEXT,notes TEXT,before_json TEXT,after_json TEXT,
                created TEXT DEFAULT CURRENT_TIMESTAMP)''')

    def history(self,id):
        self.get(id)
        with self.connect() as db:rows=db.execute('SELECT * FROM dataset_review_history WHERE dataset_id=? ORDER BY rowid DESC',(id,)).fetchall()
        return [{**dict(r),'before_json':json.loads(r['before_json']) if r['before_json'] else None,'after_json':json.loads(r['after_json']) if r['after_json'] else None} for r in rows]

    def review(self,id,question_id,data):
        current=self.get(id)
        if data.expected_revision!=current['revision']:raise HTTPException(409,'Dataset revision changed. Reload before reviewing.')
        question=next((q for q in current['questions'] if q['id']==question_id),None)
        if not question:raise HTTPException(404,'Question not found.')
        if not data.reviewer.strip():raise HTTPException(422,'A reviewer name is required for an explicit decision.')
        question.update(review_status={'approve':'reviewed','reject':'rejected','reopen':'unreviewed'}[data.action],
            human_reviewed=data.action=='approve',reviewer=data.reviewer.strip(),review_notes=data.notes)
        return self.save(DatasetInput(**{**current,'editor':data.reviewer,'expected_revision':data.expected_revision}),id,decision=(question_id,data.action))

    def resolve_document(self,key):
        with self.connect() as db:
            rows=db.execute('SELECT * FROM documents WHERE id=? OR name=?',(key,key)).fetchall()
        exact=[r for r in rows if r['id']==key]
        if exact:return dict(exact[0])
        if len(rows)!=1:raise HTTPException(422,f'Source {key!r} is missing or ambiguous. Upload it, or specify its document ID.')
        return dict(rows[0])

    def validate(self,data):
        if not data.name.strip():raise HTTPException(422,'Dataset name cannot be blank.')
        documents={}
        for key in data.document_ids:
            d=self.resolve_document(key);documents[d['id']]=d
        questions=[];ids=set()
        for q in data.questions:
            if not q.question.strip():raise HTTPException(422,'Questions cannot be blank.')
            if q.id in ids:raise HTTPException(422,'Question IDs must be unique.')
            ids.add(q.id)
            if q.human_reviewed and not q.reviewer.strip():raise HTTPException(422,'Record a reviewer name before marking a question and its evidence as human reviewed.')
            if q.review_status=='rejected' and q.human_reviewed:raise HTTPException(422,'Rejected questions cannot be human reviewed. Reopen and approve explicitly.')
            if q.review_status=='rejected' and not q.reviewer.strip():raise HTTPException(422,'Rejected questions require reviewer attribution.')
            spans=[];span_ids=set()
            for e in q.relevant_spans:
                d=self.resolve_document(e.document_id or e.document_name)
                documents[d['id']]=d;fingerprint=sha(d['text'])
                if e.source_sha256 and e.source_sha256!=fingerprint:raise HTTPException(422,'Source text changed. Review and re-anchor the evidence span.')
                start,end=e.start,e.end
                if start is None:
                    if not e.quote or d['text'].count(e.quote)!=1:raise HTTPException(422,'A quote without offsets must appear exactly once in the source. Set explicit start/end offsets.')
                    start=d['text'].index(e.quote)
                if end is None:end=start+len(e.quote)
                if end<=start or end>len(d['text']):raise HTTPException(422,'Evidence offsets must be a non-empty half-open interval inside the source.')
                quote=d['text'][start:end]
                if not quote.strip() or (e.quote and quote!=e.quote):raise HTTPException(422,'Evidence quote does not match the exact original source offsets.')
                if e.id in span_ids:raise HTTPException(422,'Evidence IDs must be unique within a question.')
                if any(x['document_id']==d['id'] and max(start,x['start'])<min(end,x['end']) for x in spans):raise HTTPException(422,'Gold evidence spans must not overlap. Merge overlapping spans into one evidence unit.')
                span_ids.add(e.id)
                spans.append({'id':e.id,'document_id':d['id'],'document_name':d['name'],'start':start,'end':end,
                              'quote':quote,'source_sha256':fingerprint,'page_numbers':pages_for(json.loads(d['pages']),start,end)})
            if q.answerability=='unanswerable' and spans:raise HTTPException(422,'An unanswerable question cannot have relevant source evidence.')
            references=list(dict.fromkeys([s.strip() for s in [q.reference_answer,*q.reference_answers] if s.strip()]))
            if q.human_reviewed and q.answerability=='answerable' and (not spans or not references):raise HTTPException(422,'A reviewed answerable question needs a reference answer and at least one validated evidence span.')
            questions.append({**q.model_dump(exclude={'relevant_spans','reference_answers'}),'question':q.question.strip(),
                              'reference_answers':references,'relevant_spans':spans,'review_status':'rejected' if q.review_status=='rejected' else ('reviewed' if q.human_reviewed else 'unreviewed')})
        if not documents:raise HTTPException(422,'Select at least one document for the dataset collection.')
        return sorted(documents),questions

    def save(self,data,id=None,*,decision=None):
        document_ids,questions=self.validate(data)
        id=id or str(uuid4())
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current=db.execute('SELECT revision,questions FROM benchmark_datasets WHERE id=?',(id,)).fetchone()
            if data.expected_revision is not None and (not current or current['revision']!=data.expected_revision):raise HTTPException(409,'This dataset was updated elsewhere. Reload before saving.')
            previous={q['id']:q for q in json.loads(current['questions'])} if current else {}
            # Approval belongs to exact question/reference/evidence content. Edits require a new decision.
            content_keys=['question','reference_answer','reference_answers','answerability','relevant_spans']
            for q in questions:
                old=previous.get(q['id'])
                if old and (any(old.get(k)!=q.get(k) for k in content_keys) or (old.get('reviewer','')!=q.get('reviewer','') and (not decision or decision[0]!=q['id']))):
                    q.update(human_reviewed=False,review_status='unreviewed')
            revision=current['revision']+1 if current else 1
            if current:
                db.execute('UPDATE benchmark_datasets SET name=?,description=?,revision=revision+1,document_ids=?,questions=?,sample=?,updated=CURRENT_TIMESTAMP WHERE id=?',
                           (data.name.strip(),data.description,json.dumps(document_ids),json.dumps(questions),int(data.sample),id))
            else:
                db.execute('INSERT INTO benchmark_datasets(id,name,description,revision,document_ids,questions,sample) VALUES(?,?,?,1,?,?,?)',
                           (id,data.name.strip(),data.description,json.dumps(document_ids),json.dumps(questions),int(data.sample)))
            after={q['id']:q for q in questions}
            for qid in sorted(previous.keys()|after.keys()):
                old,new=previous.get(qid),after.get(qid)
                if old==new and (not decision or decision[0]!=qid):continue
                action='created' if old is None else ('removed' if new is None else 'edited')
                if old and new:
                    old_status=old.get('review_status') or ('reviewed' if old.get('human_reviewed') else 'unreviewed')
                    if old_status!=new['review_status']:action={'reviewed':'approved','rejected':'rejected','unreviewed':'reopened'}[new['review_status']]
                    if any(old.get(k)!=new.get(k) for k in content_keys):action='edited_approval_revoked' if old.get('human_reviewed') else 'edited'
                if decision and decision[0]==qid:action={'approve':'approved','reject':'rejected','reopen':'reopened'}[decision[1]]
                actor=data.editor.strip() or ((new or old).get('reviewer','').strip() if action in ('approved','rejected','reopened') else None) or None
                db.execute('INSERT INTO dataset_review_history(id,dataset_id,question_id,revision,action,actor,notes,before_json,after_json) VALUES(?,?,?,?,?,?,?,?,?)',
                    (str(uuid4()),id,qid,revision,action,actor,(new or old).get('review_notes',''),json.dumps(old) if old else None,json.dumps(new) if new else None))
        return self.get(id)

    def get(self,id):
        with self.connect() as db:r=db.execute('SELECT * FROM benchmark_datasets WHERE id=?',(id,)).fetchone()
        if not r:raise HTTPException(404,'Dataset not found.')
        data=dict(r);data['document_ids']=json.loads(data['document_ids']);data['questions']=json.loads(data['questions']);data['sample']=bool(data['sample'])

        for q in data['questions']:q.setdefault('review_status','reviewed' if q.get('human_reviewed') else 'unreviewed')
        data['rejected_count']=sum(q['review_status']=='rejected' for q in data['questions'])
        data['question_count']=len(data['questions']);data['reviewed_count']=sum(q['human_reviewed'] for q in data['questions'])
        return data

    def list(self):
        with self.connect() as db:ids=[r[0] for r in db.execute('SELECT id FROM benchmark_datasets ORDER BY updated DESC,rowid DESC')]
        return [{k:v for k,v in self.get(id).items() if k!='questions'} for id in ids]

    def snapshot(self,id,include_unreviewed=False,split='all'):
        if split not in ('all','train','validation','test'):raise HTTPException(422,'Invalid evaluation split.')
        data=self.get(id)
        questions=[q for q in data['questions'] if q['answerability']!='unknown' and q.get('review_status')!='rejected' and (q['human_reviewed'] or include_unreviewed) and (split=='all' or q.get('split','unassigned')==split)]
        if not questions or not any(q['answerability']=='answerable' for q in questions):raise HTTPException(422,'Review at least one answerable question with reference/evidence, or explicitly include provisional annotations.')
        for q in questions:
            if q['answerability']=='answerable' and (not q['relevant_spans'] or not q['reference_answers']):raise HTTPException(422,'Every included answerable question needs reference answers and relevant source spans.')
        sources=[]
        for id in data['document_ids']:
            d=self.resolve_document(id);sources.append({'id':id,'name':d['name'],'sha256':sha(d['text'])})
        hashes={d['id']:d['sha256'] for d in sources}
        for q in questions:
            for e in q['relevant_spans']:
                if hashes.get(e['document_id'])!=e['source_sha256']:raise HTTPException(409,'Evidence source changed. Review the dataset before benchmarking.')
        snapshot={'dataset_id':data['id'],'name':data['name'],'revision':data['revision'],'sample':data['sample'],
                  'document_ids':data['document_ids'],'sources':sources,'questions':questions,
                  'review_history_ids':[event['id'] for event in self.history(data['id']) if event['revision']<=data['revision']],
                  'split':split,'include_unreviewed':include_unreviewed,'provisional':any(not q['human_reviewed'] for q in questions),
                  'reviewed_questions':sum(q['human_reviewed'] for q in questions),'excluded_questions':len(data['questions'])-len(questions)}
        snapshot['fingerprint']=sha(json.dumps(snapshot,sort_keys=True))
        return snapshot

    def import_file(self,filename,raw,name='',collection=None):
        try:
            text=raw.decode('utf-8-sig')
            if filename.lower().endswith('.json'):
                parsed=json.loads(text)
                if isinstance(parsed,list):parsed={'questions':parsed}
                if not isinstance(parsed,dict):raise ValueError('Expected a JSON dataset object or question array.')
            elif filename.lower().endswith('.csv'):
                rows=list(csv.DictReader(io.StringIO(text)))
                if not rows or 'question' not in rows[0]:raise ValueError('CSV needs a question column.')
                grouped={}
                for i,row in enumerate(rows):
                    id=row.get('question_id') or row.get('id') or f'q-{i+1}'
                    if id not in grouped:
                        reviewed=(row.get('human_reviewed') or 'false').strip().lower()
                        if reviewed not in ('true','false','1','0'):raise ValueError('human_reviewed must be true/false or 1/0.')
                        grouped[id]={'id':id,'question':row['question'],'reference_answer':row.get('reference_answer',''),
                            'reference_answers':json.loads(row.get('reference_answers') or '[]'),'answerability':row.get('answerability') or 'answerable',
                            'human_reviewed':reviewed in ('true','1'),'reviewer':row.get('reviewer',''),'review_notes':row.get('review_notes',''),
                            'review_status':row.get('review_status') or 'unreviewed','split':row.get('split') or 'unassigned','group_id':row.get('group_id') or '',
                            'annotation_origin':'import','relevant_spans':[]}
                    else:
                        expected=grouped[id]
                        check={'review_status':row.get('review_status') or 'unreviewed','split':row.get('split') or 'unassigned','group_id':row.get('group_id') or '', 'question':row['question'],'reference_answer':row.get('reference_answer',''),
                               'reference_answers':json.loads(row.get('reference_answers') or '[]'),
                               'answerability':row.get('answerability') or 'answerable',
                               'reviewer':row.get('reviewer',''),'review_notes':row.get('review_notes','')}
                        if any(expected[k]!=v for k,v in check.items()):raise ValueError('Rows sharing a question_id must have consistent question, reference, answerability and review metadata.')
                        value=(row.get('human_reviewed') or 'false').strip().lower()
                        if value not in ('true','false','1','0') or expected['human_reviewed']!=(value in ('true','1')):raise ValueError('Rows sharing a question_id have conflicting human-review flags.')
                    if row.get('document_id') or row.get('document_name'):
                        grouped[id]['relevant_spans'].append({'document_id':row.get('document_id') or '', 'document_name':row.get('document_name') or '',
                            'start':int(row['start']) if row.get('start') else None,'end':int(row['end']) if row.get('end') else None,
                            'quote':row.get('quote') or '', 'source_sha256':row.get('source_sha256') or ''})
                parsed={'questions':list(grouped.values())}
            else:raise HTTPException(415,'Import a UTF-8 CSV or JSON dataset.')
            parsed['name']=name or parsed.get('name') or Path(filename).stem
            if collection:parsed['document_ids']=collection
            # Imported attestation flags are not a review performed in this application.
            for question in parsed.get('questions',[]):
                question.update(human_reviewed=False,review_status='unreviewed',reviewer='',annotation_origin='import')
            return self.save(DatasetInput(**parsed))
        except HTTPException:raise
        except Exception as exc:raise HTTPException(422,'Dataset import failed: '+str(exc)[:300])

    def sample(self,adaptive=False):
        directory=Path(__file__).parent/'samples'
        document_ids=[]
        with self.connect() as db:
            for filename in (['adaptive-campus.txt'] if adaptive else ['campus-guide.txt','retrieval-notes.md']):
                text=(directory/filename).read_text()
                match=db.execute('SELECT id FROM documents WHERE name=? AND text=?',(filename,text)).fetchone()
                id=match['id'] if match else str(uuid4())
                if not match:db.execute('INSERT INTO documents(id,name,text,pages,bytes) VALUES(?,?,?,?,?)',(id,filename,text,json.dumps([text]),len(text.encode())))
                document_ids.append(id)
        template=json.loads((directory/('adaptive-sample.json' if adaptive else 'benchmark-sample.json')).read_text())
        return self.save(DatasetInput(**{**template,'document_ids':document_ids}))

    def export(self,id,format):
        data=self.get(id)
        if format=='json':return Response(json.dumps({**data,'review_history':self.history(id)},indent=2),media_type='application/json',headers={'Content-Disposition':'attachment; filename="raglab-dataset.json"'})
        if format!='csv':raise HTTPException(422,'Choose csv or json.')
        out=io.StringIO();fields=['question_id','question','reference_answer','reference_answers','split','group_id','answerability','human_reviewed','review_status','reviewer','review_notes','document_id','document_name','start','end','quote','source_sha256']
        writer=csv.DictWriter(out,fieldnames=fields,lineterminator='\n');writer.writeheader()
        write_row=writer.writerow
        writer.writerow=lambda row:write_row({k:csv_safe(v) for k,v in row.items()})
        for q in data['questions']:
            for span in q['relevant_spans'] or [{}]:
                writer.writerow({'question_id':q['id'],**{k:q.get(k,'') for k in ['question','reference_answer','split','group_id','answerability','review_status','reviewer','review_notes']},
                    'reference_answers':json.dumps(q['reference_answers']),'human_reviewed':str(q['human_reviewed']).lower(),
                    **{k:span.get(k,'') for k in ['document_id','document_name','start','end','quote','source_sha256']}})
        return Response(out.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="raglab-dataset.csv"'})


def router(store):
    routes=APIRouter(prefix='/datasets',tags=['Datasets'])
    @routes.get('')
    def list_datasets():return store.list()
    @routes.post('',status_code=201)
    def create_dataset(data:DatasetInput):return store.save(data)
    @routes.post('/sample',status_code=201)
    def sample_dataset():return store.sample()
    @routes.post('/sample/adaptive',status_code=201)
    def adaptive_sample():return store.sample(adaptive=True)
    @routes.post('/import',status_code=201)
    async def import_dataset(file:UploadFile,name:str=Form(''),document_ids:str=Form('[]')):
        raw=await file.read(2*1024*1024+1)
        if len(raw)>2*1024*1024:raise HTTPException(413,'Dataset import exceeds 2 MB.')
        try:collection=json.loads(document_ids)
        except ValueError:raise HTTPException(422,'document_ids must be a JSON array.')
        if not isinstance(collection,list):raise HTTPException(422,'document_ids must be an array.')
        return store.import_file(file.filename or '',raw,name,collection)
    @routes.get('/{id}')
    def get_dataset(id:str):return store.get(id)
    @routes.put('/{id}')
    def update_dataset(id:str,data:DatasetInput):
        store.get(id);return store.save(data,id)
    @routes.get('/{id}/history')
    def history(id:str):return store.history(id)
    @routes.post('/{id}/questions/{question_id}/review')
    def review(id:str,question_id:str,data:ReviewInput):return store.review(id,question_id,data)
    @routes.post('/{id}/split')
    def split_dataset(id:str,data:SplitInput):
        return assign_splits(store,id,data)
    @routes.get('/{id}/export')
    def export_dataset(id:str,format:str='json'):return store.export(id,format)
    return routes


class SplitInput(BaseModel):
    expected_revision:int
    seed:int=Field(7,ge=0,le=2**31-1)


def evidence_groups(questions):
    """Connected components: explicit groups, duplicate questions and overlapping evidence."""
    from evaluation import normalize_answer
    parents=list(range(len(questions)))
    def root(i):
        while parents[i]!=i:
            parents[i]=parents[parents[i]];i=parents[i]
        return i
    for i,a in enumerate(questions):
        for j in range(i):
            b=questions[j]
            shared_group=bool(a.get('group_id')) and a.get('group_id')==b.get('group_id')
            duplicate=normalize_answer(a['question'])==normalize_answer(b['question'])
            overlap=any(x['document_id']==y['document_id'] and max(x['start'],y['start'])<min(x['end'],y['end']) for x in a['relevant_spans'] for y in b['relevant_spans'])
            if shared_group or duplicate or overlap:parents[root(i)]=root(j)
    groups={}
    for i,q in enumerate(questions):groups.setdefault(root(i),[]).append(q)
    return list(groups.values())


def validate_split_isolation(questions):
    for group in evidence_groups(questions):
        splits={q.get('split','unassigned') for q in group}-{ 'unassigned' }
        if len(splits)>1:raise HTTPException(422,'Leakage risk: duplicate questions, overlapping evidence or an explicit group cross split boundaries. Assign the whole group to one split.')


def assign_splits(store,id,data):
    import random
    current=store.get(id)
    if current['revision']!=data.expected_revision:raise HTTPException(409,'Dataset revision changed. Reload before splitting.')
    groups=evidence_groups(current['questions'])
    if len(groups)<3:raise HTTPException(422,'Need at least three independent evidence/question groups for train, validation and test. Add independent questions first.')
    groups.sort(key=lambda g:sorted(q['id'] for q in g))
    random.Random(data.seed).shuffle(groups)
    # Approximately 60/20/20, ensuring each partition has at least one group.
    n=len(groups);n_test=max(1,round(n*.2));n_val=max(1,round(n*.2))
    for i,group in enumerate(groups):
        split='test' if i<n_test else ('validation' if i<n_test+n_val else 'train')
        for q in group:q['split']=split
    validate_split_isolation(current['questions'])
    return store.save(DatasetInput(**{**current,'expected_revision':data.expected_revision}),id)


class ReviewInput(BaseModel):
    expected_revision:int
    action:Literal['approve','reject','reopen']
    reviewer:str=Field(min_length=1,max_length=100)
    notes:str=Field('',max_length=2000)

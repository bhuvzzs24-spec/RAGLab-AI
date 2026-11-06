'use client';
import {useEffect,useState} from 'react';
import {RefreshCw} from 'lucide-react';
import {request} from './pipeline-types';
import {metric} from './benchmark-types';
type Evaluation={reviewed_answers:number;stored_answers:number;correctness:number|null;groundedness:number|null;correctness_n:number;groundedness_n:number;correctness_unique_questions:number;groundedness_unique_questions:number;limitation:string;as_of:string};
export default function HumanEvaluationSummary({runId}:{runId:string}){
 const [data,setData]=useState<Evaluation|null>(null),[error,setError]=useState(''),[tick,setTick]=useState(0);
 useEffect(()=>{const c=new AbortController();setError('');setData(null);request<Evaluation>(`/benchmarks/runs/${runId}/answer-reviews`,{signal:c.signal}).then(setData).catch(e=>{if(!c.signal.aborted)setError(e.message)});return()=>c.abort()},[runId,tick]);
 return <section className="panel benchmark-integrity human-evaluation"><div className="section-title"><h3>Human answer judgments</h3><button className="button" onClick={()=>setTick(n=>n+1)}><RefreshCw size={14}/> Refresh answer reviews</button></div>{error&&<p className="alert" role="alert">{error}</p>}{data?<><div><span>Reviewed / stored answers</span><strong>{data.reviewed_answers} / {data.stored_answers}</strong></div><div><span>Human correctness · {data.correctness_n} judgments / {data.correctness_unique_questions} questions</span><strong>{metric(data.correctness)}</strong></div><div><span>Human claim groundedness · {data.groundedness_n} judgments / {data.groundedness_unique_questions} questions</span><strong>{metric(data.groundedness)}</strong></div><p>{data.limitation} Review actual answers in RAG Playground. Absent or uncertain judgments remain unevaluated. As of {new Date(data.as_of).toLocaleString()}.</p></>:!error&&<div className="skeleton"/>}</section>
}

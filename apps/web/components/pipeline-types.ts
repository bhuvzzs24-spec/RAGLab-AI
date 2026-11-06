export type DocumentInfo={id:string;name:string};
export type ModelInfo={id:string;name:string;repository:string;revision:string;dimensions:number;max_tokens:number;query_prefix:string;document_prefix:string;normalized:boolean;license:string};
export type BuildConfig={document_ids:string[];model_id:string;strategy:string;budget:number;overlap:number;threshold:number;rebuild?:boolean};
export type VectorIndex={id:string;model_id:string;model_revision:string;dimensions:number;config:BuildConfig;status:string;phase:string;progress:number;total:number;cancel_requested:number;error:string|null;stats:{vectors?:number;parent_chunks?:number;documents?:number;cache_hits?:number;disk_bytes?:number;build_ms?:number;norm_min?:number;norm_max?:number};created:string;cache_reused?:boolean};
export type Hit={id:string;ordinal:number;document_id:string;source_name:string;chunk_index:number;part:number;start:number;end:number;tokens:number;model_tokens:number;page_numbers:number[];text:string;score:number;source_id:number;source_url:string};
export type RetrievalResult={id:string;retrieval_id:string;index_id:string;model_id:string;model_revision:string;query:string;hits:Hit[];latency_ms:number;timings:{query_embedding_ms:number;search_and_load_ms:number};expected_hit:boolean|null;index_reused:boolean};
export type Citation={source_id:number;quote:string;chunk_id:string;document_id:string;page_numbers:number[];start:number;end:number};
export type Generation={id?:string;claims?:{text:string}[];status:string;answer:string|null;citations:Citation[];message?:string;model?:string;latency_ms?:number;grounding_note?:string};
export type Provider={configured:boolean;model:string|null;provider_host:string|null;protocol:string};
export type Point={stable_id?:string;start?:number;end?:number;x:number;y:number;ordinal:number;document_id:string;source_name:string;tokens:number;page_numbers:number[]};
export type Projection={method:string;sampled:number;total:number;explained_variance:number[];points:Point[]};
export async function request<T>(path:string, init?:RequestInit):Promise<T>{
 const response=await fetch('/api'+path,init);
 if(!response.ok){let message=`Request failed (HTTP ${response.status}).`;try{const body=await response.json();message=typeof body.detail==='string'?body.detail:Array.isArray(body.detail)?body.detail.map((x:{msg:string})=>x.msg).join('; '):message}catch{message='API unavailable. Start the FastAPI server and retry.'}throw new Error(message)}
 return response.json() as Promise<T>;
}
export function post<T>(path:string,data:unknown):Promise<T>{return request<T>(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})}
export const titleFor=(i:VectorIndex)=>`${i.model_id==='minilm'?'MiniLM':'BGE Small'} · ${i.config.strategy} · ${i.config.budget} words · ${i.config.document_ids.length} doc${i.config.document_ids.length===1?'':'s'}`;

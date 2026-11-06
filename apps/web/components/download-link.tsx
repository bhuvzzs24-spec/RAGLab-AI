'use client';
import {useState,type AnchorHTMLAttributes,type MouseEvent} from 'react';
// Keep exports in the workspace so an API error cannot replace the application.
export default function DownloadLink({href,children,...props}:AnchorHTMLAttributes<HTMLAnchorElement>){
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 const download=async(e:MouseEvent<HTMLAnchorElement>)=>{if(e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;e.preventDefault();if(busy||!href)return;setBusy(true);setError('');try{
  const response=await fetch(href,{signal:AbortSignal.timeout(60000)});
  if(!response.ok){let message=`Download failed (HTTP ${response.status}). Please retry.`;try{const body=await response.json();if(typeof body.detail==='string')message=body.detail}catch{}throw Error(message)}
  const blob=await response.blob();const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=response.headers.get('content-disposition')?.match(/filename="?([^";]+)"?/i)?.[1]||'raglab-export';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 }catch(e){setError((e as Error).name==='TimeoutError'?'Download timed out. Please retry.':(e as Error).message)}finally{setBusy(false)}};
 return <span className="download-control"><a {...props} href={href} onClick={download} aria-disabled={busy} aria-busy={busy}>{children}{busy&&<span role="status"> · Downloading…</span>}</a>{error&&<span className="download-error" role="alert">{error}</span>}</span>
}

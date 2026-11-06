'use client';
import {useEffect,useRef} from 'react';
import dynamic from 'next/dynamic';
const Intro=dynamic(()=>import('./cinematic-intro'),{loading:()=> <div className="skeleton"/>});
const Tour=dynamic(()=>import('./pipeline-tour'),{loading:()=> <div className="skeleton"/>});
export default function ExperienceDialog({kind,onClose,onTour}:{kind:'intro'|'tour';onClose:()=>void;onTour:()=>void}){
 const ref=useRef<HTMLDialogElement>(null);
 useEffect(()=>{const dialog=ref.current;const old=document.activeElement as HTMLElement|null;dialog?.showModal();const overflow=document.body.style.overflow;document.body.style.overflow='hidden';return()=>{dialog?.close();document.body.style.overflow=overflow;old?.focus()}},[]);
 return <dialog className="experience-dialog" ref={ref} aria-label={kind==='intro'?'RAGLab optional introduction':'Interactive RAG pipeline tour'} onCancel={e=>{e.preventDefault();onClose()}}>{kind==='intro'?<Intro onClose={onClose} onTour={onTour}/>:<Tour onClose={onClose}/>}</dialog>
}

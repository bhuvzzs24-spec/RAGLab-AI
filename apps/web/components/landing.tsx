'use client';
import {Component,useEffect,useState,type ReactNode} from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import {motion} from 'framer-motion';
import {ArrowUpRight,ArrowRight,Layers3,Pause,RotateCcw} from 'lucide-react';
import {useSystemReducedMotion} from './motion-preferences';
import {request} from './pipeline-types';
import {useWorkspaceTransition} from './landing-transition';
import type {MouseEvent} from 'react';
import './landing.css';
const Gallery=dynamic(()=>import('./landing-gallery'),{ssr:false,loading:()=> <div className="landing-loading" role="status">Preparing the gallery…</div>});
class GalleryBoundary extends Component<{children:ReactNode;onRetry:()=>void},{failed:boolean}>{state={failed:false};static getDerivedStateFromError(){return {failed:true}}render(){return this.state.failed?<div className="landing-fallback"><p>The gallery could not load. Your workspace is still available.</p><button onClick={this.props.onRetry}>Retry gallery</button></div>:this.props.children}}
export default function Landing(){
 const reduced=useSystemReducedMotion(),[stopped,setStopped]=useState(false),[visible,setVisible]=useState(true),[replay,setReplay]=useState(0),[api,setApi]=useState<'checking'|'connected'|'offline'>('checking');
 useEffect(()=>{const update=()=>setVisible(!document.hidden);update();document.addEventListener('visibilitychange',update);return()=>document.removeEventListener('visibilitychange',update)},[]);
 useEffect(()=>{const c=new AbortController();request<{status:string}>('/health',{signal:c.signal}).then(h=>setApi(h.status==='ok'?'connected':'offline')).catch(()=>{if(!c.signal.aborted)setApi('offline')});return()=>c.abort()},[]);
 const {active,enter}=useWorkspaceTransition();
 const navigate=(href:string)=>(event:MouseEvent<HTMLAnchorElement>)=>{if(event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;event.preventDefault();enter(href)};
 const playing=!reduced&&!stopped&&visible;
 return <motion.main className="raglab-landing" initial={false} animate={{opacity:active && !reduced ? 0.5 : 1,scale:active && !reduced ? 0.985 : 1}} transition={{duration:reduced?0:.3}} aria-busy={active}><a className="landing-skip" href="/overview">Skip to workspace</a><div className="landing-visual">{playing?<GalleryBoundary key={replay} onRetry={()=>setReplay(n=>n+1)}><Gallery/></GalleryBoundary>:<div className="landing-still"><span className="landing-still-orbit"/><p>From source.<br/><em>To evidence.</em><br/>To better answers.</p><small>{reduced?'Reduced motion · animated gallery is not loaded':stopped?'Animation stopped · replay starts a new scene':'Gallery suspended while this tab is hidden'}</small></div>}</div><header className="landing-header"><Link href="/" className="landing-brand" aria-label="RAGLab AI landing page"><Layers3 size={23}/><h1>RAGLab<span>AI</span></h1></Link><span className="landing-edition">AN ADAPTIVE RETRIEVAL STUDIO</span><Link href="/overview" className="landing-top-link">Skip Intro <ArrowUpRight size={15}/></Link></header><motion.section className="landing-caption" initial={reduced?false:{opacity:0,y:14}} animate={{opacity:1,y:0}} transition={{duration:.55,delay:.12}}><div><p className="landing-kicker"><span/> CURIOSITY, WITH A PAPER TRAIL</p><h2>Adaptive RAG<br/>Benchmarking &amp; Optimization</h2><p className="landing-description">Source. Context. Evidence.</p></div><div className="landing-actions"><Link className="landing-enter" href="/overview" onClick={navigate('/overview')}>Enter Workspace <ArrowRight size={20}/></Link><Link className="landing-pipeline" href="/overview?experience=tour" onClick={navigate('/overview?experience=tour')}>Explore Pipeline <ArrowUpRight size={17}/></Link><p className={`landing-api ${api}`} role="status"><span/>{api==='checking'?'Checking local API…':api==='connected'?'Local API connected':'API unavailable · open Settings in the workspace for diagnostics'}</p></div></motion.section><footer className="landing-footer"><span>HOVER / TOUCH THE ARTWORK TO SET IT IN MOTION</span><div>{!reduced&&<button onClick={()=>{setStopped(v=>!v);setReplay(n=>n+1)}} aria-pressed={stopped}>{stopped?<RotateCcw size={13}/>:<Pause size={13}/>} {stopped?'Replay animation':'Stop animation'}</button>}<span>Visual: ThreeUI / Halftone Loop</span></div></footer></motion.main>
}

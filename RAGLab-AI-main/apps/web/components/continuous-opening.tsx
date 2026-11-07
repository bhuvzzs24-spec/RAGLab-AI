'use client';
import {useRef} from 'react';
import {motion,useScroll,useTransform} from 'framer-motion';
import Landing from './landing';
import Studio from './studio';
import {useSystemReducedMotion} from './motion-preferences';
import './continuous-opening.css';
export default function ContinuousOpening(){
 const workspace=useRef<HTMLElement>(null),reduced=useSystemReducedMotion();
 const {scrollYProgress}=useScroll({target:workspace,offset:['start end','start start']});
 const clip=useTransform(scrollYProgress,p=>p>=.999?'none':`inset(0 ${32*(1-p)}px 0 round ${32*(1-p)}px)`);
 const opacity=useTransform(scrollYProgress,[0,.35,1],[.96,1,1]);
 const enter=(instant=false)=>{if(!workspace.current)return;if(window.location.hash!=='#workspace')window.history.pushState(null,'','#workspace');workspace.current.scrollIntoView({behavior:instant||reduced?'instant':'smooth',block:'start'});workspace.current.focus({preventScroll:true})};
 return <div className="continuous-opening"><div className="handoff-wash" aria-hidden="true"/><Landing onEnterWorkspace={enter}/><motion.section id="workspace" ref={workspace} tabIndex={-1} aria-label="RAGLab workspace" className="workspace-reveal" style={reduced?undefined:{clipPath:clip,opacity}}><Studio page="overview" embedded/></motion.section></div>
}

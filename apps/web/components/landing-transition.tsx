'use client';
import {createContext,useCallback,useContext,useEffect,useRef,useState,type ReactNode} from 'react';
import {useRouter} from 'next/navigation';
import {AnimatePresence,motion} from 'framer-motion';
import {useSystemReducedMotion} from './motion-preferences';
const WorkspaceTransition=createContext({active:false,enter:(_href:string)=>{}});
export const useWorkspaceTransition=()=>useContext(WorkspaceTransition);
export default function LandingTransition({children}:{children:ReactNode}){
 const router=useRouter(),reduced=useSystemReducedMotion(),[active,setActive]=useState(false),[duration,setDuration]=useState(.78),timers=useRef<ReturnType<typeof setTimeout>[]>([]),running=useRef(false);
 const clear=useCallback(()=>{timers.current.forEach(clearTimeout);timers.current=[]},[]);useEffect(()=>clear,[clear]);
 const enter=useCallback((href:string)=>{if(running.current)return;if(reduced){router.push(href);return}running.current=true;const seconds=window.matchMedia('(max-width: 700px)').matches ? 0.38 : 0.78;setDuration(seconds);setActive(true);timers.current=[setTimeout(()=>router.push(href),seconds*400),setTimeout(()=>{setActive(false);running.current=false;timers.current=[]},seconds*1000)]},[reduced,router]);
 return <WorkspaceTransition.Provider value={{active,enter}}>{children}<AnimatePresence>{active&&<motion.div className="workspace-entry-mask" data-duration-ms={duration*1000} aria-hidden="true" initial={{y:'100%'}} animate={{y:['100%','0%','0%','-100%']}} transition={{duration,times:[0,.4,.57,1],ease:[.76,0,.24,1]}} style={{position:'fixed',inset:0,zIndex:2000,background:'#FCFAF8',display:'grid',placeItems:'center',pointerEvents:'all'}}><motion.span initial={{opacity:0,y:10}} animate={{opacity:[0,1,1,0],y:[10,0,0,-10]}} transition={{duration,times:[0,.3,.6,1]}} style={{fontFamily:'Didot, Georgia, serif',fontSize:'clamp(28px,5vw,58px)',color:'#400849',letterSpacing:'-1px'}}>RAGLab <span style={{color:'#FF5A0A'}}>AI</span></motion.span></motion.div>}</AnimatePresence></WorkspaceTransition.Provider>
}

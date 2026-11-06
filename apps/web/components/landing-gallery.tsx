'use client';
import {useEffect,useRef} from 'react';
import {raglabDocument} from './gallery/raglab-document';
export default function LandingGallery(){
 const ref=useRef<HTMLIFrameElement>(null);
 // Preserve the official component's frame-leave handshake for its authored
 // hover/touch easing; listeners and the frame document are released on unmount.
 useEffect(()=>{const frame=ref.current;if(!frame)return;let inside=false;
  const leave=()=>{if(inside){inside=false;frame.contentWindow?.postMessage({threeuiRuntime:{hover:0}},'*')}};
  const message=(e:MessageEvent)=>{if(e.source===frame.contentWindow&&e.data?.threeuiPointerOver)inside=true};
  const move=(e:PointerEvent)=>{const b=frame.getBoundingClientRect();if(e.clientX<b.left||e.clientX>b.right||e.clientY<b.top||e.clientY>b.bottom)leave()};
  window.addEventListener('message',message);window.addEventListener('pointermove',move,true);window.addEventListener('blur',leave);frame.addEventListener('pointerleave',leave);document.addEventListener('mouseleave',leave);
  return()=>{window.removeEventListener('message',message);window.removeEventListener('pointermove',move,true);window.removeEventListener('blur',leave);frame.removeEventListener('pointerleave',leave);document.removeEventListener('mouseleave',leave)};
 },[]);
 return <div className="shader-frame"><iframe ref={ref} title="RAGLAB AI Halftone Loop canvas animation" srcDoc={raglabDocument} sandbox="allow-scripts" style={{display:'block',width:'100%',height:'100%',border:0,background:'#120715'}}/></div>
}

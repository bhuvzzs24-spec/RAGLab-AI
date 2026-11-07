'use client';
import {createContext,useContext,useSyncExternalStore} from 'react';
export const MotionPreference=createContext('system');
const query='(prefers-reduced-motion: reduce)';
const subscribe=(listener:()=>void)=>{const media=window.matchMedia(query);media.addEventListener('change',listener);return()=>media.removeEventListener('change',listener)};
const snapshot=()=>window.matchMedia(query).matches;
const serverSnapshot=()=>true;
export function useSystemReducedMotion(){return useSyncExternalStore(subscribe,snapshot,serverSnapshot)}
export function useMotionSafety(){const preference=useContext(MotionPreference);const os=useSystemReducedMotion();return preference==='reduced'||os}

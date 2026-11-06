'use client';
import {createContext,useContext} from 'react';
import {useReducedMotion} from 'framer-motion';
export const MotionPreference=createContext('system');
export function useMotionSafety(){const preference=useContext(MotionPreference);const os=useReducedMotion();return preference==='reduced'||Boolean(os)}

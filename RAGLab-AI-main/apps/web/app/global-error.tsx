'use client';
import StudioError from './error';
export default function GlobalError(props:{error:Error & {digest?:string};reset:()=>void}){return <html lang="en"><body style={{margin:0,padding:20,background:'#FCFAF8'}}><StudioError {...props}/></body></html>}

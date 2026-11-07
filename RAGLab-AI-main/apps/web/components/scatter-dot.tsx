'use client';
/** Recharts 2 wraps each symbol in role=img. Its direct title supplies a real accessible name. */
export default function ScatterDot(value:unknown){
 const p=value as {cx?:number;cy?:number;fill?:string;payload?:{name?:string;latency?:number;quality?:number;recall?:number}};
 const q=p.payload?.quality??p.payload?.recall;const latency=p.payload?.latency;
 const label=`${p.payload?.name||'Measured configuration'}${q==null?'':`, quality ${q.toFixed(3)}`}${latency==null?'':`, mean latency ${latency.toFixed(2)} ms`}`;
 return <><title>{label}</title><circle cx={p.cx} cy={p.cy} r={5} fill={p.fill}/></>
}

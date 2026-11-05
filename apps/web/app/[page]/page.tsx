import Studio from '../../components/studio';
import {notFound} from 'next/navigation';
export default async function Page({params}:{params:Promise<{page:string}>}){const {page}=await params;if(!['datasets','benchmarks','documents','chunking','embeddings','experiments','leaderboard','playground','reports','settings'].includes(page))notFound();return <Studio page={page}/>}

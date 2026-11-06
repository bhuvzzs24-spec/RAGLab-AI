import './globals.css';
import LandingTransition from '../components/landing-transition';
import type { Metadata } from 'next';
export const metadata: Metadata = {title:'RAGLab — Retrieval, refined.',description:'A document-grounded RAG benchmarking and optimization studio'};
export default function Layout({children}:{children:React.ReactNode}){return <html lang="en"><body><LandingTransition>{children}</LandingTransition></body></html>}

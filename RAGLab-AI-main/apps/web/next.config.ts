import type { NextConfig } from 'next';
import path from 'node:path';
const config: NextConfig = {modularizeImports:{'@designcodeio/threeui':{transform:'@designcodeio/threeui/components/{{member}}',skipDefaultConversion:true}},outputFileTracingRoot:path.resolve(process.cwd(),'../..'), async rewrites(){ return [{source:'/api/:path*',destination:`${process.env.API_URL || 'http://127.0.0.1:8000'}/:path*`}]; }};
export default config;

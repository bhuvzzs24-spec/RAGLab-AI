import {defineConfig} from '@playwright/test';
const shellQuote=(value:string)=>"'"+value.replaceAll("'","'\\''")+"'";
export default defineConfig({
 testDir:'./apps/web/e2e',timeout:240000,expect:{timeout:15000},workers:1,fullyParallel:false,
 reporter:[['list'],['json',{outputFile:'work/browser-results.json'}]],
 outputDir:'work/browser-artifacts',
 use:{actionTimeout:15000,navigationTimeout:30000,baseURL:'http://127.0.0.1:3000',headless:true,trace:'retain-on-failure',screenshot:'only-on-failure',reducedMotion:'reduce'},
 projects:[{name:'desktop-chromium',use:{browserName:'chromium',viewport:{width:1440,height:1000}}},{name:'mobile-chromium',use:{browserName:'chromium',viewport:{width:390,height:844},isMobile:true,hasTouch:true}}],
 webServer:[
  {command:`${shellQuote(process.env.RAGLAB_PYTHON||'python3')} -m uvicorn main:app --app-dir apps/api --host 127.0.0.1 --port 8000`,url:'http://127.0.0.1:8000/health',reuseExistingServer:false,timeout:120000,env:{RAGLAB_DATA_DIR:process.env.RAGLAB_E2E_DATA_DIR||'./work/e2e-data'}},
  {command:'npm run start -w apps/web',url:'http://127.0.0.1:3000',reuseExistingServer:false,timeout:120000,env:{API_URL:'http://127.0.0.1:8000'}}
 ]
});

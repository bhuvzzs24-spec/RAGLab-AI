import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
test.describe.configure({mode:'serial'});

test('dataset source review rejects unsubstantiated human-review flags',async({page})=>{
 await page.goto('/datasets');
 await page.getByRole('button',{name:'Load CC0 sample',exact:true}).click();
 await expect(page.getByRole('status')).toContainText('All annotations are explicitly unreviewed');
 await page.getByRole('button',{name:/“The campus library lends energy meters to students/}).click();
 await expect(page.locator('.source-annotator mark')).toContainText('The campus library lends energy meters');
 const reviewed=page.getByRole('checkbox',{name:/I have reviewed this question/});
 await reviewed.check();await page.getByRole('button',{name:'Save dataset',exact:true}).click();
 await expect(page.locator('.alert[role="alert"]')).toContainText('reviewer name');
 await reviewed.uncheck();await page.getByRole('button',{name:'Save dataset',exact:true}).click();
 await expect(page.getByRole('status')).toContainText('Dataset saved');
});

test('run 18 real configurations, inspect charts, filter, optimize and export actual results',async({page,request},testInfo)=>{
 const seeded=await request.post('/api/datasets/sample');expect(seeded.status()).toBe(201);const dataset=await seeded.json();
 await page.goto('/benchmarks');
 await page.getByRole('combobox',{name:'Benchmark dataset',exact:true}).selectOption(dataset.id);
 await page.getByLabel('Run name',{exact:true}).fill(`Browser real benchmark ${testInfo.project.name}`);
 await page.getByLabel('Repetitions per question',{exact:true}).fill('1');
 await page.getByRole('checkbox',{name:/Include unreviewed annotations/}).check();
 await expect(page.locator('input:invalid')).toHaveCount(0);
 const created=page.waitForResponse(r=>r.url().endsWith('/api/benchmarks/runs')&&r.request().method()==='POST',{timeout:20000});
 await page.getByRole('button',{name:'Run 18 configurations',exact:true}).click();
 const response=await created;expect(response.status()).toBe(202);const started=await response.json();
 await page.getByRole('button',{name:'Cancel run',exact:true}).click();
 await expect.poll(async()=>{const r=await request.get('/api/benchmarks/runs/'+started.id);return (await r.json()).status},{timeout:45000,intervals:[300,600]}).toBe('cancelled');
 await page.getByRole('button',{name:'Resume missing work',exact:true}).click();
 await expect.poll(async()=>{const r=await request.get('/api/benchmarks/runs/'+started.id);return (await r.json()).status},{timeout:180000,intervals:[500,1000,1500]}).toBe('completed');
 await expect(page.getByText('18/18 configurations completed',{exact:true})).toBeVisible();
 await expect(page.locator('.benchmark-table tbody tr')).toHaveCount(18);
 await expect(page.getByText('108/108 persisted measurements',{exact:true})).toBeVisible();
 await expect(page.locator('.run-progress .benchmark-notice')).toContainText('PROVISIONAL');
 await expect(page.locator('.heat-cell:not(:disabled)')).toHaveCount(18);
 await page.getByRole('combobox',{name:'Optimization objective',exact:true}).selectOption('speed');
 await expect(page.locator('.optimizer-card')).toContainText('speed score');
 await page.getByRole('combobox',{name:'Filter benchmark model',exact:true}).selectOption('bge-small');
 await expect(page.locator('.benchmark-table tbody tr')).toHaveCount(9);
 await expect(page.locator('.heat-cell:not(:disabled)')).toHaveCount(9);
 await page.locator('.benchmark-table tbody tr input[type=checkbox]').nth(0).check();
 await page.locator('.benchmark-table tbody tr input[type=checkbox]').nth(1).check();
 await expect(page.getByRole('heading',{name:'Configuration comparison',exact:true})).toBeVisible();
 const download=page.waitForEvent('download');await page.getByRole('link',{name:'CSV',exact:true}).click();
 const file=await download;const path=await file.path();expect(path).toBeTruthy();
 const csv=await readFile(path!,'utf8');expect(csv.split('\n').filter(Boolean)).toHaveLength(109);expect(csv).toContain('dataset_fingerprint');
 await page.evaluate(()=>window.scrollTo(0,0));
 await page.screenshot({path:`work/browser-${testInfo.project.name}.png`,fullPage:true});
});

test('Phase 2 retrieval and original source highlights remain functional',async({page,request})=>{
 const indexes=await (await request.get('/api/indexes')).json();const index=indexes.find((i:{status:string;model_id:string})=>i.status==='ready'&&i.model_id==='minilm');expect(index).toBeTruthy();
 await page.goto('/playground');await page.getByRole('combobox').first().selectOption(index.id);
 await page.getByRole('textbox',{name:'Your research question',exact:true}).fill('Where can students borrow energy meters?');
 await page.getByRole('button',{name:'Retrieve & answer',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Retrieval complete · LLM not configured',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Open source 1',exact:true}).click();
 await expect(page.locator('.source-dialog')).toBeVisible();
 await expect(page.locator('.source-dialog mark')).toContainText('energy meters');
 await page.getByRole('button',{name:'Close source preview',exact:true}).click();
 await expect(page.locator('.source-dialog')).toHaveCount(0);
});

test('adaptive search freezes a validation choice, evaluates held-out, downloads PDF and preserves all pages',async({page,request},testInfo)=>{
 const response=await request.post('/api/datasets/sample/adaptive');expect(response.status()).toBe(201);const dataset=await response.json();
 await page.goto('/datasets');await page.getByRole('combobox',{name:'Choose dataset',exact:true}).selectOption(dataset.id);
 await expect(page.getByRole('combobox',{name:'Question split',exact:true})).toHaveValue('train');
 await page.getByRole('checkbox',{name:'Show only pending human reviews',exact:true}).check();
 await expect(page.locator('.question-row')).toHaveCount(12);
 await page.goto('/benchmarks');
 await page.getByRole('combobox',{name:'Adaptive dataset',exact:true}).selectOption(dataset.id);
 await page.getByRole('checkbox',{name:'Include unreviewed labels · clearly provisional',exact:true}).check();
 await page.getByRole('spinbutton',{name:'Adaptive repetitions',exact:true}).fill('1');
 const created=page.waitForResponse(r=>r.url().endsWith('/api/adaptive/searches')&&r.request().method()==='POST');
 await page.getByRole('button',{name:'Search & evaluate held-out',exact:true}).click();
 const start=await created;expect([202,409]).toContain(start.status());let search:{id:string};
 if(start.status()===409){
  await expect(page.locator('.adaptive-panel .alert')).toContainText('already reserved/exposed');
  const previous=await (await request.get('/api/adaptive/searches')).json();search=previous.find((s:{status:string})=>s.status==='completed');expect(search).toBeTruthy();
  await page.getByRole('combobox',{name:'Adaptive search history',exact:true}).selectOption(search.id);
 }else search=await start.json();
 await expect.poll(async()=>{const r=await request.get('/api/adaptive/searches/'+search.id);return (await r.json()).status},{timeout:180000,intervals:[500,1500]}).toBe('completed');
 await expect(page.locator('.heldout-card')).toContainText('Frozen choice:');
 await expect(page.locator('.heldout-card')).toContainText('PROVISIONAL');
 await page.getByRole('button',{name:'Validation run',exact:false}).click();
 await expect(page.locator('.benchmark-table tbody tr')).toHaveCount(18);
 await page.getByRole('button',{name:'Analyse selected run',exact:true}).click();
 await expect(page.locator('.adaptive-analysis')).toContainText('18 measured candidates');
 await expect(page.locator('.pareto-figure')).toBeVisible();
 const download=page.waitForEvent('download');await page.getByRole('link',{name:'PDF report',exact:true}).click();
 const file=await download;expect((await readFile((await file.path())!)).subarray(0,4).toString()).toBe('%PDF');
 await page.getByRole('button',{name:'Held-out run & exports',exact:true}).click();
 await expect(page.locator('.benchmark-table tbody tr')).toHaveCount(1);
 await expect(page.getByRole('button',{name:'Analyse selected run',exact:true})).toBeDisabled();
 await page.screenshot({path:`work/adaptive-${testInfo.project.name}.png`,fullPage:true});
 for(const path of ['/','/documents','/chunking','/embeddings','/experiments','/leaderboard','/playground','/reports','/settings']){
  await page.goto(path);await expect(page.locator('h1')).toBeVisible();await expect(page.locator('.alert[role="alert"]')).toHaveCount(0);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
 }
 await page.getByRole('button',{name:'Toggle color theme',exact:true}).click();await expect(page.locator('.studio')).toHaveClass(/dark/);
});

test('upload, chunk preview, saved experiments and settings work through the browser',async({page},testInfo)=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 const name=`browser-${testInfo.project.name}.txt`;
 await page.goto('/documents');
 await page.getByLabel('Upload document',{exact:true}).setInputFiles({name,mimeType:'text/plain',buffer:Buffer.from('The observatory opens at sunset. Visitors book a place at the science desk. Bring warm clothing for the evening session.')});
 await expect(page.getByRole('status')).toContainText('Document extracted and saved.');
 const row=page.locator('tr').filter({hasText:name});await row.getByRole('button',{name:'Preview',exact:true}).click();
 await expect(page.locator('.page-text pre')).toContainText('observatory opens at sunset');
 await page.goto('/chunking');await page.getByLabel('Source document',{exact:true}).selectOption({label:name});
 await page.getByLabel('Token budget',{exact:true}).fill('8');await page.getByLabel('Overlap',{exact:true}).fill('2');
 await page.getByRole('button',{name:'Preview chunks',exact:true}).click();await expect(page.locator('.chunk-item').first()).toContainText('CHUNK 01');
 await page.getByRole('button',{name:'Save experiment',exact:false}).click();await expect(page.getByRole('status')).toContainText('Experiment saved');
 await page.goto('/experiments');await expect(page.locator('tbody')).toContainText('fixed · 8 tokens');
 await page.goto('/settings');await page.getByLabel('Project name',{exact:true}).fill('Verified research workspace');await page.getByRole('button',{name:'Save preferences',exact:false}).click();
 await expect(page.getByRole('status')).toContainText('Preferences saved');await page.reload();await expect(page.getByLabel('Project name',{exact:true})).toHaveValue('Verified research workspace');
 expect(errors).toEqual([]);
});

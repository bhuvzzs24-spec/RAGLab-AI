import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';

test('theme survives navigation and New experiment opens the working lab',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');const toggle=page.getByRole('button',{name:'Toggle color theme',exact:true});await expect(toggle).toBeVisible();
 const wasDark=await toggle.getAttribute('aria-pressed');await toggle.click();await expect(toggle).toHaveAttribute('aria-pressed',wasDark==='true'?'false':'true');
 await page.getByRole('link',{name:'New experiment',exact:true}).click();await expect(page).toHaveURL(/\/chunking$/);await expect(page.getByRole('button',{name:'Toggle color theme',exact:true})).toHaveAttribute('aria-pressed',wasDark==='true'?'false':'true');
 await page.reload();await expect(page.getByRole('button',{name:'Toggle color theme',exact:true})).toHaveAttribute('aria-pressed',wasDark==='true'?'false':'true');
 await page.getByRole('button',{name:'Toggle color theme',exact:true}).click();expect(errors).toEqual([]);
});

test('chunk controls invalidate previews and comparisons after parameter changes',async({page})=>{
 await page.goto('/chunking');await page.getByRole('button',{name:'Preview chunks',exact:true}).click();await expect(page.locator('.chunk-item').first()).toBeVisible();
 await page.getByRole('button',{name:'Compare three strategies',exact:true}).click();await expect(page.locator('.chunk-compare-grid>div')).toHaveCount(3);
 await page.getByLabel('Token budget',{exact:true}).fill('32');await expect(page.locator('.chunk-item')).toHaveCount(0);await expect(page.locator('.chunk-compare-grid')).toHaveCount(0);
 await page.getByRole('button',{name:'Preview chunks',exact:true}).click();await expect(page.locator('.chunk-item').first()).toBeVisible();
 await page.getByRole('combobox',{name:'Strategy',exact:true}).selectOption('sentence');await expect(page.locator('.chunk-item')).toHaveCount(0);
 let release!:()=>void,entered!:()=>void;const gate=new Promise<void>(r=>release=r),started=new Promise<void>(r=>entered=r);
 await page.route('**/api/chunks/preview',async route=>{const response=await route.fetch();entered();await gate;await route.fulfill({response})},{times:1});
 await page.getByRole('button',{name:'Preview chunks',exact:true}).click();await started;await page.getByLabel('Token budget',{exact:true}).fill('40');release();
 await expect(page.getByRole('button',{name:'Preview chunks',exact:true})).toBeEnabled();await expect(page.locator('.chunk-item')).toHaveCount(0);

});

test('dataset controls protect unsaved drafts and clear empty selection',async({page})=>{
 await page.goto('/datasets');await expect(page.getByLabel('Name',{exact:true})).toBeVisible();
 await page.getByLabel('Name',{exact:true}).fill('Unsaved control regression draft');
 page.once('dialog',d=>d.dismiss());await page.getByRole('button',{name:'New dataset',exact:true}).click();await expect(page.getByLabel('Name',{exact:true})).toHaveValue('Unsaved control regression draft');
 page.once('dialog',d=>d.dismiss());await page.getByRole('button',{name:'Load CC0 sample',exact:true}).click();await expect(page.getByLabel('Name',{exact:true})).toHaveValue('Unsaved control regression draft');
 page.once('dialog',d=>d.accept());await page.getByRole('combobox',{name:'Choose dataset',exact:true}).selectOption('');await expect(page.getByRole('heading',{name:'A place for your research questions.',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'New dataset',exact:true}).click();await expect(page.getByLabel('Name',{exact:true})).toHaveValue('New research dataset');
});

test('exports retain the workspace on failure and retry real CSV JSON PDF downloads',async({page})=>{
 await page.goto('/reports');const csv=page.getByRole('link',{name:'Download CSV measurements',exact:true});await expect(csv).toBeVisible();
 await page.route('**/api/benchmarks/runs/*/export?format=csv',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Export temporarily unavailable. Retry this download.'})}));
 await csv.click();await expect(page.getByRole('alert').filter({hasText:'Export temporarily unavailable'})).toBeVisible();await expect(page).toHaveURL(/\/reports$/);
 await page.unroute('**/api/benchmarks/runs/*/export?format=csv');
 for(const [label,signature] of [['Download CSV measurements','dataset_fingerprint'],['Download JSON package','snapshot'],['Download PDF report','%PDF']]){
  const pending=page.waitForEvent('download');await page.getByRole('link',{name:label,exact:true}).click();const download=await pending;const body=await readFile((await download.path())!);expect(body.toString()).toContain(signature);
 }
 await expect(page.locator('.download-error')).toHaveCount(0);
});

test('provider status failures are visible while real retrieval remains usable',async({page,request})=>{
 const indexes=await (await request.get('/api/indexes')).json();const index=indexes.find((i:{status:string})=>i.status==='ready');expect(index).toBeTruthy();
 await page.route('**/api/provider',route=>route.abort('failed'));await page.goto('/playground');await expect(page.getByRole('alert').filter({hasText:'Provider status unavailable'})).toBeVisible();
 await page.getByRole('combobox').first().selectOption(index.id);await page.getByRole('checkbox',{name:'Generate grounded answer',exact:true}).uncheck();await page.getByRole('textbox',{name:'Your research question',exact:true}).fill('Where can students borrow energy meters?');await page.getByRole('button',{name:'Retrieve passages',exact:true}).click();await expect(page.locator('.retrieval-metrics')).toContainText('passages');
});

test('tour launcher works on every viewport with local error recovery and source inspection',async({page,request})=>{
 const docs=await (await request.get('/api/documents')).json();const source=docs.find((d:{name:string})=>d.name==='campus-guide.txt');
 const indexes=await (await request.get('/api/indexes')).json();const index=indexes.find((i:{status:string;config:{document_ids:string[]}})=>i.status==='ready'&&i.config.document_ids.includes(source.id));expect(index).toBeTruthy();
 await page.goto('/embeddings');await page.getByRole('button',{name:'Pipeline tour',exact:false}).click();const dialog=page.getByRole('dialog',{name:'Interactive RAG pipeline tour',exact:true});await expect(dialog).toBeVisible();
 await dialog.getByLabel('Tour document',{exact:true}).selectOption(source.id);await dialog.getByLabel('Tour vector index',{exact:true}).selectOption(index.id);
 await dialog.locator('a[href="#tour-step-3"]').click();await dialog.getByLabel('Tour question',{exact:true}).fill('Where can students borrow energy meters?');
 await page.route('**/api/retrieve',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Retrieval temporarily unavailable; retry.'})}));await dialog.getByRole('button',{name:'Retrieve real passages',exact:true}).click();await expect(dialog.locator('#tour-step-3 [role=alert]')).toContainText('temporarily unavailable');
 await page.unroute('**/api/retrieve');await dialog.getByRole('button',{name:'Retrieve real passages',exact:true}).click();await expect(dialog.locator('.tour-retrieval')).toContainText('energy meters');
 await dialog.getByRole('button',{name:'View original source [1]',exact:true}).click();await expect(page.locator('.source-dialog mark')).toContainText('energy meters');await page.getByRole('button',{name:'Close source preview',exact:true}).click();
 await dialog.locator('a[href="#tour-step-4"]').click();await expect(dialog.getByRole('region',{name:'Actual benchmark recall comparison',exact:true})).toBeVisible();
 expect(await dialog.evaluate(el=>el.scrollTop)).toBeGreaterThan(0);await dialog.getByRole('button',{name:'Close tour',exact:true}).click();
});

test('build index, inspect and rebuild use real persistent jobs',async({page,request},info)=>{
 const uploaded=await request.post('/api/documents',{multipart:{file:{name:`index-controls-${info.project.name}-${Date.now()}.txt`,mimeType:'text/plain',buffer:Buffer.from('The science desk lends telescopes to students. Return the telescope before sunset. Reserve equipment at the science desk.')}}});expect(uploaded.status()).toBe(201);const doc=await uploaded.json();
 await page.goto('/embeddings');await page.getByRole('checkbox',{name:doc.name,exact:true}).check();await page.getByLabel('Word budget',{exact:true}).fill('16');await page.getByLabel('Word overlap',{exact:true}).fill('2');
 const pending=page.waitForResponse(r=>r.url().endsWith('/api/indexes')&&r.request().method()==='POST');await page.getByRole('button',{name:'Build index',exact:true}).click();const response=await pending;expect([200,202]).toContain(response.status());const index=await response.json();
 await expect.poll(async()=> (await (await request.get('/api/indexes/'+index.id)).json()).status,{timeout:90000}).toBe('ready');
 const job=page.locator('.index-job').filter({hasText:index.id.slice(0,8)});await job.getByRole('button',{name:'Inspect',exact:true}).click();await expect(page.getByRole('combobox',{name:'Inspect index',exact:true})).toHaveValue(index.id);await expect(page.locator('#index-inspector')).toBeInViewport();
 const rebuild=page.waitForResponse(r=>r.url().endsWith(`/api/indexes/${index.id}/rebuild`)&&r.request().method()==='POST');await job.getByRole('button',{name:/Rebuild/}).click();expect((await rebuild).ok()).toBe(true);
 await expect.poll(async()=> (await (await request.get('/api/indexes/'+index.id)).json()).status,{timeout:90000}).toBe('ready');
 await page.getByRole('combobox',{name:'Inspect a plotted source passage',exact:true}).selectOption('0');await expect(page.locator('.source-dialog mark')).toContainText('science desk');await page.getByRole('button',{name:'Close source preview',exact:true}).click();
});

test('tour motion follows native scrolling and switches off for reduced motion',async({page,request})=>{
 const settings=await (await request.get('/api/settings')).json();await request.put('/api/settings',{data:{...settings,motion:'system'}});
 await page.emulateMedia({reducedMotion:'no-preference'});await page.goto('/');await page.getByRole('button',{name:'Launch pipeline tour',exact:true}).click();
 const dialog=page.getByRole('dialog',{name:'Interactive RAG pipeline tour',exact:true});const step=dialog.locator('#tour-step-0');await expect(step).toBeVisible();
 const initial=await step.evaluate(e=>getComputedStyle(e).transform);await dialog.hover({position:{x:150,y:300}});await page.mouse.wheel(0,700);
 await expect.poll(()=>dialog.evaluate(e=>e.scrollTop)).toBeGreaterThan(100);await expect.poll(()=>step.evaluate(e=>getComputedStyle(e).transform)).not.toBe(initial);
 await page.emulateMedia({reducedMotion:'reduce'});await expect.poll(()=>step.evaluate(e=>getComputedStyle(e).transform)).toBe('none');
 await page.keyboard.press('Escape');await expect(dialog).toHaveCount(0);await request.put('/api/settings',{data:settings});
});

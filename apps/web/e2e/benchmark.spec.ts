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
 await expect(page.locator('.benchmark-notice')).toContainText('PROVISIONAL');
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

import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {writeFile} from 'node:fs/promises';
test.describe.configure({mode:'serial'});

test('explicit evidence decisions persist, revoke approval after edits, and retain audit history',async({page,request})=>{
 const uploaded=await request.post('/api/documents',{multipart:{file:{name:'review-ui-fixture.txt',mimeType:'text/plain',buffer:Buffer.from('Controlled UI fixture only. The fixture science desk lends telescopes. This is not a human-reviewed research dataset.')}}});expect(uploaded.status()).toBe(201);const doc=await uploaded.json();
 const created=await request.post('/api/datasets',{data:{name:'AUTOMATED REVIEW UI FIXTURE - not research evidence',document_ids:[doc.id],questions:[{id:'ui-q1',question:'What does the fixture desk lend?',reference_answer:'Telescopes.',human_reviewed:false,relevant_spans:[{document_id:doc.id,quote:'The fixture science desk lends telescopes.'}]}]}});expect(created.status()).toBe(201);const d=await created.json();
 await page.goto('/datasets');await page.getByRole('combobox',{name:'Choose dataset',exact:true}).selectOption(d.id);
 await page.getByLabel('Reviewer',{exact:true}).fill('Automated UI fixture - not a real reviewer');await page.getByRole('button',{name:'Save dataset',exact:true}).click();await expect(page.getByRole('status')).toContainText('Dataset saved');
 await page.getByRole('button',{name:'Approve evidence',exact:true}).click();await expect(page.locator('.review-decision .review-label')).toHaveText('reviewed');
 await page.getByLabel('Reference answer',{exact:true}).fill('A telescope (edited fixture reference).');await page.getByRole('button',{name:'Save dataset',exact:true}).click();await expect(page.locator('.review-decision .review-label')).toHaveText('unreviewed');
 await page.locator('.review-history>summary').click();await expect(page.locator('.review-history')).toContainText('edited approval revoked');
 await page.getByRole('button',{name:'Reject evidence',exact:true}).click();await expect(page.locator('.review-decision .review-label')).toHaveText('rejected');
 await page.getByRole('combobox',{name:'Filter review state',exact:true}).selectOption('rejected');await expect(page.locator('.question-row')).toHaveCount(1);
 const bad=await request.post('/api/benchmarks/runs',{data:{dataset_id:d.id,include_unreviewed:true}});expect(bad.status()).toBe(422);
 await page.getByRole('button',{name:'Reopen review',exact:true}).click();await page.getByRole('combobox',{name:'Filter review state',exact:true}).selectOption('all');await expect(page.locator('.review-decision .review-label')).toHaveText('unreviewed');
 const history=await (await request.get(`/api/datasets/${d.id}/history`)).json();expect(history.map((e:{action:string})=>e.action)).toEqual(expect.arrayContaining(['created','approved','edited_approval_revoked','rejected','reopened']));
});

test('optional intro and native-scroll pipeline tour show real chunks, vectors and retrieval',async({page,request},info)=>{
 const docs=await (await request.get('/api/documents')).json();const source=docs.find((d:{name:string})=>d.name==='campus-guide.txt');expect(source).toBeTruthy();
 const indexes=await (await request.get('/api/indexes')).json();const index=indexes.find((i:{status:string;model_id:string;config:{document_ids:string[]}})=>i.status==='ready'&&i.model_id==='minilm'&&i.config.document_ids.includes(source.id));expect(index).toBeTruthy();
 await page.goto('/overview');await page.getByRole('button',{name:'Watch the introduction',exact:false}).click();
 const intro=page.getByRole('dialog',{name:'RAGLab optional introduction',exact:true});await expect(intro).toBeVisible();await expect(intro).toContainText('Conceptual motion only');await intro.getByRole('button',{name:'Next stage',exact:false}).click();await expect(intro).toContainText('Find the boundaries');await intro.getByRole('button',{name:'Skip intro',exact:true}).click();await expect(intro).toHaveCount(0);
 await page.getByRole('button',{name:'Launch pipeline tour',exact:true}).click();const dialog=page.getByRole('dialog',{name:'Interactive RAG pipeline tour',exact:true});await expect(dialog).toBeVisible();
 await dialog.getByRole('combobox',{name:'Tour document',exact:true}).selectOption(source.id);
 await dialog.locator('nav a[href="#tour-step-1"]').click();await expect(dialog.locator('.tour-chunks article').first()).toContainText('chars');
 await dialog.getByRole('combobox',{name:'Tour chunking method',exact:true}).selectOption('semantic');await expect(dialog.locator('.tour-chunks article').first()).toBeVisible();
 await dialog.locator('nav a[href="#tour-step-2"]').click();await dialog.getByRole('combobox',{name:'Tour vector index',exact:true}).selectOption(index.id);await expect(dialog.locator('.actual-vector-chart circle').first()).toBeVisible();
 await dialog.locator('.actual-vector-chart circle').first().focus();await page.keyboard.press('Enter');await expect(dialog.locator('#tour-step-2 > p[role=status]')).toContainText('Passage');
 await dialog.locator('nav a[href="#tour-step-3"]').click();await dialog.getByRole('textbox',{name:'Tour question',exact:true}).fill('Where can students borrow energy meters?');await dialog.getByRole('button',{name:'Retrieve real passages',exact:true}).click();await expect(dialog.locator('.tour-retrieval')).toContainText('energy meters');
 expect(await dialog.evaluate(e=>e.scrollWidth<=e.clientWidth+1)).toBe(true);
 await dialog.screenshot({path:`work/tour-${info.project.name}.png`});
 await page.keyboard.press('Escape');await expect(dialog).toHaveCount(0);await expect(page.getByRole('button',{name:'Launch pipeline tour',exact:true})).toBeFocused();
});

test('provider and storage status stay honest, motion preference and mobile menu work',async({page},info)=>{
 await page.goto('/settings');await page.getByRole('button',{name:'Check provider access',exact:true}).click();await expect(page.locator('.provider-panel')).toContainText('not configured');
 await page.getByRole('button',{name:'Verify index artifacts',exact:true}).click();await expect(page.locator('.environment-grid .success')).toContainText('0 invalid');
 await page.getByRole('combobox',{name:'Motion preference',exact:true}).selectOption('reduced');await page.getByRole('button',{name:'Save preferences',exact:false}).click();await expect(page.getByRole('status').filter({hasText:'Preferences saved'})).toBeVisible();await page.reload();await expect(page.locator('.studio')).toHaveClass(/motion-reduced/);
 if(info.project.name==='mobile-chromium'){
  await page.getByRole('button',{name:'Toggle navigation',exact:true}).click();await expect(page.getByRole('navigation',{name:'Workspace',exact:true})).toBeVisible();await page.getByRole('button',{name:'Close navigation',exact:true}).click();await expect(page.getByRole('navigation',{name:'Workspace',exact:true})).not.toBeVisible();
 }
 await page.goto('/chunking');await page.getByRole('button',{name:'Compare three strategies',exact:true}).click();await expect(page.locator('.chunk-compare-grid>div')).toHaveCount(3);await expect(page.locator('.chunk-compare-grid article').first()).toContainText('chars');
 await page.goto('/leaderboard');await expect(page.getByRole('heading',{name:'Complete-run Pareto frontier',exact:true})).toBeVisible();await page.locator('.ranking-explanation summary').first().click();await expect(page.locator('.ranking-explanation[open]')).toContainText('unique answerable questions');
 await page.goto('/reports');await expect(page.locator('.report-format-grid article')).toHaveCount(3);await expect(page.getByRole('link',{name:'Download PDF report',exact:true})).toBeVisible();
});

test('real repeated runs compare stored measurements and research scope excludes provisional results',async({page,request})=>{
 const history=await (await request.get('/api/benchmarks/runs')).json();const baseline=history.find((r:{status:string;total_configs:number;snapshot:{question_count:number};settings:{evaluation_split:string}})=>r.status==='completed'&&r.total_configs===18&&r.snapshot.question_count===6&&r.settings.evaluation_split==='all');expect(baseline).toBeTruthy();
 const response=await request.post('/api/benchmarks/runs',{data:{...baseline.settings,dataset_id:baseline.dataset_id,name:'Actual browser repeat for paired comparison',include_unreviewed:true,repetitions:1,rebuild_indexes:false}});expect(response.status()).toBe(202);const repeat=await response.json();
 await expect.poll(async()=>{return (await (await request.get('/api/benchmarks/runs/'+repeat.id)).json()).status},{timeout:180000,intervals:[500,1500]}).toBe('completed');
 await page.goto('/benchmarks');await page.getByRole('combobox',{name:'Earlier run',exact:true}).selectOption(baseline.id);await page.getByRole('combobox',{name:'Later run',exact:true}).selectOption(repeat.id);await page.getByRole('button',{name:'Compare stored runs',exact:true}).click();await expect(page.locator('.run-comparison')).toContainText('Comparable question/evidence cohort.');await expect(page.locator('.run-comparison tbody tr')).toHaveCount(18);
 await page.getByRole('combobox',{name:'Research scope',exact:true}).selectOption('reviewed');await expect(page.locator('.run-progress')).toHaveCount(0);await expect(page.getByRole('combobox',{name:'Choose benchmark run',exact:true}).locator('option')).toHaveCount(1);
 await page.getByRole('combobox',{name:'Research scope',exact:true}).selectOption('provisional');await expect(page.locator('.run-progress .benchmark-notice')).toContainText('PROVISIONAL');
});

test('all eleven pages pass automated WCAG A/AA checks and responsive bounds',async({page},info)=>{
 const failures:{route:string;theme:string;violations:unknown[]}[]=[];
 for(const route of ['/overview','/documents','/chunking','/embeddings','/datasets','/benchmarks','/experiments','/leaderboard','/playground','/reports','/settings']){
  await page.goto(route);await expect(page.locator('h1')).toBeVisible();await expect(page.locator('.header-right .status')).toContainText('API connected');await expect(page.locator('.skeleton-grid')).toHaveCount(0);await expect(page.locator('.alert[role=alert]')).toHaveCount(0);
  if(route==='/benchmarks'||route==='/leaderboard'||route==='/reports')await expect(page.locator('.run-progress')).toBeVisible();
  if(route==='/')await expect(page.locator('.research-kpis')).toBeVisible();
  if(['/overview','/documents','/embeddings','/datasets','/reports','/settings'].includes(route))await page.screenshot({path:`work/page-${route==='/'?'overview':route.slice(1)}-${info.project.name}.png`,fullPage:true});
  const r=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();if(r.violations.length)failures.push({route,theme:'light',violations:r.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}))});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),route).toBe(true);
 }
 await page.goto('/overview');await page.getByRole('button',{name:'Toggle color theme',exact:true}).click();await expect(page.locator('.studio')).toHaveClass(/dark/);const dark=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();if(dark.violations.length)failures.push({route:'/',theme:'dark',violations:dark.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}))});
 await writeFile(`work/a11y-${info.project.name}.json`,JSON.stringify(failures,null,2));expect(failures).toEqual([]);
});

test('all eleven dark-theme pages retain accessible contrast and responsive bounds',async({page},info)=>{
 const failures:{route:string;violations:unknown[]}[]=[];
 for(const route of ['/overview','/documents','/chunking','/embeddings','/datasets','/benchmarks','/experiments','/leaderboard','/playground','/reports','/settings']){
  await page.goto(route);await expect(page.locator('.header-right .status')).toContainText('API connected');await expect(page.locator('.skeleton-grid')).toHaveCount(0);
  if(!await page.locator('.studio').evaluate(e=>e.classList.contains('dark')))await page.getByRole('button',{name:'Toggle color theme',exact:true}).click();
  if(route==='/benchmarks'||route==='/leaderboard'||route==='/reports')await expect(page.locator('.run-progress')).toBeVisible();
  const r=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();if(r.violations.length)failures.push({route,violations:r.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}))});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),route).toBe(true);
 }
 await writeFile(`work/a11y-dark-${info.project.name}.json`,JSON.stringify(failures,null,2));expect(failures).toEqual([]);
});

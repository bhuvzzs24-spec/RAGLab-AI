import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('official Halftone Loop canvas animates, stops, replays and enters Overview',async({page})=>{
 await page.emulateMedia({reducedMotion:'no-preference'});const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');await expect(page.getByRole('heading',{name:'RAGLabAI',exact:true})).toBeVisible();
 const frame=page.frameLocator('iframe[title="One Wall, Twelve Plates canvas animation"]');const canvas=frame.locator('canvas');await expect(canvas).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 const cdp=page.viewportSize()!.width<700?await page.context().newCDPSession(page):null;
 if(cdp)await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:150,y:220}]});else await frame.locator('body').hover({position:{x:400,y:280}});
 const image=await canvas.evaluate((c:HTMLCanvasElement)=>c.toDataURL());await expect.poll(()=>canvas.evaluate((c:HTMLCanvasElement)=>c.toDataURL()),{timeout:15000}).not.toBe(image);
 if(cdp){await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await cdp.detach()}
 const frameDocument=await page.locator('iframe').getAttribute('srcdoc');expect(frameDocument).toContain('requestAnimationFrame');expect(await page.locator('iframe').getAttribute('sandbox')).toBe('allow-scripts');
 await page.getByRole('button',{name:'Stop animation',exact:true}).click();await expect(page.locator('iframe')).toHaveCount(0);await expect(page.getByText('Animation stopped · replay starts a new scene',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Replay animation',exact:true}).click();await expect(canvas).toBeVisible();
 await page.getByRole('link',{name:'Enter Workspace',exact:true}).click();await expect(page.locator('.workspace-entry-mask')).toHaveAttribute('data-duration-ms',String((page.viewportSize()?.width??1440)<=700?380:780));await expect(page).toHaveURL(/\/overview$/);await expect(page.locator('h1')).toHaveText('Good research starts here.');await expect(page.locator('iframe')).toHaveCount(0);await expect(page.locator('.workspace-entry-mask')).toHaveCount(0);await page.goBack();await expect(canvas).toBeVisible();expect(errors).toEqual([]);
});

test('reduced-motion landing does not load a canvas and pipeline CTA opens the separate tour',async({page})=>{
 await page.goto('/');await expect(page.getByText('Reduced motion · animated gallery is not loaded',{exact:true})).toBeVisible();await expect(page.locator('iframe')).toHaveCount(0);
 const violations=(await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations;expect(violations).toEqual([]);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 await page.getByRole('link',{name:'Explore Pipeline',exact:true}).click();await expect(page).toHaveURL(/\/overview$/);await expect(page.locator('.workspace-entry-mask')).toHaveCount(0);const tour=page.getByRole('dialog',{name:'Interactive RAG pipeline tour',exact:true});await expect(tour).toBeVisible();await tour.getByRole('button',{name:'Close tour',exact:true}).click();await expect(tour).toHaveCount(0);
});

test('all existing workspace routes and Overview navigation remain direct and error-free',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 for(const route of ['overview','documents','chunking','embeddings','datasets','benchmarks','experiments','leaderboard','playground','reports','settings']){await page.goto('/'+route);await expect(page.locator('h1')).toBeVisible();await expect(page.getByText('API unavailable. Start FastAPI on port 8000.',{exact:true})).toHaveCount(0);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true)}
 if(await page.getByRole('button',{name:'Toggle navigation',exact:true}).isVisible())await page.getByRole('button',{name:'Toggle navigation',exact:true}).click();
 await page.getByRole('link',{name:'Overview',exact:true}).click();await expect(page).toHaveURL(/\/overview$/);await expect(page.locator('h1')).toHaveText('Good research starts here.');expect(errors).toEqual([]);
});

test('API failure stays visible rather than claiming connectivity',async({page})=>{
 await page.route('**/api/health',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Controlled offline test'})}));await page.goto('/');await expect(page.getByRole('status')).toContainText('API unavailable');await page.goto('/overview');await expect(page.getByRole('alert').filter({hasText:'Controlled offline test'})).toContainText('Controlled offline test');await page.unroute('**/api/health');await page.getByRole('button',{name:'Retry connection',exact:true}).click();await expect(page.locator('.alert[role=alert]')).toHaveCount(0);await expect(page.locator('.header-right .status')).toContainText('API connected');
});

test('client view error offers a working full reload recovery',async({page})=>{
 await page.addInitScript(()=>{if(!sessionStorage.getItem('controlled-recovery-test')){sessionStorage.setItem('controlled-recovery-test','1');window.matchMedia=()=>{throw new Error('Controlled client-view error for recovery regression')}}});
 await page.goto('/overview');await expect(page.getByRole('heading',{name:'This view could not load',exact:true})).toBeVisible();await page.getByRole('button',{name:'Reload studio',exact:true}).click();await expect(page.locator('h1')).toHaveText('Good research starts here.');
});


test('Skip Intro enters directly without a transition mask',async({page})=>{await page.emulateMedia({reducedMotion:'no-preference'});await page.goto('/');await page.getByRole('link',{name:'Skip Intro',exact:true}).click();await expect(page).toHaveURL(/\/overview$/);await expect(page.locator('h1')).toHaveText('Good research starts here.');await expect(page.locator('.workspace-entry-mask')).toHaveCount(0)});

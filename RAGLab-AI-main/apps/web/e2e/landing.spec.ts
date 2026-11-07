import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const frameTitle='RAGLAB AI Halftone Loop canvas animation';

test('project wording is drawn inside the real moving Canvas; stop and replay release it',async({page})=>{
 await page.emulateMedia({reducedMotion:'no-preference'});
 await page.addInitScript(()=>{const recorded=window as Window&{__canvasTexts?:string[]};recorded.__canvasTexts=[];const original=CanvasRenderingContext2D.prototype.fillText;CanvasRenderingContext2D.prototype.fillText=function(text,x,y,width){if(!recorded.__canvasTexts!.includes(String(text)))recorded.__canvasTexts!.push(String(text));return width===undefined?original.call(this,text,x,y):original.call(this,text,x,y,width)}});
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('/');
 const frame=page.frameLocator(`iframe[title="${frameTitle}"]`),canvas=frame.locator('canvas');await expect(canvas).toBeVisible();
 const drawn=await canvas.evaluate(()=> (window as Window&{__canvasTexts?:string[]}).__canvasTexts);expect(drawn).toContain('RAGLAB AI');expect(drawn).toContain('RETRIEVE. EVALUATE. OPTIMIZE.');expect(drawn).not.toContain('ONE WALL');expect(drawn).not.toContain('TWELVE PLATES');
 const html=await page.locator(`iframe[title="${frameTitle}"]`).getAttribute('srcdoc');expect(html).not.toMatch(/ONE WALL|TWELVE PLATES|One Wall, Twelve Plates/);expect(html).toContain('#120715');const original=JSON.parse(await readFile('apps/web/components/gallery/official-halftone.json','utf8'));expect(createHash('sha256').update(original.html).digest('hex')).toBe(original.document_sha256);
 const restored=html!.replaceAll('RAGLAB AI — RETRIEVE. EVALUATE. OPTIMIZE.','One Wall, Twelve Plates').replace("s:'RAGLAB AI', top:930,  w:1132, fill:'#E7B0DE'","s:'ONE WALL', top:930,  w:1132, fill:'#c0402c'").replace("s:'RETRIEVE. EVALUATE. OPTIMIZE.'","s:'TWELVE PLATES'").replaceAll('background:#120715','background:#000000').replaceAll('background: #120715','background: #000000').replace("ctx.fillStyle = '#120715';","ctx.fillStyle = '#000000';");expect(restored).toBe(original.html);
 const cdp=page.viewportSize()!.width<700?await page.context().newCDPSession(page):null;
 if(cdp)await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:150,y:200}]});else await frame.locator('body').hover({position:{x:400,y:220}});
 const image=await canvas.evaluate((c:HTMLCanvasElement)=>c.toDataURL());await expect.poll(()=>canvas.evaluate((c:HTMLCanvasElement)=>c.toDataURL())).not.toBe(image);
 if(cdp){await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await cdp.detach()}
 await page.getByRole('button',{name:'Stop animation',exact:true}).click();await expect(canvas).toHaveCount(0);await page.getByRole('button',{name:'Replay animation',exact:true}).click();await expect(canvas).toBeVisible();expect(errors).toEqual([]);
});

test('natural scrolling reveals one persistent workspace and reverses without routing',async({page})=>{
 await page.emulateMedia({reducedMotion:'no-preference'});await page.goto('/');await expect(page.locator('.studio')).toHaveCount(1);await page.locator('.studio').evaluate(el=>el.setAttribute('data-continuity-probe','kept'));
 const initial=await page.locator('#workspace').evaluate(e=>getComputedStyle(e).clipPath);expect(initial).toContain('inset');
 if(page.viewportSize()!.width<=640){const touch=await page.context().newCDPSession(page);await touch.send('Input.synthesizeScrollGesture',{x:100,y:300,yDistance:-Math.round(page.viewportSize()!.height*.45),gestureSourceType:'touch',speed:650});await touch.detach()}else await page.mouse.wheel(0,Math.round(page.viewportSize()!.height*.45));await expect.poll(()=>page.evaluate(()=>scrollY)).toBeGreaterThan(100);await expect.poll(()=>page.locator('#workspace').evaluate(e=>getComputedStyle(e).clipPath)).not.toBe(initial);
 await page.mouse.wheel(0,page.viewportSize()!.height);await expect(page.locator('#workspace .studio')).toBeVisible();await expect.poll(()=>page.locator('#workspace').evaluate(e=>getComputedStyle(e).clipPath)).toBe('none');await expect(page.locator(`iframe[title="${frameTitle}"]`)).toHaveCount(0);
 expect(new URL(page.url()).pathname).toBe('/');await page.mouse.wheel(0,-5000);await expect.poll(()=>page.evaluate(()=>scrollY)).toBe(0);await expect(page.locator(`iframe[title="${frameTitle}"]`)).toBeVisible();await expect(page.locator('.studio')).toHaveAttribute('data-continuity-probe','kept');expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});

test('Enter Workspace scrolls within the page, keeps navigation usable and supports Back',async({page},info)=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));await page.emulateMedia({reducedMotion:'no-preference'});await page.goto('/');await page.getByRole('link',{name:'Enter Workspace',exact:true}).click();await expect(page).toHaveURL(/\/#workspace$/);
 await expect.poll(()=>page.locator('#workspace').evaluate(e=>Math.abs(e.getBoundingClientRect().top))).toBeLessThan(3);await expect(page.locator('#workspace h1')).toHaveText('Good research starts here.');await expect(page.locator('.workspace-entry-mask')).toHaveCount(0);
 if(page.viewportSize()!.width<=640)await page.getByRole('button',{name:'Toggle navigation',exact:true}).click();
 const nav=page.getByRole('navigation',{name:'Workspace',exact:true});await nav.getByRole('link',{name:/Documents/}).click();await expect(page).toHaveURL(/\/documents$/);await expect(page.getByLabel('Upload document',{exact:true})).toBeAttached();
 await page.goBack();expect(new URL(page.url()).pathname).toBe('/');await expect(page.locator('.studio')).toHaveCount(1);await expect(page.locator('.alert[role=alert]')).toHaveCount(0);expect(errors).toEqual([]);
});

test('reduced motion is immediate, blush palette is accessible, and keyboard scrolling works',async({page})=>{
 await page.goto('/');await expect(page.getByText('Reduced motion · animated gallery is not loaded',{exact:true})).toBeVisible();await expect(page.locator('iframe')).toHaveCount(0);
 await page.locator('body').press('PageDown');await expect.poll(()=>page.evaluate(()=>scrollY)).toBeGreaterThan(0);
 await page.getByRole('link',{name:'Skip Intro',exact:true}).click();await expect.poll(()=>page.locator('#workspace').evaluate(e=>Math.abs(e.getBoundingClientRect().top))).toBeLessThan(3);const theme=page.getByRole('button',{name:'Toggle color theme',exact:true});if(await theme.getAttribute('aria-pressed')==='true')await theme.click();await expect(page.locator('.studio')).toHaveCSS('background-color','rgb(247, 240, 245)');await expect(page.locator('.panel').first()).toHaveCSS('background-color','rgb(255, 251, 253)');
 expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});

test('direct routes and the separate Pipeline Tour survive without forcing an intro',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));for(const route of ['overview','documents','chunking','embeddings','datasets','benchmarks','experiments','leaderboard','playground','reports','settings']){await page.goto('/'+route);await expect(page.locator('h1')).toBeVisible();await expect(page.locator('.raglab-landing')).toHaveCount(0);await expect(page.locator('.alert[role=alert]')).toHaveCount(0);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true)}
 await page.goto('/');await page.getByRole('link',{name:'Explore Pipeline',exact:true}).click();const tour=page.getByRole('dialog',{name:'Interactive RAG pipeline tour',exact:true});await expect(tour).toBeVisible();await tour.getByRole('button',{name:'Close tour',exact:true}).click();await expect(page).toHaveURL(/\/overview$/);expect(errors).toEqual([]);
});

test('API failure remains actionable and reconnects in the real embedded workspace',async({page})=>{
 await page.route('**/api/health',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Controlled offline test'})}));await page.goto('/');await page.getByRole('link',{name:'Enter Workspace',exact:true}).click();await expect(page.locator('.studio .alert')).toContainText('Controlled offline test');await page.unroute('**/api/health');await page.getByRole('button',{name:'Retry connection',exact:true}).click();await expect(page.locator('.studio .alert')).toHaveCount(0);await expect(page.locator('.header-right .status')).toContainText('API connected');
});

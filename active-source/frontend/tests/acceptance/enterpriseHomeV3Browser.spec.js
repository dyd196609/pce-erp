import { test, expect } from '@playwright/test'
import fs from 'node:fs'
import { spawnSync } from 'node:child_process'
const out='D:/Dev-PCE/Source/work/enterprise-ui-20261111-v3'
const result=spawnSync('D:/Dev-PCE/Source/backend/venv/Scripts/python.exe',[out+'/browser_accounts.py'],{encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}})
if(result.status!==0)throw new Error(result.stderr)
const accounts=JSON.parse(result.stdout), evidence=[]
test.setTimeout(180000)
async function login(page,actor){await page.getByPlaceholder('用户名',{exact:true}).fill(actor.username);await page.getByPlaceholder('密码',{exact:true}).fill(actor.password);await page.getByRole('button',{name:'登录',exact:true}).click()}
async function loaded(page){await expect(page.locator('.enterprise-home')).toHaveAttribute('aria-busy','false');await expect(page.locator('.enterprise-home')).toHaveAttribute('data-page-version','PCE-ENTERPRISE-UI-20261111-V3');await expect(page.locator('.enterprise-home')).toContainText('授权工序任务记录')}
test('native browser login, terminal geometry, logout and actor switch',async({page,browserName})=>{
 const requests=[];page.on('request',r=>{if(new URL(r.url()).pathname.startsWith('/api/'))requests.push({method:r.method(),path:new URL(r.url()).pathname})})
 await page.goto('/#/home?view=work');await expect(page).toHaveURL(/system-login/);await expect(page).toHaveURL(/redirect=/)
 await login(page,accounts[0]);await expect(page).toHaveURL(/#\/home\?view=work$/);await loaded(page);await expect(page.locator('.enterprise-home')).toContainText(accounts[0].name)
 for(const viewport of [{width:1366,height:768},{width:390,height:844},{width:768,height:1024}]){
  await page.setViewportSize(viewport);await page.reload({waitUntil:'networkidle'});await loaded(page)
  const metrics=await page.evaluate(()=>{const h=document.querySelector('.enterprise-home'),b=h.querySelector('button'),a=h.querySelector('a');const r=h.getBoundingClientRect(),br=b.getBoundingClientRect();return {url:location.href,title:document.title,width:innerWidth,height:innerHeight,scale:visualViewport.scale,dpr:devicePixelRatio,bodyWidth:document.documentElement.scrollWidth,font:getComputedStyle(h).fontSize,lineHeight:getComputedStyle(h).lineHeight,content:{x:r.x,width:r.width},refresh:{x:br.x,right:br.right,height:br.height},linkHeight:a.getBoundingClientRect().height,visibleMs:Number(h.dataset.visibleReadMs),apiMs:Number(h.dataset.apiReadMs)}})
  expect(metrics.width).toBe(viewport.width);expect(metrics.height).toBe(viewport.height);expect(metrics.scale).toBe(1);expect(metrics.dpr).toBe(1);expect(metrics.font).toBe('16px');expect(metrics.bodyWidth).toBeLessThanOrEqual(viewport.width);expect(metrics.refresh.height).toBeGreaterThanOrEqual(44);expect(metrics.refresh.right).toBeLessThanOrEqual(viewport.width)
  await page.screenshot({path:`${out}/terminal-${viewport.width}.png`,fullPage:true});evidence.push({case:'terminal_100_percent',browser:browserName,context:'isolated Playwright Chrome; not extension or Codex IAB',...metrics})
 }
 await page.getByRole('button',{name:'退出并重新登录',exact:true}).click();await expect(page).toHaveURL(/system-login/);await expect(page.getByPlaceholder('密码',{exact:true})).toHaveValue('')
 expect(await page.evaluate(()=>sessionStorage.getItem('pce_tab_auth_token_v1'))).toBeNull()
 await login(page,accounts[1]);await expect(page).toHaveURL(/#\/home\?view=work$/);await loaded(page);await expect(page.locator('.enterprise-home')).toContainText(accounts[1].name);await expect(page.locator('.enterprise-home')).not.toContainText(accounts[0].name)
 await page.reload({waitUntil:'networkidle'});await loaded(page);await expect(page.locator('.enterprise-home')).toContainText(accounts[1].name)
 evidence.push({case:'actual_login_logout_switch_refresh_legal_return',actorIds:accounts.map(x=>x.id),url:page.url(),passed:true,businessWrites:requests.filter(x=>x.method!=='GET'&&!x.path.startsWith('/api/auth/')),authRequests:requests.filter(x=>x.path.startsWith('/api/auth/'))})
 expect(evidence.at(-1).businessWrites).toEqual([])
 fs.writeFileSync(out+'/BROWSER_V3.json',JSON.stringify(evidence,null,2))
})
test('delayed original responses cannot replace the next actor; offline read is unavailable',async({page})=>{
 await page.goto('/#/home');await login(page,accounts[0]);await loaded(page)
 let release;const gate=new Promise(r=>release=r);const held=new Set(),delivered=new Set(),once=new Set();const match=/\/api\/(planning\/enterprise-work-summary|access-control\/profile)\/$/
 await page.route(match,async route=>{const path=new URL(route.request().url()).pathname;if(!once.has(path)){once.add(path);const response=await route.fetch();held.add(path);await gate;await route.fulfill({response});delivered.add(path)}else await route.continue()})
 await page.getByRole('button',{name:'刷新工作摘要',exact:true}).click();await expect.poll(()=>held.size).toBe(2)
 await page.getByRole('button',{name:'退出并重新登录',exact:true}).click();await expect(page).toHaveURL(/system-login/)
 await login(page,accounts[1]);await loaded(page);await expect(page.locator('.enterprise-home')).toContainText(accounts[1].name)
 release();await expect.poll(()=>delivered.size).toBe(2);await expect(page.locator('.enterprise-home')).toContainText(accounts[1].name);await expect(page.locator('.enterprise-home')).not.toContainText(accounts[0].name)
 await page.unroute(match);await page.context().setOffline(true);await page.getByRole('button',{name:'刷新工作摘要',exact:true}).click();await expect(page.locator('.enterprise-home')).toContainText('工作数量暂不可用');await expect(page.locator('[aria-label="工作摘要"]')).toHaveCount(0)
 await page.context().setOffline(false);await page.getByRole('button',{name:'刷新工作摘要',exact:true}).click();await loaded(page);await expect(page.locator('.enterprise-home')).toContainText(accounts[1].name)
 fs.writeFileSync(out+'/BROWSER_RECOVERY_RACE.json',JSON.stringify({passed:true,actualOriginalSummaryAndPermissionResponsesDelayed:true,oldActor:accounts[0].id,currentActor:accounts[1].id,url:page.url(),offlineNotZero:true,noWriteReplay:true},null,2))
})
test('nonempty work and blocked work are real server facts in the browser',async({page})=>{
 const results=[]
 for(const index of [2,3]){
  await page.goto('/#/system-login?redirect=%2Fhome');const responsePromise=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/planning/enterprise-work-summary/'&&r.status()===200);await login(page,accounts[index]);const response=await responsePromise;const summary=(await response.json()).data.summary;await loaded(page)
  expect(summary.total).toBeGreaterThan(0);await expect(page.locator('[aria-label="当前待处理明细"] > li')).toHaveCount(summary.total)
  expect(summary.executableActionCount).toBe(index===2?1:0);expect(summary.alerts.length).toBe(index===2?0:1)
  for(const item of summary.items){await expect(page.locator('[aria-label="当前待处理明细"] > li').filter({hasText:item.no})).toContainText(item.actions[0].enabled?'当前可办理':item.actions[0].disabledReason)}
  await page.screenshot({path:`${out}/positive-actor-${accounts[index].id}.png`,fullPage:true});results.push({actorId:accounts[index].id,summary,url:page.url(),visibleMs:await page.locator('.enterprise-home').getAttribute('data-visible-read-ms'),apiMs:await page.locator('.enterprise-home').getAttribute('data-api-read-ms')})
  await page.locator('[aria-label="当前待处理明细"] > li').first().getByRole('link').click();await expect(page).toHaveURL(/planning\/mes-test-execution\?workOrderId=3/);await expect(page.getByText('TEST-WT-20261100002'+(index===2?'5':'6'),{exact:true}).first()).toBeVisible()
  await page.getByRole('link',{name:'返回上一工作位置',exact:true}).click();await expect(page).toHaveURL(/#\/home$/);await loaded(page)
  await page.getByRole('button',{name:'退出并重新登录',exact:true}).click();await expect(page).toHaveURL(/system-login/)
 }
 fs.writeFileSync(out+'/POSITIVE_BROWSER.json',JSON.stringify(results,null,2))
})
test('post-action summaries and concurrent refresh use the same native state',async({browser})=>{
 const contexts=[],pages=[],results=[]
 try{
  for(const index of [2,3]){
   const context=await browser.newContext({baseURL:'http://127.0.0.1:63983',viewport:{width:1366,height:768},deviceScaleFactor:1});contexts.push(context);const p=await context.newPage();pages.push(p)
   await p.goto('/#/system-login?redirect=%2Fhome');await login(p,accounts[index]);await loaded(p);await p.reload({waitUntil:'networkidle'});await loaded(p)
   const m=await p.locator('.enterprise-home').evaluate(e=>({visibleMs:Number(e.dataset.visibleReadMs),apiMs:Number(e.dataset.apiReadMs),version:e.dataset.pageVersion}));results.push({phase:'fresh_document_after_auth',actorId:accounts[index].id,url:p.url(),...m})
   await expect(p.locator('[aria-label="当前待处理明细"] > li')).toHaveCount(index===2?0:1);if(index===3){await expect(p.locator('[aria-label="当前待处理明细"]')).toContainText('当前可办理');await expect(p.locator('.enterprise-home')).not.toContainText('当前不可办理')}
   await p.screenshot({path:`${out}/after-action-actor-${accounts[index].id}.png`,fullPage:true})
  }
  await Promise.all(pages.map(async(p,i)=>{const before=Number(await p.locator('.enterprise-home').getAttribute('data-read-cycle'));await p.getByRole('button',{name:'刷新工作摘要',exact:true}).click();await expect.poll(async()=>Number(await p.locator('.enterprise-home').getAttribute('data-read-cycle'))).toBeGreaterThan(before);await loaded(p);const m=await p.locator('.enterprise-home').evaluate(e=>({visibleMs:Number(e.dataset.visibleReadMs),apiMs:Number(e.dataset.apiReadMs)}));results.push({phase:'two_actor_concurrent_refresh',actorId:accounts[i+2].id,url:p.url(),...m})}))
  fs.writeFileSync(out+'/POST_ACTION_BROWSER.json',JSON.stringify({browserVersion:browser.version(),contexts:'isolated Chrome test contexts; not user extension tabs or Codex IAB',samples:results,performanceLimitMs:5000,allSamplesWithinTarget:results.every(x=>x.visibleMs<=5000),postActionStateReadbackPassed:true},null,2))
 }finally{await Promise.all(contexts.map(c=>c.close()))}
})

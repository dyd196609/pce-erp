import {test,expect} from '@playwright/test'
import fs from 'node:fs/promises'
import path from 'node:path'
const out=process.env.PCE_UI_EVIDENCE_ROOT
if(!out)throw Error('Explicit isolated evidence root required')
const credentials=JSON.parse(process.env.PCE_NATIVE_AUTH_JSON||'[]')
const save=(name,value)=>fs.writeFile(path.join(out,name),JSON.stringify(value,null,2))
async function login(page){const a=credentials.find(x=>x.id===8);expect(a).toBeTruthy();await page.getByPlaceholder('用户名',{exact:true}).fill(a.username);await page.getByPlaceholder('密码',{exact:true}).fill(a.password);await page.getByRole('button',{name:'登录',exact:true}).click()}
async function home(page){await expect(page.locator('.enterprise-home')).toHaveAttribute('aria-busy','false');await expect(page.locator('.enterprise-home')).toHaveAttribute('data-page-version','PCE-ENTERPRISE-UI-20261111-V3')}
async function summary(page){return page.evaluate(async()=>{const r=await fetch('/api/planning/enterprise-work-summary/',{headers:{Authorization:'Bearer '+sessionStorage.getItem('pce_tab_auth_token_v1')}});if(!r.ok)throw Error('native summary read failed');return (await r.json()).data.summary})}
async function transfer(page){return page.evaluate(async()=>{const r=await fetch('/api/planning/finished-goods-handovers/?transferId=2',{headers:{Authorization:'Bearer '+sessionStorage.getItem('pce_tab_auth_token_v1')}});if(!r.ok)throw Error('native FG read failed');return r.json()})}
const facts=r=>r.data.finishedGoodsFacts

test('new native FG sample: home exact item -> original receive -> fresh browser native readback',async({page,browser,baseURL})=>{
 test.setTimeout(180000)
 await page.goto('/#/home');await expect(page).toHaveURL(/system-login/);await login(page);await home(page)
 const beforeSummary=await summary(page);expect(beforeSummary.total).toBeGreaterThan(0)
 await expect(page.locator('[aria-label="当前待处理明细"] > li')).toHaveCount(beforeSummary.total)
 const pending=beforeSummary.items.find(x=>x.pageUrl.includes('transferId=2'));expect(pending).toBeTruthy();expect(pending.actions.some(x=>x.enabled)).toBe(true)
 await page.locator('[aria-label="当前待处理明细"]').getByRole('link').filter({hasText:pending.no}).click()
 await expect(page).toHaveURL(/planning\/finished-goods-handovers\?transferId=2$/)
 await expect(page.locator('.finished-goods')).toHaveAttribute('data-load-status','loaded',{timeout:60000})
 const beforeResponse=await transfer(page),before=facts(beforeResponse);expect(before.selectedTransfer.statusCode).toBe('in_transit');expect(Number(before.selectedTransfer.quantity)).toBe(1);expect(before.selectedTransfer.conversionBasis.productUomId).toBe(13);expect(before.selectedTransfer.warehouseReceipt).toBeFalsy();expect(before.availableActions.receive.enabled).toBe(true)
 await save('FG_BROWSER_BEFORE.json',{summary:beforeSummary,response:beforeResponse})
 await page.screenshot({path:path.join(out,'fg-browser-before.png'),fullPage:true})
 await page.getByLabel('成品操作',{exact:true}).selectOption('receive')
 await page.getByLabel('成品办理说明',{exact:true}).fill('SIMULATED_FOR_TEST：独立副本新样本；Codex按原服务验证仓管实际接收及入库，不冒称人工验收。')
 const posted=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/planning/finished-goods-handovers/2/receive/'&&r.request().method()==='POST')
 await page.getByRole('button',{name:'确认整批成品接收并测试入库',exact:true}).click()
 const response=await posted,postBody=await response.json();await save('FG_BROWSER_WRITE.json',{httpStatus:response.status(),request:response.request().postDataJSON(),response:postBody});expect(response.ok(),JSON.stringify(postBody)).toBe(true)
 await expect(page.locator('.finished-goods')).toHaveAttribute('data-load-status','loaded',{timeout:60000});await expect(page.locator('.finished-goods')).toContainText('原请求已独立核实',{timeout:60000})
 const afterResponse=await transfer(page),after=facts(afterResponse);expect(after.selectedTransfer.statusCode).toBe('received');expect(after.selectedTransfer.warehouseReceipt.inboundId).toBeTruthy();expect(after.availableActions.receive.enabled).toBe(false)
 await save('FG_BROWSER_AFTER.json',afterResponse);await page.screenshot({path:path.join(out,'fg-browser-after.png'),fullPage:true})
 const freshContext=await browser.newContext({baseURL,viewport:{width:1366,height:768}})
 try{const fresh=await freshContext.newPage();await fresh.goto('/#/home');await login(fresh);await home(fresh);const afterSummary=await summary(fresh);expect(afterSummary.items.some(x=>x.pageUrl.includes('transferId=2'))).toBe(false);expect(afterSummary.total).toBe(beforeSummary.total-1)
 await fresh.goto('/#/planning/finished-goods-handovers?transferId=2');await expect(fresh.locator('.finished-goods')).toHaveAttribute('data-load-status','loaded',{timeout:60000});const reread=await transfer(fresh);expect(facts(reread).selectedTransfer.warehouseReceipt).toEqual(after.selectedTransfer.warehouseReceipt);expect(facts(reread).selectedTransfer.statusCode).toBe('received')
 await save('FG_BROWSER_FRESH_READBACK.json',{freshBrowserContext:true,originalAuthentication:true,serverReadback:true,summaryBefore:beforeSummary,summaryAfter:afterSummary,readback:reread,uiVersion:'PCE-ENTERPRISE-UI-20261111-V3',context:'isolated Playwright Chrome, not user IAB or extension',baseURL})
 }finally{await freshContext.close()}
})

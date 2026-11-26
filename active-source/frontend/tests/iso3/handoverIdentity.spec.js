import {test,expect} from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
test('original handover business numbers retain their actual typed server identities',async({page})=>{
 const response=JSON.parse(fs.readFileSync(path.resolve(process.cwd(),'../../NATIVE_DETAIL_8.json'),'utf8'))
 const facts=response.data.operationHandoverFacts,header=facts.selectedHandover
 expect(header.workOrderNo).toBe('WO202611000003');expect(header.workOrderId).toBe(6);expect(header.taskId).toBe(41)
 await page.setViewportSize({width:390,height:844})
 await page.addInitScript(actor=>sessionStorage.setItem('pce_current_identity_v1',JSON.stringify(actor)),facts.currentActorEvidence)
 await page.route(url=>url.pathname.startsWith('/api/'),r=>{expect(r.request().method()).toBe('GET');return r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(response)})})
 await page.goto('/tests/three-page-navigation.html?mode=handover&handoverId=8')
 await expect(page.locator('[data-load-status="loaded"]').first()).toBeVisible()
 await expect(page.getByRole('region',{name:'工序交接事实与定位'})).toContainText(header.workOrderNo)
 const next=page.locator('[data-acceptance-id="compact-flow-navigation"]').getByRole('link',{name:'独立审核完工',exact:true})
 await expect(next).toHaveAttribute('href',`/planning/operation-completions?taskId=${header.taskId}&workOrderId=${header.workOrderId}`)
 const sizes=await page.evaluate(()=>({innerWidth,scrollWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth}))
 expect(sizes.innerWidth).toBe(390);expect(sizes.scrollWidth).toBeLessThanOrEqual(sizes.clientWidth)
 fs.mkdirSync('test-results/iso3-ui-r3',{recursive:true});fs.writeFileSync('test-results/iso3-ui-r3/identity.json',JSON.stringify({headerId:header.id,taskId:header.taskId,workOrderId:header.workOrderId,workOrderNo:header.workOrderNo,sizes,scope:'Native response replay; not password authentication or physical phone acceptance'},null,2))
 await page.screenshot({path:'test-results/iso3-ui-r3/handover390.png',fullPage:true})
})

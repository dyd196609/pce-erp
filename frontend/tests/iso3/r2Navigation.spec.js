import {test,expect} from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
const root=path.resolve(process.cwd(),'../..')
for(const [index,mode] of ['report','handover','completion'].entries())test(`Integrated R2 ${mode} at 390`,async({page})=>{
 const response=JSON.parse(fs.readFileSync(path.join(root,`NATIVE_READ_${index}.json`),'utf8'))
 const facts=response.data.operationReportFacts||response.data.operationHandoverFacts||response.data.operationCompletionFacts
 await page.setViewportSize({width:390,height:844})
 await page.addInitScript(actor=>sessionStorage.setItem('pce_current_identity_v1',JSON.stringify(actor)),facts.currentActorEvidence)
 await page.route(url=>url.pathname.startsWith('/api/'),route=>{
  expect(route.request().method()).toBe('GET')
  return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(response)})
 })
 await page.goto('/tests/three-page-navigation.html?mode='+mode)
 await expect(page.locator('[data-load-status="loaded"]').first()).toBeVisible()
 const nav=page.locator('[data-acceptance-id="compact-flow-navigation"]')
 await expect(nav).toBeVisible();await expect(nav.locator('a')).toHaveCount(2)
 const guide=page.locator('[data-acceptance-id="compact-page-guide"]')
 for(let n=0;n<2;n++){await guide.locator('summary').click();await expect(nav).toBeVisible()}
 const dimensions=await page.evaluate(()=>({innerWidth,clientWidth:document.documentElement.clientWidth,scrollWidth:document.documentElement.scrollWidth,loaded:document.querySelector('[data-load-status]')?.getAttribute('data-load-status')}))
 expect(dimensions.innerWidth).toBe(390);expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth)
 fs.mkdirSync('test-results/iso3-r2',{recursive:true})
 fs.writeFileSync(`test-results/iso3-r2/${mode}.json`,JSON.stringify({dimensions,scope:'Actual wrapper plus read-only native response replay, no password authentication, business writes or physical-phone PASS'},null,2))
 await page.screenshot({path:`test-results/iso3-r2/${mode}.png`,fullPage:true})
})

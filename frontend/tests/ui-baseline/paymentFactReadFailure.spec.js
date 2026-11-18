import {test,expect} from '@playwright/test'
import {listPceProcessNavigationModules} from '../../src/meta/runtime/pceBusinessModuleRegistry.js'
for(const [route,api] of [['/finance/payment-order-drafts','/api/finance/payment-order-drafts/'],['/finance/formal-payment-orders','/api/finance/formal-payment-orders/']]) {
  test(`${route}: unauthenticated failure is visible without invented counts`,async({page})=>{
    const errors=[];page.on('pageerror',e=>errors.push(e.message))
    const response=page.waitForResponse(r=>new URL(r.url()).pathname===api)
    await page.goto('/#'+route,{waitUntil:'networkidle'})
    expect((await response).status()).toBe(401)
    await expect(page.getByText('服务端资料读取失败，数量未知；请检查登录身份后刷新。',{exact:true})).toBeVisible()
    expect(errors).toEqual([])
  })
}
for(const id of ['payment-record-review','payment-voucher-review']) {
  test(`${id}: existing result options render without undefined bindings`,async({page})=>{
    const module=listPceProcessNavigationModules().find(x=>x.moduleId===id)
    expect(module).toBeTruthy()
    const warnings=[],errors=[]
    page.on('console',msg=>{if(msg.type()==='warning'&&msg.text().includes('not defined'))warnings.push(msg.text().slice(0,180))})
    page.on('pageerror',e=>errors.push(e.message))
    await page.goto('/#'+module.route,{waitUntil:'networkidle'})
    await expect(page.locator('[data-acceptance-id="page-business-title"]').first()).toHaveText(module.canonicalName)
    await page.getByRole('button',{name:'展开高级筛选',exact:true}).first().click()
    expect(await page.locator('.pce-result-filter-select').count()).toBeGreaterThanOrEqual(5)
    expect(warnings).toEqual([])
    expect(errors).toEqual([])
  })
}

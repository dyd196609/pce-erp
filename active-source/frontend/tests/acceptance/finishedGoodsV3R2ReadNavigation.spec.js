import {test,expect} from '@playwright/test'
import fs from 'node:fs/promises'
import path from 'node:path'
const out=process.env.PCE_UI_EVIDENCE_ROOT
const account=JSON.parse(process.env.PCE_NATIVE_AUTH_JSON||'[]').find(x=>x.id===8)
const target='/planning/finished-goods-handovers'
const wait=async page=>{await expect(page.locator('.finished-goods')).toHaveAttribute('data-load-status','loaded',{timeout:60000});await expect(page.locator('.finished-goods')).toHaveAttribute('data-fg-view-version','PCE-ENTERPRISE-UI-20261111-V3-R2')}
async function login(page){await page.getByPlaceholder('用户名',{exact:true}).fill(account.username);await page.getByPlaceholder('密码',{exact:true}).fill(account.password);await page.getByRole('button',{name:'登录',exact:true}).click()}
async function assertNew(page){await wait(page);await expect(page.getByTestId('fg-transfer-no')).toHaveText('TFG202611110001');await expect(page.getByTestId('fg-inbound-no')).toHaveText('TFIN202611110001');await expect(page.getByLabel('测试生产工单',{exact:true})).toHaveValue('3')}
test('ordinary warehouse: direct/login, typed locator, original directory, refresh and old/new results without writes',async({page,baseURL})=>{
 test.setTimeout(240000)
 const requests=[],reads=[];page.on('request',r=>{const u=new URL(r.url());if(u.pathname.startsWith('/api/'))requests.push({method:r.method(),path:u.pathname,query:u.search})})
 await page.goto('/#'+target+'?transferId=2');await expect(page).toHaveURL(/system-login.*redirect=/);await login(page);await expect(page).toHaveURL(/finished-goods-handovers\?transferId=2$/);await assertNew(page)
 await page.getByRole('link',{name:'本轮终点：读取原成品及入库回执',exact:true}).click();await expect(page).toHaveURL(/transferId=2&workOrderId=3$/);await assertNew(page)
 await page.reload({waitUntil:'networkidle'});await assertNew(page)
 await page.getByText('查看原入库单、库存流水及余额（只读）',{exact:true}).click();await expect(page.getByTestId('fg-inventory-transaction')).toContainText('TIT202611110001');await expect(page.getByTestId('fg-inventory-balance')).toContainText('1 套')
 await page.getByRole('button',{name:'重新读取入库单、流水及余额',exact:true}).click();await assertNew(page)
 await page.screenshot({path:path.join(out,'warehouse-new-result.png'),fullPage:true})
 await page.getByLabel('测试生产工单',{exact:true}).selectOption('2');await expect(page).toHaveURL(/workOrderId=2$/);await wait(page);await expect(page.getByTestId('fg-inbound-no')).toHaveCount(0);await expect(page.getByRole('row').filter({hasText:'TFG202611090001'})).toBeVisible()
 await page.getByRole('row').filter({hasText:'TFG202611090001'}).getByRole('button',{name:'读取原单',exact:true}).click();await wait(page);await expect(page.getByTestId('fg-transfer-no')).toHaveText('TFG202611090001');await expect(page.getByLabel('测试生产工单',{exact:true})).toHaveValue('2');const oldInbound=await page.getByTestId('fg-inbound-no').textContent();expect(oldInbound).not.toBe('TFIN202611110001')
 await page.getByRole('link',{name:'查看本人全部成品交接记录',exact:true}).click();await wait(page);await expect(page.getByRole('row').filter({hasText:'TFG202611110001'})).toBeVisible();await expect(page.getByRole('row').filter({hasText:'TFG202611090001'})).toBeVisible()
 await page.getByRole('link',{name:'本人首页',exact:true}).first().click();await expect(page.locator('.enterprise-home')).toHaveAttribute('aria-busy','false');await page.getByRole('link',{name:'成品交接及入库历史',exact:true}).click();await wait(page)
 await page.getByRole('row').filter({hasText:'TFG202611110001'}).getByRole('button',{name:'读取原单',exact:true}).click();await assertNew(page)
 const response=await page.evaluate(async()=>{const r=await fetch('/api/planning/finished-goods-handovers/?transferId=2',{headers:{Authorization:'Bearer '+sessionStorage.getItem('pce_tab_auth_token_v1')}});return {status:r.status,body:await r.json()}});expect(response.status).toBe(200);reads.push(response.body.data.finishedGoodsFacts.selectedTransfer)
 const businessWrites=requests.filter(x=>x.method!=='GET'&&!x.path.startsWith('/api/auth/'));expect(businessWrites).toEqual([])
 await fs.writeFile(path.join(out,'BROWSER_READ_NAVIGATION.json'),JSON.stringify({passed:true,actor:'pce_warehouse_r11',baseURL,actualBrowser:'isolated Playwright Chrome; user Chrome extension verified separately',directThenRealLogin:true,queryPreserved:true,selectedWorkOrderMatchesTransfer:true,refreshSameObject:true,oldInbound,normalChinesePath:'本人首页 → 成品交接及入库历史 → 新成品交接单所在行 → 读取原单',businessWrites,requests,reads},null,2))
})

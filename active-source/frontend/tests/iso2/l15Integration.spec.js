import {test,expect} from '@playwright/test'
import fs from 'node:fs'
import names from '../../src/meta/runtime/verifiedBookmarkNames.json' with {type:'json'}
for(const width of [1440,390])test(`L1.5 integrated at ${width}`,async({page})=>{
 await page.setViewportSize({width,height:1000})
 await page.addInitScript(accounts=>localStorage.setItem('pce_account_shortcut_names_v1',JSON.stringify(accounts.map(username=>({username,label:username})))),Object.keys(names))
 await page.goto('/#/system-login',{waitUntil:'networkidle'})
 await expect(page.locator('.login-environment')).toContainText('L1.5')
 await expect(page.locator('.capabilities article')).toHaveCount(7)
 expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
 const username=page.locator('input[autocomplete="username"]')
 const password=page.locator('input[autocomplete="current-password"]')
 const results=[]
 for(const [account,name] of Object.entries(names)){
  await page.locator('.account-picker summary').click()
  const option=page.locator('.account-options button').filter({hasText:account})
  await expect(option).toContainText(name)
  await option.click();await expect(username).toHaveValue(account);await expect(password).toHaveValue('')
  results.push({account,label:name,submitted:false})
 }
 const positions=await page.locator('.capabilities article').evaluateAll(nodes=>nodes.map(n=>({x:n.getBoundingClientRect().x,y:n.getBoundingClientRect().y})))
 if(width===1440)expect(Math.abs(positions[6].x-positions[0].x)).toBeLessThanOrEqual(1)
 fs.mkdirSync('test-results/iso2-l15',{recursive:true})
 fs.writeFileSync(`test-results/iso2-l15/${width}.json`,JSON.stringify({width,results,positions,fixture:'Isolated account bookmarks seeded from preserved verified-name mapping; no password or authorization fixture',authentication:'Existing scoped user PASS reused; no credentials submitted by this test'},null,2))
 await page.screenshot({path:`test-results/iso2-l15/${width}.png`,fullPage:true})
})

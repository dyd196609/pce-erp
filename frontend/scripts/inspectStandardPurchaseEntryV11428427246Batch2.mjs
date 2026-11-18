import { chromium } from 'playwright'
import { cpSync, mkdirSync, mkdtempSync } from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'

const route = process.argv[2] || '/scm/purchase-order/create'
const cloneLocalStorage = process.argv.includes('--clone-local-storage')
const launchOptions = {
  headless: true,
  executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
}
let browser
let context
if (cloneLocalStorage) {
  const profile = mkdtempSync(join(tmpdir(), 'pce-b2-chrome-'))
  const target = join(profile, 'Default', 'Local Storage', 'leveldb')
  mkdirSync(target, { recursive: true })
  cpSync('C:\\Users\\DAODA\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Local Storage\\leveldb', target, {
    recursive: true, filter: source => !source.endsWith('LOCK'),
  })
  context = await chromium.launchPersistentContext(profile, { ...launchOptions,
    viewport: { width: 1600, height: 1000 }, args: ['--profile-directory=Default'] })
} else {
  browser = await chromium.launch(launchOptions)
  context = await browser.newContext({ viewport: { width: 1600, height: 1000 } })
}
const page = context.pages()[0] || await context.newPage()
try {
  await page.goto('http://localhost:5173/#/login', { waitUntil: 'networkidle' })
  await page.locator('input[autocomplete="username"]').fill('admin')
  await page.locator('input[autocomplete="current-password"]').fill('admin123')
  await page.getByRole('button', { name: /Enter|登录|进入/ }).click()
  await page.waitForTimeout(1500)
  await page.goto(`http://localhost:5173/#${route}`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1500)
  const storage = await page.evaluate(() => Object.fromEntries(
    Object.keys(localStorage).filter(key => /purchase|gate|recommend|approval/i.test(key))
      .map(key => [key, localStorage.getItem(key)]),
  ))
  console.log(JSON.stringify({ url: page.url(), title: await page.title(),
    body: (await page.locator('body').innerText()).slice(0, 8000), storage }, null, 2))
} finally {
  await context.close()
  if (browser) await browser.close()
}

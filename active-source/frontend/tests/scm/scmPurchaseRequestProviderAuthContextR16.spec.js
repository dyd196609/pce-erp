import { expect, test } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const referenceTypes = ['employees', 'organization-tree', 'projects', 'cost-centers', 'expense-categories', 'budget-categories', 'materials', 'suppliers']

test('R16 provider requests inherit JWT and same-origin session authentication context', async ({ page }) => {
  const statuses = new Map()
  const requestContext = new Map()
  let factsStatus = 0

  page.on('response', async (response) => {
    if (response.url().includes('/scm-page-facts/purchase-request/')) factsStatus = response.status()
    const match = response.url().match(/purchase-request-references\/([^/?]+)\//)
    if (!match) return
    const headers = await response.request().allHeaders()
    statuses.set(match[1], response.status())
    requestContext.set(match[1], {
      authorizationPresent: Boolean(headers.authorization),
      cookiePresent: Boolean(headers.cookie),
      origin: headers.origin || new URL(response.url()).origin,
      csrfHeaderPresent: Boolean(headers['x-csrftoken']),
    })
  })

  await page.goto('/?r16-login=1#/system-login')
  await page.getByRole('textbox', { name: '用户名' }).fill(process.env.PCE_TEST_USERNAME || 'admin')
  await page.getByRole('textbox', { name: '密码' }).fill(process.env.PCE_TEST_PASSWORD || 'admin123')
  const loginResponsePromise = page.waitForResponse((response) => response.url().endsWith('/api/auth/login/'))
  await page.getByRole('button', { name: '登录' }).click()
  expect((await loginResponsePromise).status()).toBe(200)
  await expect(page).not.toHaveURL(/system-login/)

  await page.goto('/?r16-jwt=1#/scm/purchase-request')
  await expect.poll(() => statuses.size).toBe(referenceTypes.length)
  for (const type of referenceTypes) expect(statuses.get(type), `${type} JWT request`).toBe(200)
  expect([...requestContext.values()].every((item) => item.authorizationPresent)).toBe(true)
  expect([...requestContext.values()].every((item) => item.cookiePresent)).toBe(true)

  statuses.clear()
  requestContext.clear()
  await page.evaluate(() => localStorage.removeItem('token'))
  await page.goto('/?r16-session=1#/scm/purchase-request')
  await expect.poll(() => statuses.size).toBe(referenceTypes.length)
  for (const type of referenceTypes) expect(statuses.get(type), `${type} session request`).toBe(200)
  expect([...requestContext.values()].every((item) => !item.authorizationPresent)).toBe(true)
  expect([...requestContext.values()].every((item) => item.cookiePresent)).toBe(true)
  expect(factsStatus).toBe(200)

  await page.getByRole('button', { name: '新增采购申请' }).click()
  const dialog = page.getByRole('dialog', { name: '新增采购申请' })
  const field = (label) => dialog.locator('.el-form-item').filter({ has: page.locator(`label:text-is("${label}")`) }).first()
  await field('请购人').locator('.el-select').click()
  await expect(page.getByRole('option', { name: /EMP006 \/ 周丽 \/ 采购部/ })).toBeVisible()
  await page.getByRole('option', { name: /EMP006 \/ 周丽 \/ 采购部/ }).click()
  await expect(field('请购部门')).toContainText('采购部')
  await field('需求部门').locator('.el-select').click()
  await expect(page.getByRole('treeitem').first()).toBeVisible()
  await page.keyboard.press('Escape')
  await field('项目').locator('.el-select').click()
  await expect(page.getByRole('option', { name: /PRJ-PCE-ERP-2026/ })).toBeVisible()
  await page.keyboard.press('Escape')
  await field('成本中心').locator('.el-select').click()
  await expect(page.getByRole('option', { name: /CC-PROCUREMENT/ })).toBeVisible()
  await page.keyboard.press('Escape')
  await field('物料').locator('.el-select').click()
  await expect(page.getByRole('option')).toHaveCount(80)
  await expect(page.getByRole('option', { name: /MT001/ })).toBeVisible()
  await page.keyboard.press('Escape')
  await field('建议供应商').locator('.el-select').click()
  await expect(page.getByRole('option', { name: /SUP001/ })).toBeVisible()

  const evidenceDir = resolve('test-results', 'scm-purchase-request-v1142142-r16')
  mkdirSync(evidenceDir, { recursive: true })
  writeFileSync(resolve(evidenceDir, 'browser-provider-auth-context-evidence.json'), `${JSON.stringify({
    version: 'V1.14.2.8.4.14.2-R16',
    result: 'PASS',
    factsHttpStatus: factsStatus,
    providerHttpStatus: Object.fromEntries(statuses),
    sessionContext: Object.fromEntries(requestContext),
    jwtContextVerified: true,
    sessionFallbackVerified: true,
    csrfRequiredForGet: false,
    selectorsVerified: ['employee', 'department-tree', 'project', 'cost-center', 'materials-80', 'supplier'],
    productionUserDataWritten: false,
    nextPageAllowed: false,
  }, null, 2)}\n`, 'utf8')
})

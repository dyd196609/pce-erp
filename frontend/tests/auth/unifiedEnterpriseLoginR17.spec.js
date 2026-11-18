import { expect, test } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const referenceTypes = ['employees', 'organization-tree', 'projects', 'cost-centers', 'expense-categories', 'budget-categories', 'materials', 'suppliers']

test('R17 ordinary ProfitOS login establishes backend JWT and session before dashboard', async ({ page }) => {
  const providerStatuses = new Map()
  const providerAuthContext = new Map()
  let loginStatus = 0
  page.on('response', async (response) => {
    if (response.url().endsWith('/api/auth/login/')) loginStatus = response.status()
    const match = response.url().match(/purchase-request-references\/([^/?]+)\//)
    if (!match) return
    const headers = await response.request().allHeaders()
    providerStatuses.set(match[1], response.status())
    providerAuthContext.set(match[1], {
      authorizationPresent: Boolean(headers.authorization),
      cookiePresent: Boolean(headers.cookie),
    })
  })

  await page.goto('/?r17=1#/login')
  await expect(page.getByText('Demo Company').first()).toBeVisible()
  await expect(page.getByText('Role', { exact: true })).toBeVisible()
  await expect(page.getByText('Plan', { exact: true })).toBeVisible()
  await page.getByPlaceholder('Enterprise username').fill(process.env.PCE_TEST_USERNAME || 'admin')
  await page.getByPlaceholder('Enterprise password').fill(process.env.PCE_TEST_PASSWORD || 'admin123')
  await page.getByRole('button', { name: 'Enter ProfitOS' }).click()
  await expect(page).toHaveURL(/#\/dashboard$/)
  expect(loginStatus).toBe(200)

  await page.goto('/?r17=2#/scm/purchase-request')
  await expect(page.getByRole('button', { name: '新增采购申请' })).toBeVisible()
  await expect.poll(() => providerStatuses.size).toBe(referenceTypes.length)
  for (const type of referenceTypes) expect(providerStatuses.get(type), `${type} HTTP status`).toBe(200)
  expect([...providerAuthContext.values()].every((context) => context.authorizationPresent && context.cookiePresent)).toBe(true)

  await page.getByRole('button', { name: '新增采购申请' }).click()
  const dialog = page.getByRole('dialog', { name: '新增采购申请' })
  const field = (label) => dialog.locator('.el-form-item').filter({ has: page.locator(`label:text-is("${label}")`) }).first()
  await field('请购人').locator('.el-select').click()
  await expect(page.getByRole('option', { name: /EMP006 \/ 周丽 \/ 采购部/ })).toBeVisible()
  await page.keyboard.press('Escape')
  await field('物料').locator('.el-select').click()
  await expect(page.getByRole('option')).toHaveCount(80)
  await page.keyboard.press('Escape')
  await field('建议供应商').locator('.el-select').click()
  await expect(page.getByRole('option', { name: /SUP001/ })).toBeVisible()

  const outputDir = resolve('test-results', 'unified-enterprise-login-r17')
  mkdirSync(outputDir, { recursive: true })
  writeFileSync(resolve(outputDir, 'browser-evidence.json'), `${JSON.stringify({
    version: 'V1.14.2.8.4.15-R17',
    result: 'PASS',
    entryUrl: '/login',
    targetUrl: '/dashboard',
    loginHttpStatus: loginStatus,
    providerHttpStatus: Object.fromEntries(providerStatuses),
    providerAuthContext: Object.fromEntries(providerAuthContext),
    commercialFieldsPreserved: ['Demo Company', 'Role', 'Plan'],
    productionUserDataWritten: false,
    nextPageAllowed: false,
  }, null, 2)}\n`, 'utf8')
})

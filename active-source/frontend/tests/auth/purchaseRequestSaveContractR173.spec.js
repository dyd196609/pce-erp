import { expect, test } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

test('R17.3 captures the browser 400 contract and verifies only PR202608010012', async ({ page, context }) => {
  await context.clearCookies()
  let loginToken = ''
  page.on('response', async (response) => {
    if (!response.url().endsWith('/api/auth/login/')) return
    const body = await response.json().catch(() => ({}))
    loginToken = body.token || ''
  })
  await page.goto('/?r173=login#/login')
  await page.getByPlaceholder('Enterprise username').fill(process.env.PCE_TEST_USERNAME || 'admin')
  await page.getByPlaceholder('Enterprise password').fill(process.env.PCE_TEST_PASSWORD || 'admin123')
  await page.getByRole('button', { name: 'Enter ProfitOS' }).click()
  await expect(page).toHaveURL(/#\/dashboard$/)
  expect(loginToken).not.toBe('')

  const payload = {
    requestDate: '2026-08-01',
    requestType: 'production',
    requesterEmployeeId: 6,
    departmentId: 8,
    usageDepartmentId: 8,
    purchaseDepartmentId: 8,
    projectId: 1,
    costCenterId: 1,
    expenseCategoryId: 1,
    budgetCategoryId: 1,
    sourceType: 'ManualRequest',
    requiredDate: '2026-08-10',
    applicationReason: 'R17.3采购申请保存字段契约验收',
    purchasePurpose: '生产物料采购',
    technicalDescription: '',
    deliveryRequirements: '按需求日期交付',
    noteDescription: 'V1.14.2.8.4.15-R17.3',
    items: [{
      materialId: 3,
      quantity: '1',
      requiredDate: '2026-08-10',
      demandReason: '生产需求',
      suggestedSupplierId: 1,
      technicalRequirements: '',
      brandRequirements: '',
      substituteRequirement: '',
      purchaseRemark: '',
      remark: 'R17.3 contract evidence',
    }],
  }

  const invalidPayload = { ...payload, departmentId: 16 }
  const invalidResult = await page.evaluate(async ({ body, token }) => {
    const response = await fetch('/api/procurement/purchase-requests/', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(body),
    })
    const responseBody = await response.json()
    return { status: response.status, responseBody }
  }, { body: invalidPayload, token: loginToken })

  const finalResult = await page.evaluate(async (token) => {
    const response = await fetch('/api/procurement/purchase-requests/?search=PR202608010012', {
      credentials: 'include',
      headers: { Authorization: `Bearer ${token}` },
    })
    return { status: response.status, responseBody: await response.json() }
  }, loginToken)

  const outputDir = resolve('test-results', 'purchase-request-save-contract-r17-3')
  mkdirSync(outputDir, { recursive: true })
  writeFileSync(resolve(outputDir, 'http-contract-evidence.json'), `${JSON.stringify({
    version: 'V1.14.2.8.4.15-R17.3',
    request: { method: 'POST', url: '/api/procurement/purchase-requests/', payload: invalidPayload },
    response: invalidResult,
    correctedPayload: payload,
    finalVerification: finalResult,
  }, null, 2)}\n`, 'utf8')

  expect(invalidResult.status).toBe(400)
  expect(invalidResult.responseBody.departmentId).toBeTruthy()
  expect(finalResult.status).toBe(200)
  expect(finalResult.responseBody.results).toHaveLength(1)
  expect(finalResult.responseBody.results[0].requestNo).toBe('PR202608010012')
  expect(finalResult.responseBody.results[0].status).toBe('draft')
  expect(finalResult.responseBody.results[0].inquiryEligibility?.inquiryObjectCreated).toBe(false)
})

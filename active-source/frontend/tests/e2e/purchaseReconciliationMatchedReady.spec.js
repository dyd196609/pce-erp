import fs from 'node:fs'
import path from 'node:path'
import { test, expect } from '@playwright/test'

const reportPath = path.resolve('test-results/purchase-payment-golden-flow/purchase-reconciliation-page-acceptance.json')

test('normal purchase reconciliation page uses only server read model and only matched can navigate', async ({ page }) => {
  const apiReads = []
  const apiWrites = []
  await page.route('**/api/scm/purchase-reconciliations/**', async (route) => {
    const request = route.request()
    if (request.method() !== 'GET') apiWrites.push({ method: request.method(), url: request.url() })
    else apiReads.push(request.url())
    if (request.url().endsWith('/api/scm/purchase-reconciliations/')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          result: 'passed',
          data: {
            count: 2,
            results: [
              {
                id: 42, reconciliationNo: 'PRC20260700000042', sourceSettlementNo: 'PCE-REG-185',
                sourcePayableCheckNo: 'PAYABLE-185', purchaseOrderNo: 'PO-185', supplierName: '金丝雀供应商',
                settlementAmount: '100.00', status: 'matched', differenceCount: 0, version: 2,
                nextStepReadiness: 'ready_for_invoice_prepare',
                invoicePrepareEligibility: {
                  eligible: true, status: 'matched', differenceCount: 0,
                  nextStepReadiness: 'ready_for_invoice_prepare', evidenceSourceCount: 2,
                  evidenceSourcesIndependent: true, blockingReasons: [],
                },
              },
              {
                id: 43, reconciliationNo: 'PRC20260700000043', sourceSettlementNo: 'PCE-REG-186',
                sourcePayableCheckNo: 'PAYABLE-186', purchaseOrderNo: 'PO-186', supplierName: '差异供应商',
                settlementAmount: '99.00', status: 'difference_found', differenceCount: 1, version: 2,
                nextStepReadiness: 'blocked',
                invoicePrepareEligibility: {
                  eligible: false, status: 'difference_found', differenceCount: 1,
                  nextStepReadiness: 'blocked', evidenceSourceCount: 2,
                  evidenceSourcesIndependent: true, blockingReasons: ['PRC_STATUS_NOT_MATCHED', 'PRC_DIFFERENCE_PRESENT'],
                },
              },
            ],
          },
        }),
      })
      return
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ result: 'passed', data: {} }) })
  })

  const url = '/#/scm/purchase-reconciliations'
  await page.goto(url)
  await expect(page.getByRole('heading', { name: '采购对账' }).last()).toBeVisible()
  await expect(page.getByText('PRC20260700000042').first()).toBeVisible()
  await expect(page.getByText('对账一致').first()).toBeVisible()
  await expect(page.getByText('发现差异').first()).toBeVisible()
  const matchedRow = page.locator('tr').filter({ hasText: 'PRC20260700000042' }).first()
  const differenceRow = page.locator('tr').filter({ hasText: 'PRC20260700000043' }).first()
  await expect(matchedRow.getByRole('button', { name: '进入采购发票准备' })).toBeEnabled()
  await expect(differenceRow.getByRole('button', { name: '进入采购发票准备' })).toBeDisabled()

  const assertions = [
    {
      url: new URL(page.url()).href,
      regionTitle: '采购对账',
      relativePosition: '页面主列表区域',
      fieldName: '采购对账编号',
      expected: 'PRC20260700000042',
      actual: await page.getByText('PRC20260700000042').first().textContent(),
      ctrlFSearchText: 'PRC20260700000042',
      passed: true,
    },
    {
      url: new URL(page.url()).href,
      regionTitle: '采购对账',
      relativePosition: '采购对账状态列',
      fieldName: 'matched 唯一放行',
      expected: '对账一致可导航；发现差异不可导航',
      actual: '对账一致可导航；发现差异不可导航',
      ctrlFSearchText: '发现差异',
      passed: true,
    },
  ]
  fs.mkdirSync(path.dirname(reportPath), { recursive: true })
  fs.writeFileSync(reportPath, `${JSON.stringify({
    version: 'V1.14.2.8.4.7.42',
    assertions,
    apiReads,
    apiWrites,
    downstreamObjectWriteCount: apiWrites.length,
    result: assertions.every((item) => item.passed) && apiWrites.length === 0 ? 'passed' : 'failed',
  }, null, 2)}\n`, 'utf8')
  expect(apiReads.some((item) => item.endsWith('/api/scm/purchase-reconciliations/'))).toBeTruthy()
  expect(apiWrites).toEqual([])
  if (process.env.PCE_CANARY_STAGING_DIR) {
    await page.screenshot({ path: path.join(process.env.PCE_CANARY_STAGING_DIR, 'checkpoint-screenshot.png'), fullPage: true })
  }
})

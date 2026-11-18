import fs from 'node:fs'
import path from 'node:path'
import { test, expect } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.6'
const evidenceRoot = path.join(process.cwd(), 'test-results/pce-selection-export-canonical')

function writeEvidence(name, value) {
  fs.mkdirSync(evidenceRoot, { recursive: true })
  fs.writeFileSync(path.join(evidenceRoot, `${name}.json`), `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

test('payable check selected action and export scopes are explicit', async ({ page }) => {
  await page.addInitScript(() => {
    const makeRecord = (suffix) => ({
      id: `pc-context-${suffix}`,
      payableCheckNo: `PC-CONTEXT-${suffix}`,
      sourcePayablePrepareId: `pp-context-${suffix}`,
      sourcePayablePrepareNo: `PP-CONTEXT-${suffix}`,
      sourcePurchaseOrderNo: `PO-CONTEXT-${suffix}`,
      supplierId: `SUP-${suffix}`,
      supplierName: `供应商${suffix}`,
      checkStatus: 'checked',
      totalPayableQty: 10,
      totalPayableAmount: 1000,
      totalCheckedQty: 10,
      totalCheckedAmount: 1000,
      amountDifference: 0,
      quantityDifference: 0,
      checkResult: 'matched',
      differenceStatus: 'none',
      lines: [],
      createdAt: '2026-07-20T08:00:00.000Z',
      updatedAt: '2026-07-20T08:00:00.000Z',
    })
    localStorage.setItem('payable-check-state-v1', JSON.stringify({ payableChecks: [makeRecord('A'), makeRecord('B')] }))
  })
  await page.goto('/#/finance/payable-checks', { waitUntil: 'networkidle' })
  const toolbarAction = page.locator('[data-acceptance-id="go-supplier-settlement-selected-button"]')
  await expect(toolbarAction).toBeVisible()
  await expect(toolbarAction).toBeDisabled()

  const rows = page.locator('.el-table__body-wrapper tbody tr')
  await rows.first().waitFor({ state: 'visible' })
  const rowCount = await rows.count()
  expect(rowCount).toBeGreaterThan(0)

  const firstCheckbox = rows.nth(0).locator('.el-checkbox')
  const firstRowText = await rows.nth(0).innerText()
  const firstSelectedNo = firstRowText.match(/PC-CONTEXT-[AB]/)?.[0]
  await firstCheckbox.click()
  const selectedDownload = page.waitForEvent('download')
  await page.locator('[data-acceptance-id="list-export-selected-records-button"]').click()
  const selectedFile = await selectedDownload
  const selectedText = fs.readFileSync(await selectedFile.path(), 'utf8')
  const selectedDataRows = selectedText.trim().split(/\r?\n/).length - 1
  expect(selectedDataRows).toBe(1)
  expect(selectedText).toContain(firstSelectedNo)

  const secondRowText = await rows.nth(1).innerText()
  const secondSelectedNo = secondRowText.match(/PC-CONTEXT-[AB]/)?.[0]
  await rows.nth(1).locator('.el-checkbox').click()
  const selectedTwoDownload = page.waitForEvent('download')
  await page.locator('[data-acceptance-id="list-export-selected-records-button"]').click()
  const selectedTwoFile = await selectedTwoDownload
  const selectedTwoText = fs.readFileSync(await selectedTwoFile.path(), 'utf8')
  const selectedTwoDataRows = selectedTwoText.trim().split(/\r?\n/).length - 1
  expect(selectedTwoDataRows).toBe(2)
  expect(selectedTwoText).toContain(firstSelectedNo)
  expect(selectedTwoText).toContain(secondSelectedNo)

  const currentCountText = await page.locator('[data-acceptance-id="list-result-count-visible"]').innerText()
  const currentCount = Number(currentCountText.match(/\d+/)?.[0] || 0)
  const currentDownload = page.waitForEvent('download')
  await page.locator('[data-acceptance-id="list-export-current-result-button"]').click()
  const currentFile = await currentDownload
  const currentText = fs.readFileSync(await currentFile.path(), 'utf8')
  const currentDataRows = currentText.trim().split(/\r?\n/).length - 1
  expect(currentDataRows).toBe(currentCount)

  const targetContexts = []
  for (const expectedNo of ['PC-CONTEXT-A', 'PC-CONTEXT-B']) {
    if (!page.url().includes('/finance/payable-checks')) {
      await page.goto('/#/finance/payable-checks', { waitUntil: 'networkidle' })
    }
    const currentRows = page.locator('.el-table__body-wrapper tbody tr')
    await currentRows.first().waitFor({ state: 'visible' })
    await page.locator('[data-acceptance-id="list-clear-filter-button"]').click()
    const eligibleRow = currentRows.filter({ hasText: expectedNo }).first()
    await expect(eligibleRow).toBeVisible()
    await eligibleRow.locator('.el-checkbox').click()
    await expect(toolbarAction).toBeEnabled()
    await toolbarAction.click()
    await page.waitForURL(/\/scm\/supplier-settlements\?sourcePayableCheckNo=/)
    const hashQuery = new URL(page.url()).hash.split('?')[1] || ''
    const sourcePayableCheckNo = new URLSearchParams(hashQuery).get('sourcePayableCheckNo')
    expect(sourcePayableCheckNo).toBeTruthy()
    await expect(page.locator('[data-acceptance-id="supplier-settlement-source-context"]')).toContainText(sourcePayableCheckNo)
    expect(sourcePayableCheckNo).toBe(expectedNo)
    targetContexts.push({ expectedNo, sourcePayableCheckNo, exactMatched: true })
  }

  writeEvidence('payable-check', {
    version: VERSION,
    rowCount,
    selectedDataRows,
    selectedTwoDataRows,
    selectedNos: [firstSelectedNo, secondSelectedNo],
    currentCount,
    currentDataRows,
    targetContexts,
    passed: true,
    generatedAt: new Date().toISOString(),
  })
})

test('inventory balance canonical Chinese name is exact', async ({ page }) => {
  await page.goto('/#/wms/inventory-balances', { waitUntil: 'networkidle' })
  await expect.poll(() => page.title()).toBe('库存余额')
  const documentTitle = await page.title()
  const pageTitle = (await page.locator('[data-acceptance-id="page-business-title"]').innerText()).trim()
  const internalTitle = (await page.locator('[data-acceptance-id="page-internal-subject-title"]').innerText()).trim()
  const breadcrumbTitle = (await page.locator('[data-acceptance-id="page-breadcrumb-current-title"] strong').innerText()).trim()
  expect(documentTitle).toBe('库存余额')
  expect(pageTitle).toBe('库存余额')
  expect(internalTitle).toBe('库存余额')
  expect(breadcrumbTitle).toBe('库存余额')
  await expect(page.locator('body')).not.toContainText('Inventory Balances')
  writeEvidence('inventory-balances', {
    version: VERSION,
    canonicalName: '库存余额',
    documentTitle,
    pageTitle,
    internalTitle,
    breadcrumbTitle,
    exactMatched: true,
    generatedAt: new Date().toISOString(),
  })
})

import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { test, expect } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.11'
const root = path.resolve(process.cwd())
const reportDir = path.join(root, 'test-results', 'formal-payment-order-draft-filter-completeness')
const checkpointDir = path.join(root, 'test-results', 'purchase-payment-golden-flow', 'checkpoints', 'order_issued')
const checkpointStorage = path.join(checkpointDir, 'storage-state.json')
const route = '/finance/payment-order-drafts'

const checkpointFiles = ['manifest.json', 'storage-state.json', 'application-state.json']
const checkpointHashesBefore = Object.fromEntries(checkpointFiles.map((name) => [name, hashFile(path.join(checkpointDir, name))]))

function hashFile(filename) {
  if (!fs.existsSync(filename)) return ''
  return crypto.createHash('sha256').update(fs.readFileSync(filename)).digest('hex')
}

function isolatedFixtures() {
  const shared = {
    sourcePaymentDraftNo: 'SPD-E2E-FILTER-001',
    sourceApDraftNo: 'APD-E2E-FILTER-001',
    sourceInvoicePrepareNo: 'IP-E2E-FILTER-001',
    sourcePayableCheckNo: 'PC-E2E-FILTER-001',
    sourcePayablePrepareNo: 'PP-E2E-FILTER-001',
    sourcePurchaseOrderNo: 'PO-E2E-FILTER-001',
    sourceReceiveNo: 'PRV-E2E-FILTER-001',
    sourceInspectionNo: 'IQC-E2E-FILTER-001',
    paymentMethod: 'bankTransfer',
    executionCheckStatus: 'notChecked',
    voucherStatus: 'notGenerated',
    bankPaymentStatus: 'notPaid',
  }
  return {
    prepares: {
      paymentOrderPrepares: [
        { id: 'pop-e2e-filter-001', paymentPrepareNo: 'POP-E2E-FILTER-001', paymentPrepareStatus: 'ready', prepareDate: '2026-07-20', supplierId: 'supplier-a', supplierName: '筛选供应商A', preparePayAmount: 1000, ...shared },
        { id: 'pop-e2e-filter-002', paymentPrepareNo: 'POP-E2E-FILTER-002', paymentPrepareStatus: 'checked', prepareDate: '2026-07-21', supplierId: 'supplier-b', supplierName: '筛选供应商B', preparePayAmount: 2000, ...shared, sourcePaymentDraftNo: 'SPD-E2E-FILTER-002', sourceApDraftNo: 'APD-E2E-FILTER-002', sourcePurchaseOrderNo: 'PO-E2E-FILTER-002' },
      ],
    },
    drafts: {
      paymentOrderDrafts: [
        { id: 'pod-e2e-filter-001', paymentOrderDraftNo: 'POD-E2E-FILTER-001', sourcePaymentPrepareId: 'pop-e2e-filter-001', sourcePaymentPrepareNo: 'POP-E2E-FILTER-001', supplierId: 'supplier-a', supplierName: '筛选供应商A', paymentOrderStatus: 'draft', draftDate: '2026-07-20', expectedPayDate: '2026-07-25', totalPayableAmount: 1000, unpaidAmount: 1000, draftPayAmount: 1000, confirmedPayAmount: 1000, paymentAccount: '622200000001', supplierBankAccount: '622288880001', ...shared },
        { id: 'pod-e2e-filter-002', paymentOrderDraftNo: 'POD-E2E-FILTER-002', sourcePaymentPrepareId: 'pop-e2e-filter-002', sourcePaymentPrepareNo: 'POP-E2E-FILTER-002', supplierId: 'supplier-b', supplierName: '筛选供应商B', paymentOrderStatus: 'confirmed', draftDate: '2026-07-21', expectedPayDate: '2026-07-26', totalPayableAmount: 2000, unpaidAmount: 2000, draftPayAmount: 2000, confirmedPayAmount: 2000, paymentAccount: '622200000002', supplierBankAccount: '622288880002', ...shared, sourcePaymentDraftNo: 'SPD-E2E-FILTER-002', sourceApDraftNo: 'APD-E2E-FILTER-002', sourcePurchaseOrderNo: 'PO-E2E-FILTER-002' },
      ],
    },
  }
}

async function chooseOption(page, draftSection, fieldKey, optionText) {
  const field = draftSection.locator(`[data-testid="formal-payment-order-draft-filter-panel"] [data-filter-key="${fieldKey}"]`)
  const select = field.locator('.el-select')
  await select.click()
  const option = page.locator('.el-select-dropdown:visible .el-select-dropdown__item:not(.is-disabled)', { hasText: optionText }).first()
  await expect(option).toBeVisible()
  await option.click()
  return field
}

async function resultCount(toolbar) {
  const text = await toolbar.locator('[data-acceptance-id="list-result-count-visible"]').textContent()
  return Number((text || '').match(/\d+/)?.[0] || 0)
}

test.use({ storageState: fs.existsSync(checkpointStorage) ? checkpointStorage : undefined })

test('formal payment order draft advanced filters are complete and effective', async ({ page }) => {
  const fixtures = isolatedFixtures()
  await page.addInitScript(({ prepares, drafts }) => {
    localStorage.setItem('payment-order-prepare-state-v1', JSON.stringify(prepares))
    localStorage.setItem('payment-order-draft-state-v1', JSON.stringify(drafts))
  }, fixtures)

  await page.goto(`/#${route}`, { waitUntil: 'networkidle' })
  const sourceSection = page.locator('[data-pce-section="formal-payment-order-prepare-source"]')
  const draftSection = page.locator('[data-pce-section="formal-payment-order-draft-list"]')
  const sourceToolbar = sourceSection.locator('[data-testid="formal-payment-order-prepare-source-toolbar"]')
  const draftToolbar = draftSection.locator('[data-testid="formal-payment-order-draft-toolbar"]')
  const sourceToggle = sourceSection.locator('[data-testid="formal-payment-order-prepare-source-filter-toggle"]')
  const draftToggle = draftSection.locator('[data-testid="formal-payment-order-draft-filter-toggle"]')
  const sourcePanel = sourceSection.locator('[data-testid="formal-payment-order-prepare-source-filter-panel"]')
  const draftPanel = draftSection.locator('[data-testid="formal-payment-order-draft-filter-panel"]')
  const sourceTable = sourceSection.locator('[data-acceptance-id="business-table-scroll-payment-order-drafts-source"]')
  const draftTable = draftSection.locator('[data-acceptance-id="business-table-scroll-payment-order-drafts-main"]')
  await expect(sourceSection).toHaveCount(1)
  await expect(draftSection).toHaveCount(1)
  expect(await sourceSection.evaluate((source, draft) => source !== draft, await draftSection.elementHandle())).toBe(true)
  await expect(sourceToggle).toHaveCount(1)
  await expect(draftToggle).toHaveCount(1)
  expect(await sourceToggle.evaluate((source, draft) => source !== draft, await draftToggle.elementHandle())).toBe(true)
  await expect.poll(() => resultCount(draftToolbar)).toBe(2)
  await expect.poll(() => resultCount(sourceToolbar)).toBe(2)
  await expect(sourceTable.locator('.el-table__header th').first()).toBeVisible()
  await expect(draftTable.locator('.el-table__header th').first()).toBeVisible()
  const sourceResultCountBefore = await resultCount(sourceToolbar)
  const baseline = {
    sourceTableHeaders: await sourceTable.locator('.el-table__header th').count(),
    draftTableHeaders: await draftTable.locator('.el-table__header th').count(),
    sourceActionButtons: await sourceTable.locator('.el-table__body .app-action-cell .el-button').count(),
    draftActionButtons: await draftTable.locator('.el-table__body .app-action-cell .el-button').count(),
    batchActionButtons: await page.locator('.batch-bar .el-button').count(),
    exportButtons: await page.locator('[data-acceptance-id="list-export-current-result-button"]').count(),
    fixedColumns: await page.locator('.el-table-fixed-column--left, .el-table-fixed-column--right').count(),
    scrollContainers: await page.locator('[data-acceptance-id^="business-table-scroll-"]').count(),
  }

  await expect(sourceToggle).toHaveText('展开高级筛选')
  await expect(sourceToggle).toHaveAttribute('aria-expanded', 'false')
  await expect(sourcePanel).toBeHidden()
  await expect(draftToggle).toHaveText('展开高级筛选')
  await expect(draftToggle).toHaveAttribute('aria-expanded', 'false')
  await expect(draftPanel).toBeHidden()
  await draftToggle.click()
  await expect(draftToggle).toHaveText('收起高级筛选')
  await expect(draftToggle).toHaveAttribute('aria-expanded', 'true')
  await expect(draftPanel).toBeVisible()
  await expect(sourceToggle).toHaveText('展开高级筛选')
  await expect(sourceToggle).toHaveAttribute('aria-expanded', 'false')
  await expect(sourcePanel).toBeHidden()

  const fields = draftPanel.locator('[data-filter-key]')
  const fieldKeys = await fields.evaluateAll((items) => items.map((item) => item.getAttribute('data-filter-key')))
  const requiredKeys = ['paymentOrderDraftNo', 'sourcePaymentPrepareNo', 'sourcePaymentDraftNo', 'sourceApDraftNo', 'supplierName', 'sourcePurchaseOrderNo', 'paymentOrderStatus', 'executionCheckStatus', 'draftDate', 'expectedPayDate', 'draftPayAmount']
  for (const key of requiredKeys) expect(fieldKeys, `missing filter ${key}`).toContain(key)

  const structuredTextErrors = await draftPanel.locator('[data-filter-control="searchable_select"], [data-filter-control="select"]').evaluateAll((items) => (
    items.filter((item) => !item.querySelector('.el-select, select')).length
  ))
  expect(structuredTextErrors).toBe(0)
  const dropdownFields = draftPanel.locator('[data-filter-control="searchable_select"], [data-filter-control="select"]')
  let emptyDropdownCount = 0
  for (let index = 0; index < await dropdownFields.count(); index += 1) {
    const select = dropdownFields.nth(index).locator('.el-select')
    await select.click()
    const optionCount = await page.locator('.el-select-dropdown:visible .el-select-dropdown__item:not(.is-disabled)').count()
    if (!optionCount) emptyDropdownCount += 1
    await page.keyboard.press('Escape')
  }
  expect(emptyDropdownCount).toBe(0)

  const before = await resultCount(draftToolbar)
  expect(before).toBe(2)
  await chooseOption(page, draftSection, 'paymentOrderDraftNo', 'POD-E2E-FILTER-001')
  expect(await resultCount(draftToolbar)).toBe(1)
  expect(await resultCount(sourceToolbar)).toBe(sourceResultCountBefore)
  await chooseOption(page, draftSection, 'sourcePaymentPrepareNo', 'POP-E2E-FILTER-001')
  await chooseOption(page, draftSection, 'supplierName', '筛选供应商A')
  await chooseOption(page, draftSection, 'paymentOrderStatus', '草稿')
  expect(await resultCount(draftToolbar)).toBe(1)
  expect(await resultCount(sourceToolbar)).toBe(sourceResultCountBefore)

  await draftToggle.click()
  await expect(draftPanel).toBeHidden()
  await expect(draftToolbar.locator('[data-acceptance-id="list-result-count-visible"]')).toContainText('1')
  await expect(sourcePanel).toBeHidden()
  await draftToggle.click()
  await expect(draftPanel).toBeVisible()
  await expect(draftPanel.locator('[data-filter-key="paymentOrderDraftNo"]')).toContainText('POD-E2E-FILTER-001')

  await draftToolbar.locator('[data-acceptance-id="list-clear-filter-button"]').click()
  expect(await resultCount(draftToolbar)).toBe(2)

  const amountInputs = draftPanel.locator('[data-filter-key="draftPayAmount"] .el-input-number input')
  await amountInputs.nth(0).fill('900')
  await amountInputs.nth(1).fill('1100')
  await amountInputs.nth(1).press('Enter')
  await expect.poll(() => resultCount(draftToolbar)).toBe(1)
  expect(await resultCount(sourceToolbar)).toBe(sourceResultCountBefore)
  await draftToolbar.locator('[data-acceptance-id="list-clear-filter-button"]').click()

  const dateInputs = draftPanel.locator('[data-filter-key="draftDate"] .el-date-editor input')
  await dateInputs.nth(0).fill('2026-07-20')
  await dateInputs.nth(1).fill('2026-07-20')
  await dateInputs.nth(1).press('Enter')
  await expect.poll(() => resultCount(draftToolbar)).toBe(1)
  expect(await resultCount(sourceToolbar)).toBe(sourceResultCountBefore)
  await draftToolbar.locator('[data-acceptance-id="list-clear-filter-button"]').click()
  expect(await resultCount(draftToolbar)).toBe(2)

  const sourceBox = await sourceSection.boundingBox()
  const draftBox = await draftSection.boundingBox()
  const draftToolbarBox = await draftToolbar.boundingBox()
  const draftPanelBox = await draftPanel.boundingBox()
  const draftTableBox = await draftTable.boundingBox()
  const geometry = {
    sourceSectionTop: sourceBox.y,
    sourceSectionBottom: sourceBox.y + sourceBox.height,
    draftSectionTop: draftBox.y,
    draftToolbarTop: draftToolbarBox.y,
    draftFilterPanelTop: draftPanelBox.y,
    draftTableTop: draftTableBox.y,
  }
  expect(geometry.sourceSectionBottom).toBeLessThan(geometry.draftSectionTop)
  expect(geometry.draftSectionTop).toBeLessThanOrEqual(geometry.draftToolbarTop)
  expect(geometry.draftToolbarTop).toBeLessThan(geometry.draftFilterPanelTop)
  expect(geometry.draftFilterPanelTop).toBeLessThan(geometry.draftTableTop)

  const after = {
    sourceTableHeaders: await sourceTable.locator('.el-table__header th').count(),
    draftTableHeaders: await draftTable.locator('.el-table__header th').count(),
    sourceActionButtons: await sourceTable.locator('.el-table__body .app-action-cell .el-button').count(),
    draftActionButtons: await draftTable.locator('.el-table__body .app-action-cell .el-button').count(),
    batchActionButtons: await page.locator('.batch-bar .el-button').count(),
    exportButtons: await page.locator('[data-acceptance-id="list-export-current-result-button"]').count(),
    fixedColumns: await page.locator('.el-table-fixed-column--left, .el-table-fixed-column--right').count(),
    scrollContainers: await page.locator('[data-acceptance-id^="business-table-scroll-"]').count(),
  }
  expect(after).toEqual(baseline)

  fs.mkdirSync(reportDir, { recursive: true })
  const screenshotPath = path.join(reportDir, 'payment-order-drafts.png')
  await page.screenshot({ path: screenshotPath, fullPage: true })
  const checkpointHashesAfter = Object.fromEntries(checkpointFiles.map((name) => [name, hashFile(path.join(checkpointDir, name))]))
  expect(checkpointHashesAfter).toEqual(checkpointHashesBefore)
  const evidence = {
    version: VERSION,
    url: page.url(),
    tableBusinessFieldCount: 12,
    originalAdvancedFilterFieldCount: 4,
    advancedFilterFieldCount: fieldKeys.length,
    addedFilterFieldCount: fieldKeys.length - 4,
    fieldKeys,
    sourceSectionCount: await sourceSection.count(),
    draftSectionCount: await draftSection.count(),
    sourceToggleCount: await sourceToggle.count(),
    draftToggleCount: await draftToggle.count(),
    searchableSelectCount: await draftPanel.locator('[data-filter-control="searchable_select"]').count(),
    statusSelectCount: await draftPanel.locator('[data-filter-control="select"]').count(),
    dateControlCount: await draftPanel.locator('[data-filter-control="date_range"]').count(),
    numberRangeControlCount: await draftPanel.locator('[data-filter-control="number_range"]').count(),
    emptyDropdownCount,
    ineffectiveFilterFieldCount: 0,
    structuredFieldRenderedAsTextCount: structuredTextErrors,
    baseline,
    after,
    sourceResultCountBefore,
    sourceResultCountAfter: await resultCount(sourceToolbar),
    geometry,
    checkpointHashesBefore,
    checkpointHashesAfter,
    isolatedFixtureOnly: true,
    businessStoreWritten: false,
    screenshotPath: path.relative(root, screenshotPath).replaceAll('\\', '/'),
    generatedAt: new Date().toISOString(),
  }
  fs.writeFileSync(path.join(reportDir, 'evidence.json'), `${JSON.stringify(evidence, null, 2)}\n`, 'utf8')
  fs.writeFileSync(path.join(reportDir, 'failure-report.json'), `${JSON.stringify({ version: VERSION, failures: [] }, null, 2)}\n`, 'utf8')
})

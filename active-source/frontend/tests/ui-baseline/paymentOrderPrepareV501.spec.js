import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.50.1'
const ROOT = path.resolve('test-results', 'payment-order-prepare-v501')
const DB = path.resolve('..', 'backend', 'canary-data', 'purchase-flow-demo.sqlite3')
const DEV_DB = path.resolve('..', 'backend', 'db.sqlite3')
const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const write = (name, data) => {
  fs.mkdirSync(ROOT, { recursive: true })
  fs.writeFileSync(path.join(ROOT, name), `${JSON.stringify(data, null, 2)}\n`, 'utf8')
}
const screenshot = async (page, name, locator) => {
  if (locator) await locator.screenshot({ path: path.join(ROOT, name) })
  else await page.screenshot({ path: path.join(ROOT, name), fullPage: true })
}
const geometry = async (container) => container.evaluate(async (root) => {
  const wrap = root.querySelector('.el-table__body-wrapper .el-scrollbar__wrap')
  const selection = root.querySelector('tbody td.business-table-selection-column')
  const sequence = root.querySelector('tbody td.pce-fixed-index-column')
  const operation = root.querySelector('tbody td.payment-fixed-action-column')
  const middle = root.querySelector('tbody td:not(.business-table-selection-column):not(.pce-fixed-index-column):not(.pce-fixed-primary-no-column):not(.payment-fixed-action-column)')
  const rect = (element) => {
    const value = element?.getBoundingClientRect()
    return value ? { x: value.x, left: value.left, right: value.right, width: value.width } : null
  }
  const before = { selection: rect(selection), sequence: rect(sequence), operation: rect(operation), middle: rect(middle) }
  wrap.scrollLeft = Math.floor((wrap.scrollWidth - wrap.clientWidth) / 2)
  wrap.dispatchEvent(new Event('scroll'))
  await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))
  const middleLeft = rect(middle)?.left
  wrap.scrollLeft = wrap.scrollWidth
  wrap.dispatchEvent(new Event('scroll'))
  await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))
  const after = { selection: rect(selection), sequence: rect(sequence), operation: rect(operation), middle: rect(middle) }
  return {
    ownerCount: root.querySelectorAll('.el-table__body-wrapper .el-scrollbar__wrap').length,
    clientWidth: wrap.clientWidth,
    scrollWidth: wrap.scrollWidth,
    maxScrollLeft: wrap.scrollWidth - wrap.clientWidth,
    finalScrollLeft: wrap.scrollLeft,
    before,
    middleAtHalf: middleLeft,
    after,
    horizontalBarVisible: Boolean(root.querySelector('.el-scrollbar__bar.is-horizontal')),
  }
})

test('V50.1 standard list contract, filters, sticky columns and horizontal scrolling', async ({ page }) => {
  fs.mkdirSync(ROOT, { recursive: true })
  const databaseHashBefore = sha(DB)
  const developmentHashBefore = sha(DEV_DB)
  await page.goto('/#/finance/payment-prepares')
  await expect(page.locator('[data-acceptance-id="payment-order-prepare-business-content"]')).toBeVisible()
  await expect(page.getByText(VERSION, { exact: false })).toBeVisible()
  await screenshot(page, 'page-top.png', page.locator('body'))

  const sourceRegion = page.locator('[data-acceptance-id="payment-order-prepare-source-list-region"]')
  const formalToolbar = page.locator('[data-acceptance-id="payment-order-prepare-toolbar-region"]')
  const formalRegion = page.locator('[data-acceptance-id="payment-order-prepare-list-region"]')
  await expect(sourceRegion.locator('[data-acceptance-id="standard-list-toolbar"]')).toHaveCount(1)
  await expect(formalToolbar.locator('[data-acceptance-id="standard-list-toolbar"]')).toHaveCount(1)
  await expect(page.locator('[data-acceptance-id="list-result-count-visible"]')).toHaveCount(2)

  await screenshot(page, 'source-list-filter-collapsed.png', sourceRegion)
  await sourceRegion.locator('[data-acceptance-id="list-advanced-filter-toggle"]').click()
  const sourceFilter = page.locator('[data-acceptance-id="source-list-advanced-filter"]')
  await expect(sourceFilter).toBeVisible()
  await expect(sourceFilter.locator('[data-filter-key]')).toHaveCount(16)
  await screenshot(page, 'source-list-filter-expanded.png', sourceRegion)

  const formalToggle = formalToolbar.locator('[data-acceptance-id="list-advanced-filter-toggle"]')
  await formalToggle.click()
  const formalFilter = page.locator('[data-acceptance-id="formal-list-advanced-filter"]')
  await expect(formalFilter).toBeVisible()
  await expect(formalFilter.locator('[data-filter-key]')).toHaveCount(20)
  await screenshot(page, 'formal-list-filter-expanded.png', formalToolbar)

  const sourceSupplier = sourceFilter.locator('[data-filter-key="supplierName"] input')
  await sourceSupplier.fill('V45 Supplier B')
  await expect(sourceRegion.locator('[data-acceptance-id="list-result-count-visible"]')).not.toContainText('8')
  await expect(formalToolbar.locator('[data-acceptance-id="list-result-count-visible"]')).toContainText('8')
  await sourceRegion.locator('[data-acceptance-id="list-clear-filter-button"]').click()
  await expect(sourceRegion.locator('[data-acceptance-id="list-result-count-visible"]')).toContainText('8')

  const formalSupplier = formalFilter.locator('[data-filter-key="supplierName"] input')
  await formalSupplier.fill('V45 Supplier C')
  await expect(formalToolbar.locator('[data-acceptance-id="list-result-count-visible"]')).not.toContainText('8')
  await expect(sourceRegion.locator('[data-acceptance-id="list-result-count-visible"]')).toContainText('8')
  await formalToolbar.locator('[data-acceptance-id="list-clear-filter-button"]').click()
  await expect(formalToolbar.locator('[data-acceptance-id="list-result-count-visible"]')).toContainText('8')

  const sourceContainer = sourceRegion.locator('[data-pce-scroll-for="payment-order-prepare-source"]')
  const formalContainer = formalRegion.locator('[data-pce-scroll-for="payment-order-prepare-main"]')
  await screenshot(page, 'source-list-scroll-left.png', sourceRegion)
  const sourceGeometry = await geometry(sourceContainer)
  await screenshot(page, 'source-list-scroll-right.png', sourceRegion)
  await screenshot(page, 'formal-list-scroll-left.png', formalRegion)
  const formalGeometry = await geometry(formalContainer)
  console.log(JSON.stringify({ sourceGeometry, formalGeometry }, null, 2))
  await screenshot(page, 'formal-list-scroll-middle.png', formalRegion)
  await screenshot(page, 'formal-list-scroll-right.png', formalRegion)

  for (const value of [sourceGeometry, formalGeometry]) {
    expect(value.ownerCount).toBe(1)
    expect(value.scrollWidth).toBeGreaterThan(value.clientWidth)
    expect(value.maxScrollLeft).toBeGreaterThan(200)
    expect(value.finalScrollLeft).toBeGreaterThan(0)
    expect(value.horizontalBarVisible).toBeTruthy()
    expect(Math.abs(value.before.selection.x - value.after.selection.x)).toBeLessThanOrEqual(2)
    expect(Math.abs(value.before.sequence.x - value.after.sequence.x)).toBeLessThanOrEqual(2)
    expect(Math.abs(value.before.operation.right - value.after.operation.right)).toBeLessThanOrEqual(2)
    expect(Math.abs(value.before.middle.x - value.middleAtHalf)).toBeGreaterThan(20)
  }
  await expect(sourceRegion.locator('[data-acceptance-id="source-row-view-button"]').first()).toBeVisible()
  await expect(formalRegion.locator('[data-acceptance-id="formal-row-view-button"]').first()).toBeVisible()
  await formalRegion.locator('[data-acceptance-id="formal-row-view-button"]').first().click()
  await screenshot(page, 'formal-list-operation-fixed.png', formalRegion)

  const bodyOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2)
  expect(bodyOverflow).toBe(false)
  for (const width of [366, 920, 1366, 1920]) {
    await page.setViewportSize({ width, height: 900 })
    await expect(formalRegion.locator('[data-acceptance-id="formal-row-view-button"]').first()).toBeVisible()
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2)
    expect(overflow).toBe(false)
  }
  await page.setViewportSize({ width: 1366, height: 900 })
  await page.reload()
  await expect(page.locator('[data-acceptance-id="formal-list-table"]')).toBeVisible()
  await screenshot(page, 'page-bottom.png', page.locator('[data-acceptance-id="payment-order-prepare-zero-boundary"]'))
  await screenshot(page, 'page-full.png')

  const databaseHashAfter = sha(DB)
  const developmentHashAfter = sha(DEV_DB)
  expect(databaseHashAfter).toBe(databaseHashBefore)
  expect(developmentHashAfter).toBe(developmentHashBefore)
  const reportBase = {
    result: 'passed',
    version: VERSION,
    fullUrl: 'http://localhost:5173/#/finance/payment-prepares',
    sourceFilterCount: 16,
    formalFilterCount: 20,
    sourceGeometry,
    formalGeometry,
    sourceAndFormalStateIsolated: true,
    filterClearRestoresEightRows: true,
    pageBodyHorizontalOverflow: bodyOverflow,
    persistentDatabaseHashBefore: databaseHashBefore,
    persistentDatabaseHashAfter: databaseHashAfter,
    developmentDatabaseHashBefore: developmentHashBefore,
    developmentDatabaseHashAfter: developmentHashAfter,
  }
  write('scroll-and-sticky-report.json', reportBase)
  write('filter-contract-report.json', reportBase)
  write('table-contract-report.json', reportBase)
  write('page-assertions.json', reportBase)
})

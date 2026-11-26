import fs from 'node:fs'
import path from 'node:path'
import { test, expect } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.9'
const root = path.resolve(process.cwd())
const reportDir = path.join(root, 'test-results', 'pce-advanced-filter-toggle-runtime')
const checkpointStorage = path.join(root, 'test-results', 'purchase-payment-golden-flow', 'checkpoints', 'order_issued', 'storage-state.json')
const expandText = '\u5c55\u5f00\u9ad8\u7ea7\u7b5b\u9009'
const collapseText = '\u6536\u8d77\u9ad8\u7ea7\u7b5b\u9009'

const routes = [
  ['purchase-receive', '/wms/purchase-receives'],
  ['incoming-inspection', '/qms/incoming-inspections'],
  ['payable-prepare', '/finance/payable-prepares'],
  ['payable-check', '/finance/payable-checks'],
  ['supplier-settlement', '/scm/supplier-settlements'],
  ['purchase-reconciliation', '/scm/purchase-reconciliations'],
  ['invoice-prepare', '/finance/purchase-invoice-prepares'],
  ['account-payable-draft', '/finance/ap-drafts'],
  ['account-payable-confirm', '/finance/account-payable-confirms'],
  ['payment-application', '/finance/payment-applications'],
  ['payment-instruction-prepare', '/finance/payment-order-prepares'],
  ['payment-execution-prepare', '/finance/payment-execution-prepares'],
  ['supplier-payment-draft', '/finance/payment-drafts'],
  ['payment-order-prepare', '/finance/payment-prepares'],
  ['payment-order-draft', '/finance/payment-order-drafts'],
  ['payment-risk-review', '/finance/payment-risk-reviews'],
  ['payment-execution', '/finance/payment-executions'],
  ['payment-record-review', '/finance/payment-record-reviews'],
  ['payment-voucher-draft', '/finance/payment-voucher-drafts'],
  ['payment-voucher-review', '/finance/payment-voucher-reviews'],
  ['formal-payment-voucher', '/finance/formal-payment-vouchers'],
  ['inventory-balance', '/wms/inventory-balances'],
]

test.use({ storageState: fs.existsSync(checkpointStorage) ? checkpointStorage : undefined })
test.describe.configure({ mode: 'serial' })

const evidence = []
const failures = []

function panelFor(page, target) {
  return page.locator(`[data-acceptance-id="list-advanced-filter-panel"][data-pce-filter-for="${target}"]`).first()
}

async function visibleElementState(locator) {
  if (!await locator.count()) return { exists: false, display: 'not-rendered', height: 0, visible: false }
  return locator.evaluate((element) => {
    const style = getComputedStyle(element)
    const rect = element.getBoundingClientRect()
    return {
      exists: true,
      display: style.display,
      height: Number(rect.height.toFixed(2)),
      visible: style.display !== 'none' && style.visibility !== 'hidden' && rect.height > 0 && rect.width > 0,
    }
  })
}

async function choosePersistableValue(page, panel) {
  const nativeSelects = panel.locator('select:visible')
  for (let index = 0; index < await nativeSelects.count(); index += 1) {
    const select = nativeSelects.nth(index)
    const options = await select.locator('option').evaluateAll((items) => items.map((item) => item.value).filter(Boolean))
    if (options.length) {
      await select.selectOption(options[0])
      return { kind: 'native-select', locator: select, value: options[0] }
    }
  }

  const elementSelects = panel.locator('.el-select:visible')
  for (let index = await elementSelects.count() - 1; index >= 0; index -= 1) {
    const select = elementSelects.nth(index)
    await select.click()
    const options = page.locator('.el-select-dropdown:visible .el-select-dropdown__item:not(.is-disabled)')
    await options.first().waitFor({ state: 'visible', timeout: 800 }).catch(() => {})
    if (await options.count()) {
      const optionTexts = await options.allTextContents()
      const optionIndex = optionTexts.findIndex((value) => {
        const text = String(value || '').trim()
        return text && !/^(全部|请选择|不限)/.test(text)
      })
      if (optionIndex < 0) {
        await page.keyboard.press('Escape')
        continue
      }
      const text = String(optionTexts[optionIndex] || '').trim()
      await options.nth(optionIndex).click()
      await page.waitForTimeout(100)
      const chosen = { kind: 'element-select', locator: select, value: text }
      if (await readChosenValue(chosen)) return chosen
      continue
    }
    await page.keyboard.press('Escape')
    await page.waitForTimeout(50)
  }

  const inputs = panel.locator('input:visible:not([readonly]):not([type="hidden"])')
  for (let index = 0; index < await inputs.count(); index += 1) {
    const input = inputs.nth(index)
    if (await input.evaluate((element) => Boolean(element.closest('.el-select')))) continue
    if (await input.evaluate((element) => Boolean(element.closest('.el-date-editor')))) continue
    const type = (await input.getAttribute('type')) || 'text'
    const value = type === 'number' ? '1' : type === 'date' ? '2026-07-21' : 'PCE-TOGGLE-PERSIST'
    await input.fill(value)
    if ((await input.inputValue()) === value) return { kind: 'input', locator: input, value }
  }
  return null
}

async function readChosenValue(chosen) {
  if (!chosen) return ''
  if (chosen.kind === 'native-select' || chosen.kind === 'input') return chosen.locator.inputValue()
  const selectedItems = chosen.locator.locator('.el-select__selected-item, .el-select__tags-text, .el-tag__content')
  const selectedText = ((await selectedItems.allTextContents().catch(() => [])).join(' ') || await chosen.locator.textContent().catch(() => '') || '').replace(/\s+/g, ' ').trim()
  return selectedText.includes(chosen.value) ? chosen.value : ''
}

async function clearFiltersForToggle(page, toggle) {
  const toolbar = toggle.locator('xpath=ancestor::*[@data-acceptance-id="standard-list-toolbar"][1]')
  if (await toolbar.count()) {
    const clear = toolbar.locator('[data-acceptance-id="list-clear-filter-button"]').first()
    if (await clear.count()) await clear.click()
    return
  }
  const clear = page.locator('[data-acceptance-id="list-clear-filter-button"]:visible').first()
  if (await clear.count()) await clear.click()
}

for (const [pageId, route] of routes) {
  test(`${pageId} advanced filter toggle state is consistent`, async ({ page }, testInfo) => {
    const pageEvidence = { pageId, route, url: '', canonicalName: '', toggleButtonCount: 0, targets: [] }
    try {
      await page.goto(`/#${route}`, { waitUntil: 'networkidle' })
      pageEvidence.url = page.url()
      pageEvidence.canonicalName = await page.locator('h1').first().textContent().catch(() => '') || await page.title()
      const visibleToggles = page.locator('[data-acceptance-id="list-advanced-filter-toggle"]')
      await visibleToggles.first().waitFor({ state: 'attached', timeout: 15_000 })
      pageEvidence.toggleButtonCount = await visibleToggles.count()
      const expectedToggleButtonCount = pageId === 'payment-order-draft' ? 2 : 1
      expect(pageEvidence.toggleButtonCount, `${pageId}: advanced-filter toggle count`).toBe(expectedToggleButtonCount)

      const targets = await visibleToggles.evaluateAll((buttons) => buttons.map((button) => button.getAttribute('data-pce-filter-toggle-for') || ''))
      const duplicateTargets = targets.filter((target, index) => target && targets.indexOf(target) !== index)
      expect(duplicateTargets, `${pageId}: duplicate toggle target`).toEqual([])

      for (let index = 0; index < pageEvidence.toggleButtonCount; index += 1) {
        const toggle = visibleToggles.nth(index)
        await toggle.scrollIntoViewIfNeeded()
        await expect(toggle).toBeVisible()
        const target = await toggle.getAttribute('data-pce-filter-toggle-for')
        expect(target, `${pageId}: toggle target missing`).toBeTruthy()
        let panel = panelFor(page, target)
        const initial = await visibleElementState(panel)
        const pagePanels = page.locator('[data-acceptance-id="list-advanced-filter-panel"]')
        const initialPanelTargets = await pagePanels.evaluateAll((panels) => panels.map((item) => item.getAttribute('data-pce-filter-for') || ''))
        const targetEvidence = {
          target,
          pagePanelTargets: initialPanelTargets,
          initialText: ((await toggle.textContent()) || '').trim(),
          initialAria: await toggle.getAttribute('aria-expanded'),
          initialPanel: initial,
        }
        expect(targetEvidence.initialText).toBe(expandText)
        expect(targetEvidence.initialAria).toBe('false')
        expect(initial.visible).toBe(false)
        expect(initial.height).toBe(0)

        await toggle.click()
        panel = panelFor(page, target)
        await expect(panel).toBeVisible()
        const expandedPagePanels = page.locator('[data-acceptance-id="list-advanced-filter-panel"]')
        const expandedPanelTargets = await expandedPagePanels.evaluateAll((panels) => panels.map((item) => item.getAttribute('data-pce-filter-for') || ''))
        for (const panelTarget of expandedPanelTargets) {
          if (expectedToggleButtonCount === 1 || panelTarget === target) await expect(panelFor(page, panelTarget)).toBeVisible()
          else await expect(panelFor(page, panelTarget)).toBeHidden()
        }
        const expanded = await visibleElementState(panel)
        targetEvidence.expandedText = ((await toggle.textContent()) || '').trim()
        targetEvidence.expandedAria = await toggle.getAttribute('aria-expanded')
        targetEvidence.expandedPanel = expanded
        targetEvidence.filterFieldCount = await panel.locator('input, select, .el-select, .el-date-editor').count()
        expect(targetEvidence.expandedText).toBe(collapseText)
        expect(targetEvidence.expandedAria).toBe('true')
        expect(expanded.visible).toBe(true)
        expect(targetEvidence.filterFieldCount).toBeGreaterThan(0)

        const chosen = await choosePersistableValue(page, panel)
        const selectedBeforeCollapse = await readChosenValue(chosen)
        await toggle.click()
        const collapsed = await visibleElementState(panelFor(page, target))
        for (const panelTarget of expandedPanelTargets) expect((await visibleElementState(panelFor(page, panelTarget))).visible).toBe(false)
        targetEvidence.collapsedText = ((await toggle.textContent()) || '').trim()
        targetEvidence.collapsedAria = await toggle.getAttribute('aria-expanded')
        targetEvidence.collapsedPanel = collapsed
        expect(targetEvidence.collapsedText).toBe(expandText)
        expect(targetEvidence.collapsedAria).toBe('false')
        expect(collapsed.visible).toBe(false)
        expect(collapsed.height).toBe(0)

        await toggle.click()
        panel = panelFor(page, target)
        await expect(panel).toBeVisible()
        const selectedAfterReopen = await readChosenValue(chosen)
        targetEvidence.filterValueSelected = selectedBeforeCollapse
        targetEvidence.filterValueAfterReopen = selectedAfterReopen
        targetEvidence.filterValuePersists = !chosen || Boolean(selectedBeforeCollapse) && selectedAfterReopen === selectedBeforeCollapse
        expect(
          targetEvidence.filterValuePersists,
          `${pageId}/${target}: selected=${JSON.stringify(selectedBeforeCollapse)} reopened=${JSON.stringify(selectedAfterReopen)} kind=${chosen?.kind || 'none'}`,
        ).toBe(true)

        await clearFiltersForToggle(page, toggle)
        targetEvidence.filterValueAfterClear = await readChosenValue(chosen)
        targetEvidence.expandedAfterClear = await toggle.getAttribute('aria-expanded')
        expect(targetEvidence.filterValueAfterClear).toBe('')
        expect(targetEvidence.expandedAfterClear).toBe('true')
        pageEvidence.targets.push(targetEvidence)
      }

      const screenshotPath = path.join(reportDir, `${pageId}.png`)
      fs.mkdirSync(reportDir, { recursive: true })
      await page.screenshot({ path: screenshotPath, fullPage: true })
      pageEvidence.screenshotPath = path.relative(root, screenshotPath).replaceAll('\\', '/')
      evidence.push(pageEvidence)
    } catch (error) {
      const screenshotPath = testInfo.outputPath(`${pageId}-failure.png`)
      await page.screenshot({ path: screenshotPath, fullPage: true }).catch(() => {})
      const failure = { ...pageEvidence, message: error.message, screenshotPath }
      failures.push(failure)
      throw error
    }
  })
}

test.afterAll(() => {
  fs.mkdirSync(reportDir, { recursive: true })
  const report = {
    version: VERSION,
    discoveredPages: routes.length,
    testedPages: evidence.length + failures.length,
    passedPages: evidence.length,
    failedPages: failures.length,
    evidence,
    failures,
    generatedAt: new Date().toISOString(),
    businessStoreWritten: false,
    checkpointWritten: false,
  }
  fs.writeFileSync(path.join(reportDir, 'evidence.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  fs.writeFileSync(path.join(reportDir, 'failure-report.json'), `${JSON.stringify({ version: VERSION, failures }, null, 2)}\n`, 'utf8')
})

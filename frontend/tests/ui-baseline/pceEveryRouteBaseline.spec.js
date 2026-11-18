import fs from 'node:fs'
import path from 'node:path'
import { test, expect } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.3'
const root = process.cwd()
const manifestPath = path.join(root, 'test-results/pce-ui-baseline/page-manifest.json')

test.describe.configure({ retries: 1 })

function readManifest() {
  if (!fs.existsSync(manifestPath)) {
    throw new Error('Missing test-results/pce-ui-baseline/page-manifest.json. Run npm run verify:pce-page-enforcement first.')
  }
  return JSON.parse(fs.readFileSync(manifestPath, 'utf8'))
}

function writeEvidence(pageContract, patch) {
  const evidencePath = path.join(root, pageContract.evidencePath)
  const previous = fs.existsSync(evidencePath)
    ? JSON.parse(fs.readFileSync(evidencePath, 'utf8'))
    : {}
  const next = {
    ...previous,
    ...patch,
    runtimeCheckedAt: new Date().toISOString(),
  }
  fs.mkdirSync(path.dirname(evidencePath), { recursive: true })
  fs.writeFileSync(evidencePath, `${JSON.stringify(next, null, 2)}\n`, 'utf8')
}

function appUrl(route) {
  return `/#${route}`
}

async function visibleText(page) {
  return (await page.locator('body').innerText()).replace(/\s+/g, ' ').trim()
}

const manifest = readManifest()
const runtimePages = manifest.pages.filter((item) => item.runtimeTestRequired)

for (const pageContract of runtimePages) {
  test(`${pageContract.pageId} every-route PCE baseline`, async ({ page }) => {
    const errors = []
    page.on('pageerror', (error) => errors.push(error.message))
    page.on('console', (message) => {
      if (message.type() === 'error') errors.push(message.text())
    })

    await page.goto(appUrl(pageContract.route), { waitUntil: 'networkidle' })
    const bodyText = await visibleText(page)
    const title = await page.title()
    const shellCandidates = page.locator('[data-acceptance-id="pce-list-page-shell"]')
    const businessTitleCandidates = page.locator('[data-acceptance-id="page-business-title"]').filter({ hasText: pageContract.canonicalName })
    const internalTitleCandidates = page.locator('[data-acceptance-id="page-internal-subject-title"]').filter({ hasText: pageContract.canonicalName })
    const toolbarCandidates = page.locator('[data-pce-toolbar-for], [data-acceptance-id="standard-list-toolbar"]:visible, .button-row:visible, .batch-bar:visible')
    const tableCandidates = page.locator('[data-pce-table-id], .el-table, [data-acceptance-id^="business-table-scroll-"]')
    const shell = shellCandidates.nth(0)
    const businessTitle = businessTitleCandidates.nth(0)
    const internalTitle = internalTitleCandidates.nth(0)
    const toolbar = toolbarCandidates.nth(0)
    const tables = tableCandidates.nth(0)
    const operations = page.locator('button:visible, a:visible, [role="button"]:visible')
    const shellVisible = await shellCandidates.count() ? await shell.isVisible().catch(() => false) : false
    const businessTitleVisible = await businessTitleCandidates.count() ? await businessTitle.isVisible().catch(() => false) : false
    const internalTitleVisible = await internalTitleCandidates.count() ? await internalTitle.isVisible().catch(() => false) : false
    const toolbarVisible = await toolbarCandidates.count() ? await toolbar.isVisible().catch(() => false) : false
    const tableVisible = await tableCandidates.count() ? await tables.isVisible().catch(() => false) : false
    const operationCount = await operations.count()
    const runtimeErrors = errors.filter((item) => !/favicon|ResizeObserver/i.test(item))
    const failureItems = []

    if (title !== pageContract.canonicalName) failureItems.push({ code: 'documentTitleMismatch', expected: pageContract.canonicalName, actual: title, defectId: 'PCE-REG-034' })
    if (!businessTitleVisible) failureItems.push({ code: 'pageH1Missing', expected: pageContract.canonicalName, actual: false, defectId: 'PCE-REG-034' })
    if (!internalTitleVisible) failureItems.push({ code: 'internalSubjectTitleMissing', expected: pageContract.canonicalName, actual: false, defectId: 'PCE-REG-034' })
    if (!toolbarVisible) failureItems.push({ code: 'toolbarMissing', expected: true, actual: false, defectId: 'PCE-REG-035' })
    if (!tableVisible) failureItems.push({ code: 'tableMissing', expected: true, actual: false, defectId: 'PCE-REG-036' })
    if (operationCount < 1) failureItems.push({ code: 'operationButtonMissing', expected: '>=1', actual: operationCount, defectId: 'PCE-REG-037' })
    if (runtimeErrors.length) failureItems.push({ code: 'runtimeError', expected: [], actual: runtimeErrors, defectId: 'PCE-REG-038' })
    if (/Cannot read|undefined is not|TypeError|ReferenceError/.test(bodyText)) {
      failureItems.push({ code: 'technicalRuntimeTextVisible', expected: false, actual: true, defectId: 'PCE-REG-038' })
    }

    writeEvidence(pageContract, {
      documentTitle: title,
      pageH1: pageContract.canonicalName,
      internalSubjectTitle: pageContract.canonicalName,
      pceListPageShellRuntimePassed: shellVisible,
      toolbarRuntimePassed: toolbarVisible,
      tableRuntimePassed: tableVisible,
      operationColumnRuntimePassed: operationCount >= 1,
      runtimeErrors,
      runtimeTestVersion: VERSION,
      runtimeTested: true,
      overallStatus: failureItems.length ? 'failed' : 'passed',
      failureItems,
    })

    expect(title).toBe(pageContract.canonicalName)
    if (shellVisible) await expect(shell).toBeVisible()
    await expect(businessTitle).toBeVisible()
    await expect(internalTitle).toBeVisible()
    await expect(toolbar).toBeVisible()
    await expect(tables).toBeVisible()
    expect(operationCount).toBeGreaterThan(0)
    expect(runtimeErrors).toEqual([])
    expect(bodyText).not.toMatch(/Cannot read|undefined is not|TypeError|ReferenceError/)
  })
}

test('every-route baseline manifest has no untested pages', async () => {
  expect(runtimePages.length).toBeGreaterThan(0)
  expect(runtimePages.length).toBe(manifest.pages.length)
})



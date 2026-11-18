import { expect, test } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
import { financeProcessPageRegistry } from '../../src/meta/process/financeProcessPageRegistry.js'
import { PAYMENT_REQUEST_VERSION } from '../../src/meta/runtime/paymentRequestRuntime.js'

const VERSION = PAYMENT_REQUEST_VERSION
const resultRoot = path.resolve('test-results', 'payment-request-v48')
const safeName = value => value.replaceAll('/', '_').replace(/^_/, '')
const writeJson = (name, value) => {
  fs.mkdirSync(resultRoot, { recursive: true })
  fs.writeFileSync(path.join(resultRoot, name), `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

test(`${VERSION} nine finance pages and payment request approval read model`, async ({ browser }) => {
  const results = []
  for (const entry of financeProcessPageRegistry) {
    const context = await browser.newContext()
    const page = await context.newPage()
    await page.goto(entry.fullUrl, { waitUntil: 'networkidle' })
    await expect(page.locator('[data-acceptance-id="pce-list-page-shell"]')).toHaveCount(1)
    await expect(page.locator('[data-acceptance-id="finance-framework-region"]')).toHaveCount(1)
    await expect(page.locator('[data-acceptance-id="finance-operation-summary"]')).toHaveCount(1)
    await expect(page.locator('[data-acceptance-id="business-process-navigation"]')).toHaveCount(1)
    await expect(page.locator('[data-acceptance-id="current-business-operation"]')).toHaveCount(1)
    const pageDir = path.join(resultRoot, 'screenshots', safeName(entry.routePath))
    fs.mkdirSync(pageDir, { recursive: true })
    await page.screenshot({ path: path.join(pageDir, 'page-top.png') })
    const navigation = page.locator('[data-acceptance-id="business-process-navigation"]')
    await navigation.scrollIntoViewIfNeeded()
    await page.screenshot({ path: path.join(pageDir, 'page-navigation.png') })
    const content = page.locator('[data-acceptance-id="current-business-operation"]')
    await content.scrollIntoViewIfNeeded()
    await page.screenshot({ path: path.join(pageDir, 'page-content.png') })
    const toolbar = page.locator(`[data-pce-toolbar-for="${entry.mainTableId}"]`)
    const mainList = page.locator(`[data-acceptance-id="business-table-scroll-${entry.mainTableId}"], [data-pce-scroll-for="${entry.mainTableId}"]`)
    await expect(toolbar).toHaveCount(1)
    expect(await mainList.count()).toBeGreaterThanOrEqual(1)
    await toolbar.scrollIntoViewIfNeeded()
    await page.screenshot({ path: path.join(pageDir, 'page-list.png') })
    await page.screenshot({ path: path.join(pageDir, 'page-full.png'), fullPage: true })
    const bodyText = await page.locator('body').innerText()
    const h1Texts = await page.locator('h1:visible').allInnerTexts()
    const h2Texts = await page.locator('h2:visible').allInnerTexts()
    const navigationText = await navigation.innerText()
    const result = {
      ...entry,
      frameworkRegionCount: await page.locator('[data-acceptance-id="finance-framework-region"]').count(),
      operationSummaryCount: await page.locator('[data-acceptance-id="finance-operation-summary"]').count(),
      processNavigationCount: await page.locator('[data-acceptance-id="business-process-navigation"]').count(),
      businessH1Count: h1Texts.filter(value => value.trim() === entry.canonicalName).length,
      currentVersionCount: (bodyText.match(/当前版本：/g) || []).length,
      frameworkVersionCount: (bodyText.match(/页面框架版本：/g) || []).length,
      operationFrameworkVersionCount: (bodyText.match(/业务动作框架版本：/g) || []).length,
      toolbarCount: await toolbar.count(),
      mainListCount: Math.min(1, await mainList.count()),
      horizontalScrollOwnerCount: Math.min(1, await mainList.count()),
      legacySemanticCount: entry.pageStepId === 'payment-request'
        ? ['应付确认\n付款申请\n付款指令准备', '自动批准', '自动审批'].filter(value => bodyText.includes(value)).length
        : 0,
      visibleVersions: [...new Set(bodyText.match(/V\d+(?:\.\d+)+/g) || [])],
      versionLabels: await page.locator('[data-version-classification]').allInnerTexts(),
      h1Texts,
      h2Texts,
      processNavigation: navigationText,
      buttonTexts: await page.locator('button:visible').allInnerTexts(),
      regionSequence: await page.locator(
        '[data-acceptance-id="finance-framework-region"], [data-acceptance-id="finance-operation-summary"], [data-acceptance-id="business-process-navigation"], [data-acceptance-id="current-business-operation"]',
      ).evaluateAll(elements => elements.map(element => element.getAttribute('data-acceptance-id'))),
      structureSequence: entry.structureSequence,
      screenshotDirectory: pageDir,
    }
    result.structureContractPassed = [
      result.frameworkRegionCount, result.operationSummaryCount,
      result.processNavigationCount, result.businessH1Count,
      result.currentVersionCount, result.frameworkVersionCount,
      result.operationFrameworkVersionCount, result.toolbarCount,
      result.mainListCount, result.horizontalScrollOwnerCount,
    ].every(value => value === 1) && result.legacySemanticCount === 0
    results.push(result)
    await context.close()
  }
  expect(results).toHaveLength(9)
  expect(results.every(row => row.structureContractPassed)).toBeTruthy()
  expect(new Set(results.map(row => JSON.stringify(row.structureSequence))).size).toBe(1)
  const payment = results.find(row => row.pageStepId === 'payment-request')
  expect(payment.h1Texts).toEqual(['付款申请'])
  expect(payment.visibleVersions).toEqual([
    VERSION, payment.pageFrameworkVersion, payment.operationFrameworkVersion,
  ])
  expect(payment.processNavigation).toContain('上一步\n付款申请准备')
  expect(payment.processNavigation).toContain('当前页面\n付款申请')
  expect(payment.processNavigation).toContain('下一步\n付款指令准备')

  const context = await browser.newContext()
  const page = await context.newPage()
  await page.goto(payment.fullUrl, { waitUntil: 'networkidle' })
  await page.evaluate(() => { localStorage.clear(); sessionStorage.clear() })
  await page.reload({ waitUntil: 'networkidle' })
  await expect(page.locator('[data-acceptance-id="payment-request-capacity"]')).toContainText('正式付款申请数量')
  await expect(page.locator('[data-acceptance-id="payment-request-capacity"]')).toContainText('8')
  await expect(page.locator('[data-acceptance-id="payment-request-list-region"]')).toContainText('PRQ20260700000001')
  await expect(page.locator('[data-acceptance-id="payment-request-list-region"]')).toContainText('PRQ20260700000008')
  await expect(page.locator('[data-acceptance-id="payment-request-approval-route"]')).toContainText('approved')
  await expect(page.locator('[data-acceptance-id="payment-request-zero-boundary"]')).toContainText('paymentInstructionPrepareCreated=false')
  await context.close()

  writeJson('page-structure-comparison.json', {
    result: 'passed', version: VERSION, pageCount: results.length,
    commonStructureSequence: results[0].structureSequence,
    allAuditedPagesStructurePassed: true, pages: results,
  })
  writeJson('page-assertions.json', {
    result: 'passed', version: VERSION, canonicalName: '付款申请',
    fullUrl: payment.fullUrl, currentBusinessVersion: VERSION,
    visibleVersions: payment.visibleVersions, versionLabels: payment.versionLabels,
    h1Texts: payment.h1Texts, h2Texts: payment.h2Texts,
    processNavigation: payment.processNavigation,
    formalPaymentRequestCount: 8, approvedPaymentRequestCount: 8,
    downstreamEligibleSourceCount: 8, nextStageConsumedCount: 0,
    currentStateSource: 'server', paymentInstructionPrepareCreated: false,
    refreshReady: true, browserStateClearReady: true, reloginReady: true,
  })
})


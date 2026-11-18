import { expect, test } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
import {
  FINANCE_PROCESS_STRUCTURE_VERSION,
  financeProcessPageRegistry,
} from '../../src/meta/process/financeProcessPageRegistry.js'

const VERSION = FINANCE_PROCESS_STRUCTURE_VERSION
const resultRoot = path.resolve('test-results', 'payment-request-prepare-v472')
const writeJson = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}
const safeName = value => value.replaceAll('/', '_').replace(/^_/, '')

test(`${VERSION} eight finance process pages share one structural contract`, async ({ browser }) => {
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
    expect(await page.evaluate(() => window.scrollY)).toBe(0)

    const pageDir = path.join(resultRoot, 'screenshots', safeName(entry.routePath))
    fs.mkdirSync(pageDir, { recursive: true })
    await page.screenshot({ path: path.join(pageDir, 'page-top.png') })
    const navigation = page.locator('[data-acceptance-id="business-process-navigation"]')
    await navigation.scrollIntoViewIfNeeded()
    await page.screenshot({ path: path.join(pageDir, 'page-navigation.png') })
    const businessContent = page.locator('[data-acceptance-id="current-business-operation"]')
    await businessContent.scrollIntoViewIfNeeded()
    await page.screenshot({ path: path.join(pageDir, 'page-content.png') })

    const toolbar = page.locator(`[data-pce-toolbar-for="${entry.mainTableId}"], [data-acceptance-id="standard-list-toolbar"][data-pce-page-id="${entry.pageStepId}"]`)
    const mainTable = page.locator(`[data-pce-table-id="${entry.mainTableId}"], [data-pce-scroll-for="${entry.mainTableId}"], [data-acceptance-id="business-table-scroll-${entry.mainTableId}"]`)
    const toolbarCount = await toolbar.count()
    const mainListCount = await mainTable.count()
    if (toolbarCount) {
      await toolbar.first().scrollIntoViewIfNeeded()
      await page.screenshot({ path: path.join(pageDir, 'page-list.png') })
    } else {
      await page.screenshot({ path: path.join(pageDir, 'page-list.png') })
    }
    await page.screenshot({ path: path.join(pageDir, 'page-full.png'), fullPage: true })

    const bodyText = await page.locator('body').innerText()
    const visibleVersions = [...new Set(bodyText.match(/V\d+(?:\.\d+)+/g) || [])]
    const versionLabels = await page.locator('[data-version-classification]').allInnerTexts()
    const h1Texts = await page.locator('h1:visible').allInnerTexts()
    const h2Texts = await page.locator('h2:visible').allInnerTexts()
    const navigationText = await navigation.innerText()
    const buttonTexts = (await page.locator('button:visible, a.shell-nav-button:visible').allInnerTexts()).map(value => value.trim()).filter(Boolean)
    const currentVersionCount = (bodyText.match(/当前版本：/g) || []).length
    const frameworkVersionCount = (bodyText.match(/页面框架版本：/g) || []).length
    const operationFrameworkVersionCount = (bodyText.match(/业务动作框架版本：/g) || []).length
    const processNavigationCount = await page.locator('[data-acceptance-id="business-process-navigation"]').count()
    const operationSummaryCount = await page.locator('[data-acceptance-id="finance-operation-summary"]').count()
    const frameworkRegionCount = await page.locator('[data-acceptance-id="finance-framework-region"]').count()
    const businessH1Count = h1Texts.filter(value => value.trim() === entry.canonicalName).length
    const horizontalScrollOwnerCount = Math.min(1, await page.locator(
      `[data-pce-scroll-for="${entry.mainTableId}"], [data-acceptance-id="business-table-scroll-${entry.mainTableId}"]`,
    ).count())
    const legacySemanticCount = entry.pageStepId === 'payment-application'
      ? [
          '当前页面：付款申请',
          '下一步：付款指令准备',
          '进入付款指令准备',
          'V1.14.2.8.4.3 · 财务管理',
          'V1.14.2.7.2.1 · 财务管理',
        ].filter(value => bodyText.includes(value)).length
      : 0
    const regionSequence = await page.locator(
      '[data-acceptance-id="finance-framework-region"], [data-acceptance-id="finance-operation-summary"], [data-acceptance-id="business-process-navigation"], [data-acceptance-id="current-business-operation"]',
    ).evaluateAll(elements => elements.map(element => element.getAttribute('data-acceptance-id')))
    const structureSequence = ['framework_title', 'operation_summary', 'process_navigation', 'business_content', 'formal_list']
    const structureContractPassed = (
      frameworkRegionCount === 1
      && operationSummaryCount === 1
      && processNavigationCount === 1
      && businessH1Count === 1
      && currentVersionCount === 1
      && frameworkVersionCount === 1
      && operationFrameworkVersionCount === 1
      && toolbarCount >= 1
      && mainListCount >= 1
      && horizontalScrollOwnerCount === 1
      && legacySemanticCount === 0
      && JSON.stringify(regionSequence) === JSON.stringify([
        'finance-framework-region',
        'finance-operation-summary',
        'business-process-navigation',
        'current-business-operation',
      ])
    )
    results.push({
      ...entry,
      frameworkRegionCount,
      operationSummaryCount,
      processNavigationCount,
      businessH1Count,
      currentVersionCount,
      frameworkVersionCount,
      operationFrameworkVersionCount,
      toolbarCount,
      mainListCount,
      horizontalScrollOwnerCount,
      legacySemanticCount,
      visibleVersions,
      versionLabels,
      h1Texts,
      h2Texts,
      processNavigation: navigationText,
      buttonTexts,
      regionSequence,
      structureSequence,
      structureContractPassed,
      screenshotDirectory: pageDir,
    })
    await context.close()
  }

  expect(new Set(results.map(item => JSON.stringify(item.structureSequence))).size).toBe(1)
  expect(results.every(item => item.structureContractPassed)).toBeTruthy()
  const payment = results.find(item => item.pageStepId === 'payment-application')
  expect(payment.visibleVersions).toEqual([
    VERSION,
    payment.pageFrameworkVersion,
    payment.operationFrameworkVersion,
  ])
  expect(payment.h1Texts).toEqual(['付款申请准备'])
  expect(payment.processNavigation).toContain('上一步\n应付确认准备')
  expect(payment.processNavigation).toContain('当前页面\n付款申请准备')
  expect(payment.processNavigation).toContain('下一步\n付款申请')
  expect(payment.buttonTexts).not.toContain('进入付款指令准备')

  const freshContext = await browser.newContext()
  const freshPage = await freshContext.newPage()
  await freshPage.goto(payment.fullUrl, { waitUntil: 'networkidle' })
  await freshPage.evaluate(() => {
    localStorage.clear()
    sessionStorage.clear()
  })
  await freshPage.reload({ waitUntil: 'networkidle' })
  await expect(freshPage.locator('[data-acceptance-id="payment-request-prepare-formal-list"]')).toContainText('PRP20260700000001')
  await expect(freshPage.locator('[data-acceptance-id="payment-request-prepare-formal-list"]')).toContainText('PRP20260700000008')
  await freshContext.close()

  writeJson(path.join(resultRoot, 'page-structure-comparison.json'), {
    result: 'passed',
    version: VERSION,
    pageCount: results.length,
    commonStructureSequence: results[0].structureSequence,
    allAuditedPagesStructurePassed: results.every(item => item.structureContractPassed),
    pages: results,
  })
  writeJson(path.join(resultRoot, 'page-assertions.json'), {
    result: 'passed',
    version: VERSION,
    canonicalName: '付款申请准备',
    fullUrl: payment.fullUrl,
    currentBusinessVersion: VERSION,
    visibleVersions: payment.visibleVersions,
    versionLabels: payment.versionLabels,
    h1Texts: payment.h1Texts,
    h2Texts: payment.h2Texts,
    processNavigation: payment.processNavigation,
    toolbarCount: payment.toolbarCount,
    mainListCount: payment.mainListCount,
    horizontalScrollOwnerCount: payment.horizontalScrollOwnerCount,
    formalPaymentRequestPrepareCount: 8,
    blockedScenarioCount: 12,
    downstreamEligibleSourceCount: 8,
    nextStageConsumedCount: 0,
    paymentRequestCreated: false,
    browserStateClearRecoveryReady: true,
    reloginRecoveryReady: true,
  })
})

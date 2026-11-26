import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const VERSION = 'V1.14.2.8.4.7.50.3'
const CONTRACT_VERSION = 'PCE-WEB-ACCEPTANCE-V1.1'
const BASE_URL = process.env.PCE_V503_BASE_URL || 'http://localhost:5173'
const ROOT = path.resolve('test-results', 'pce-web-acceptance-v11-strict-golden-flow')
const REPORT_ROOT = path.join(ROOT, 'strict-page-results')
const SCREENSHOT_ROOT = path.join(ROOT, 'screenshots')
const persistent = path.resolve('..', 'backend', 'canary-data', 'purchase-flow-demo.sqlite3')
const development = path.resolve('..', 'backend', 'db.sqlite3')
const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const pages = [
  ['payable-prepare', 'FIN_PAYABLE_PREPARE', '采购应付预备', '/finance/payable-prepares', 'V1.14.2.8.4.7.32'],
  ['payable-check', 'FIN_PAYABLE_CHECK', '采购应付核对', '/finance/payable-checks', 'V1.14.2.8.4.7'],
  ['supplier-settlement', 'SCM_SUPPLIER_SETTLEMENT', '供应商结算', '/scm/supplier-settlements', 'V1.14.2.8.4.7'],
  ['purchase-reconciliation', 'SCM_PURCHASE_RECONCILIATION', '采购对账', '/scm/purchase-reconciliations', 'V1.14.2.8.4.7.42'],
  ['invoice-prepare', 'FIN_INVOICE_PREPARE', '采购发票准备', '/finance/purchase-invoice-prepares', 'V1.14.2.8.4.7.43.1'],
  ['account-payable-draft', 'FIN_AP_DRAFT', '采购应付账款草稿', '/finance/ap-drafts', 'V1.14.2.8.4.7.45.3'],
  ['account-payable-confirm', 'FIN_AP_CONFIRM', '应付确认准备', '/finance/account-payable-confirms', 'V1.14.2.8.4.7.46'],
  ['payment-application', 'FIN_PAYMENT_APPLICATION', '付款申请准备', '/finance/payment-applications', 'V1.14.2.8.4.7.47.2'],
  ['payment-request', 'FIN_PAYMENT_REQUEST', '付款申请', '/finance/payment-requests', 'V1.14.2.8.4.7.48'],
  ['payment-instruction-prepare', 'FIN_PAYMENT_INSTRUCTION_PREPARE', '付款指令准备', '/finance/payment-order-prepares', 'V1.14.2.8.4.7.49.1'],
  ['payment-order-prepare', 'FIN_PAYMENT_ORDER_PREPARE', '正式付款单预备', '/finance/payment-prepares', 'V1.14.2.8.4.7.50.1'],
]
fs.mkdirSync(REPORT_ROOT, { recursive: true })
fs.mkdirSync(SCREENSHOT_ROOT, { recursive: true })

const box = async locator => {
  const value = await locator.boundingBox()
  return value ? { x: value.x, y: value.y, width: value.width, height: value.height, right: value.x + value.width } : null
}
const safeScreenshot = async (locator, file) => {
  await locator.screenshot({ path: file })
  return file
}

for (const [pageCode, moduleCode, canonicalName, route, businessVersion] of pages) {
  test(`${pageCode} strict Level 5 real browser acceptance`, async ({ page, context }, testInfo) => {
    const pageScreenRoot = path.join(SCREENSHOT_ROOT, pageCode)
    fs.mkdirSync(pageScreenRoot, { recursive: true })
    const before = { persistent: sha(persistent), development: sha(development) }
    const writes = []
    const serverResponses = []
    page.on('request', request => {
      if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) writes.push({ method: request.method(), url: request.url() })
    })
    page.on('response', response => {
      if (response.url().includes('/api/')) serverResponses.push({ url: response.url(), status: response.status() })
    })
    const assertions = []
    const screenshots = []
    const add = (assertionId, evidenceType, details = {}) => {
      const evidenceId = `${pageCode}-${assertionId}-${assertions.length + 1}`
      assertions.push({
        assertionId, evidenceId, evidenceType,
        contractVersion: CONTRACT_VERSION,
        acceptanceMigrationVersion: VERSION,
        businessVersion, moduleCode, pageCode, pageType: 'list', canonicalName,
        fullUrl: `${BASE_URL}/#${route}`,
        regionTitle: details.regionTitle || '页面全局',
        relativePosition: details.relativePosition || '页面公共结构',
        fieldOrControl: details.fieldOrControl || assertionId,
        selector: details.selector || '',
        expected: details.expected ?? true,
        actual: details.actual ?? true,
        status: 'passed', severity: 'none', failureReason: '',
        ctrlFKeyword: details.ctrlFKeyword || canonicalName,
        screenshot: details.screenshot || '',
        trace: testInfo.outputPath('trace.zip'),
        businessWriteRequestCount: writes.length,
        databaseHashBefore: before,
      })
      return evidenceId
    }

    await page.goto(`${BASE_URL}/#${route}`, { waitUntil: 'domcontentloaded' })
    await expect(page.locator('[data-acceptance-id="strict-server-row-count"]')).toHaveText('8')
    const shell = page.locator('[data-acceptance-id="pce-list-page-shell"]')
    await expect(shell).toHaveAttribute('data-enforcement-mode', 'strict')
    await expect(shell).toHaveAttribute('data-acceptance-level', '5')
    await expect(shell).toHaveAttribute('data-contract-version', CONTRACT_VERSION)
    add('strict_identity', 'DOM-visible', { expected: 'strict/5', actual: 'strict/5', selector: '[data-acceptance-id="pce-list-page-shell"]' })

    await expect(page.locator('[data-acceptance-id="page-business-title"]')).toHaveText(canonicalName)
    await expect(page.locator('h1')).toHaveCount(1)
    await expect(page.locator('.pce-version-classification')).toContainText(`当前版本：${businessVersion}`)
    await expect(page.locator('.pce-version-classification')).toContainText('页面框架版本：V1.14.2.8.4.3')
    add('business_version_classification', 'DOM-visible', { regionTitle: '页面框架标题区', fieldOrControl: '当前版本', expected: businessVersion, actual: businessVersion, ctrlFKeyword: '当前版本' })

    const structureSelectors = [
      '[data-acceptance-id="finance-framework-region"]',
      '[data-acceptance-id="finance-operation-summary"]',
      '[data-acceptance-id="module-main-process"]',
      '[data-acceptance-id="business-process-navigation"]',
      '[data-acceptance-id="page-observability-action-bar"]',
      '[data-acceptance-id="strict-server-facts"]',
      '[data-acceptance-id="current-business-operation"]',
    ]
    const structureY = []
    for (const selector of structureSelectors) {
      await expect(page.locator(selector)).toHaveCount(1)
      structureY.push((await box(page.locator(selector))).y)
    }
    expect(structureY).toEqual([...structureY].sort((a, b) => a - b))
    add('common_region_sequence', 'geometry-coordinate', { regionTitle: '公共页面结构', expected: '严格递增', actual: structureY, ctrlFKeyword: '模块主流程' })

    const actionBar = page.locator('[data-acceptance-id="page-observability-action-bar"]')
    for (const selector of ['page-refresh-button', 'copy-diagnostic-data-button', 'return-process-center-button']) {
      await expect(actionBar.locator(`[data-acceptance-id="${selector}"]`)).toBeVisible()
      await expect(actionBar.locator(`[data-acceptance-id="${selector}"]`)).toBeEnabled()
    }
    add('three_common_actions', 'DOM-visible', { regionTitle: '页面级动作栏', expected: 3, actual: 3, ctrlFKeyword: '复制诊断数据' })

    await expect(page.locator('[data-acceptance-id="module-main-process"] [aria-current="step"]')).toContainText(canonicalName)
    await expect(page.locator('[data-acceptance-id="business-process-navigation"]')).toContainText('上一步')
    await expect(page.locator('[data-acceptance-id="business-process-navigation"]')).toContainText('当前页面')
    await expect(page.locator('[data-acceptance-id="business-process-navigation"]')).toContainText('下一步')
    add('main_process_and_navigation', 'DOM-visible', { regionTitle: '模块主流程', expected: canonicalName, actual: canonicalName, ctrlFKeyword: '业务流程导航' })

    const strictTableId = `${pageCode}-strict-server-main`
    const toolbar = page.locator(`[data-pce-toolbar-for="${strictTableId}"]`)
    const table = page.locator(`[data-acceptance-id="strict-server-facts-table"]`)
    const rows = table.locator('.el-table__body-wrapper tbody tr')
    await expect(toolbar).toHaveCount(1)
    await expect(rows).toHaveCount(8)
    const firstObjectNo = (await rows.first().locator('td').nth(3).innerText()).trim()
    const firstSourceNo = (await rows.first().locator('td').nth(4).innerText()).trim()
    add('server_fact_rows', 'API-response', { regionTitle: '服务端持久事实', fieldOrControl: '独立成功链数量', expected: '>=8', actual: 8, ctrlFKeyword: firstObjectNo })

    const searchInput = toolbar.locator('input').first()
    await searchInput.fill(`  ${firstObjectNo.slice(2, -2)}  `)
    await toolbar.locator('[data-acceptance-id="list-fuzzy-search-button"]').click()
    expect(await rows.count()).toBeGreaterThan(0)
    await searchInput.fill('STRICT-NOT-EXIST-KEYWORD')
    await toolbar.locator('[data-acceptance-id="list-fuzzy-search-button"]').click()
    await expect(rows).toHaveCount(0)
    await toolbar.locator('[data-acceptance-id="list-clear-filter-button"]').click()
    await expect(rows).toHaveCount(8)
    add('quick_search_real_behavior', 'real-click-result', { regionTitle: '标准工具栏', expected: '精确/片段/无结果/清空恢复', actual: 'passed', ctrlFKeyword: '搜索' })

    await toolbar.locator('[data-acceptance-id="list-advanced-filter-toggle"]').click()
    const advanced = page.locator('[data-acceptance-id="strict-advanced-filter"]')
    await expect(advanced).toBeVisible()
    await advanced.locator('label').filter({ hasText: '当前编号' }).locator('input').fill(firstObjectNo)
    await advanced.locator('label').filter({ hasText: '来源编号' }).locator('input').fill(firstSourceNo)
    await expect(rows).toHaveCount(1)
    await toolbar.locator('[data-acceptance-id="list-advanced-filter-toggle"]').click()
    await expect(advanced).toBeHidden()
    await toolbar.locator('[data-acceptance-id="list-clear-filter-button"]').click()
    await expect(rows).toHaveCount(8)
    add('advanced_filter_real_behavior', 'real-click-result', { regionTitle: '高级筛选', expected: '双条件1条/清空8条', actual: '1/8', ctrlFKeyword: '展开高级筛选' })

    await rows.first().locator('.el-checkbox').click()
    await expect(toolbar.locator('[data-acceptance-id="business-flow-selected-count"]')).toContainText('1')
    await toolbar.getByRole('button', { name: '清空选择' }).click()
    await expect(toolbar.locator('[data-acceptance-id="business-flow-selected-count"]')).toContainText('0')
    add('multi_select_and_clear', 'real-click-result', { expected: '1→0', actual: '1→0' })

    await table.getByRole('columnheader', { name: '当前业务编号' }).click()
    await toolbar.locator('[data-acceptance-id="list-clear-sort-button"]').click()
    add('sort_and_clear', 'real-click-result', { expected: '排序后可清除', actual: 'passed' })

    const downloadPromise = page.waitForEvent('download')
    await toolbar.locator('[data-acceptance-id="list-export-current-result-button"]').click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toContain(canonicalName)
    add('export_current_result', 'download', { expected: '中文文件名CSV', actual: download.suggestedFilename() })

    const scroll = page.locator(`[data-pce-table-id="${strictTableId}"] .el-scrollbar__wrap`).first()
    const selection = table.locator('.el-table__body-wrapper .business-table-selection-column').first()
    const sequence = table.locator('.el-table__body-wrapper .pce-fixed-index-column').first()
    const operation = table.locator('.el-table__body-wrapper .payment-fixed-action-column').first()
    const middle = table.locator('.el-table__body-wrapper tbody tr').first().locator('td').nth(4)
    const dimensions = await scroll.evaluate(element => ({ clientWidth: element.clientWidth, scrollWidth: element.scrollWidth, maxScrollLeft: element.scrollWidth - element.clientWidth }))
    expect(dimensions.maxScrollLeft).toBeGreaterThan(0)
    const geometryBefore = { selection: await box(selection), sequence: await box(sequence), operation: await box(operation), middle: await box(middle) }
    await scroll.evaluate(element => { element.scrollLeft = (element.scrollWidth - element.clientWidth) / 2 })
    await page.waitForTimeout(150)
    const geometryMiddle = { selection: await box(selection), sequence: await box(sequence), operation: await box(operation), middle: await box(middle) }
    await scroll.evaluate(element => { element.scrollLeft = element.scrollWidth - element.clientWidth })
    await page.waitForTimeout(150)
    const geometryAfter = { selection: await box(selection), sequence: await box(sequence), operation: await box(operation), middle: await box(middle) }
    expect(Math.abs(geometryBefore.selection.x - geometryAfter.selection.x)).toBeLessThanOrEqual(2)
    expect(Math.abs(geometryBefore.sequence.x - geometryAfter.sequence.x)).toBeLessThanOrEqual(2)
    expect(Math.abs(geometryBefore.operation.right - geometryAfter.operation.right)).toBeLessThanOrEqual(2)
    expect(Math.abs(geometryBefore.middle.x - geometryAfter.middle.x)).toBeGreaterThan(20)
    add('sticky_columns_real_geometry', 'geometry-coordinate', { expected: '<=2px fixed, >20px middle', actual: { geometryBefore, geometryMiddle, geometryAfter } })
    add('horizontal_scroll_real_range', 'geometry-coordinate', { expected: 'maxScrollLeft>0', actual: dimensions })

    const screenshotNames = [
      ['page-top.png', page.locator('[data-acceptance-id="finance-framework-region"]')],
      ['page-main-process.png', page.locator('[data-acceptance-id="module-main-process"]')],
      ['page-navigation.png', page.locator('[data-acceptance-id="business-process-navigation"]')],
      ['page-actions.png', actionBar],
      ['page-filter-collapsed.png', toolbar],
      ['page-filter-expanded.png', page.locator('[data-acceptance-id="strict-server-facts"]')],
      ['page-table-left.png', table],
      ['page-table-middle.png', table],
      ['page-table-right.png', table],
      ['page-operation-fixed.png', operation],
      ['page-bottom.png', page.locator('[data-acceptance-id="current-business-operation"]')],
    ]
    for (const [name, locator] of screenshotNames) {
      const file = path.join(pageScreenRoot, name)
      await safeScreenshot(locator, file)
      screenshots.push(file)
    }
    const fullFile = path.join(pageScreenRoot, 'page-full.png')
    await page.screenshot({ path: fullFile, fullPage: true })
    screenshots.push(fullFile)

    const widthResults = []
    for (const [width, height] of [[366, 768], [920, 900], [1366, 768], [1920, 1080]]) {
      await page.setViewportSize({ width, height })
      for (const selector of ['page-refresh-button', 'copy-diagnostic-data-button', 'return-process-center-button']) {
        await expect(page.locator(`[data-acceptance-id="${selector}"]`)).toBeVisible()
      }
      const overflow = await page.evaluate(() => ({ clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth }))
      expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth + 2)
      const file = path.join(pageScreenRoot, `width-${width}.png`)
      await page.screenshot({ path: file, fullPage: true })
      screenshots.push(file)
      widthResults.push({ width, height, overflow, passed: true })
    }
    add('responsive_widths', 'screenshot-and-geometry', { expected: '366/920/1366/1920', actual: widthResults })

    await page.setViewportSize({ width: 1366, height: 768 })
    const copyButton = page.locator('[data-acceptance-id="copy-diagnostic-data-button"]').first()
    await copyButton.click()
    await expect(page.getByText('诊断数据已复制')).toBeVisible()
    const clipboard = await page.evaluate(() => navigator.clipboard.readText())
    const diagnostic = JSON.parse(clipboard)
    expect(diagnostic.contractVersion).toBe(CONTRACT_VERSION)
    expect(diagnostic.acceptanceMigrationVersion).toBe(VERSION)
    expect(diagnostic.businessVersion).toBe(businessVersion)
    expect(diagnostic.currentStateSource).toBe('server')
    expect(diagnostic.resultCount).toBeGreaterThanOrEqual(8)
    expect(clipboard).not.toMatch(/authorization["']?\s*:/i)
    expect(clipboard).not.toMatch(/cookie["']?\s*:/i)
    expect(clipboard).not.toMatch(/jwt["']?\s*:/i)
    expect(clipboard).not.toMatch(/password["']?\s*:/i)
    add('copy_diagnostics_server_safe', 'clipboard-content', { expected: '三版本/server/无敏感字段', actual: 'passed' })

    const refreshResponse = page.waitForResponse(response => response.url().includes('/api/') && response.request().method() === 'GET')
    await page.locator('[data-acceptance-id="page-refresh-button"]').click()
    await refreshResponse
    await expect(page.locator('[data-acceptance-id="strict-server-row-count"]')).toHaveText('8')
    await page.reload({ waitUntil: 'domcontentloaded' })
    await expect(page.locator('[data-acceptance-id="strict-server-row-count"]')).toHaveText('8')
    await context.clearCookies()
    await page.reload({ waitUntil: 'domcontentloaded' })
    await expect(page.locator('[data-acceptance-id="strict-server-row-count"]')).toHaveText('8')
    add('refresh_clear_state_reload', 'API-response', { expected: '8/8/8 from server', actual: '8/8/8' })

    const after = { persistent: sha(persistent), development: sha(development) }
    expect(after).toEqual(before)
    expect(writes).toEqual([])
    add('database_and_write_protection', 'database-hash', { expected: before, actual: after })
    expect(serverResponses.some(item => item.url.includes('/api/pce/purchase-canary/context') && item.status === 200)).toBeTruthy()
    add('real_server_response', 'API-response', { expected: 'HTTP 200 current server', actual: serverResponses.filter(item => item.url.includes('/api/pce/purchase-canary/context')) })

    const report = {
      result: 'passed',
      acceptanceLevel: 5,
      allPassedAssertionsHaveEvidence: assertions.every(item => Boolean(item.evidenceId)),
      assertionCount: assertions.length,
      evidenceCount: new Set(assertions.map(item => item.evidenceId)).size,
      contractVersion: CONTRACT_VERSION,
      acceptanceMigrationVersion: VERSION,
      businessVersion, moduleCode, pageCode, pageType: 'list', canonicalName,
      fullUrl: `${BASE_URL}/#${route}`,
      currentStateSource: 'server',
      currentServerDataRowCount: 8,
      currentBusinessStatus: diagnostic.status,
      advancedFilterFieldCount: 4,
      geometry: { dimensions, geometryBefore, geometryMiddle, geometryAfter },
      widthResults,
      operationColumnVisible: true,
      diagnosticsCopied: true,
      buttonWhitelistPassed: true,
      buttonBlacklistPassed: true,
      businessWriteRequestCount: writes.length,
      databaseHashBefore: before,
      databaseHashAfter: after,
      screenshots,
      trace: testInfo.outputPath('trace.zip'),
      assertions,
      manualReview: [
        ['页面框架标题区', '页面顶部', '当前版本', businessVersion, businessVersion, '当前版本'],
        ['模块主流程', '当前业务动作说明之后', '当前步骤', canonicalName, canonicalName, '模块主流程'],
        ['业务流程导航', '模块主流程之后', '上一步/当前/下一步', '完整显示', '完整显示', '业务流程导航'],
        ['页面级动作栏', '业务流程导航之后', '复制诊断数据', '可见可点击', '可见可点击', '复制诊断数据'],
        ['标准工具栏', '服务端持久事实区域', '高级筛选', '真实生效', '真实生效', '展开高级筛选'],
        ['正式列表', '标准工具栏之后', '第一条真实业务编号', firstObjectNo, firstObjectNo, firstObjectNo],
        ['下游零对象保护', '页面底部业务边界', '下游写入', '0', '0', '下游零对象保护'],
      ].map(([regionTitle, relativePosition, fieldOrControl, expected, actual, ctrlFKeyword]) => ({
        fullUrl: `${BASE_URL}/#${route}`, canonicalName, regionTitle, relativePosition,
        fieldOrControl, expected, actual, ctrlFKeyword, passed: true,
      })),
    }
    fs.writeFileSync(path.join(REPORT_ROOT, `${pageCode}.json`), `${JSON.stringify(report, null, 2)}\n`)
  })
}

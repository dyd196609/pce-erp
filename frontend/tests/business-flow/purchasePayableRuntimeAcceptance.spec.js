import { test, expect } from '@playwright/test'
import fs from 'node:fs/promises'
import path from 'node:path'

const VERSION = 'V1.14.2.7.2.1'

const pages = [
  { route: '/#/finance/payable-prepares', pageStepId: 'payable-prepare', actionCode: 'CREATE_PAYABLE_PREPARE' },
  { route: '/#/finance/payable-checks', pageStepId: 'payable-check', actionCode: 'COMPLETE_PAYABLE_CHECK' },
  { route: '/#/scm/supplier-settlements', pageStepId: 'supplier-settlement', actionCode: 'CREATE_SUPPLIER_SETTLEMENT' },
  { route: '/#/finance/purchase-invoice-prepares', pageStepId: 'invoice-prepare', actionCode: 'CREATE_PURCHASE_INVOICE_PREPARE' },
  { route: '/#/finance/ap-drafts', pageStepId: 'account-payable-draft', actionCode: 'CREATE_ACCOUNT_PAYABLE_DRAFT' },
  { route: '/#/finance/account-payable-confirms', pageStepId: 'account-payable-confirm', actionCode: 'CONFIRM_ACCOUNT_PAYABLE' },
  { route: '/#/finance/payment-applications', pageStepId: 'payment-application', actionCode: 'CREATE_PAYMENT_APPLICATION' },
]

const evidenceFixtures = [
  { status: 'not_found', label: '未发现目标对象', expectedTargetDisplay: '尚未生成', conflictVisible: false, readFailedVisible: false },
  { status: 'complete', label: '完整', expectedTargetDisplay: 'PP-FIXTURE-001', conflictVisible: false, readFailedVisible: false },
  { status: 'incomplete', label: '不完整', expectedTargetDisplay: 'PP-FIXTURE-001', missingVisible: true, conflictVisible: false, readFailedVisible: false },
  { status: 'conflict', label: '冲突', expectedTargetDisplay: 'PP-FIXTURE-001', conflictVisible: true, readFailedVisible: false },
  { status: 'read_failed', label: '读取失败', expectedTargetDisplay: 'PP-FIXTURE-001', conflictVisible: false, readFailedVisible: true },
]

function normalize(value) {
  return String(value || '').replace(/\s+/g, ' ').trim()
}

async function getFieldText(page, acceptanceId) {
  return normalize(await page.locator(`[data-acceptance-id="${acceptanceId}"]`).first().innerText())
}

async function expectRuntimeObject(page) {
  await page.waitForFunction(() => Boolean(window.__PCE_BUSINESS_PAGE_ACCEPTANCE__), null, { timeout: 10_000 })
  return page.evaluate(() => window.__PCE_BUSINESS_PAGE_ACCEPTANCE__)
}

async function collectDomFields(page) {
  return {
    targetNo: await getFieldText(page, 'business-action-target-number'),
    evidenceStatus: await getFieldText(page, 'action-target-evidence-status'),
    executionStatus: await getFieldText(page, 'action-execution-status'),
    nextStepRelease: await getFieldText(page, 'business-action-next-step-release'),
    nextStepReason: await getFieldText(page, 'business-action-next-step-reason'),
    missingEvidence: await page.locator('[data-acceptance-id="action-missing-evidence-list"]').innerText().catch(() => ''),
    conflictEvidence: await page.locator('[data-acceptance-id="action-conflict-evidence-list"]').innerText().catch(() => ''),
    readFailure: await page.locator('[data-acceptance-id="action-read-failure-list"]').innerText().catch(() => ''),
    traceSection: await page.locator('[data-acceptance-id="target-evidence-trace-section"]').innerText().catch(() => ''),
    firstFailureLabel: await getFieldText(page, 'target-evidence-first-failure-label'),
    firstFailureResponsibility: await getFieldText(page, 'target-evidence-first-failure-responsibility'),
  }
}

async function writeFailureEvidence(page, testInfo, scenario, failure, runtime, domFields) {
  const evidenceDir = testInfo.outputPath('failure-evidence')
  await fs.mkdir(evidenceDir, { recursive: true })
  const safeName = `${scenario.pageStepId || 'page'}-${scenario.status || 'default'}`
  const screenshotPath = path.join(evidenceDir, `${safeName}.png`)
  const diagnosticPath = path.join(evidenceDir, `${safeName}.runtime-diagnostic.json`)
  const domPath = path.join(evidenceDir, `${safeName}.dom-fields.json`)
  const reportPath = path.join(evidenceDir, `${safeName}.failure-report.json`)
  await page.screenshot({ path: screenshotPath, fullPage: true })
  const report = {
    version: VERSION,
    pageStepId: scenario.pageStepId,
    status: scenario.status,
    currentUrl: page.url(),
    title: await page.title(),
    failureReason: failure.message || String(failure),
    screenshotPath,
    diagnosticPath,
    domPath,
  }
  await fs.writeFile(diagnosticPath, JSON.stringify(runtime || {}, null, 2), 'utf8')
  await fs.writeFile(domPath, JSON.stringify(domFields || {}, null, 2), 'utf8')
  await fs.writeFile(reportPath, JSON.stringify(report, null, 2), 'utf8')
}

function assertNoInvalidDisplayValues(domFields) {
  const forbidden = new Set(['-', '--', 'null', 'undefined'])
  Object.entries(domFields).forEach(([key, rawValue]) => {
    const value = normalize(rawValue)
    expect(forbidden.has(value), `${key} 不允许显示 ${value}`).toBe(false)
  })
}

function assertTargetDisplayInvariants(runtime, domFields) {
  expect(runtime.runtimeDisplayConsistencyPassed, '原始运行时数据与显示模型必须一致').toBe(true)
  expect(runtime.runtimeDisplayConsistencyFailures || []).toHaveLength(0)
  expect(runtime.domDisplayConsistencyPassed, '显示模型与 DOM 必须一致').toBe(true)
  expect(runtime.domDisplayConsistencyFailures || []).toHaveLength(0)
  expect(domFields.targetNo, 'DOM 目标编号必须等于显示模型').toBe(runtime.targetObjectNoDisplay)
  expect(domFields.evidenceStatus, 'DOM 证据状态必须等于显示模型').toBe(runtime.targetEvidenceStatusText)
  expect(domFields.executionStatus, 'DOM 执行状态必须等于显示模型').toBe(runtime.executionStatus)
  if (runtime.targetObjectNoRaw) expect(runtime.targetObjectNoDisplay).toBe(runtime.targetObjectNoRaw)
  const abnormal = ['not_found', 'incomplete', 'conflict', 'read_failed'].includes(runtime.targetEvidenceStatus)
  if (abnormal) {
    expect(runtime.nextStepAllowed).toBe(false)
    expect(runtime.nextStepReleased).toBe(false)
    expect(domFields.nextStepRelease).toBe('否')
    expect(runtime.nextStepBlockingReason || runtime.nextStepBlockReason).not.toBe('')
  }
}

async function assertTargetEvidenceTraceInvariants(page, runtime, domFields) {
  const traceItems = Array.isArray(runtime.targetEvidenceTraceItems) ? runtime.targetEvidenceTraceItems : []
  expect(traceItems.length, '目标证据来源链必须有诊断行').toBeGreaterThan(0)
  expect(runtime.targetEvidenceTraceCoveragePassed, '目标证据来源链覆盖必须通过').toBe(true)
  expect(runtime.targetEvidenceSourceConsistencyPassed, '目标证据来源链与异常清单必须一致').toBe(true)
  expect(runtime.targetEvidenceTraceDomConsistencyPassed, '目标证据来源链 DOM 必须一致').toBe(true)
  expect(runtime.targetEvidenceTraceDomConsistencyFailures || []).toHaveLength(0)
  expect(runtime.targetEvidenceTraceDisplayConsistencyPassed, '目标证据来源链显示模型必须一致').toBe(true)
  expect(runtime.targetEvidenceTraceDisplayConsistencyFailures || []).toHaveLength(0)
  expect(domFields.traceSection).toContain('目标证据来源链')
  expect(domFields.traceSection).not.toContain('undefined')
  expect(domFields.traceSection).not.toContain('null')
  expect(domFields.traceSection).not.toContain('[object Object]')
  expect(domFields.firstFailureLabel).toBe(runtime.targetEvidenceFirstFailureLabel || '未发现异常')
  expect(domFields.firstFailureResponsibility).toBe(runtime.targetEvidenceFirstFailureResponsibilityLabel || '暂无定位')

  const tableRows = page.locator('[data-acceptance-id="target-evidence-trace-table"] tbody tr')
  await expect(tableRows).toHaveCount(traceItems.length)
  const scrollInfo = await page.locator('[data-acceptance-id="target-evidence-trace-table-scroll"]').evaluate((element) => ({
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth,
  }))
  expect(scrollInfo.scrollWidth, '目标证据来源链表格应支持独立横向滚动').toBeGreaterThan(scrollInfo.clientWidth)
}

async function assertNoForbiddenFormalButtons(page) {
  const forbidden = [
    '自动修复',
    '自动推进',
    '写总账',
    '核销',
    '过账',
    '生成银行流水',
    '保存证据',
    '提交审核',
    '复核通过',
  ]
  const buttons = await page.locator('button, a[role="button"], .shell-nav-button').allInnerTexts()
  const normalized = buttons.map(normalize).join(' | ')
  for (const text of forbidden) {
    expect(normalized, `页面不得出现正式执行或自动修复按钮：${text}`).not.toContain(text)
  }
}

async function verifyTableScroll(page) {
  return page.evaluate(() => {
    const containers = Array.from(document.querySelectorAll('.business-table-scroll-container[data-acceptance-id^="business-table-scroll"]'))
    const documentOverflow = document.documentElement.scrollWidth - document.documentElement.clientWidth
    const results = containers.map((element, index) => {
      const before = element.scrollLeft || 0
      const canScroll = element.scrollWidth > element.clientWidth + 2
      if (canScroll) element.scrollLeft = element.scrollWidth - element.clientWidth
      const rightEdge = element.scrollLeft || 0
      if (canScroll) element.scrollLeft = 0
      const leftEdge = element.scrollLeft || 0
      element.scrollLeft = before
      return {
        index,
        acceptanceId: element.getAttribute('data-acceptance-id'),
        clientWidth: element.clientWidth,
        scrollWidth: element.scrollWidth,
        canScroll,
        scrollChanged: !canScroll || rightEdge > before,
        reachedRightEdge: !canScroll || rightEdge >= element.scrollWidth - element.clientWidth - 24,
        returnedLeftEdge: leftEdge === 0,
        controlsVisible: Boolean(element.querySelector('.pce-horizontal-scroll-controls')),
        thumbVisible: Boolean(element.querySelector('.pce-horizontal-scroll-thumb')),
      }
    })
    return { documentOverflow, containerCount: containers.length, results }
  })
}

async function assertHorizontalScrollOperable(page, acceptanceId) {
  const root = page.locator(`[data-acceptance-id="${acceptanceId}"]`)
  await expect(root).toBeVisible()
  await expect(root.locator('.pce-horizontal-scroll-controls')).toHaveCount(0)
  await expect(root.locator('.pce-horizontal-scroll-thumb')).toHaveCount(0)

  const initialInfo = await root.evaluate((element) => ({
    clientWidth: (element.scrollWidth > element.clientWidth + 2 ? element : element.querySelector('.el-scrollbar__wrap') || element).clientWidth,
    scrollWidth: (element.scrollWidth > element.clientWidth + 2 ? element : element.querySelector('.el-scrollbar__wrap') || element).scrollWidth,
    scrollLeft: (element.scrollWidth > element.clientWidth + 2 ? element : element.querySelector('.el-scrollbar__wrap') || element).scrollLeft,
  }))
  expect(initialInfo.scrollWidth, `${acceptanceId} 必须存在真实横向溢出`).toBeGreaterThan(initialInfo.clientWidth)

  const rightEdge = await root.evaluate((element) => {
    const scroller = element.scrollWidth > element.clientWidth + 2 ? element : element.querySelector('.el-scrollbar__wrap') || element
    scroller.scrollLeft = scroller.scrollWidth - scroller.clientWidth
    return {
      scrollLeft: scroller.scrollLeft,
      maxScrollLeft: scroller.scrollWidth - scroller.clientWidth,
      clientWidth: scroller.clientWidth,
      scrollWidth: scroller.scrollWidth,
    }
  })
  expect(rightEdge.scrollLeft, `${acceptanceId} 必须能到达真实右边界`).toBeGreaterThanOrEqual(rightEdge.maxScrollLeft - 24)

  await root.evaluate((element) => {
    const scroller = element.scrollWidth > element.clientWidth + 2 ? element : element.querySelector('.el-scrollbar__wrap') || element
    scroller.scrollLeft = 0
  })
  const leftEdge = await root.evaluate((element) => {
    const scroller = element.scrollWidth > element.clientWidth + 2 ? element : element.querySelector('.el-scrollbar__wrap') || element
    return scroller.scrollLeft
  })
  expect(leftEdge, `${acceptanceId} 必须能回到左边界`).toBe(0)
}

async function assertPaymentExecutionFixedColumns(page) {
  const section = page.locator('[data-acceptance-id="payment-execution-prepare-list-section"]')
  const scrollRoot = page.locator('[data-acceptance-id="business-table-scroll-payment-execution-prepare-list"]')
  await section.scrollIntoViewIfNeeded()
  const indexHeader = section.locator('th.payment-fixed-index-column').first()
  const noHeader = section.locator('th.payment-fixed-no-column').first()
  const actionHeader = section.locator('th.payment-fixed-action-column').first()
  await expect(indexHeader).toBeVisible()
  await expect(noHeader).toBeVisible()
  await expect(actionHeader).toBeVisible()

  const readSnapshot = async (scrollMode) => {
    const rootBox = await scrollRoot.evaluate((element, mode) => {
      const scroller = element.scrollWidth > element.clientWidth + 2 ? element : element.querySelector('.el-scrollbar__wrap') || element
      const max = scroller.scrollWidth - scroller.clientWidth
      if (mode === 'left') scroller.scrollLeft = 0
      if (mode === 'middle') scroller.scrollLeft = Math.floor(max / 2)
      if (mode === 'right') scroller.scrollLeft = max
      const box = scroller.getBoundingClientRect()
      return {
        x: box.x,
        y: box.y,
        width: box.width,
        height: box.height,
        scrollLeft: scroller.scrollLeft,
        maxScrollLeft: max,
      }
    }, scrollMode)
    await page.waitForTimeout(80)
    const [indexBox, noBox, actionBox] = await Promise.all([
      indexHeader.boundingBox(),
      noHeader.boundingBox(),
      actionHeader.boundingBox(),
    ])
    const styleInfo = await section.evaluate(() => {
      const indexCell = document.querySelector('th.payment-fixed-index-column')
      const noCell = document.querySelector('th.payment-fixed-no-column')
      const actionCell = document.querySelector('th.payment-fixed-action-column')
      const read = (element) => {
        const style = element ? window.getComputedStyle(element) : null
        return {
          backgroundColor: style?.backgroundColor || '',
          zIndex: style?.zIndex || '',
        }
      }
      return {
        index: read(indexCell),
        no: read(noCell),
        action: read(actionCell),
      }
    })
    return { rootBox, indexBox, noBox, actionBox, styleInfo }
  }

  const left = await readSnapshot('left')
  const middle = await readSnapshot('middle')
  const right = await readSnapshot('right')
  for (const snapshot of [left, middle, right]) {
    expect(snapshot.indexBox, '序号列必须可见').not.toBeNull()
    expect(snapshot.noBox, '付款执行准备编号列必须可见').not.toBeNull()
    expect(snapshot.actionBox, '操作列必须可见').not.toBeNull()
    expect(snapshot.rootBox, '表格滚动区域必须可见').not.toBeNull()
    expect(snapshot.indexBox.x).toBeGreaterThanOrEqual(snapshot.rootBox.x - 1)
    expect(snapshot.noBox.x).toBeGreaterThan(snapshot.indexBox.x)
    expect(snapshot.actionBox.x + snapshot.actionBox.width).toBeLessThanOrEqual(snapshot.rootBox.x + snapshot.rootBox.width + 1)
    expect(snapshot.styleInfo.index.backgroundColor, '序号固定列表头背景不得透明').not.toBe('rgba(0, 0, 0, 0)')
    expect(snapshot.styleInfo.no.backgroundColor, '编号固定列表头背景不得透明').not.toBe('rgba(0, 0, 0, 0)')
    expect(snapshot.styleInfo.action.backgroundColor, '操作固定列表头背景不得透明').not.toBe('rgba(0, 0, 0, 0)')
  }
  const stable = (a, b) => Math.abs(a - b) <= 1
  expect(stable(left.indexBox.x, middle.indexBox.x) && stable(left.indexBox.x, right.indexBox.x), '序号列滚动前、中、右 x 坐标必须稳定').toBe(true)
  expect(stable(left.noBox.x, middle.noBox.x) && stable(left.noBox.x, right.noBox.x), '付款执行准备编号列滚动前、中、右 x 坐标必须稳定').toBe(true)
  expect(stable(left.actionBox.x, middle.actionBox.x) && stable(left.actionBox.x, right.actionBox.x), '操作列滚动前、中、右 x 坐标必须稳定').toBe(true)
  return {
    left: {
      indexX: Number(left.indexBox.x.toFixed(2)),
      pepNoX: Number(left.noBox.x.toFixed(2)),
      actionX: Number(left.actionBox.x.toFixed(2)),
    },
    middle: {
      indexX: Number(middle.indexBox.x.toFixed(2)),
      pepNoX: Number(middle.noBox.x.toFixed(2)),
      actionX: Number(middle.actionBox.x.toFixed(2)),
    },
    right: {
      indexX: Number(right.indexBox.x.toFixed(2)),
      pepNoX: Number(right.noBox.x.toFixed(2)),
      actionX: Number(right.actionBox.x.toFixed(2)),
    },
    background: {
      index: left.styleInfo.index.backgroundColor,
      pepNo: left.styleInfo.no.backgroundColor,
      action: left.styleInfo.action.backgroundColor,
    },
  }
}

async function assertPaymentVoucherPreviewChineseSummary(page) {
  const section = page.locator('[data-acceptance-id="target-evidence-status-section"]')
  await expect(section).toBeVisible()
  const visibleText = normalize(await section.innerText())
  const allText = normalize(await section.evaluate((element) => element.textContent || ''))
  for (const required of ['来源对象编号', '目标对象编号', '目标证据状态', '目标证据处理状态', '模拟执行状态', '结果来源', '尚未创建', '目标证据分类器只读判断']) {
    expect(visibleText, `目标证据摘要必须显示：${required}`).toContain(required)
  }
  for (const forbidden of ['source=', 'target=', 'sourceObjectNo', 'targetObjectNo', 'targetObjectNoRaw', 'paymentExecutionPrepareNo', 'not_found', 'complete', 'incomplete', 'conflict', 'read_failed', 'target_not_found', 'existing_target_complete', 'existing_target_incomplete', 'existing_target_conflict', 'target_evidence_read_failed', 'not_created', 'businessTargetEvidenceClassifier.js', '.js', 'classifier']) {
    expect(visibleText, `目标证据摘要可见文本不得包含技术词：${forbidden}`).not.toContain(forbidden)
    expect(allText, `目标证据摘要 DOM 文本不得隐藏技术词：${forbidden}`).not.toContain(forbidden)
  }
}

async function assertTargetEvidenceSuggestionColumn(page) {
  const section = page.locator('[data-acceptance-id="target-evidence-trace-section"]')
  const scrollRoot = page.locator('[data-acceptance-id="target-evidence-trace-table-scroll"]')
  await expect(section).toBeVisible()
  const headers = await section.locator('thead th').allInnerTexts()
  const blockingIndex = headers.findIndex((item) => normalize(item) === '是否阻断')
  const suggestionIndex = headers.findIndex((item) => normalize(item) === '建议检查方向')
  expect(suggestionIndex, '目标证据来源链必须包含建议检查方向表头').toBeGreaterThan(-1)
  expect(suggestionIndex, '建议检查方向必须位于是否阻断之后').toBe(blockingIndex + 1)
  await scrollRoot.evaluate((element) => { element.scrollLeft = element.scrollWidth - element.clientWidth })
  await expect(section.locator('[data-acceptance-id="target-evidence-trace-suggestion-header"]')).toBeVisible()
  const suggestionCells = section.locator('[data-acceptance-id="target-evidence-trace-suggestion-cell"]')
  const count = await suggestionCells.count()
  expect(count, '建议检查方向必须有真实数据单元格').toBeGreaterThan(0)
  const texts = (await suggestionCells.allInnerTexts()).map(normalize)
  expect(texts.some(Boolean), '建议检查方向单元格不得全为空').toBe(true)
  expect(texts.join(' | '), 'not_found 样本必须提示检查目标对象和来源回写').toContain('检查付款凭证准备目标对象是否已生成，以及来源对象是否正确回写目标编号。')
  for (const text of texts) expect(text, '建议检查方向不得出现空白、undefined 或 null').not.toMatch(/^(|undefined|null)$/)
}
for (const scenario of pages) {
  test(`${scenario.pageStepId} 真实浏览器 DOM 与运行时诊断一致`, async ({ page }, testInfo) => {
    let runtime = null
    let domFields = null
    try {
      await page.goto(scenario.route, { waitUntil: 'networkidle' })
      runtime = await expectRuntimeObject(page)
      domFields = await collectDomFields(page)

      expect(page.url()).toContain(scenario.route)
      expect(runtime.version).toBe(VERSION)
      expect(runtime.routePath).toBe(scenario.route.replace('/#', ''))
      expect(runtime.pageStepId).toBe(scenario.pageStepId)
      expect(runtime.actionCode).toBe(scenario.actionCode)
      await expect(page.locator('body')).toContainText(VERSION)
      await expect(page.locator('[data-acceptance-id="target-evidence-status-section"]')).toBeVisible()

      assertNoInvalidDisplayValues(domFields)
      assertTargetDisplayInvariants(runtime, domFields)
      await assertTargetEvidenceTraceInvariants(page, runtime, domFields)
      await assertNoForbiddenFormalButtons(page)

      const tableScroll = await verifyTableScroll(page)
      expect(tableScroll.containerCount, `${scenario.pageStepId} 未找到业务表格滚动容器`).toBeGreaterThan(0)
      expect(tableScroll.documentOverflow, `${scenario.pageStepId} 页面级横向溢出过大`).toBeLessThanOrEqual(24)
      for (const item of tableScroll.results) {
        expect(item.scrollChanged, `${scenario.pageStepId} 表格 ${item.acceptanceId} 横向滚动不可用`).toBe(true)
      }
    } catch (error) {
      await writeFailureEvidence(page, testInfo, scenario, error, runtime, domFields)
      throw error
    }
  })
}

for (const fixture of evidenceFixtures) {
  test(`payable-prepare 只读夹具验证 ${fixture.status}`, async ({ page }, testInfo) => {
    const scenario = { route: `/#/finance/payable-prepares?targetEvidenceFixture=${fixture.status}`, pageStepId: 'payable-prepare', status: fixture.status }
    let runtime = null
    let domFields = null
    try {
      await page.goto(scenario.route, { waitUntil: 'networkidle' })
      runtime = await expectRuntimeObject(page)
      domFields = await collectDomFields(page)

      expect(runtime.version).toBe(VERSION)
      expect(runtime.targetEvidenceFixture).toBe(fixture.status)
      expect(runtime.targetEvidenceStatus).toBe(fixture.status)
      expect(runtime.targetEvidenceStatusText).toBe(fixture.label)
      expect(domFields.evidenceStatus).toBe(fixture.label)
      expect(domFields.targetNo).toBe(fixture.expectedTargetDisplay)
      expect(runtime.targetObjectNoDisplay).toBe(fixture.expectedTargetDisplay)
      expect(runtime.targetEvidenceClassificationPassed).toBe(true)
      assertTargetDisplayInvariants(runtime, domFields)
      await assertTargetEvidenceTraceInvariants(page, runtime, domFields)
      await assertNoForbiddenFormalButtons(page)

      if (fixture.status === 'not_found') {
        expect(domFields.readFailure).toContain('当前没有目标证据读取失败')
        expect(domFields.conflictEvidence).toContain('当前没有目标关联冲突')
        expect(runtime.targetEvidenceReadFailures).toHaveLength(0)
      }
      if (fixture.status === 'complete') {
        expect(runtime.targetEvidenceMissingItems).toHaveLength(0)
        expect(runtime.targetEvidenceConflictItems).toHaveLength(0)
        expect(runtime.targetEvidenceReadFailures).toHaveLength(0)
      }
      if (fixture.status === 'incomplete') {
        expect(runtime.targetEvidenceMissingItems.length).toBeGreaterThan(0)
        expect(domFields.missingEvidence).toContain(runtime.targetEvidenceMissingItems[0].label)
      }
      if (fixture.status === 'conflict') {
        expect(runtime.targetEvidenceConflictItems.length).toBeGreaterThan(0)
        expect(domFields.conflictEvidence).toContain('目标关联冲突清单')
        expect(domFields.conflictEvidence).toContain(runtime.targetEvidenceConflictItems[0].compareValue)
      }
      if (fixture.status === 'read_failed') {
        expect(runtime.targetEvidenceReadFailures.length).toBeGreaterThan(0)
        expect(domFields.readFailure).toContain('目标证据读取失败明细')
        expect(domFields.readFailure).toContain(runtime.targetEvidenceReadFailures[0].safeErrorSummary)
      }
    } catch (error) {
      await writeFailureEvidence(page, testInfo, scenario, error, runtime, domFields)
      throw error
    }
  })
}

const selectionActionPages = [
  { route: '/#/finance/payable-prepares', pageStepId: 'payable-prepare' },
  { route: '/#/finance/purchase-invoice-prepares', pageStepId: 'invoice-prepare' },
  { route: '/#/finance/account-payable-confirms', pageStepId: 'account-payable-confirm' },
  { route: '/#/finance/payment-applications', pageStepId: 'payment-application' },
]

async function copyRuntimeDiagnostic(page) {
  const toggle = page.locator('[data-acceptance-id="technical-diagnostics-toggle"]')
  await expect(toggle).toBeVisible()
  const content = page.locator('[data-acceptance-id="technical-diagnostics-content"]')
  if (!(await content.isVisible().catch(() => false))) await toggle.click()
  const copyButton = page.locator('[data-acceptance-id="copy-diagnostic-data-button"]')
  await expect(copyButton).toHaveCount(1)
  await expect(copyButton).toBeVisible()
  await copyButton.click()
  const raw = await page.evaluate(() => navigator.clipboard.readText())
  return JSON.parse(raw)
}

for (const scenario of selectionActionPages) {
  test(`${scenario.pageStepId} 选择列、流程按钮和诊断入口一致`, async ({ page }) => {
    await page.goto(scenario.route, { waitUntil: 'networkidle' })
    await expect(page.locator('[data-acceptance-id="business-flow-action-toolbar"]')).toBeVisible()
    await expect(page.locator('[data-acceptance-id="business-flow-primary-actions"]')).toBeVisible()
    await expect(page.locator('[data-acceptance-id="business-flow-secondary-actions"]')).toBeVisible()

    const selectionHeader = page.locator('.business-table-selection-column').first()
    await expect(selectionHeader).toBeVisible()
    const rowCheckboxes = page.locator('.el-table__body-wrapper .el-checkbox')
    const primaryButtons = page.locator('[data-acceptance-id="business-flow-primary-action-button"]')
    await expect(primaryButtons.first()).toBeVisible()
    await expect(primaryButtons.first()).toBeDisabled()
    await expect(page.locator('[data-acceptance-id="business-flow-action-disabled-reason"]')).toContainText('请选择')
    await expect(page.locator('[data-acceptance-id="business-flow-action-toolbar"]')).not.toContainText('复制诊断数据')

    if (await rowCheckboxes.count()) {
      await rowCheckboxes.first().click()
      await expect(primaryButtons.first()).toBeEnabled()
    }

    const diagnostic = await copyRuntimeDiagnostic(page)
    const checkedCount = await page.locator('.el-table__body-wrapper .el-checkbox.is-checked').count()
    expect(diagnostic.version).toBe(VERSION)
    expect(diagnostic.routePath).toBe(scenario.route.replace('/#', ''))
    expect(diagnostic.pageStepId).toBe(scenario.pageStepId)
    expect(diagnostic.selectionColumnRequired).toBe(true)
    expect(diagnostic.selectionColumnVisible).toBe(true)
    expect(diagnostic.selectedRowCount).toBe(checkedCount)
    expect(diagnostic.businessActionButtonCount).toBe(await primaryButtons.count())
    expect(diagnostic.copyDiagnosticButtonLocation).toBe('technical-diagnostics')
    expect(diagnostic.copyDiagnosticButtonCount).toBe(1)
    expect(Array.isArray(diagnostic.targetEvidenceTraceItems)).toBe(true)
    expect(diagnostic.targetEvidenceTraceItems.length).toBeGreaterThan(0)
    expect(diagnostic.targetEvidenceTraceCoveragePassed).toBe(true)
    expect(diagnostic.targetEvidenceSourceConsistencyPassed).toBe(true)
    expect(diagnostic.targetEvidenceFirstFailureLabel).not.toBe('')
    assertTargetDisplayInvariants(diagnostic, await collectDomFields(page))
  })
}

const accessiblePages = [
  '/#/finance/payment-order-drafts',
  '/#/finance/payment-risk-reviews',
]

for (const route of accessiblePages) {
  test(`${route} 页面名称可访问`, async ({ page }) => {
    await page.goto(route, { waitUntil: 'networkidle' })
    await expect(page.locator('[data-acceptance-id="page-business-title"]')).toBeVisible()
  })
}

const horizontalScrollViewports = [
  { width: 1280, height: 720 },
  { width: 1366, height: 768 },
  { width: 1920, height: 1080 },
]

for (const viewport of horizontalScrollViewports) {
  test(`付款执行准备横向滚动真实鼠标操作 ${viewport.width}x${viewport.height}`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport)
    await page.goto('/#/finance/payment-execution-prepares', { waitUntil: 'networkidle' })
    await expect(page.locator('[data-acceptance-id="manual-acceptance-navigation"]')).toBeVisible()
    await expect(page.locator('[data-acceptance-id="payment-execution-prepare-list-section"]')).toContainText('付款执行准备列表')
    await assertHorizontalScrollOperable(page, 'business-table-scroll-payment-execution-prepare-list')
    const fixedColumnCoordinates = await assertPaymentExecutionFixedColumns(page)
    await fs.writeFile(
      testInfo.outputPath('payment-execution-fixed-column-coordinates.json'),
      JSON.stringify({ version: VERSION, viewport, fixedColumnCoordinates }, null, 2),
      'utf8',
    )

    const listSection = page.locator('[data-acceptance-id="payment-execution-prepare-list-section"]')
    const previewButtons = listSection.getByRole('button', { name: '查看付款凭证准备预览' })
    const previewButtonCount = await previewButtons.count()
    if (previewButtonCount > 0) {
      const previewButton = previewButtons.first()
      await expect(previewButton).toBeEnabled()
      const firstPepNo = normalize(await listSection.locator('.payment-fixed-no-column').nth(1).innerText())
      await page.locator('[data-acceptance-id="business-table-scroll-payment-execution-prepare-list"]').evaluate((element) => {
        const scroller = element.scrollWidth > element.clientWidth + 2 ? element : element.querySelector('.el-scrollbar__wrap') || element
        scroller.scrollLeft = scroller.scrollWidth - scroller.clientWidth
      })
      await previewButton.click()
      await expect(page).toHaveURL(new RegExp(`/finance/payment-voucher-prepare-preview/${firstPepNo}`))
    }
  })
}

test('付款凭证准备预览中文净化与来源链建议检查方向真实页面验收', async ({ page }) => {
  await page.goto('/#/finance/payment-voucher-prepare-preview/PEP2026071311191257', { waitUntil: 'networkidle' })
  await assertPaymentVoucherPreviewChineseSummary(page)
  await assertTargetEvidenceSuggestionColumn(page)
})



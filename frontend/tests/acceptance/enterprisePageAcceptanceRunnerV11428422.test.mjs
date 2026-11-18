import test from 'node:test'
import assert from 'node:assert/strict'
import os from 'node:os'
import path from 'node:path'
import { mkdtemp } from 'node:fs/promises'
import { normalizeEnterprisePageUrl, resolveEnterprisePage } from '../../src/meta/acceptance/runner/enterprisePageResolver.js'
import { resolveEnterpriseAcceptanceTemplate } from '../../src/meta/acceptance/runner/enterpriseAcceptanceTemplateResolver.js'
import { assertEnterpriseAcceptanceReadOnly, createRun, execute, generateReport } from '../../src/meta/acceptance/runner/enterprisePageAcceptanceRunner.js'
import { archiveEnterprisePageAcceptanceRun, verifyEnterprisePageAcceptanceRunArchive } from '../../scripts/enterprisePageAcceptanceRunnerArchiveWriter.mjs'

const runtimeFor = run => ({
  route: { registered: true, pageCode: run.pageCode, moduleCode: 'SCM', component: 'ScmPurchaseRequestPage' },
  pageIdentity: { pageCode: run.pageCode, pageName: '采购申请', pageUrl: '/scm/purchase-request', moduleCode: 'SCM', businessObject: 'PurchaseRequest', pageVersion: 'V1.14.2.8.4.22' },
  serverFacts: { apiFacts: {}, pageFacts: {}, diagnosticFacts: {}, strictFacts: {}, acceptanceFacts: {}, factSource: 'server' },
  api: { endpoint: '/api/procurement/scm-page-facts/purchase-request/', method: 'GET', httpStatus: 200, authenticated: true, responseTime: 5, factSource: 'server', mutatingRequestCount: 0, dataMode: 'production', productionApiCallCount: 1, canaryApiCallCount: 0 },
  list: { contract: 'PCE-ENTERPRISE-LIST-CONTRACT-V1.1', component: 'PceEnterpriseListTable', advancedFilter: true, frozenColumns: true, horizontalScroll: true, pagination: true, actionColumn: true },
  navigation: { previousNode: '流程中心', currentPage: '/scm/purchase-request', nextNode: '采购询价', pageUrl: '/scm/purchase-request', actualNavigation: true, refreshPreserved: true },
  actions: { readOnlyObserved: true, dangerActionExecuted: false, paymentWriteCount: 0, bankWriteCount: 0, financeWriteCount: 0 },
  databaseProtection: { databaseHashBefore: 'same', databaseHashAfter: 'same', databaseHashUnchanged: true, businessWriteCount: 0, productionUserDataWritten: false },
  performance: { routeLoadTime: 1, schemaLoadTime: 2, apiTime: 3, renderTime: 4, totalTime: 10 },
  browser: { url: 'http://localhost:5173/#/scm/purchase-request', pageOpened: true, visibleRegions: ['page-identity-region'], keyTexts: ['采购申请'], refreshPreserved: true, screenshotRefs: ['page.png'], traceRefs: ['trace.zip'], evidenceRefs: ['page.png','trace.zip'] },
  businessActions: [],
})

test('URL解析保留路径与场景参数', () => {
  const parsed = normalizeEnterprisePageUrl('http://localhost:5173/#/scm/purchase-request?scenarioCode=HAPPY_PATH')
  assert.equal(parsed.pagePath, '/scm/purchase-request')
  assert.equal(parsed.query.scenarioCode, 'HAPPY_PATH')
})

test('pageCode自动识别为SCM_PURCHASE_REQUEST', () => {
  const page = resolveEnterprisePage({ pageUrl: '/scm/purchase-request' })
  assert.equal(page.result, 'PASS')
  assert.equal(page.pageCode, 'SCM_PURCHASE_REQUEST')
})

test('模板精准匹配SCM业务页面模板', () => {
  const template = resolveEnterpriseAcceptanceTemplate(resolveEnterprisePage({ pageUrl: '/scm/purchase-request' }))
  assert.equal(template.templateCode, 'SCM_BUSINESS_PAGE_ACCEPTANCE_TEMPLATE')
  assert.equal(template.matchType, 'pageCode')
})

test('未知页面与无模板结果保持UNKNOWN', () => {
  const page = resolveEnterprisePage({ pageUrl: '/unknown/not-registered' })
  const template = resolveEnterpriseAcceptanceTemplate(page)
  assert.equal(page.result, 'UNKNOWN')
  assert.equal(template.result, 'UNKNOWN')
})

test('正常运行调用Evidence Engine并生成PASS', async () => {
  const run = createRun({ runId: 'RUNNER-UNIT-PASS', pageUrl: '/scm/purchase-request', mode: 'production', readonly: true })
  const result = await execute(run, { runtimeContextProvider: current => runtimeFor(current) })
  assert.equal(result.success, true)
  assert.equal(result.evidenceCount, 24)
  assert.equal(run.collectorCount, 10)
})

test('Collector异常被Evidence Engine记录而不中断Runner', async () => {
  const run = createRun({ runId: 'RUNNER-UNIT-COLLECTOR-ERROR', pageUrl: '/scm/purchase-request', mode: 'production', readonly: true })
  const result = await execute(run, { runtimeContextProvider: current => new Proxy(runtimeFor(current), { get(target, property) { if (property === 'api') throw new Error('API_DOWN'); return target[property] } }) })
  assert.equal(result.result, 'UNKNOWN')
  assert.ok(run.collection.evidence.some(item => item.error?.code === 'COLLECTOR_ERROR'))
})

test('Report自动生成并包含保护结果', async () => {
  const run = createRun({ runId: 'RUNNER-UNIT-REPORT', pageUrl: '/scm/purchase-request', mode: 'production', readonly: true })
  await execute(run, { runtimeContextProvider: current => runtimeFor(current) })
  const report = generateReport(run)
  assert.equal(report.result, 'PASS')
  assert.equal(report.businessWriteCount, 0)
})

test('Archive生成强制文件且Hash一致', async () => {
  const archiveRoot = await mkdtemp(path.join(os.tmpdir(), 'pce-runner-'))
  const run = createRun({ runId: 'RUNNER-UNIT-ARCHIVE', pageUrl: '/scm/purchase-request', mode: 'production', readonly: true })
  const result = await execute(run, { runtimeContextProvider: current => runtimeFor(current), archiveWriter: archiveEnterprisePageAcceptanceRun, archiveRoot, version: 'V1.14.2.8.4.22' })
  const verification = await verifyEnterprisePageAcceptanceRunArchive(result.archivePath)
  assert.equal(verification.valid, true)
  assert.equal(run.status, 'ARCHIVED')
})

test('ReadOnly=false立即阻断', () => {
  assert.throws(() => createRun({ pageUrl: '/scm/purchase-request', readonly: false }), /RUNNER_READONLY_REQUIRED/)
})

test('Business Action Guard阻断submit等动作', () => {
  assert.throws(() => assertEnterpriseAcceptanceReadOnly({ readonly: true, businessActions: ['submit'] }), /RUNNER_BUSINESS_ACTION_FORBIDDEN/)
})

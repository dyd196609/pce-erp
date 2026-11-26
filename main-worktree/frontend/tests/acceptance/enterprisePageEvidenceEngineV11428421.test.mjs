import test from 'node:test'
import assert from 'node:assert/strict'
import os from 'node:os'
import path from 'node:path'
import { mkdtemp } from 'node:fs/promises'
import { createEvidence, assertUniqueEvidenceIds, EVIDENCE_TYPES } from '../../src/meta/acceptance/evidence/enterprisePageEvidenceModel.js'
import { listEvidenceCollectors } from '../../src/meta/acceptance/evidence/enterprisePageEvidenceCollectorRegistry.js'
import { registerScmBusinessPageEvidenceCollectors } from '../../src/meta/acceptance/evidence/scmBusinessPageEvidenceCollectors.js'
import { collectEnterprisePageEvidence, createEvidenceCollectionPlan, evaluateCollectedEvidence, archiveEnterprisePageEvidence } from '../../src/meta/acceptance/evidence/enterprisePageEvidenceEngine.js'
import { archiveEnterprisePageEvidenceFiles, verifyEnterprisePageEvidenceArchive } from '../../scripts/enterprisePageEvidenceArchiveWriter.mjs'

const pageIdentity = { pageCode: 'SCM_PURCHASE_REQUEST', pageName: '采购申请', pageUrl: '/scm/purchase-request', moduleCode: 'SCM', businessObject: 'PurchaseRequest', pageVersion: 'V1.14.2.8.4.21' }
const runtime = {
  route: { registered: true, pageCode: pageIdentity.pageCode, moduleCode: 'SCM', component: 'ScmPurchaseRequestPage' },
  pageIdentity,
  serverFacts: { apiFacts: {}, pageFacts: {}, diagnosticFacts: {}, strictFacts: {}, acceptanceFacts: {}, factSource: 'server' },
  api: { endpoint: '/api/procurement/scm-page-facts/purchase-request/', method: 'GET', httpStatus: 200, authenticated: true, responseTime: 5, factSource: 'server', mutatingRequestCount: 0 },
  list: { contract: 'PCE-ENTERPRISE-LIST-CONTRACT-V1.1', component: 'PceEnterpriseListTable', advancedFilter: true, frozenColumns: true, horizontalScroll: true, pagination: true, actionColumn: true },
  navigation: { previousNode: '流程中心', currentPage: '/scm/purchase-request', nextNode: '询价', pageUrl: '/scm/purchase-request', actualNavigation: true, refreshPreserved: true },
  actions: { readOnlyObserved: true, dangerActionExecuted: false, paymentWriteCount: 0, bankWriteCount: 0, financeWriteCount: 0 },
  databaseProtection: { databaseHashUnchanged: true, businessWriteCount: 0, productionUserDataWritten: false },
  performance: { routeLoadTime: 1, schemaLoadTime: 2, apiTime: 3, renderTime: 4, totalTime: 10 },
  browser: { url: 'http://localhost:5173/#/scm/purchase-request', pageOpened: true, visibleRegions: ['page-identity-region'], keyTexts: ['采购申请'], refreshPreserved: true, screenshotRefs: ['screenshots/purchase-request.png'], traceRefs: ['traces/trace.zip'], evidenceRefs: ['screenshots/purchase-request.png','traces/trace.zip'] },
}

test('证据模型包含统一字段与类型', () => {
  const item = createEvidence({ evidenceId: 'E1', acceptanceRunId: 'R1', pageCode: 'P1', checkId: 'C1', evidenceType: 'route', source: 'router', collectorCode: 'ROUTE_EVIDENCE_COLLECTOR', result: 'PASS' })
  assert.equal(item.result, 'PASS')
  assert.ok(EVIDENCE_TYPES.includes('database_protection'))
  assert.equal(item.metadata instanceof Object, true)
})

test('固定注册十个只读采集器且顺序正确', () => {
  assert.equal(registerScmBusinessPageEvidenceCollectors(), 10)
  const codes = listEvidenceCollectors().map(item => item.collectorCode)
  assert.deepEqual(codes, ['ROUTE_EVIDENCE_COLLECTOR','PAGE_IDENTITY_COLLECTOR','SERVER_FACTS_COLLECTOR','API_EVIDENCE_COLLECTOR','LIST_CONTRACT_COLLECTOR','NAVIGATION_COLLECTOR','ACTION_EVIDENCE_COLLECTOR','DATABASE_PROTECTION_COLLECTOR','PERFORMANCE_COLLECTOR','BROWSER_EVIDENCE_COLLECTOR'])
  assert.ok(listEvidenceCollectors().every(item => item.executionMode === 'read_only'))
})

test('SCM证据计划合并公共与SCM检查项', () => {
  const plan = createEvidenceCollectionPlan({ pageIdentity, moduleCode: 'SCM', acceptanceRunId: 'PLAN-001' })
  assert.equal(plan.checks.length, 24)
  assert.ok(plan.checks.every(item => item.collectorRegistered))
})

test('完整运行时事实采集后FAIL和UNKNOWN均为零', async () => {
  const plan = createEvidenceCollectionPlan({ pageIdentity, moduleCode: 'SCM', acceptanceRunId: 'RUN-PASS' })
  const result = evaluateCollectedEvidence(await collectEnterprisePageEvidence(plan, runtime))
  assert.equal(result.acceptance.summary.FAIL, 0)
  assert.equal(result.acceptance.summary.UNKNOWN, 0)
  assert.equal(result.evidence.length, 24)
  assert.equal(runtime.databaseProtection.businessWriteCount, 0)
  assert.equal(runtime.databaseProtection.productionUserDataWritten, false)
})

test('事实缺失不得自动PASS而是UNKNOWN', async () => {
  const plan = createEvidenceCollectionPlan({ pageIdentity, moduleCode: 'SCM', acceptanceRunId: 'RUN-MISSING' })
  const result = evaluateCollectedEvidence(await collectEnterprisePageEvidence(plan, {}))
  assert.ok(result.acceptance.summary.UNKNOWN > 0)
})

test('采集器异常转换为UNKNOWN并保留错误', async () => {
  const plan = createEvidenceCollectionPlan({ pageIdentity, moduleCode: 'SCM', acceptanceRunId: 'RUN-ERROR' })
  const broken = new Proxy(runtime, { get(target, property) { if (property === 'api') throw new Error('API_UNAVAILABLE'); return target[property] } })
  const collection = await collectEnterprisePageEvidence(plan, broken)
  const item = collection.evidence.find(entry => entry.collectorCode === 'API_EVIDENCE_COLLECTOR')
  assert.equal(item.result, 'UNKNOWN')
  assert.equal(item.error.code, 'COLLECTOR_ERROR')
})

test('N/A缺少原因确认人与引用时必须FAIL且不删除', () => {
  const item = createEvidence({ evidenceId: 'ENA', acceptanceRunId: 'RNA', pageCode: 'PNA', checkId: 'CNA', evidenceType: 'manual', source: 'manual', collectorCode: 'MANUAL', result: 'N/A' })
  assert.equal(item.result, 'FAIL')
  assert.equal(item.error.code, 'INVALID_NA')
})

test('合法N/A保留原因确认人与证据引用', () => {
  const item = createEvidence({ evidenceId: 'ENA-VALID', acceptanceRunId: 'RNA', pageCode: 'PNA', checkId: 'CNA', evidenceType: 'manual', source: 'manual', collectorCode: 'MANUAL', result: 'N/A', naReason: '当前页面不适用', confirmedBy: 'acceptance-owner', evidenceRefs: ['manual-acceptance.md'] })
  assert.equal(item.result, 'N/A')
  assert.equal(item.evidenceRefs.length, 1)
})

test('未登记采集器生成UNKNOWN而不中断', async () => {
  const original = createEvidenceCollectionPlan({ pageIdentity, moduleCode: 'SCM', acceptanceRunId: 'RUN-UNREGISTERED' })
  const plan = { ...original, checks: [{ ...original.checks[0], collectorCode: 'UNREGISTERED_COLLECTOR' }] }
  const collection = await collectEnterprisePageEvidence(plan, runtime)
  assert.equal(collection.evidence[0].result, 'UNKNOWN')
  assert.equal(collection.evidence[0].error.code, 'COLLECTOR_MISSING')
})

test('重复evidenceId必须拒绝', () => {
  const base = { evidenceId: 'DUP', acceptanceRunId: 'RD', pageCode: 'PD', checkId: 'CD', evidenceType: 'manual', source: 'manual', collectorCode: 'MANUAL', result: 'PASS' }
  assert.throws(() => assertUniqueEvidenceIds([createEvidence(base), createEvidence({ ...base, checkId: 'CD2' })]), /DUPLICATE_EVIDENCE_ID/)
})

test('归档生成强制文件且Hash可复核', async () => {
  const plan = createEvidenceCollectionPlan({ pageIdentity, moduleCode: 'SCM', acceptanceRunId: 'RUN-ARCHIVE' })
  const evaluated = evaluateCollectedEvidence(await collectEnterprisePageEvidence(plan, runtime))
  const archiveRoot = await mkdtemp(path.join(os.tmpdir(), 'pce-evidence-'))
  const archived = await archiveEnterprisePageEvidence(evaluated, { archiveWriter: archiveEnterprisePageEvidenceFiles, archiveRoot, databaseProtection: runtime.databaseProtection })
  const verification = await verifyEnterprisePageEvidenceArchive(archived.archiveDir)
  assert.equal(verification.valid, true)
  assert.equal(archived.immutable, true)
})

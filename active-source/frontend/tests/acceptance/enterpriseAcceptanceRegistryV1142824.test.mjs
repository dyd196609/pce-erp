import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import os from 'node:os'
import path from 'node:path'
import { mkdtemp, readFile, readdir } from 'node:fs/promises'
import {
  ENTERPRISE_ACCEPTANCE_REGISTRY,
  getEnterpriseAcceptanceModuleRegistration,
} from '../../src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'
import { activateAcceptanceFramework } from '../../src/meta/acceptance/registry/enterpriseAcceptanceActivator.js'
import {
  activateModule,
  executeModuleAcceptance,
  getModuleAcceptanceProfile,
  validateModuleRegistration,
} from '../../src/meta/acceptance/registry/enterpriseAcceptanceFrameworkService.js'
import {
  REGISTRY_ARCHIVE_FILES,
  verifyEnterpriseAcceptanceRegistry,
  writeEnterpriseAcceptanceRegistryArchive,
} from '../../scripts/verifyEnterpriseAcceptanceRegistryV1142824.mjs'

const runtimeFor = run => ({
  route: { registered: true, pageCode: run.pageCode, moduleCode: 'SCM', component: 'ScmPurchaseRequestPage' },
  pageIdentity: { pageCode: run.pageCode, pageName: '采购申请', pageUrl: '/scm/purchase-request', moduleCode: 'SCM', businessObject: 'PurchaseRequest', pageVersion: 'V1.14.2.8.4.24' },
  serverFacts: { apiFacts: {}, pageFacts: {}, diagnosticFacts: {}, strictFacts: {}, acceptanceFacts: {}, factSource: 'server' },
  api: { endpoint: '/api/procurement/scm-page-facts/purchase-request/', method: 'GET', httpStatus: 200, authenticated: true, responseTime: 5, factSource: 'server', mutatingRequestCount: 0, dataMode: 'production', productionApiCallCount: 1, canaryApiCallCount: 0 },
  list: { contract: 'PCE-ENTERPRISE-LIST-CONTRACT-V1.1', component: 'PceEnterpriseListTable', advancedFilter: true, frozenColumns: true, horizontalScroll: true, pagination: true, actionColumn: true },
  navigation: { previousNode: '流程中心', currentPage: '/scm/purchase-request', nextNode: '采购询价', pageUrl: '/scm/purchase-request', actualNavigation: true, refreshPreserved: true },
  actions: { readOnlyObserved: true, dangerActionExecuted: false, paymentWriteCount: 0, bankWriteCount: 0, financeWriteCount: 0 },
  databaseProtection: { databaseHashBefore: 'same', databaseHashAfter: 'same', databaseHashUnchanged: true, businessWriteCount: 0, productionUserDataWritten: false },
  performance: { routeLoadTime: 1, schemaLoadTime: 2, apiTime: 3, renderTime: 4, totalTime: 10 },
  browser: { url: 'http://localhost:5173/#/scm/purchase-request', pageOpened: true, visibleRegions: ['page-identity-region'], keyTexts: ['采购申请'], refreshPreserved: true, screenshotRefs: ['page.png'], traceRefs: ['trace.zip'], evidenceRefs: ['page.png', 'trace.zip'] },
  businessActions: [],
})

test('SCM 注册完整且只读', () => {
  assert.equal(ENTERPRISE_ACCEPTANCE_REGISTRY.registryVersion, 'V1')
  assert.equal(validateModuleRegistration({ moduleCode: 'SCM' }).valid, true)
  assert.equal(getEnterpriseAcceptanceModuleRegistration('SCM').readOnlyActivation, true)
})

test('模板栈自动加载 Master、Common 与 SCM V2', () => {
  const activation = activateAcceptanceFramework({ moduleCode: 'SCM' })
  assert.equal(activation.templates, 3)
  assert.ok(activation.templateCodes.includes('SCM_BUSINESS_PAGE_ACCEPTANCE_TEMPLATE_V2'))
})

test('十个现有只读 Collector 自动加载且别名复用', () => {
  const registration = getEnterpriseAcceptanceModuleRegistration('SCM')
  const activation = activateAcceptanceFramework('SCM')
  assert.equal(activation.collectors, 10)
  assert.equal(registration.collectorAliases.SCM_TRACE_COLLECTOR, 'SERVER_FACTS_COLLECTOR')
  assert.equal(registration.collectorAliases.SCM_ACTION_COLLECTOR, 'ACTION_EVIDENCE_COLLECTOR')
})

test('八个规则集自动形成二十个激活规则绑定', () => {
  const activation = activateAcceptanceFramework('SCM')
  assert.equal(activation.registeredRuleSets, 8)
  assert.equal(activation.rules, 20)
  assert.ok(activation.ruleEntryCount > 20)
})

test('Service 激活成功并返回规定 Module Profile', () => {
  const result = activateModule({ moduleCode: 'SCM' })
  const profile = getModuleAcceptanceProfile('SCM')
  assert.equal(result.success, true)
  assert.equal(result.activationStatus, 'READY')
  assert.deepEqual({ objects: profile.objects, templates: profile.templates, rules: profile.rules, collectors: profile.collectors }, { objects: 3, templates: 1, rules: 8, collectors: 10 })
})

test('未知模块被明确阻断', () => {
  const result = activateModule({ moduleCode: 'CRM_NOT_REGISTERED' })
  assert.equal(result.success, false)
  assert.equal(result.error.code, 'MODULE_NOT_REGISTERED')
})

test('缺少规则的注册不能激活', () => {
  const registration = getEnterpriseAcceptanceModuleRegistration('SCM')
  const result = activateModule({ moduleCode: 'SCM', registration: { ...registration, rules: [] } })
  assert.equal(result.success, false)
  assert.equal(result.error.code, 'MODULE_REGISTRATION_INCOMPLETE')
})

test('激活过程不产生业务写入', () => {
  const activation = activateAcceptanceFramework('SCM')
  assert.equal(activation.readOnly, true)
  assert.deepEqual(activation.businessActions, [])
  assert.equal(activation.businessWriteCount, 0)
  assert.equal(activation.productionUserDataWritten, false)
})

test('SCM Profile 激活后调用兼容 Acceptance Runner', async () => {
  const result = await executeModuleAcceptance({
    moduleCode: 'SCM',
    runInput: { runId: 'REGISTRY-RUNNER-UNIT', pageUrl: '/scm/purchase-request', mode: 'production' },
    runnerOptions: { runtimeContextProvider: current => runtimeFor(current) },
  })
  assert.equal(result.success, true)
  assert.equal(result.profile.moduleCode, 'SCM')
  assert.equal(result.runnerResult.result, 'PASS')
  assert.equal(result.businessWriteCount, 0)
  assert.equal(result.productionUserDataWritten, false)
})

test('自动验证与五文件归档可复核', async () => {
  const report = verifyEnterpriseAcceptanceRegistry()
  assert.deepEqual(report.summary, { total: 10, PASS: 10, FAIL: 0, 'N/A': 0, UNKNOWN: 0 })
  const archiveRoot = await mkdtemp(path.join(os.tmpdir(), 'enterprise-acceptance-registry-'))
  await writeEnterpriseAcceptanceRegistryArchive({ archiveRoot })
  assert.deepEqual((await readdir(archiveRoot)).sort(), REGISTRY_ARCHIVE_FILES.toSorted())
  const hashes = JSON.parse(await readFile(path.join(archiveRoot, 'hashes.json'), 'utf8'))
  for (const [name, expected] of Object.entries(hashes.files)) {
    const body = await readFile(path.join(archiveRoot, name))
    assert.equal(createHash('sha256').update(body).digest('hex'), expected)
  }
})


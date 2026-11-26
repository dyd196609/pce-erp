import test from 'node:test'
import assert from 'node:assert/strict'
import os from 'node:os'
import path from 'node:path'
import { mkdtemp, readFile, readdir } from 'node:fs/promises'
import {
  listPurchaseInquiryDomainObjects,
  resolvePurchaseInquiryDomainObject,
  validatePurchaseInquiryDomainObjectDefinition,
} from '../../src/meta/domain/scm/purchaseInquiry/purchaseInquiryDomainModel.js'
import {
  PURCHASE_INQUIRY_BUSINESS_RELATIONSHIPS,
  PURCHASE_INQUIRY_INTERNAL_RELATIONSHIPS,
  PURCHASE_INQUIRY_TRACE_CHAIN,
  evaluatePurchaseInquiryTrace,
  isPurchaseInquiryReverseGeneration,
} from '../../src/meta/domain/scm/purchaseInquiry/purchaseInquiryRelationshipModel.js'
import {
  PURCHASE_INQUIRY_LIFECYCLE,
  evaluatePurchaseInquiryStatusTransition,
} from '../../src/meta/domain/scm/purchaseInquiry/purchaseInquiryStatusModel.js'
import {
  PURCHASE_INQUIRY_ACTION_RULES,
  evaluatePurchaseInquiryAction,
} from '../../src/meta/domain/scm/purchaseInquiry/purchaseInquiryActionRules.js'
import {
  PURCHASE_INQUIRY_FINANCIAL_BOUNDARY,
  evaluatePurchaseInquiryFinancialBoundary,
} from '../../src/meta/domain/scm/purchaseInquiry/purchaseInquiryFinancialBoundary.js'
import { validatePurchaseInquiryAcceptanceProfile } from '../../src/meta/acceptance/scm/purchaseInquiryAcceptanceProfile.js'
import { activateAcceptanceFramework } from '../../src/meta/acceptance/registry/enterpriseAcceptanceActivator.js'
import { executeModuleAcceptance, getModuleAcceptanceProfile } from '../../src/meta/acceptance/registry/enterpriseAcceptanceFrameworkService.js'
import { verifyPurchaseInquiryDomainModel, writePurchaseInquiryDomainVerification } from '../../scripts/verifyPurchaseInquiryDomainModelV1142851.mjs'

const runtimeFor = run => ({
  route: { registered: true, pageCode: run.pageCode, moduleCode: 'SCM', component: 'ScmPurchaseRequestPage' },
  pageIdentity: { pageCode: run.pageCode, pageName: '采购申请', pageUrl: '/scm/purchase-request', moduleCode: 'SCM', businessObject: 'PurchaseRequest', pageVersion: 'V1.14.2.8.5.1' },
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

test('对象注册包含五个 Purchase Inquiry 领域对象', () => {
  assert.deepEqual(listPurchaseInquiryDomainObjects().map(object => object.businessObject), ['PurchaseInquiry', 'PurchaseInquiryLine', 'SupplierQuote', 'SupplierQuoteLine', 'QuoteComparison'])
  assert.equal(resolvePurchaseInquiryDomainObject('SCM_PURCHASE_INQUIRY').businessObject, 'PurchaseInquiry')
})

test('五个对象字段、关系、Trace、状态和Action声明完整', () => {
  for (const object of listPurchaseInquiryDomainObjects()) {
    assert.equal(validatePurchaseInquiryDomainObjectDefinition(object).result, 'PASS')
    assert.equal(new Set(object.fields.map(field => field.name)).size, object.fields.length)
    assert.equal(object.fields.some(field => field.name === 'traceId'), true)
    assert.equal(object.fields.some(field => field.name === object.statusField), true)
  }
})

test('对象关系覆盖主链与明细关联且禁止自动创建', () => {
  assert.equal(PURCHASE_INQUIRY_BUSINESS_RELATIONSHIPS.length, 5)
  assert.equal(PURCHASE_INQUIRY_INTERNAL_RELATIONSHIPS.length, 4)
  assert.ok([...PURCHASE_INQUIRY_BUSINESS_RELATIONSHIPS, ...PURCHASE_INQUIRY_INTERNAL_RELATIONSHIPS].every(item => item.automaticCreation === false && item.reverseGenerationForbidden === true))
})

test('Trace 主链使用 business_reference 且反向生成失败', () => {
  assert.deepEqual(PURCHASE_INQUIRY_TRACE_CHAIN, ['SCM_PURCHASE_REQUEST', 'SCM_PURCHASE_INQUIRY', 'SCM_SUPPLIER_QUOTE', 'SCM_QUOTE_COMPARISON', 'SCM_PRICE_APPROVAL', 'SCM_PURCHASE_ORDER'])
  const first = PURCHASE_INQUIRY_BUSINESS_RELATIONSHIPS[0]
  assert.equal(evaluatePurchaseInquiryTrace({ ...first, traceId: 'TRACE-001' }).result, 'PASS')
  assert.equal(isPurchaseInquiryReverseGeneration('SCM_PURCHASE_INQUIRY', 'SCM_PURCHASE_REQUEST'), true)
  assert.equal(evaluatePurchaseInquiryTrace({ sourceObject: 'SCM_PURCHASE_INQUIRY', targetObject: 'SCM_PURCHASE_REQUEST', relationshipType: 'business_reference', traceId: 'TRACE-002', direction: 'forward' }).result, 'FAIL')
})

test('状态只允许六状态相邻正向转换', () => {
  assert.deepEqual(PURCHASE_INQUIRY_LIFECYCLE, ['draft', 'issued', 'quoted', 'evaluating', 'approved', 'closed'])
  assert.equal(evaluatePurchaseInquiryStatusTransition({ fromStatus: 'quoted', toStatus: 'evaluating' }).result, 'PASS')
  assert.equal(evaluatePurchaseInquiryStatusTransition({ fromStatus: 'evaluating', toStatus: 'quoted' }).result, 'FAIL')
  assert.equal(evaluatePurchaseInquiryStatusTransition({ fromStatus: 'draft', toStatus: 'approved' }).result, 'FAIL')
})

test('Action白名单允许当前状态动作并默认拒绝未登记和越界动作', () => {
  assert.equal(PURCHASE_INQUIRY_ACTION_RULES.length, 6)
  assert.equal(evaluatePurchaseInquiryAction({ status: 'draft', action: 'addSupplier' }).result, 'PASS')
  assert.equal(evaluatePurchaseInquiryAction({ status: 'approved', action: 'sendToPriceApproval' }).result, 'PASS')
  assert.equal(evaluatePurchaseInquiryAction({ status: 'approved', action: 'createPurchaseOrder' }).result, 'FAIL')
  assert.equal(evaluatePurchaseInquiryAction({ status: 'quoted', action: 'unregisteredAction' }).result, 'FAIL')
})

test('Finance边界只允许价格事实并拒绝资金动作', () => {
  for (const fact of ['quoteAmount', 'estimatedCost', 'priceReference']) assert.equal(evaluatePurchaseInquiryFinancialBoundary({ fact }).result, 'PASS')
  for (const action of ['payment', 'bankTransfer', 'ledgerPost', 'reconcile']) assert.equal(evaluatePurchaseInquiryFinancialBoundary({ action }).result, 'FAIL')
  assert.equal(PURCHASE_INQUIRY_FINANCIAL_BOUNDARY.createsPurchaseOrder, false)
})

test('Acceptance Registry自动激活询价对象Profile', () => {
  const activation = activateAcceptanceFramework('SCM')
  const profile = getModuleAcceptanceProfile('SCM')
  assert.equal(validatePurchaseInquiryAcceptanceProfile().valid, true)
  assert.equal(activation.activated, true)
  assert.equal(activation.objectProfiles.some(item => item.objectCode === 'SCM_PURCHASE_INQUIRY'), true)
  assert.equal(profile.objectRegistrations.some(item => item.objects.length === 5), true)
})

test('既有Acceptance Runner兼容对象Profile并保持只读', async () => {
  const result = await executeModuleAcceptance({
    moduleCode: 'SCM',
    runInput: { runId: 'INQUIRY-DOMAIN-RUNNER', pageUrl: '/scm/purchase-request', mode: 'production' },
    runnerOptions: { runtimeContextProvider: current => runtimeFor(current) },
  })
  assert.equal(result.success, true)
  assert.equal(result.runnerResult.result, 'PASS')
  assert.equal(result.activation.objectProfiles.some(item => item.objectCode === 'SCM_PURCHASE_INQUIRY'), true)
  assert.equal(result.businessWriteCount, 0)
})

test('自动验证、归档与数据保护结果完整', async () => {
  const report = verifyPurchaseInquiryDomainModel()
  assert.deepEqual(report.summary, { total: 10, PASS: 10, FAIL: 0, 'N/A': 0, UNKNOWN: 0 })
  assert.equal(report.productionUserDataWritten, false)
  const outputRoot = await mkdtemp(path.join(os.tmpdir(), 'purchase-inquiry-domain-'))
  await writePurchaseInquiryDomainVerification({ outputRoot })
  assert.deepEqual((await readdir(outputRoot)).sort(), ['domain-model.json', 'verification-report.json'])
  const archived = JSON.parse(await readFile(path.join(outputRoot, 'verification-report.json'), 'utf8'))
  assert.equal(archived.status, 'PURCHASE_INQUIRY_DOMAIN_MODEL_READY')
})

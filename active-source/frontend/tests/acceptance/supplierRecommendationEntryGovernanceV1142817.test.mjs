import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { buildSupplierRecommendationEntryRouteV1142817,
  resolveSupplierRecommendationEntryTaskIdV1142817,
  SUPPLIER_RECOMMENDATION_ENTRY_ROUTE_NAME_V1142817 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationEntryRouteV1142817.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')

test('supplier recommendation restores the governed business name while retaining the batch object', () => {
  const page = read('src/meta/pages/ScmSupplierRecommendationDecisionWorkbenchPage.vue')
  const names = read('src/meta/governance/businessNameRegistry.js')
  const identity = read('src/meta/schema/scm/scmPageIdentityRegistry.js')
  assert.match(page, /data-page-name="供应商推荐"/)
  assert.match(page, /<h1>供应商推荐<\/h1>/)
  assert.doesNotMatch(page, /供应商推荐(?:决策)?工作台/)
  assert.match(names, /'SupplierRecommendationDecisionBatch','supplier-recommendation','供应商推荐'/)
  assert.match(identity, /pageCode: 'supplier-recommendation', pageName: '供应商推荐'/)
  assert.match(identity, /businessObject: 'SupplierRecommendationDecisionBatch'/)
})

test('one task path is the only active supplier recommendation route identity', () => {
  const taskId = 'SRDB-采购推荐-001'
  const url = buildSupplierRecommendationEntryRouteV1142817(taskId)
  assert.equal(url, `/scm/supplier-recommendation-task/${encodeURIComponent(taskId)}`)
  assert.equal(url.includes('?'), false)
  assert.equal(resolveSupplierRecommendationEntryTaskIdV1142817({ params: { taskId } }), taskId)
  assert.equal(SUPPLIER_RECOMMENDATION_ENTRY_ROUTE_NAME_V1142817, 'ScmSupplierRecommendationTask')
  const router = read('src/router/index.js')
  assert.match(router, /path: 'scm\/supplier-recommendation-task\/:taskId'/)
  assert.match(router, /name: 'ScmSupplierRecommendationTask'/)
  assert.match(router, /path: 'scm\/supplier-recommendations',[\s\S]*redirect: '\/process-center\?module=SCM'/)
})

test('PriceApproval single and batch actions use the same route builder', () => {
  const pricePage = read('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue')
  assert.match(pricePage, /buildSupplierRecommendationEntryRouteV1142817\(result\.activeBatch\.batchId\)/)
  assert.match(pricePage, /buildSupplierRecommendationEntryRouteV1142817\(firstBatch\.batchId\)/)
  assert.doesNotMatch(pricePage, /query:\s*\{\s*(?:batchId|decisionBatchId|runtimeContextId|priceApprovalId|quoteComparisonId)/)
})

test('Process Center resolves the same page identity from the active recommendation task', () => {
  const scmRegistry = read('src/meta/process/scmPurchaseProcessCenterRegistryV11428101.js')
  const processRegistry = read('src/meta/process/businessProcessRegistry.js')
  assert.match(scmRegistry, /resolveScmPurchaseProcessNodePageUrlV1142817/)
  assert.match(scmRegistry, /buildSupplierRecommendationEntryRouteV1142817/)
  assert.match(processRegistry, /resolveScmPurchaseProcessNodePageUrlV1142817\(node\)/)
  assert.match(scmRegistry, /\['supplier-recommendation', '供应商推荐'/)
})

test('active page entry exposes no internal query parameters and protected business logic is untouched', () => {
  const page = read('src/meta/pages/ScmSupplierRecommendationDecisionWorkbenchPage.vue')
  const route = read('src/meta/process/scm/supplierRecommendation/supplierRecommendationEntryRouteV1142817.js')
  assert.match(page, /route\.params\.taskId/)
  assert.doesNotMatch(page, /route\.query\.(?:taskId|batchId|decisionBatchId|runtimeContextId|priceApprovalId|quoteComparisonId)/)
  assert.doesNotMatch(route, /\?[^'`]*?(?:batchId|runtimeContextId|priceApprovalId|quoteComparisonId)/)
  for (const protectedFile of [
    'src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js',
    'src/meta/process/scm/supplierRecommendation/supplierRecommendationRuntimeContextV11428163.js',
    'src/meta/providers/supplierRecommendationDecisionProviderV1142816.js',
    'src/meta/runtime/supplierRecommendationActionRuntimeV1142811.js',
    'src/meta/pages/ScmPurchaseOrderGatePage.vue',
  ]) assert.doesNotMatch(read(protectedFile), /V1142817|supplierRecommendationEntryRouteV1142817/)
})

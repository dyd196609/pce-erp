import fs from 'node:fs'
import path from 'node:path'
import { resolveSupplierSettlementContext } from '../src/meta/scm/resolveSupplierSettlementContext.js'
import { listPceDefectRegressionRegistry } from '../src/meta/runtime/pceDefectRegressionRegistry.js'
import { resolveBusinessName } from '../src/meta/governance/businessNameRegistry.js'
import { resolvePageNameConsumption } from '../src/meta/governance/pageNameConsumer.js'
import {
  resolvePceCanonicalNameByModuleId,
  resolvePceCanonicalNameByRoute,
} from '../src/meta/runtime/pceCanonicalNameService.js'
import { listBusinessProcessSteps } from '../src/meta/process/businessProcessRegistry.js'
import { businessOperationPageConfigs } from '../src/meta/process/businessOperationPageRegistry.js'

const root = process.cwd()
const read = (relative) => fs.readFileSync(path.join(root, relative), 'utf8')
const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}

const sourceA = {
  payableCheckNo: 'PC-GATE-A',
  sourcePayablePrepareNo: 'PP-GATE-A',
  sourcePurchaseOrderNo: 'PO-GATE-A',
  supplierId: 'SUP-GATE-A',
  supplierName: '供应商A',
  checkStatus: 'checked',
  sourceInventoryTransactionNos: ['TXN-GATE-A'],
  sourceWarehouseTaskNo: 'WT-GATE-A',
  sourceInspectionNo: 'IQC-GATE-A',
  sourceReceiveNo: 'PRV-GATE-A',
  sourcePriceApprovalNo: 'PA-GATE-A',
}
const sourceB = {
  payableCheckNo: 'PC-GATE-B',
  sourcePayablePrepareNo: 'PP-GATE-B',
  sourcePurchaseOrderNo: 'PO-GATE-B',
  supplierId: 'SUP-GATE-B',
  supplierName: '供应商B',
  checkStatus: 'checked',
  sourceInventoryTransactionNos: ['TXN-GATE-B'],
  sourceWarehouseTaskNo: 'WT-GATE-B',
  sourceInspectionNo: 'IQC-GATE-B',
  sourceReceiveNo: 'PRV-GATE-B',
  sourcePriceApprovalNo: 'PA-GATE-B',
}
const settlementA = {
  settlementNo: 'SET-GATE-A',
  sourcePayableCheckNo: 'PC-GATE-A',
  sourcePayablePrepareNo: 'PP-GATE-A',
  purchaseOrderNo: 'PO-GATE-A',
  supplierId: 'SUP-GATE-A',
  supplierName: '供应商A',
}

const queryFor = (source) => ({
  sourcePayableCheckNo: source.payableCheckNo,
  sourcePayablePrepareNo: source.sourcePayablePrepareNo,
  purchaseOrderNo: source.sourcePurchaseOrderNo,
  supplierId: source.supplierId,
  supplierName: source.supplierName,
  sourceStatus: source.checkStatus,
})

const payableCheckPage = read('src/meta/pages/PayableCheckPage.vue')
const supplierSettlementPage = read('src/meta/pages/SupplierSettlementPage.vue')
const processRegistry = read('src/meta/process/businessProcessRegistry.js')
const operationRegistry = read('src/meta/process/businessOperationPageRegistry.js')
const router = read('src/router/index.js')
const scrollContainer = read('src/meta/components/BusinessTableScrollContainer.vue')
const appExperience = read('src/styles/appExperience.css')
const purchaseReconciliationPage = read('src/meta/pages/PurchaseReconciliationPage.vue')
const actionGate = read('src/meta/core/action-gate/businessActionGate.js')
const actionGateIntegrity = read('src/meta/core/action-gate/businessActionGateIntegrity.js')
const finalReviewAdapter = read('src/meta/scm/purchaseReconciliationFinalReview.js')
const candidateModel = read('src/meta/scm/purchaseReconciliationCandidate.js')
const simulationModel = read('src/meta/scm/purchaseReconciliationSimulation.js')
const actionTransaction = read('src/meta/core/action-transaction/businessActionTransaction.js')
const actionTransactionIntegrity = read('src/meta/core/action-transaction/businessActionTransactionIntegrity.js')
const actionIdempotency = read('src/meta/core/action-transaction/businessActionIdempotency.js')
const documentNumberPolicy = read('src/meta/core/action-transaction/businessDocumentNumberPolicy.js')
const reconciliationTransaction = read('src/meta/scm/purchaseReconciliationFormalGenerationTransaction.js')
const controlledGeneration = read('src/meta/scm/purchaseReconciliationControlledGeneration.js')
const dualGate = read('src/meta/core/action-transaction/businessActionDualGate.js')
const persistenceAdapters = read('src/meta/core/action-transaction/businessActionPersistenceAdapters.js')

const existing = resolveSupplierSettlementContext({
  query: queryFor(sourceA),
  payableChecks: [sourceA, sourceB],
  supplierSettlements: [settlementA],
})
const pending = resolveSupplierSettlementContext({
  query: queryFor(sourceB),
  payableChecks: [sourceA, sourceB],
  supplierSettlements: [settlementA],
})
const invalid = resolveSupplierSettlementContext({
  query: { ...queryFor(sourceB), sourcePayablePrepareNo: 'PP-WRONG' },
  payableChecks: [sourceA, sourceB],
  supplierSettlements: [settlementA],
})
const all = resolveSupplierSettlementContext({
  payableChecks: [sourceA, sourceB],
  supplierSettlements: [settlementA],
})

const expectedPayableCheckCanonicalName = '采购应付核对'
const authoritativePayableCheckName = resolveBusinessName({
  pageCode: 'payable-check',
  route: '/finance/payable-checks',
})
const consumedPayableCheckName = resolvePageNameConsumption({
  pageCode: 'payable-check',
  route: '/finance/payable-checks',
})
const payableCheckModuleIdentity = resolvePceCanonicalNameByModuleId('payable-check')
const payableCheckRouteIdentity = resolvePceCanonicalNameByRoute('/finance/payable-checks')
const payableCheckProcessStep = listBusinessProcessSteps().find((step) => step.stepId === 'payable-check')
const payableCheckOperationPage = businessOperationPageConfigs.find((page) => page.pageStepId === 'payable-check')

const gates = {
  canonical_name_exact:
    authoritativePayableCheckName?.pageName === expectedPayableCheckCanonicalName
    && authoritativePayableCheckName?.pageTitle === expectedPayableCheckCanonicalName
    && authoritativePayableCheckName?.browserTitle === expectedPayableCheckCanonicalName
    && authoritativePayableCheckName?.displayName === expectedPayableCheckCanonicalName
    && consumedPayableCheckName?.pageTitle === expectedPayableCheckCanonicalName
    && consumedPayableCheckName?.nameSource === 'BusinessNameRegistry'
    && payableCheckModuleIdentity?.canonicalName === expectedPayableCheckCanonicalName
    && payableCheckModuleIdentity?.routePath === '/finance/payable-checks'
    && payableCheckRouteIdentity?.canonicalName === expectedPayableCheckCanonicalName
    && payableCheckRouteIdentity?.moduleId === 'payable-check'
    && payableCheckProcessStep?.stepName === expectedPayableCheckCanonicalName
    && payableCheckProcessStep?.pageTitle === expectedPayableCheckCanonicalName
    && payableCheckProcessStep?.nameSource === 'BusinessNameRegistry'
    && payableCheckOperationPage?.pageTitle === expectedPayableCheckCanonicalName
    && payableCheckOperationPage?.routePath === '/finance/payable-checks'
    && router.includes("wrapBusinessOperationPage('payable-check'")
    && payableCheckPage.includes('payableCheckCanonicalName')
    && payableCheckPage.includes("resolvePageNameConsumption({ pageCode: 'payable-check', route: '/finance/payable-checks' })"),
  selected_context_exact:
    existing.status === 'existing_settlement'
    && existing.sourceRecord?.payableCheckNo === 'PC-GATE-A'
    && existing.displayRows[0]?.settlementNo === 'SET-GATE-A'
    && pending.status === 'pending_source'
    && pending.sourceRecord?.payableCheckNo === 'PC-GATE-B'
    && pending.displayRows[0]?.sourcePayableCheckNo === 'PC-GATE-B',
  contextual_page_not_blank:
    pending.displayRows.length === 1
    && pending.displayRows[0].settlementStatus === 'pending_source'
    && invalid.status === 'invalid_source'
    && invalid.mismatchFields.length > 0
    && all.status === 'all_settlements'
    && supplierSettlementPage.includes('supplier-settlement-context-existing')
    && supplierSettlementPage.includes('supplier-settlement-context-pending')
    && supplierSettlementPage.includes('supplier-settlement-context-invalid'),
  fixed_column_geometry:
    scrollContainer.includes('data-pce-horizontal-scroll-owner="element-plus-native"')
    && !scrollContainer.includes('translateX')
    && !scrollContainer.includes('requestAnimationFrame')
    && !scrollContainer.includes("addEventListener('scroll'")
    && !scrollContainer.includes('position: sticky')
    && !/\.el-table[^{}]*\{[^}]*position\s*:\s*sticky/s.test(appExperience),
  capability_regression_guard:
    payableCheckPage.includes('list-fuzzy-search-input')
    && payableCheckPage.includes('list-advanced-filter-toggle')
    && payableCheckPage.includes('list-export-current-result-button')
    && payableCheckPage.includes('list-export-selected-records-button')
    && payableCheckPage.includes('payable-check-main')
    && supplierSettlementPage.includes('<StandardListToolbar')
    && supplierSettlementPage.includes('@toggle-advanced=')
    && supplierSettlementPage.includes('@clear-filters=')
    && supplierSettlementPage.includes('@clear-sort=')
    && supplierSettlementPage.includes('@export-current=')
    && supplierSettlementPage.includes('supplier-settlement-main'),
  shared_action_gate_layering:
    actionGate.includes('evaluateBusinessActionConditions')
    && actionGate.includes('authorizeBusinessActionExecution')
    && !actionGate.includes('supplierSettlement')
    && !actionGate.includes('purchaseReconciliation')
    && finalReviewAdapter.includes('buildBusinessActionReviewResult')
    && finalReviewAdapter.includes('PRC_FINAL_SOURCE_SNAPSHOT_UNCHANGED'),
  final_review_integrity_single_owner:
    actionGateIntegrity.includes('stableBusinessActionGateHash')
    && candidateModel.includes('stableBusinessActionTextHash')
    && simulationModel.includes('stableBusinessActionGateHash')
    && !candidateModel.includes('Math.imul')
    && !simulationModel.includes('Math.imul')
    && !finalReviewAdapter.includes('Math.imul'),
  final_review_zero_write_boundary:
    finalReviewAdapter.includes("errorCode: 'BUSINESS_ACTION_FORMAL_EXECUTION_DISABLED'") === false
    && finalReviewAdapter.includes('runtimeFormalCreationAllowed: false')
    && !finalReviewAdapter.includes('supplierSettlementStore')
    && !finalReviewAdapter.includes('purchaseReconciliationStore')
    && !finalReviewAdapter.includes('localStorage.getItem')
    && !finalReviewAdapter.includes('localStorage.setItem')
    && !finalReviewAdapter.includes('fetch(')
    && !finalReviewAdapter.includes('axios'),
  final_review_page_is_readonly:
    purchaseReconciliationPage.includes("designMode || '') === 'final_review'")
    && purchaseReconciliationPage.includes('最终评审上下文')
    && !purchaseReconciliationPage.includes('>生成正式采购对账<'),
  purchase_reconciliation_navigation_unchanged:
    !processRegistry.includes('采购对账最终评审')
    && !operationRegistry.includes('采购对账最终评审')
    && (router.match(/path:\s*['\"]scm\/purchase-reconciliations['\"]/g) || []).length === 1,
  shared_action_transaction_layering:
    actionTransaction.includes('buildBusinessActionFormalGenerationCommand')
    && actionTransaction.includes('recoverBusinessActionTransactionOutcome')
    && reconciliationTransaction.includes('buildPurchaseReconciliationTransactionDesign')
    && !actionTransaction.includes('supplierSettlement')
    && !actionTransaction.includes('purchaseReconciliation'),
  transaction_integrity_single_owner:
    actionTransactionIntegrity.includes('stableBusinessActionTransactionHash')
    && actionTransaction.includes('stableBusinessActionTransactionHash')
    && !reconciliationTransaction.includes('Math.imul')
    && !purchaseReconciliationPage.includes('Math.imul'),
  transaction_idempotency_and_lock_not_in_page:
    actionIdempotency.includes('buildBusinessActionIdempotencyKey')
    && actionTransaction.includes('transactionLockKey')
    && !purchaseReconciliationPage.includes('buildBusinessActionIdempotencyKey')
    && !purchaseReconciliationPage.includes('purchase_reconciliation_generation::'),
  transaction_number_policy_single_owner:
    documentNumberPolicy.includes('buildBusinessDocumentNumberReservationPlan')
    && documentNumberPolicy.includes('SIM-PRC-NUM-')
    && !reconciliationTransaction.includes('SIM-PRC-NUM-')
    && !purchaseReconciliationPage.includes('SIM-PRC-NUM-'),
  transaction_zero_formal_write_boundary:
    reconciliationTransaction.includes("errorCode: 'BUSINESS_ACTION_FORMAL_EXECUTION_DISABLED'") === false
    && reconciliationTransaction.includes('formalExecutionAllowed: false')
    && !reconciliationTransaction.includes('writeDatabase')
    && !reconciliationTransaction.includes('supplierSettlementStore')
    && !reconciliationTransaction.includes('purchaseReconciliationStore')
    && !reconciliationTransaction.includes('localStorage.setItem')
    && !reconciliationTransaction.includes('fetch(')
    && !reconciliationTransaction.includes('axios'),
  transaction_state_safety:
    reconciliationTransaction.includes("transactionState: 'commit_unknown'")
    && reconciliationTransaction.includes("'rollback_failed'")
    && reconciliationTransaction.includes("transactionState: 'committed', outcome: 'succeeded_with_cleanup_failure'")
    && actionTransaction.includes("errorCode: 'BUSINESS_ACTION_FORMAL_EXECUTION_DISABLED'"),
  transaction_page_is_readonly:
    purchaseReconciliationPage.includes("designMode || '') === 'formal_generation_transaction_design'")
    && purchaseReconciliationPage.includes('正式生成命令上下文')
    && purchaseReconciliationPage.includes('事务风险与正式执行保护')
    && !purchaseReconciliationPage.includes('>正式生成采购对账<')
    && !purchaseReconciliationPage.includes('>提交正式事务<'),
  transaction_navigation_unchanged:
    !processRegistry.includes('采购对账正式生成事务设计')
    && !operationRegistry.includes('采购对账正式生成事务设计')
    && (router.match(/path:\s*['\"]scm\/purchase-reconciliations['\"]/g) || []).length === 1,
  dual_gate_required_before_execution:
    controlledGeneration.indexOf('authorizeControlledBusinessExecution') < controlledGeneration.indexOf('acquireSourceLock'),
  trusted_context_not_from_query:
    controlledGeneration.includes('validateTrustedCanaryExecutionContext') && !controlledGeneration.includes('route.query'),
  production_switch_not_from_local_storage:
    !controlledGeneration.includes('localStorage') && !persistenceAdapters.includes('localStorage'),
  production_adapter_disabled_by_default:
    controlledGeneration.includes('createDisabledProductionPersistenceAdapter()') && persistenceAdapters.includes('BUSINESS_ACTION_FORMAL_EXECUTION_DISABLED'),
  page_cannot_write_formal_object:
    !purchaseReconciliationPage.includes('writeFormalObject') && !purchaseReconciliationPage.includes('executePurchaseReconciliationControlledGeneration'),
  page_cannot_select_persistence_adapter:
    !purchaseReconciliationPage.includes('createCanaryIsolatedPersistenceAdapter') && !purchaseReconciliationPage.includes('createDisabledProductionPersistenceAdapter'),
  formal_object_builder_single_owner:
    controlledGeneration.includes('buildPurchaseReconciliationFormalEquivalentObject') && !purchaseReconciliationPage.includes('businessHash:'),
  formal_number_scope_not_hardcoded:
    !reconciliationTransaction.includes("legalEntityId || 'LE-") && !reconciliationTransaction.includes("ledgerBookId || 'LEDGER-") && !reconciliationTransaction.includes("accountingPeriod || '20"),
  canary_number_rejected_by_formal_validator:
    documentNumberPolicy.includes('SIM-PRC-NUM-'),
  same_idempotency_single_object:
    controlledGeneration.includes("outcome: 'existing_result'") && persistenceAdapters.includes('supportsUniqueIdempotencyKey'),
  same_source_single_target:
    controlledGeneration.includes('readExistingTargets') && persistenceAdapters.includes('supportsUniqueSourceKey'),
  audit_required_for_commit:
    controlledGeneration.indexOf('writeAuditRecord') < controlledGeneration.indexOf('validateStagedState'),
  source_lifecycle_not_auto_completed:
    controlledGeneration.includes("supplierSettlementLifecycleStatusAfter: 'reconciling'") && controlledGeneration.includes('supplierSettlementLifecycleStatusWriteCount: 0'),
  review_passed_not_equal_execution_allowed:
    dualGate.includes('transactionGatePassed') && dualGate.includes('trustedExecutionContext') && dualGate.includes('explicitUserAction'),
  production_capability_not_inferred_from_canary:
    persistenceAdapters.includes('disabledProductionCapabilities') && persistenceAdapters.includes('canaryIsolatedCapabilities'),
  formal_write_requires_server_authorization:
    dualGate.includes('serverAuthorizationSupported') && persistenceAdapters.includes('supportsServerSideAuthorization'),
  payment_not_created_by_reconciliation_generation:
    controlledGeneration.includes('paymentObjectCount: 0') && controlledGeneration.includes('paymentVoucherCount: 0'),
  module_navigation_unchanged:
    !processRegistry.includes('采购对账正式生成受控执行') && !operationRegistry.includes('采购对账正式生成受控执行'),
}

for (const [gate, passed] of Object.entries(gates)) assert(passed, `${gate} failed`)

const requiredDefects = ['PCE-REG-084', 'PCE-REG-085', 'PCE-REG-086', 'PCE-REG-087', 'PCE-REG-088', 'PCE-REG-089']
const registeredDefects = new Set(listPceDefectRegressionRegistry().map((item) => item.defectId))
for (const id of requiredDefects) assert(registeredDefects.has(id), `${id} is not registered`)

console.log(JSON.stringify({
  page: 'verifyPurchasePayableSliceStability',
  version: 'V1.14.2.8.4.7',
  gates,
  contextResults: {
    existing: existing.status,
    pending: pending.status,
    invalid: invalid.status,
    all: all.status,
  },
  registeredDefects: requiredDefects,
  businessStoreModifiedByGate: false,
}, null, 2))

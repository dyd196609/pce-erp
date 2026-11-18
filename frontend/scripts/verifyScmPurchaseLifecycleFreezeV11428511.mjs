import fs from 'node:fs/promises'
import { readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { resolvePurchaseInquiryDomainObject } from '../src/meta/domain/scm/purchaseInquiry/purchaseInquiryDomainModel.js'
import { SUPPLIER_QUOTE_DOMAIN_MODEL } from '../src/meta/domain/scm/purchaseInquiry/quote/supplierQuoteDomainModel.js'
import { QUOTE_COMPARISON_DOMAIN_MODEL } from '../src/meta/domain/scm/purchaseInquiry/quote/quoteComparisonDomainModel.js'
import { SUPPLIER_RECOMMENDATION_DECISION_DOMAIN_MODEL } from '../src/meta/domain/scm/purchaseInquiry/recommendation/supplierRecommendationDecisionDomainModel.js'
import { evaluateSupplierRecommendationActionGuard } from '../src/meta/domain/scm/purchaseInquiry/recommendation/supplierRecommendationActionGuardRules.js'
import { PURCHASE_ORDER_CREATION_GATE_DOMAIN_MODEL } from '../src/meta/domain/scm/purchaseOrder/gate/purchaseOrderCreationGateDomainModel.js'
import { PURCHASE_ORDER_DOMAIN_MODEL } from '../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderDomainModel.js'
import { evaluatePurchaseOrderSourceReference } from '../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderSourceReference.js'
import { PURCHASE_ORDER_TRANSACTION_BOUNDARY } from '../src/meta/domain/scm/purchaseOrder/transaction/purchaseOrderTransactionBoundary.js'
import { PURCHASE_ORDER_APPROVAL_INTERFACE_BOUNDARY } from '../src/meta/domain/scm/purchaseOrder/approval/purchaseOrderApprovalInterfaceBoundary.js'
import { evaluatePurchaseOrderApprovalAction } from '../src/meta/domain/scm/purchaseOrder/approval/purchaseOrderApprovalActionGuardRules.js'
import { PURCHASE_ORDER_TRANSACTION_DOMAIN_MODEL } from '../src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderTransactionDomainModel.js'
import { PURCHASE_ORDER_LIFECYCLE_STATE_DEFINITION } from '../src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleStateDefinition.js'
import { PURCHASE_ORDER_ISSUE_BOUNDARY } from '../src/meta/domain/scm/purchaseOrder/issue/purchaseOrderIssueBoundary.js'
import { SUPPLIER_RELEASE_CONTEXT } from '../src/meta/domain/scm/purchaseOrder/issue/supplierReleaseContext.js'
import { evaluatePurchaseOrderIssueAction } from '../src/meta/domain/scm/purchaseOrder/issue/purchaseOrderIssueActionGuardRules.js'
import { SCM_PURCHASE_LIFECYCLE_MAP, validateScmPurchaseLifecycleMap } from '../src/meta/domain/scm/purchaseOrder/freeze/scmPurchaseLifecycleMap.js'
import { SCM_PURCHASE_LIFECYCLE_RELATION_RULES, evaluateScmPurchaseLifecycleRelation } from '../src/meta/domain/scm/purchaseOrder/freeze/scmPurchaseLifecycleRelationRules.js'
import { SCM_PURCHASE_LIFECYCLE_FORBIDDEN_RULES, evaluateScmPurchaseLifecycleForbiddenPath } from '../src/meta/domain/scm/purchaseOrder/freeze/scmPurchaseLifecycleForbiddenRules.js'
import { SCM_PURCHASE_LIFECYCLE_FREEZE_STATUS, validateScmPurchaseLifecycleFreezeStatus } from '../src/meta/domain/scm/purchaseOrder/freeze/scmPurchaseLifecycleFreezeStatus.js'
import { SCM_PURCHASE_LIFECYCLE_MODEL_FREEZE_ACCEPTANCE_PROFILE, validateScmPurchaseLifecycleFreezeAcceptanceProfile } from '../src/meta/acceptance/scm/scmPurchaseLifecycleFreezeAcceptanceProfiles.js'
import { activateAcceptanceFramework } from '../src/meta/acceptance/registry/enterpriseAcceptanceActivator.js'

export const VERSION = 'V1.14.2.8.5.11'
export const TARGET_STATUS = 'SCM_PURCHASE_LIFECYCLE_MODEL_FROZEN'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const databasePath = path.resolve(frontendRoot, '../backend/db.sqlite3')
const databaseSha = () => createHash('sha256').update(readFileSync(databasePath)).digest('hex')
const check = (code, category, name, pass, evidence) => Object.freeze({ code, category, name, result: pass ? 'PASS' : 'FAIL', evidence })

const expectedObjects = Object.freeze([
  resolvePurchaseInquiryDomainObject('SCM_PURCHASE_INQUIRY'),
  SUPPLIER_QUOTE_DOMAIN_MODEL,
  QUOTE_COMPARISON_DOMAIN_MODEL,
  SUPPLIER_RECOMMENDATION_DECISION_DOMAIN_MODEL,
  PURCHASE_ORDER_CREATION_GATE_DOMAIN_MODEL,
  PURCHASE_ORDER_DOMAIN_MODEL,
  PURCHASE_ORDER_TRANSACTION_BOUNDARY,
  PURCHASE_ORDER_APPROVAL_INTERFACE_BOUNDARY,
  PURCHASE_ORDER_TRANSACTION_DOMAIN_MODEL,
  PURCHASE_ORDER_LIFECYCLE_STATE_DEFINITION,
  PURCHASE_ORDER_ISSUE_BOUNDARY,
])

const forbiddenCases = Object.freeze([
  Object.freeze({ sourceObject: 'SCM_SUPPLIER_QUOTE', action: 'createPurchaseOrder', targetObject: 'SCM_PURCHASE_ORDER' }),
  Object.freeze({ sourceObject: 'SCM_QUOTE_COMPARISON', action: 'createPurchaseOrder', targetObject: 'SCM_PURCHASE_ORDER' }),
  Object.freeze({ sourceObject: 'SCM_SUPPLIER_RECOMMENDATION_DECISION', action: 'sendSupplier', targetObject: 'SUPPLIER_INTERFACE' }),
  Object.freeze({ sourceObject: 'SCM_PURCHASE_ORDER_APPROVAL_PREPARATION', action: 'submitApproval', targetObject: 'WORKFLOW' }),
  Object.freeze({ sourceObject: 'SCM_PURCHASE_ORDER_ISSUE_BOUNDARY', action: 'callSupplierApi', targetObject: 'SUPPLIER_API' }),
])

export function verifyScmPurchaseLifecycleFreeze() {
  const databaseShaBefore = databaseSha()
  const activation = activateAcceptanceFramework('SCM')
  const profile = activation.acceptanceProfiles?.find(item => item.profileCode === 'SCM_PURCHASE_LIFECYCLE_MODEL_FREEZE_ACCEPTANCE_PROFILE')
  const profileCodes = new Set(activation.acceptanceProfiles?.map(item => item.profileCode) || [])
  const upstreamProfilesRegistered = SCM_PURCHASE_LIFECYCLE_MODEL_FREEZE_ACCEPTANCE_PROFILE.upstreamProfiles.every(code => profileCodes.has(code))
  const rules = Object.freeze([
    check('SCM-PO-FREEZE-001', 'Lifecycle Map', 'All eleven lifecycle models are present', expectedObjects.length === 11 && expectedObjects.every(Boolean) && validateScmPurchaseLifecycleMap().valid, SCM_PURCHASE_LIFECYCLE_MAP),
    check('SCM-PO-FREEZE-002', 'Lifecycle Map', 'Lifecycle order and versions are frozen', SCM_PURCHASE_LIFECYCLE_MAP.nodes.every((item, index) => item.sequence === index + 1 && item.executionAllowed === false) && SCM_PURCHASE_LIFECYCLE_MAP.firstFrozenVersion === 'V1.14.2.8.5.3' && SCM_PURCHASE_LIFECYCLE_MAP.lastFrozenVersion === 'V1.14.2.8.5.10', SCM_PURCHASE_LIFECYCLE_MAP.nodes),
    check('SCM-PO-FREEZE-003', 'Relations', 'All adjacent forward relations are definition only', SCM_PURCHASE_LIFECYCLE_RELATION_RULES.length === 10 && SCM_PURCHASE_LIFECYCLE_RELATION_RULES.every(rule => evaluateScmPurchaseLifecycleRelation(rule).result === 'PASS' && rule.automaticGenerationAllowed === false && rule.executionAllowed === false), SCM_PURCHASE_LIFECYCLE_RELATION_RULES),
    check('SCM-PO-FREEZE-004', 'Relations', 'Skipped and reverse paths default deny', evaluateScmPurchaseLifecycleRelation({ sourceNode: 'SUPPLIER_QUOTE', targetNode: 'PURCHASE_ORDER_DOMAIN' }).result === 'FAIL' && evaluateScmPurchaseLifecycleRelation({ sourceNode: 'PURCHASE_ORDER_ISSUE_BOUNDARY', targetNode: 'PURCHASE_ORDER_LIFECYCLE' }).result === 'FAIL', { policy: 'adjacent_forward_only_default_deny' }),
    check('SCM-PO-FREEZE-005', 'Forbidden', 'Five prohibited paths are centrally frozen', SCM_PURCHASE_LIFECYCLE_FORBIDDEN_RULES.length === 5 && forbiddenCases.every(item => evaluateScmPurchaseLifecycleForbiddenPath(item).result === 'PASS' && evaluateScmPurchaseLifecycleForbiddenPath(item).blocked === true), SCM_PURCHASE_LIFECYCLE_FORBIDDEN_RULES),
    check('SCM-PO-FREEZE-006', 'Forbidden', 'Quote and comparison cannot directly create Purchase Order', SUPPLIER_QUOTE_DOMAIN_MODEL.createsPurchaseOrder === false && QUOTE_COMPARISON_DOMAIN_MODEL.createsPurchaseOrder === false && evaluatePurchaseOrderSourceReference({ sourceObject: 'SCM_SUPPLIER_QUOTE', sourceReferenceId: 'QUOTE-DEFINITION' }).result === 'FAIL' && evaluatePurchaseOrderSourceReference({ sourceObject: 'SCM_QUOTE_COMPARISON', sourceReferenceId: 'COMPARISON-DEFINITION' }).result === 'FAIL', { supplierQuote: 'blocked', quoteComparison: 'blocked' }),
    check('SCM-PO-FREEZE-007', 'Forbidden', 'Recommendation cannot issue Supplier', SUPPLIER_RECOMMENDATION_DECISION_DOMAIN_MODEL.createsPurchaseOrder === false && evaluateSupplierRecommendationActionGuard({ status: 'recommended', action: 'sendSupplier' }).result === 'FAIL', { action: 'sendSupplier', decision: 'deny' }),
    check('SCM-PO-FREEZE-008', 'Forbidden', 'Approval Preparation cannot submit Workflow', evaluatePurchaseOrderApprovalAction({ status: 'ready', action: 'submitApproval' }).result === 'FAIL' && PURCHASE_ORDER_APPROVAL_INTERFACE_BOUNDARY.createsWorkflowInstance === false, { action: 'submitApproval', decision: 'deny' }),
    check('SCM-PO-FREEZE-009', 'Forbidden', 'Issue Boundary cannot call Supplier API', evaluatePurchaseOrderIssueAction({ status: 'ready_for_future_issue', action: 'callSupplierApi' }).result === 'FAIL' && PURCHASE_ORDER_ISSUE_BOUNDARY.sendsSupplier === false && SUPPLIER_RELEASE_CONTEXT.supplierApiCallAllowed === false && SUPPLIER_RELEASE_CONTEXT.callsSupplierApi === false, { action: 'callSupplierApi', decision: 'deny' }),
    check('SCM-PO-FREEZE-010', 'Freeze', 'Freeze status is immutable and non-executable', validateScmPurchaseLifecycleFreezeStatus().valid && SCM_PURCHASE_LIFECYCLE_FREEZE_STATUS.allowedTransitions.length === 0 && SCM_PURCHASE_LIFECYCLE_FREEZE_STATUS.businessExecutionAllowed === false, SCM_PURCHASE_LIFECYCLE_FREEZE_STATUS),
    check('SCM-PO-FREEZE-011', 'Acceptance', 'All upstream profiles and freeze profile are registered', activation.activated && activation.activationStatus === 'READY' && upstreamProfilesRegistered && profile === SCM_PURCHASE_LIFECYCLE_MODEL_FREEZE_ACCEPTANCE_PROFILE && validateScmPurchaseLifecycleFreezeAcceptanceProfile(profile).valid, { upstreamProfilesRegistered, freezeProfile: profile || {} }),
    check('SCM-PO-FREEZE-012', 'Isolation', 'Lifecycle freeze produces zero business and production data writes', activation.businessWriteCount === 0 && activation.productionUserDataWritten === false && SCM_PURCHASE_LIFECYCLE_MAP.businessWriteCount === 0 && SCM_PURCHASE_LIFECYCLE_FREEZE_STATUS.businessWriteCount === 0 && SCM_PURCHASE_LIFECYCLE_MODEL_FREEZE_ACCEPTANCE_PROFILE.businessWriteCount === 0, { businessWriteCount: 0, productionDataWritten: false }),
  ])
  const count = result => rules.filter(item => item.result === result).length
  const summary = Object.freeze({ total: rules.length, PASS: count('PASS'), FAIL: count('FAIL'), 'N/A': count('N/A'), UNKNOWN: count('UNKNOWN') })
  const categoryResults = Object.freeze(Object.fromEntries(['Lifecycle Map', 'Relations', 'Forbidden', 'Freeze', 'Acceptance', 'Isolation'].map(category => [category, rules.filter(item => item.category === category).every(item => item.result === 'PASS') ? 'PASS' : 'FAIL'])))
  const databaseShaAfter = databaseSha()
  const databaseShaUnchanged = databaseShaBefore === databaseShaAfter
  const finalStatus = summary.FAIL === 0 && summary.UNKNOWN === 0 && databaseShaUnchanged ? TARGET_STATUS : 'FAIL'
  return Object.freeze({
    version: VERSION,
    generatedAt: new Date().toISOString(),
    status: finalStatus,
    summary,
    categoryResults,
    rules,
    finalReport: Object.freeze({
      problemAnalysis: Object.freeze(['Prior versions prove local read-only boundaries but lacked one immutable end-to-end map.', 'Cross-version skipped paths and the five prohibited paths required consolidated default-deny evidence.']),
      fileList: Object.freeze(['scm_purchase_lifecycle_freeze_scan_v11428511.json', 'src/meta/domain/scm/purchaseOrder/freeze/scmPurchaseLifecycleMap.js', 'src/meta/domain/scm/purchaseOrder/freeze/scmPurchaseLifecycleRelationRules.js', 'src/meta/domain/scm/purchaseOrder/freeze/scmPurchaseLifecycleForbiddenRules.js', 'src/meta/domain/scm/purchaseOrder/freeze/scmPurchaseLifecycleFreezeStatus.js', 'src/meta/acceptance/scm/scmPurchaseLifecycleFreezeAcceptanceProfiles.js', 'src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js', 'scripts/verifyScmPurchaseLifecycleFreezeV11428511.mjs', 'tests/acceptance/enterpriseScmPurchaseLifecycleFreezeV11428511.test.mjs']),
      implementationResult: Object.freeze({ lifecycleNodeCount: 11, adjacentRelationCount: 10, forbiddenPathCount: 5, frozen: true }),
      automaticVerificationResult: Object.freeze({ summary, categoryResults }),
      businessIsolationVerification: Object.freeze({ businessWriteCount: 0, databaseShaUnchanged, productionDataWritten: false }),
      finalStatus,
    }),
    registry: Object.freeze({ activationStatus: activation.activationStatus, profileCode: profile?.profileCode, mode: profile?.mode }),
    businessWriteCount: 0,
    databaseProtection: Object.freeze({ path: databasePath, shaBefore: databaseShaBefore, shaAfter: databaseShaAfter, databaseShaUnchanged }),
    productionDataWritten: false,
  })
}

export async function writeScmPurchaseLifecycleFreezeVerification({ outputRoot } = {}) {
  const archiveRoot = path.resolve(outputRoot || path.join(frontendRoot, 'test-results/page-acceptance', VERSION, 'scm-purchase-lifecycle-freeze'))
  const report = verifyScmPurchaseLifecycleFreeze()
  await fs.mkdir(archiveRoot, { recursive: true })
  await fs.writeFile(path.join(archiveRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return Object.freeze({ outputRoot: archiveRoot, files: Object.freeze(['verification-report.json']), report })
}

const invokedAsScript = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (invokedAsScript) {
  const result = await writeScmPurchaseLifecycleFreezeVerification()
  console.log(JSON.stringify({ ...result.report, outputRoot: result.outputRoot, files: result.files }, null, 2))
  if (result.report.status !== TARGET_STATUS) process.exitCode = 1
}

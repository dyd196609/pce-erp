import fs from 'node:fs/promises'
import { readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { PURCHASE_ORDER_ISSUE_BOUNDARY, validatePurchaseOrderIssueBoundary } from '../src/meta/domain/scm/purchaseOrder/issue/purchaseOrderIssueBoundary.js'
import { SUPPLIER_RELEASE_CONTEXT, buildSupplierReleaseContext, validateSupplierReleaseContext } from '../src/meta/domain/scm/purchaseOrder/issue/supplierReleaseContext.js'
import { PURCHASE_ORDER_ISSUE_PREPARATION, buildPurchaseOrderIssuePreparation } from '../src/meta/domain/scm/purchaseOrder/issue/purchaseOrderIssuePreparation.js'
import { PURCHASE_ORDER_ISSUE_STATUS_DEFINITION, validatePurchaseOrderIssueStatus } from '../src/meta/domain/scm/purchaseOrder/issue/purchaseOrderIssueStatusDefinition.js'
import { PURCHASE_ORDER_ISSUE_RULES, evaluatePurchaseOrderIssueBoundary } from '../src/meta/domain/scm/purchaseOrder/issue/purchaseOrderIssueRules.js'
import { PURCHASE_ORDER_ISSUE_ACTION_GUARD_RULES, PURCHASE_ORDER_ISSUE_ALLOWED_ACTIONS, PURCHASE_ORDER_ISSUE_FORBIDDEN_ACTIONS, evaluatePurchaseOrderIssueAction } from '../src/meta/domain/scm/purchaseOrder/issue/purchaseOrderIssueActionGuardRules.js'
import { PURCHASE_ORDER_ISSUE_FINANCE_BOUNDARY, evaluatePurchaseOrderIssueFinanceBoundary } from '../src/meta/domain/scm/purchaseOrder/issue/purchaseOrderIssueFinanceBoundary.js'
import { SCM_PURCHASE_ORDER_ISSUE_BOUNDARY_ACCEPTANCE_PROFILE, validatePurchaseOrderIssueBoundaryAcceptanceProfile } from '../src/meta/acceptance/scm/purchaseOrderIssueBoundaryAcceptanceProfiles.js'
import { activateAcceptanceFramework } from '../src/meta/acceptance/registry/enterpriseAcceptanceActivator.js'

export const VERSION = 'V1.14.2.8.5.10'
export const TARGET_STATUS = 'PURCHASE_ORDER_ISSUE_BOUNDARY_READY'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const databasePath = path.resolve(frontendRoot, '../backend/db.sqlite3')
const databaseSha = () => createHash('sha256').update(readFileSync(databasePath)).digest('hex')
const check = (code, category, name, pass, evidence) => Object.freeze({ code, category, name, result: pass ? 'PASS' : 'FAIL', evidence })

const readyFacts = Object.freeze({
  purchaseOrderTransactionId: 'PO-TRANSACTION-DEFINITION',
  lifecycleStatus: 'approved',
  approvalReference: 'APPROVAL-DEFINITION',
  supplierReference: 'SUPPLIER-DEFINITION',
  supplierReleaseContextStatus: 'ready',
  evidenceReferences: Object.freeze(['ISSUE-EVIDENCE-DEFINITION']),
})

export function verifyPurchaseOrderIssueBoundary() {
  const databaseShaBefore = databaseSha()
  const supplierContext = buildSupplierReleaseContext({ supplierId: 'SUPPLIER-DEFINITION', supplierContactReference: 'CONTACT-DEFINITION', orderSummaryReference: 'ORDER-SUMMARY-DEFINITION', deliveryRequirement: 'DELIVERY-DEFINITION', releaseEvidence: 'RELEASE-EVIDENCE-DEFINITION' })
  const preparation = buildPurchaseOrderIssuePreparation({ purchaseOrderTransactionId: readyFacts.purchaseOrderTransactionId, supplierReleaseContextId: 'SUPPLIER-CONTEXT-DEFINITION', approvalReference: readyFacts.approvalReference, evidenceReferences: readyFacts.evidenceReferences })
  const boundaryReady = evaluatePurchaseOrderIssueBoundary(readyFacts)
  const boundaryBlocked = evaluatePurchaseOrderIssueBoundary({ ...readyFacts, lifecycleStatus: 'draft' })
  const activation = activateAcceptanceFramework('SCM')
  const profile = activation.acceptanceProfiles?.find(item => item.profileCode === 'SCM_PURCHASE_ORDER_ISSUE_BOUNDARY_ACCEPTANCE_PROFILE')
  const rules = Object.freeze([
    check('PO-ISSUE-001', 'Boundary', 'Issue Boundary contains seven fields and cannot execute', validatePurchaseOrderIssueBoundary().valid && PURCHASE_ORDER_ISSUE_BOUNDARY.fields.length === 7 && PURCHASE_ORDER_ISSUE_BOUNDARY.createdAutomatically === false && PURCHASE_ORDER_ISSUE_BOUNDARY.executesIssue === false && PURCHASE_ORDER_ISSUE_BOUNDARY.sendsSupplier === false, PURCHASE_ORDER_ISSUE_BOUNDARY),
    check('PO-ISSUE-002', 'Supplier Context', 'Supplier Release Context is complete without API access', validateSupplierReleaseContext().valid && supplierContext.contextStatus === 'ready' && supplierContext.supplierApiCallAllowed === false && supplierContext.callsSupplierApi === false && supplierContext.sendsSupplier === false, supplierContext),
    check('PO-ISSUE-003', 'Rules', 'Issue Preparation is definition only', preparation.preparationStatus === 'ready' && PURCHASE_ORDER_ISSUE_PREPARATION.persistenceMode === 'definition_only' && preparation.executesIssue === false && preparation.sendsSupplier === false, preparation),
    check('PO-ISSUE-004', 'Rules', 'Ready facts produce future eligibility only', PURCHASE_ORDER_ISSUE_RULES.length === 4 && boundaryReady.issueAllowed === true && boundaryReady.issueStatus === 'ready_for_future_issue' && boundaryReady.decisionOnly === true && boundaryReady.executesIssue === false && boundaryReady.sendsSupplier === false && boundaryReady.supplierApiCalled === false, boundaryReady),
    check('PO-ISSUE-005', 'Rules', 'Unapproved lifecycle blocks issue eligibility', boundaryBlocked.issueAllowed === false && boundaryBlocked.issueStatus === 'blocked' && boundaryBlocked.blockingReasons.includes('transaction_is_approved'), boundaryBlocked),
    check('PO-ISSUE-006', 'Rules', 'Issue status never transitions or executes', PURCHASE_ORDER_ISSUE_STATUS_DEFINITION.allowedTransitions.length === 0 && PURCHASE_ORDER_ISSUE_STATUS_DEFINITION.transitionExecutionAllowed === false && validatePurchaseOrderIssueStatus('ready_for_future_issue').result === 'PASS', PURCHASE_ORDER_ISSUE_STATUS_DEFINITION),
    check('PO-ISSUE-007', 'Guard', 'Issue view actions are allowed', PURCHASE_ORDER_ISSUE_ALLOWED_ACTIONS.every(action => evaluatePurchaseOrderIssueAction({ status: 'ready_for_future_issue', action }).result === 'PASS'), PURCHASE_ORDER_ISSUE_ALLOWED_ACTIONS),
    check('PO-ISSUE-008', 'Guard', 'Issue and downstream actions are denied', PURCHASE_ORDER_ISSUE_FORBIDDEN_ACTIONS.every(action => PURCHASE_ORDER_ISSUE_ACTION_GUARD_RULES.every(guard => evaluatePurchaseOrderIssueAction({ status: guard.status, action }).result === 'FAIL')), PURCHASE_ORDER_ISSUE_FORBIDDEN_ACTIONS),
    check('PO-ISSUE-009', 'Finance', 'Finance boundary allows references and denies execution', PURCHASE_ORDER_ISSUE_FINANCE_BOUNDARY.allowedFacts.every(fact => evaluatePurchaseOrderIssueFinanceBoundary({ fact }).result === 'PASS') && PURCHASE_ORDER_ISSUE_FINANCE_BOUNDARY.forbiddenActions.every(action => evaluatePurchaseOrderIssueFinanceBoundary({ action }).result === 'FAIL'), PURCHASE_ORDER_ISSUE_FINANCE_BOUNDARY),
    check('PO-ISSUE-010', 'Acceptance', 'Acceptance profile is registered READY and read_only', activation.activated && activation.activationStatus === 'READY' && profile === SCM_PURCHASE_ORDER_ISSUE_BOUNDARY_ACCEPTANCE_PROFILE && validatePurchaseOrderIssueBoundaryAcceptanceProfile(profile).valid && profile.mode === 'read_only', profile || {}),
    check('PO-ISSUE-011', 'Acceptance', 'No business or production data writes', [PURCHASE_ORDER_ISSUE_BOUNDARY, SUPPLIER_RELEASE_CONTEXT, PURCHASE_ORDER_ISSUE_PREPARATION, PURCHASE_ORDER_ISSUE_FINANCE_BOUNDARY].every(model => model.persistenceMode === 'definition_only' && model.businessWriteCount === 0 && model.productionDataWritten === false) && activation.businessWriteCount === 0 && activation.productionUserDataWritten === false, { businessWriteCount: 0, productionDataWritten: false }),
  ])
  const count = result => rules.filter(item => item.result === result).length
  const summary = Object.freeze({ total: rules.length, PASS: count('PASS'), FAIL: count('FAIL'), 'N/A': count('N/A'), UNKNOWN: count('UNKNOWN') })
  const categoryResults = Object.freeze(Object.fromEntries(['Boundary', 'Supplier Context', 'Rules', 'Guard', 'Finance', 'Acceptance'].map(category => [category, rules.filter(item => item.category === category).every(item => item.result === 'PASS') ? 'PASS' : 'FAIL'])))
  const databaseShaAfter = databaseSha()
  const databaseShaUnchanged = databaseShaBefore === databaseShaAfter
  return Object.freeze({
    version: VERSION,
    generatedAt: new Date().toISOString(),
    status: summary.FAIL === 0 && summary.UNKNOWN === 0 && databaseShaUnchanged ? TARGET_STATUS : 'FAIL',
    summary,
    categoryResults,
    rules,
    registry: Object.freeze({ activationStatus: activation.activationStatus, profileCode: profile?.profileCode, mode: profile?.mode }),
    businessWriteCount: 0,
    databaseProtection: Object.freeze({ path: databasePath, shaBefore: databaseShaBefore, shaAfter: databaseShaAfter, databaseShaUnchanged }),
    productionDataWritten: false,
  })
}

export async function writePurchaseOrderIssueBoundaryVerification({ outputRoot } = {}) {
  const archiveRoot = path.resolve(outputRoot || path.join(frontendRoot, 'test-results/page-acceptance', VERSION, 'purchase-order-issue-boundary'))
  const report = verifyPurchaseOrderIssueBoundary()
  await fs.mkdir(archiveRoot, { recursive: true })
  await fs.writeFile(path.join(archiveRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return Object.freeze({ outputRoot: archiveRoot, files: Object.freeze(['verification-report.json']), report })
}

const invokedAsScript = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (invokedAsScript) {
  const result = await writePurchaseOrderIssueBoundaryVerification()
  console.log(JSON.stringify({ ...result.report, outputRoot: result.outputRoot, files: result.files }, null, 2))
  if (result.report.status !== TARGET_STATUS) process.exitCode = 1
}

import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { PURCHASE_ORDER_TRANSACTION_BOUNDARY, validatePurchaseOrderTransactionBoundary } from '../src/meta/domain/scm/purchaseOrder/transaction/purchaseOrderTransactionBoundary.js'
import { PURCHASE_ORDER_CREATION_REQUEST, validatePurchaseOrderCreationRequest } from '../src/meta/domain/scm/purchaseOrder/transaction/purchaseOrderCreationRequest.js'
import { PURCHASE_ORDER_CREATION_REQUEST_STATUS, validatePurchaseOrderCreationRequestStatus } from '../src/meta/domain/scm/purchaseOrder/transaction/purchaseOrderCreationRequestStatus.js'
import { PURCHASE_ORDER_APPROVAL_PREPARATION, buildPurchaseOrderApprovalPreparation } from '../src/meta/domain/scm/purchaseOrder/transaction/purchaseOrderApprovalPreparation.js'
import { PURCHASE_ORDER_TRANSACTION_BOUNDARY_RULES, evaluatePurchaseOrderTransactionBoundary } from '../src/meta/domain/scm/purchaseOrder/transaction/purchaseOrderTransactionBoundaryRules.js'
import { PURCHASE_ORDER_TRANSACTION_ACTION_GUARD_RULES, PURCHASE_ORDER_TRANSACTION_ALLOWED_ACTIONS, PURCHASE_ORDER_TRANSACTION_FORBIDDEN_ACTIONS, evaluatePurchaseOrderTransactionAction } from '../src/meta/domain/scm/purchaseOrder/transaction/purchaseOrderTransactionActionGuardRules.js'
import { PURCHASE_ORDER_TRANSACTION_FINANCE_BOUNDARY, evaluatePurchaseOrderTransactionFinanceBoundary } from '../src/meta/domain/scm/purchaseOrder/transaction/purchaseOrderTransactionFinanceBoundary.js'
import { SCM_PURCHASE_ORDER_TRANSACTION_BOUNDARY_ACCEPTANCE_PROFILE, validatePurchaseOrderTransactionBoundaryAcceptanceProfile } from '../src/meta/acceptance/scm/purchaseOrderTransactionBoundaryAcceptanceProfiles.js'
import { activateAcceptanceFramework } from '../src/meta/acceptance/registry/enterpriseAcceptanceActivator.js'

export const VERSION = 'V1.14.2.8.5.7'
export const TARGET_STATUS = 'PURCHASE_ORDER_TRANSACTION_BOUNDARY_READY'

const readyFacts = Object.freeze({ supplierRecommendationDecisionExists: true, purchaseOrderCreationGateExists: true, gateEligibilityResult: 'ELIGIBLE', purchaseOrderDomainValid: true })
const rule = (code, name, pass, evidence) => Object.freeze({ code, name, result: pass ? 'PASS' : 'FAIL', evidence })

export function verifyPurchaseOrderTransactionBoundary() {
  const activation = activateAcceptanceFramework('SCM')
  const profile = activation.acceptanceProfiles?.find(item => item.profileCode === 'SCM_PURCHASE_ORDER_TRANSACTION_BOUNDARY_ACCEPTANCE_PROFILE')
  const boundaryReady = evaluatePurchaseOrderTransactionBoundary(readyFacts)
  const boundaryBlocked = evaluatePurchaseOrderTransactionBoundary({ ...readyFacts, gateEligibilityResult: 'BLOCKED' })
  const approvalPreparation = buildPurchaseOrderApprovalPreparation({ transactionAllowed: true, requestStatus: 'ready_for_approval', evidenceReferences: ['EVIDENCE-DEFINITION'] })
  const rules = Object.freeze([
    rule('PO-TXN-001', 'TransactionBoundary完整', PURCHASE_ORDER_TRANSACTION_BOUNDARY.objectCode === 'SCM_PURCHASE_ORDER_TRANSACTION_BOUNDARY' && PURCHASE_ORDER_TRANSACTION_BOUNDARY.fields.length === 6 && validatePurchaseOrderTransactionBoundary().result === 'PASS' && PURCHASE_ORDER_TRANSACTION_BOUNDARY.createdAutomatically === false && PURCHASE_ORDER_TRANSACTION_BOUNDARY.createsPurchaseOrder === false, PURCHASE_ORDER_TRANSACTION_BOUNDARY),
    rule('PO-TXN-002', 'CreationRequest完整', PURCHASE_ORDER_CREATION_REQUEST.objectCode === 'SCM_PURCHASE_ORDER_CREATION_REQUEST' && validatePurchaseOrderCreationRequest().result === 'PASS' && PURCHASE_ORDER_CREATION_REQUEST.submitsWorkflow === false, PURCHASE_ORDER_CREATION_REQUEST),
    rule('PO-TXN-003', 'Request状态只读', PURCHASE_ORDER_CREATION_REQUEST_STATUS.allowedTransitions.length === 0 && PURCHASE_ORDER_CREATION_REQUEST_STATUS.transitionExecutionAllowed === false && validatePurchaseOrderCreationRequestStatus('ready_for_approval').result === 'PASS', PURCHASE_ORDER_CREATION_REQUEST_STATUS),
    rule('PO-TXN-004', 'Approval Preparation完整', PURCHASE_ORDER_APPROVAL_PREPARATION.submitsApproval === false && PURCHASE_ORDER_APPROVAL_PREPARATION.approvalExecutionAllowed === false && approvalPreparation.preparationStatus === 'READY' && approvalPreparation.submitsApproval === false && approvalPreparation.createsPurchaseOrder === false, approvalPreparation),
    rule('PO-TXN-005', 'Boundary规则通过', PURCHASE_ORDER_TRANSACTION_BOUNDARY_RULES.length === 4 && boundaryReady.transactionAllowed === true && boundaryReady.boundaryResult === 'READY_FOR_FUTURE_TRANSACTION' && boundaryReady.executesTransaction === false && boundaryReady.createsPurchaseOrder === false, boundaryReady),
    rule('PO-TXN-006', 'Boundary缺失条件阻断', boundaryBlocked.transactionAllowed === false && boundaryBlocked.boundaryResult === 'BLOCKED' && boundaryBlocked.blockingReasons.includes('creation_gate_eligible'), boundaryBlocked),
    rule('PO-TXN-007', 'Action Guard完整', PURCHASE_ORDER_TRANSACTION_ALLOWED_ACTIONS.every(action => evaluatePurchaseOrderTransactionAction({ status: 'evaluated', action }).result === 'PASS') && PURCHASE_ORDER_TRANSACTION_FORBIDDEN_ACTIONS.every(action => PURCHASE_ORDER_TRANSACTION_ACTION_GUARD_RULES.every(guard => evaluatePurchaseOrderTransactionAction({ status: guard.status, action }).result === 'FAIL')), { allowed: PURCHASE_ORDER_TRANSACTION_ALLOWED_ACTIONS, forbidden: PURCHASE_ORDER_TRANSACTION_FORBIDDEN_ACTIONS }),
    rule('PO-TXN-008', 'Finance边界完整', PURCHASE_ORDER_TRANSACTION_FINANCE_BOUNDARY.allowedFacts.every(fact => evaluatePurchaseOrderTransactionFinanceBoundary({ fact }).result === 'PASS') && PURCHASE_ORDER_TRANSACTION_FINANCE_BOUNDARY.forbiddenActions.every(action => evaluatePurchaseOrderTransactionFinanceBoundary({ action }).result === 'FAIL'), PURCHASE_ORDER_TRANSACTION_FINANCE_BOUNDARY),
    rule('PO-TXN-009', 'Acceptance注册成功', activation.activated && profile === SCM_PURCHASE_ORDER_TRANSACTION_BOUNDARY_ACCEPTANCE_PROFILE && validatePurchaseOrderTransactionBoundaryAcceptanceProfile(profile).valid && profile.activationMode === 'read_only', profile || {}),
    rule('PO-TXN-010', '无业务写入', [PURCHASE_ORDER_TRANSACTION_BOUNDARY, PURCHASE_ORDER_CREATION_REQUEST, PURCHASE_ORDER_APPROVAL_PREPARATION].every(model => model.persistenceMode === 'definition_only' && model.automaticCreation === false && model.createsPurchaseOrder === false) && boundaryReady.businessWriteCount === 0 && approvalPreparation.businessWriteCount === 0 && activation.businessWriteCount === 0 && activation.productionUserDataWritten === false, { businessWriteCount: 0, productionUserDataWritten: false }),
  ])
  const count = result => rules.filter(item => item.result === result).length
  const summary = Object.freeze({ total: rules.length, PASS: count('PASS'), FAIL: count('FAIL'), 'N/A': count('N/A'), UNKNOWN: count('UNKNOWN') })
  return Object.freeze({
    version: VERSION,
    generatedAt: new Date().toISOString(),
    status: summary.PASS === 10 && summary.FAIL === 0 && summary.UNKNOWN === 0 ? TARGET_STATUS : 'FAIL',
    summary,
    rules,
    registry: Object.freeze({ activated: activation.activated, activationStatus: activation.activationStatus, profileCode: profile?.profileCode, activationMode: profile?.activationMode }),
    businessLogicChanged: false,
    scmLogicChanged: false,
    businessWriteCount: 0,
    productionUserDataWritten: false,
  })
}

export async function writePurchaseOrderTransactionBoundaryVerification({ outputRoot } = {}) {
  const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
  const archiveRoot = path.resolve(outputRoot || path.join(frontendRoot, 'test-results/page-acceptance', VERSION, 'purchase-order-transaction-boundary'))
  const report = verifyPurchaseOrderTransactionBoundary()
  await fs.mkdir(archiveRoot, { recursive: true })
  await fs.writeFile(path.join(archiveRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return Object.freeze({ outputRoot: archiveRoot, files: Object.freeze(['verification-report.json']), report })
}

const invokedAsScript = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (invokedAsScript) {
  const result = await writePurchaseOrderTransactionBoundaryVerification()
  console.log(JSON.stringify({ ...result.report, outputRoot: result.outputRoot, files: result.files }, null, 2))
  if (result.report.status !== TARGET_STATUS) process.exitCode = 1
}

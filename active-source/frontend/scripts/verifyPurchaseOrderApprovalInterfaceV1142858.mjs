import fs from 'node:fs/promises'
import { readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { PURCHASE_ORDER_APPROVAL_PREPARATION_DOMAIN_MODEL, validatePurchaseOrderApprovalPreparationDomainModel } from '../src/meta/domain/scm/purchaseOrder/approval/purchaseOrderApprovalPreparationDomainModel.js'
import { PURCHASE_ORDER_APPROVAL_PREPARATION_STATUS, validatePurchaseOrderApprovalPreparationStatus } from '../src/meta/domain/scm/purchaseOrder/approval/purchaseOrderApprovalPreparationStatus.js'
import { evaluatePurchaseOrderApprovalPreparation } from '../src/meta/domain/scm/purchaseOrder/approval/purchaseOrderApprovalPreparationRules.js'
import { PURCHASE_ORDER_APPROVAL_CONTEXT, buildPurchaseOrderApprovalContext, validatePurchaseOrderApprovalContext } from '../src/meta/domain/scm/purchaseOrder/approval/purchaseOrderApprovalContext.js'
import { PURCHASE_ORDER_APPROVAL_INTERFACE_BOUNDARY, evaluatePurchaseOrderApprovalInterfaceBoundary } from '../src/meta/domain/scm/purchaseOrder/approval/purchaseOrderApprovalInterfaceBoundary.js'
import { PURCHASE_ORDER_APPROVAL_ACTION_GUARD_RULES, PURCHASE_ORDER_APPROVAL_ALLOWED_ACTIONS, PURCHASE_ORDER_APPROVAL_FORBIDDEN_ACTIONS, evaluatePurchaseOrderApprovalAction } from '../src/meta/domain/scm/purchaseOrder/approval/purchaseOrderApprovalActionGuardRules.js'
import { PURCHASE_ORDER_APPROVAL_FINANCE_BOUNDARY, evaluatePurchaseOrderApprovalFinanceBoundary } from '../src/meta/domain/scm/purchaseOrder/approval/purchaseOrderApprovalFinanceBoundary.js'
import { SCM_PURCHASE_ORDER_APPROVAL_INTERFACE_ACCEPTANCE_PROFILE, validatePurchaseOrderApprovalInterfaceAcceptanceProfile } from '../src/meta/acceptance/scm/purchaseOrderApprovalInterfaceAcceptanceProfiles.js'
import { activateAcceptanceFramework } from '../src/meta/acceptance/registry/enterpriseAcceptanceActivator.js'

export const VERSION = 'V1.14.2.8.5.8'
export const TARGET_STATUS = 'PURCHASE_ORDER_APPROVAL_INTERFACE_READY'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const databasePath = path.resolve(frontendRoot, '../backend/db.sqlite3')
const databaseSha = () => createHash('sha256').update(readFileSync(databasePath)).digest('hex')
const check = (code, category, name, pass, evidence) => Object.freeze({ code, category, name, result: pass ? 'PASS' : 'FAIL', evidence })

const preparationInput = Object.freeze({
  purchaseOrderDomainId: 'PO-DOMAIN-DEFINITION',
  creationRequestId: 'PO-CREATION-REQUEST-DEFINITION',
  transactionBoundaryId: 'PO-TRANSACTION-BOUNDARY-DEFINITION',
  supplierReference: 'SUPPLIER-DEFINITION',
  amountReference: 'AMOUNT-DEFINITION',
  deliveryRequirement: 'DELIVERY-DEFINITION',
  evidenceReferences: Object.freeze(['EVIDENCE-DEFINITION']),
  riskSummary: Object.freeze({ level: 'definition_only' }),
})

export function verifyPurchaseOrderApprovalInterface() {
  const databaseShaBefore = databaseSha()
  const preparation = evaluatePurchaseOrderApprovalPreparation(preparationInput)
  const context = buildPurchaseOrderApprovalContext({
    approvalPreparationId: 'APPROVAL-PREPARATION-DEFINITION',
    approvalSubject: { purchaseOrderDomainId: preparation.purchaseOrderDomainId },
    sourceReference: { transactionBoundaryId: preparation.transactionBoundaryId },
    businessEvidence: preparation.evidenceReferences,
  })
  const boundary = evaluatePurchaseOrderApprovalInterfaceBoundary({ preparation, context })
  const activation = activateAcceptanceFramework('SCM')
  const profile = activation.acceptanceProfiles?.find(item => item.profileCode === 'SCM_PURCHASE_ORDER_APPROVAL_INTERFACE_ACCEPTANCE_PROFILE')
  const rules = Object.freeze([
    check('PO-APPROVAL-001', 'Domain', 'Approval Preparation domain model', validatePurchaseOrderApprovalPreparationDomainModel().valid && PURCHASE_ORDER_APPROVAL_PREPARATION_DOMAIN_MODEL.fields.length === 8 && PURCHASE_ORDER_APPROVAL_PREPARATION_DOMAIN_MODEL.createdAutomatically === false && PURCHASE_ORDER_APPROVAL_PREPARATION_DOMAIN_MODEL.submitsApproval === false && PURCHASE_ORDER_APPROVAL_PREPARATION_DOMAIN_MODEL.createsWorkflowInstance === false, PURCHASE_ORDER_APPROVAL_PREPARATION_DOMAIN_MODEL),
    check('PO-APPROVAL-002', 'Domain', 'Approval Preparation rules', preparation.approvalPreparationReady === true && preparation.preparationStatus === 'ready' && preparation.businessWriteCount === 0 && preparation.productionDataWritten === false, preparation),
    check('PO-APPROVAL-003', 'Domain', 'Approval Preparation status is definition only', PURCHASE_ORDER_APPROVAL_PREPARATION_STATUS.allowedTransitions.length === 0 && PURCHASE_ORDER_APPROVAL_PREPARATION_STATUS.createsWorkflowInstance === false && validatePurchaseOrderApprovalPreparationStatus('ready').result === 'PASS', PURCHASE_ORDER_APPROVAL_PREPARATION_STATUS),
    check('PO-APPROVAL-004', 'Domain', 'Approval Context is isolated', validatePurchaseOrderApprovalContext().valid && PURCHASE_ORDER_APPROVAL_CONTEXT.fields.length === 4 && context.contextStatus === 'ready' && context.createsApprovalInstance === false && context.createsWorkflowInstance === false, context),
    check('PO-APPROVAL-005', 'Boundary', 'Approval Interface Boundary is read only', boundary.interfaceReady === true && boundary.outputMode === 'read_only_contract' && boundary.createsApprovalInstance === false && boundary.createsWorkflowInstance === false && boundary.submitsApproval === false && PURCHASE_ORDER_APPROVAL_INTERFACE_BOUNDARY.approvalDecisionAllowed === false, boundary),
    check('PO-APPROVAL-006', 'Boundary', 'Incomplete context is blocked', evaluatePurchaseOrderApprovalInterfaceBoundary({ preparation, context: buildPurchaseOrderApprovalContext({}) }).interfaceReady === false, { expected: 'blocked' }),
    check('PO-APPROVAL-007', 'Guard', 'View actions are allowed', PURCHASE_ORDER_APPROVAL_ALLOWED_ACTIONS.every(action => evaluatePurchaseOrderApprovalAction({ status: 'ready', action }).result === 'PASS'), PURCHASE_ORDER_APPROVAL_ALLOWED_ACTIONS),
    check('PO-APPROVAL-008', 'Guard', 'Execution actions are denied', PURCHASE_ORDER_APPROVAL_FORBIDDEN_ACTIONS.every(action => PURCHASE_ORDER_APPROVAL_ACTION_GUARD_RULES.every(guard => evaluatePurchaseOrderApprovalAction({ status: guard.status, action }).result === 'FAIL')), PURCHASE_ORDER_APPROVAL_FORBIDDEN_ACTIONS),
    check('PO-APPROVAL-009', 'Finance', 'Finance facts and execution boundary', PURCHASE_ORDER_APPROVAL_FINANCE_BOUNDARY.allowedFacts.every(fact => evaluatePurchaseOrderApprovalFinanceBoundary({ fact }).result === 'PASS') && PURCHASE_ORDER_APPROVAL_FINANCE_BOUNDARY.forbiddenActions.every(action => evaluatePurchaseOrderApprovalFinanceBoundary({ action }).result === 'FAIL'), PURCHASE_ORDER_APPROVAL_FINANCE_BOUNDARY),
    check('PO-APPROVAL-010', 'Acceptance', 'Acceptance profile is registered read only', activation.activated && activation.activationStatus === 'READY' && profile === SCM_PURCHASE_ORDER_APPROVAL_INTERFACE_ACCEPTANCE_PROFILE && validatePurchaseOrderApprovalInterfaceAcceptanceProfile(profile).valid && profile.mode === 'read_only', profile || {}),
    check('PO-APPROVAL-011', 'Acceptance', 'No business or production data write capability', [PURCHASE_ORDER_APPROVAL_PREPARATION_DOMAIN_MODEL, PURCHASE_ORDER_APPROVAL_CONTEXT, PURCHASE_ORDER_APPROVAL_INTERFACE_BOUNDARY, PURCHASE_ORDER_APPROVAL_FINANCE_BOUNDARY].every(model => model.persistenceMode === 'definition_only' && model.businessWriteCount === 0 && model.productionDataWritten === false) && activation.businessWriteCount === 0 && activation.productionUserDataWritten === false, { businessWriteCount: 0, productionDataWritten: false }),
  ])
  const count = result => rules.filter(item => item.result === result).length
  const summary = Object.freeze({ total: rules.length, PASS: count('PASS'), FAIL: count('FAIL'), 'N/A': count('N/A'), UNKNOWN: count('UNKNOWN') })
  const categoryResults = Object.freeze(Object.fromEntries(['Domain', 'Boundary', 'Guard', 'Finance', 'Acceptance'].map(category => [category, rules.filter(item => item.category === category).every(item => item.result === 'PASS') ? 'PASS' : 'FAIL'])))
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

export async function writePurchaseOrderApprovalInterfaceVerification({ outputRoot } = {}) {
  const archiveRoot = path.resolve(outputRoot || path.join(frontendRoot, 'test-results/page-acceptance', VERSION, 'purchase-order-approval-interface'))
  const report = verifyPurchaseOrderApprovalInterface()
  await fs.mkdir(archiveRoot, { recursive: true })
  await fs.writeFile(path.join(archiveRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return Object.freeze({ outputRoot: archiveRoot, files: Object.freeze(['verification-report.json']), report })
}

const invokedAsScript = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (invokedAsScript) {
  const result = await writePurchaseOrderApprovalInterfaceVerification()
  console.log(JSON.stringify({ ...result.report, outputRoot: result.outputRoot, files: result.files }, null, 2))
  if (result.report.status !== TARGET_STATUS) process.exitCode = 1
}

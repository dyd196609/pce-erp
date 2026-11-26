import fs from 'node:fs/promises'
import { readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { PURCHASE_ORDER_TRANSACTION_DOMAIN_MODEL, buildPurchaseOrderTransactionDefinition, validatePurchaseOrderTransactionDomainModel } from '../src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderTransactionDomainModel.js'
import { PURCHASE_ORDER_TRANSACTION_LINE_DOMAIN_MODEL, validatePurchaseOrderTransactionLineDomainModel } from '../src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderTransactionLineDomainModel.js'
import { PURCHASE_ORDER_LIFECYCLE_STATES, PURCHASE_ORDER_LIFECYCLE_STATE_DEFINITION, validatePurchaseOrderLifecycleState } from '../src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleStateDefinition.js'
import { PURCHASE_ORDER_LIFECYCLE_RULES, evaluatePurchaseOrderLifecycleRule } from '../src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleRules.js'
import { PURCHASE_ORDER_TRANSACTION_MODEL_ACTION_GUARD_RULES, PURCHASE_ORDER_TRANSACTION_MODEL_ALLOWED_ACTIONS, PURCHASE_ORDER_TRANSACTION_MODEL_FORBIDDEN_ACTIONS, evaluatePurchaseOrderTransactionModelAction } from '../src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderTransactionActionGuardRules.js'
import { PURCHASE_ORDER_TRANSACTION_MODEL_FINANCE_BOUNDARY, evaluatePurchaseOrderTransactionModelFinanceBoundary } from '../src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderTransactionFinanceBoundary.js'
import { SCM_PURCHASE_ORDER_TRANSACTION_ACCEPTANCE_PROFILE, validatePurchaseOrderTransactionAcceptanceProfile } from '../src/meta/acceptance/scm/purchaseOrderTransactionAcceptanceProfiles.js'
import { activateAcceptanceFramework } from '../src/meta/acceptance/registry/enterpriseAcceptanceActivator.js'

export const VERSION = 'V1.14.2.8.5.9'
export const TARGET_STATUS = 'PURCHASE_ORDER_TRANSACTION_MODEL_READY'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const databasePath = path.resolve(frontendRoot, '../backend/db.sqlite3')
const databaseSha = () => createHash('sha256').update(readFileSync(databasePath)).digest('hex')
const check = (code, category, name, pass, evidence) => Object.freeze({ code, category, name, result: pass ? 'PASS' : 'FAIL', evidence })

const transactionInput = Object.freeze({
  transactionNo: 'PO-TRANSACTION-DEFINITION',
  purchaseOrderDomainId: 'PO-DOMAIN-DEFINITION',
  sourceReference: 'APPROVAL-INTERFACE-DEFINITION',
  supplierId: 'SUPPLIER-DEFINITION',
  orderLines: Object.freeze(['PO-LINE-DEFINITION']),
  totalAmountReference: 'TOTAL-AMOUNT-DEFINITION',
  currency: 'CNY',
  lifecycleStatus: 'draft',
  approvalReference: 'APPROVAL-REFERENCE-DEFINITION',
})

export function verifyPurchaseOrderTransactionModel() {
  const databaseShaBefore = databaseSha()
  const transaction = buildPurchaseOrderTransactionDefinition(transactionInput)
  const activation = activateAcceptanceFramework('SCM')
  const profile = activation.acceptanceProfiles?.find(item => item.profileCode === 'SCM_PURCHASE_ORDER_TRANSACTION_ACCEPTANCE_PROFILE')
  const rules = Object.freeze([
    check('PO-TRANSACTION-MODEL-001', 'Transaction', 'Transaction model contains nine required fields', validatePurchaseOrderTransactionDomainModel().valid && PURCHASE_ORDER_TRANSACTION_DOMAIN_MODEL.fields.length === 9 && transaction.definitionStatus === 'ready', PURCHASE_ORDER_TRANSACTION_DOMAIN_MODEL),
    check('PO-TRANSACTION-MODEL-002', 'Transaction', 'Transaction model cannot create or execute business transaction', transaction.createdAutomatically === false && transaction.createsBusinessTransaction === false && transaction.executesTransaction === false && transaction.businessWriteCount === 0, transaction),
    check('PO-TRANSACTION-MODEL-003', 'Line', 'Transaction Line is definition-only child model', validatePurchaseOrderTransactionLineDomainModel().valid && PURCHASE_ORDER_TRANSACTION_LINE_DOMAIN_MODEL.independentCreationAllowed === false && PURCHASE_ORDER_TRANSACTION_LINE_DOMAIN_MODEL.executesTransaction === false, PURCHASE_ORDER_TRANSACTION_LINE_DOMAIN_MODEL),
    check('PO-TRANSACTION-MODEL-004', 'Lifecycle', 'Lifecycle defines all seven statuses', PURCHASE_ORDER_LIFECYCLE_STATES.length === 7 && ['draft', 'pending_approval', 'approved', 'issued', 'partially_received', 'completed', 'cancelled'].every(status => validatePurchaseOrderLifecycleState(status).result === 'PASS'), PURCHASE_ORDER_LIFECYCLE_STATES),
    check('PO-TRANSACTION-MODEL-005', 'Lifecycle', 'Lifecycle relationships never execute transitions', PURCHASE_ORDER_LIFECYCLE_RULES.length === 7 && PURCHASE_ORDER_LIFECYCLE_STATE_DEFINITION.automaticTransitionAllowed === false && PURCHASE_ORDER_LIFECYCLE_STATE_DEFINITION.transitionExecutionAllowed === false && PURCHASE_ORDER_LIFECYCLE_RULES.every(rule => rule.to.every(to => evaluatePurchaseOrderLifecycleRule({ from: rule.from, to }).transitionExecuted === false)), PURCHASE_ORDER_LIFECYCLE_STATE_DEFINITION),
    check('PO-TRANSACTION-MODEL-006', 'Guard', 'Read-only transaction actions are allowed', PURCHASE_ORDER_TRANSACTION_MODEL_ALLOWED_ACTIONS.every(action => evaluatePurchaseOrderTransactionModelAction({ status: 'ready', action }).result === 'PASS'), PURCHASE_ORDER_TRANSACTION_MODEL_ALLOWED_ACTIONS),
    check('PO-TRANSACTION-MODEL-007', 'Guard', 'Transaction execution actions are denied', PURCHASE_ORDER_TRANSACTION_MODEL_FORBIDDEN_ACTIONS.every(action => PURCHASE_ORDER_TRANSACTION_MODEL_ACTION_GUARD_RULES.every(guard => evaluatePurchaseOrderTransactionModelAction({ status: guard.status, action }).result === 'FAIL')), PURCHASE_ORDER_TRANSACTION_MODEL_FORBIDDEN_ACTIONS),
    check('PO-TRANSACTION-MODEL-008', 'Finance', 'Finance facts are references and execution is forbidden', PURCHASE_ORDER_TRANSACTION_MODEL_FINANCE_BOUNDARY.allowedFacts.every(fact => evaluatePurchaseOrderTransactionModelFinanceBoundary({ fact }).result === 'PASS') && PURCHASE_ORDER_TRANSACTION_MODEL_FINANCE_BOUNDARY.forbiddenActions.every(action => evaluatePurchaseOrderTransactionModelFinanceBoundary({ action }).result === 'FAIL'), PURCHASE_ORDER_TRANSACTION_MODEL_FINANCE_BOUNDARY),
    check('PO-TRANSACTION-MODEL-009', 'Acceptance', 'Acceptance profile is registered READY and read_only', activation.activated && activation.activationStatus === 'READY' && profile === SCM_PURCHASE_ORDER_TRANSACTION_ACCEPTANCE_PROFILE && validatePurchaseOrderTransactionAcceptanceProfile(profile).valid && profile.mode === 'read_only', profile || {}),
    check('PO-TRANSACTION-MODEL-010', 'Acceptance', 'No business or production data writes', [PURCHASE_ORDER_TRANSACTION_DOMAIN_MODEL, PURCHASE_ORDER_TRANSACTION_LINE_DOMAIN_MODEL, PURCHASE_ORDER_TRANSACTION_MODEL_FINANCE_BOUNDARY].every(model => model.persistenceMode === 'definition_only' && model.businessWriteCount === 0 && model.productionDataWritten === false) && activation.businessWriteCount === 0 && activation.productionUserDataWritten === false, { businessWriteCount: 0, productionDataWritten: false }),
  ])
  const count = result => rules.filter(item => item.result === result).length
  const summary = Object.freeze({ total: rules.length, PASS: count('PASS'), FAIL: count('FAIL'), 'N/A': count('N/A'), UNKNOWN: count('UNKNOWN') })
  const categoryResults = Object.freeze(Object.fromEntries(['Transaction', 'Line', 'Lifecycle', 'Guard', 'Finance', 'Acceptance'].map(category => [category, rules.filter(item => item.category === category).every(item => item.result === 'PASS') ? 'PASS' : 'FAIL'])))
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

export async function writePurchaseOrderTransactionModelVerification({ outputRoot } = {}) {
  const archiveRoot = path.resolve(outputRoot || path.join(frontendRoot, 'test-results/page-acceptance', VERSION, 'purchase-order-transaction-model'))
  const report = verifyPurchaseOrderTransactionModel()
  await fs.mkdir(archiveRoot, { recursive: true })
  await fs.writeFile(path.join(archiveRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return Object.freeze({ outputRoot: archiveRoot, files: Object.freeze(['verification-report.json']), report })
}

const invokedAsScript = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (invokedAsScript) {
  const result = await writePurchaseOrderTransactionModelVerification()
  console.log(JSON.stringify({ ...result.report, outputRoot: result.outputRoot, files: result.files }, null, 2))
  if (result.report.status !== TARGET_STATUS) process.exitCode = 1
}

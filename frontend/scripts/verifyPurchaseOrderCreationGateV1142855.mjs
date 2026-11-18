import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { PURCHASE_ORDER_CREATION_GATE_DOMAIN_MODEL, validatePurchaseOrderCreationGateDomainModel } from '../src/meta/domain/scm/purchaseOrder/gate/purchaseOrderCreationGateDomainModel.js'
import { PURCHASE_ORDER_CREATION_RULES } from '../src/meta/domain/scm/purchaseOrder/gate/purchaseOrderCreationRules.js'
import { evaluatePurchaseOrderCreationEligibility } from '../src/meta/domain/scm/purchaseOrder/gate/purchaseOrderCreationEligibility.js'
import { PURCHASE_ORDER_CREATION_GATE_ACTION_GUARD_RULES, PURCHASE_ORDER_CREATION_GATE_ALLOWED_ACTIONS, PURCHASE_ORDER_CREATION_GATE_FORBIDDEN_ACTIONS, evaluatePurchaseOrderCreationGateAction } from '../src/meta/domain/scm/purchaseOrder/gate/purchaseOrderCreationGateActionGuardRules.js'
import { PURCHASE_ORDER_CREATION_FINANCE_BOUNDARY, evaluatePurchaseOrderCreationFinanceBoundary } from '../src/meta/domain/scm/purchaseOrder/gate/purchaseOrderCreationFinanceBoundary.js'
import { SCM_PURCHASE_ORDER_CREATION_GATE_ACCEPTANCE_PROFILE, validatePurchaseOrderCreationGateAcceptanceProfile } from '../src/meta/acceptance/scm/purchaseOrderCreationGateAcceptanceProfiles.js'
import { activateAcceptanceFramework } from '../src/meta/acceptance/registry/enterpriseAcceptanceActivator.js'

export const VERSION = 'V1.14.2.8.5.5'
export const TARGET_STATUS = 'PURCHASE_ORDER_CREATION_GATE_MODEL_READY'

const eligibleFacts = Object.freeze({ recommendationDecisionExists: true, supplierQuoteValid: true, quoteComparisonCompleted: true, supplierValid: true })
const rule = (code, name, pass, evidence) => Object.freeze({ code, name, result: pass ? 'PASS' : 'FAIL', evidence })

export function verifyPurchaseOrderCreationGate() {
  const activation = activateAcceptanceFramework('SCM')
  const profile = activation.acceptanceProfiles?.find(item => item.profileCode === 'SCM_PURCHASE_ORDER_CREATION_GATE_ACCEPTANCE_PROFILE')
  const eligible = evaluatePurchaseOrderCreationEligibility(eligibleFacts)
  const missingDecision = evaluatePurchaseOrderCreationEligibility({ ...eligibleFacts, recommendationDecisionExists: false })
  const invalidDependencies = evaluatePurchaseOrderCreationEligibility({ recommendationDecisionExists: true, supplierQuoteValid: false, quoteComparisonCompleted: false, supplierValid: false })
  const rules = Object.freeze([
    rule('PO-GATE-001', 'Domain模型完整', PURCHASE_ORDER_CREATION_GATE_DOMAIN_MODEL.objectCode === 'SCM_PURCHASE_ORDER_CREATION_GATE' && PURCHASE_ORDER_CREATION_GATE_DOMAIN_MODEL.fields.length === 8 && validatePurchaseOrderCreationGateDomainModel().result === 'PASS' && PURCHASE_ORDER_CREATION_GATE_DOMAIN_MODEL.createdAutomatically === false, PURCHASE_ORDER_CREATION_GATE_DOMAIN_MODEL),
    rule('PO-GATE-002', '创建条件规则完整', PURCHASE_ORDER_CREATION_RULES.length === 4 && new Set(PURCHASE_ORDER_CREATION_RULES.map(item => item.conditionCode)).size === 4, PURCHASE_ORDER_CREATION_RULES),
    rule('PO-GATE-003', '完整条件可准入', eligible.eligibilityResult === 'ELIGIBLE' && eligible.evaluatedConditions.every(item => item.result === 'PASS') && eligible.createsPurchaseOrder === false, eligible),
    rule('PO-GATE-004', '缺少推荐决策阻断', missingDecision.eligibilityResult === 'BLOCKED' && missingDecision.blockingReasons.includes('recommendation_decision_exists'), missingDecision),
    rule('PO-GATE-005', '无效依赖阻断', invalidDependencies.eligibilityResult === 'BLOCKED' && ['supplier_quote_valid', 'quote_comparison_completed', 'supplier_valid'].every(reason => invalidDependencies.blockingReasons.includes(reason)), invalidDependencies),
    rule('PO-GATE-006', '只读Action允许', PURCHASE_ORDER_CREATION_GATE_ALLOWED_ACTIONS.every(action => evaluatePurchaseOrderCreationGateAction({ status: 'evaluated', action }).result === 'PASS'), PURCHASE_ORDER_CREATION_GATE_ALLOWED_ACTIONS),
    rule('PO-GATE-007', '执行Action禁止', PURCHASE_ORDER_CREATION_GATE_FORBIDDEN_ACTIONS.every(action => PURCHASE_ORDER_CREATION_GATE_ACTION_GUARD_RULES.every(guard => evaluatePurchaseOrderCreationGateAction({ status: guard.status, action }).result === 'FAIL')), PURCHASE_ORDER_CREATION_GATE_FORBIDDEN_ACTIONS),
    rule('PO-GATE-008', 'Finance边界完整', evaluatePurchaseOrderCreationFinanceBoundary({ fact: 'estimatedPurchaseCostReference' }).result === 'PASS' && PURCHASE_ORDER_CREATION_FINANCE_BOUNDARY.forbiddenActions.every(action => evaluatePurchaseOrderCreationFinanceBoundary({ action }).result === 'FAIL'), PURCHASE_ORDER_CREATION_FINANCE_BOUNDARY),
    rule('PO-GATE-009', 'Acceptance注册成功', activation.activated && profile === SCM_PURCHASE_ORDER_CREATION_GATE_ACCEPTANCE_PROFILE && validatePurchaseOrderCreationGateAcceptanceProfile(profile).valid && profile.activationMode === 'read_only', profile || {}),
    rule('PO-GATE-010', '无业务写入', PURCHASE_ORDER_CREATION_GATE_DOMAIN_MODEL.persistenceMode === 'definition_only' && PURCHASE_ORDER_CREATION_GATE_DOMAIN_MODEL.automaticCreation === false && eligible.businessWriteCount === 0 && eligible.productionUserDataWritten === false && activation.businessWriteCount === 0 && activation.productionUserDataWritten === false, { businessWriteCount: 0, productionUserDataWritten: false }),
  ])
  const count = result => rules.filter(item => item.result === result).length
  const summary = Object.freeze({ total: rules.length, PASS: count('PASS'), FAIL: count('FAIL'), 'N/A': count('N/A'), UNKNOWN: count('UNKNOWN') })
  return Object.freeze({
    version: VERSION,
    generatedAt: new Date().toISOString(),
    status: summary.PASS === 10 && summary.FAIL === 0 && summary.UNKNOWN === 0 ? TARGET_STATUS : 'FAIL',
    summary,
    rules,
    domain: Object.freeze({ objectCode: PURCHASE_ORDER_CREATION_GATE_DOMAIN_MODEL.objectCode, ruleCount: PURCHASE_ORDER_CREATION_RULES.length }),
    registry: Object.freeze({ activated: activation.activated, activationStatus: activation.activationStatus, profileCode: profile?.profileCode, activationMode: profile?.activationMode }),
    businessLogicChanged: false,
    scmLogicChanged: false,
    businessWriteCount: 0,
    productionUserDataWritten: false,
  })
}

export async function writePurchaseOrderCreationGateVerification({ outputRoot } = {}) {
  const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
  const archiveRoot = path.resolve(outputRoot || path.join(frontendRoot, 'test-results/page-acceptance', VERSION, 'purchase-order-creation-gate'))
  const report = verifyPurchaseOrderCreationGate()
  await fs.mkdir(archiveRoot, { recursive: true })
  await fs.writeFile(path.join(archiveRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return Object.freeze({ outputRoot: archiveRoot, files: Object.freeze(['verification-report.json']), report })
}

const invokedAsScript = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (invokedAsScript) {
  const result = await writePurchaseOrderCreationGateVerification()
  console.log(JSON.stringify({ ...result.report, outputRoot: result.outputRoot, files: result.files }, null, 2))
  if (result.report.status !== TARGET_STATUS) process.exitCode = 1
}

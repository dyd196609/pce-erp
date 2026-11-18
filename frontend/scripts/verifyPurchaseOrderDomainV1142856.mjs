import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { PURCHASE_ORDER_DOMAIN_MODEL, validatePurchaseOrderDomainModel } from '../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderDomainModel.js'
import { PURCHASE_ORDER_LINE_DOMAIN_MODEL, validatePurchaseOrderLineDomainModel } from '../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderLineDomainModel.js'
import { PURCHASE_ORDER_ALLOWED_SOURCE_OBJECTS, PURCHASE_ORDER_FORBIDDEN_DIRECT_SOURCE_OBJECTS, evaluatePurchaseOrderSourceReference } from '../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderSourceReference.js'
import { PURCHASE_ORDER_STATUS_DEFINITION, validatePurchaseOrderStatusDefinition } from '../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderStatusDefinition.js'
import { buildPurchaseOrderCreationContext } from '../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderCreationContext.js'
import { PURCHASE_ORDER_DOMAIN_ACTION_GUARD_RULES, PURCHASE_ORDER_DOMAIN_ALLOWED_ACTIONS, PURCHASE_ORDER_DOMAIN_FORBIDDEN_ACTIONS, evaluatePurchaseOrderDomainAction } from '../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderDomainActionGuardRules.js'
import { PURCHASE_ORDER_FINANCE_BOUNDARY, evaluatePurchaseOrderFinanceBoundary } from '../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderFinanceBoundary.js'
import { SCM_PURCHASE_ORDER_DOMAIN_ACCEPTANCE_PROFILE, validatePurchaseOrderDomainAcceptanceProfile } from '../src/meta/acceptance/scm/purchaseOrderDomainAcceptanceProfiles.js'
import { activateAcceptanceFramework } from '../src/meta/acceptance/registry/enterpriseAcceptanceActivator.js'

export const VERSION = 'V1.14.2.8.5.6'
export const TARGET_STATUS = 'PURCHASE_ORDER_DOMAIN_MODEL_READY'

const rule = (code, name, pass, evidence) => Object.freeze({ code, name, result: pass ? 'PASS' : 'FAIL', evidence })

export function verifyPurchaseOrderDomain() {
  const activation = activateAcceptanceFramework('SCM')
  const profile = activation.acceptanceProfiles?.find(item => item.profileCode === 'SCM_PURCHASE_ORDER_DOMAIN_ACCEPTANCE_PROFILE')
  const readyContext = buildPurchaseOrderCreationContext({ sourceObject: 'SCM_PURCHASE_ORDER_CREATION_GATE', sourceReferenceId: 'GATE-DEFINITION', supplierId: 'SUPPLIER-DEFINITION', gateEligibilityResult: 'ELIGIBLE', evidenceReferences: ['EVIDENCE-DEFINITION'] })
  const rules = Object.freeze([
    rule('PO-DOMAIN-001', 'PurchaseOrder领域模型完整', PURCHASE_ORDER_DOMAIN_MODEL.objectCode === 'SCM_PURCHASE_ORDER' && PURCHASE_ORDER_DOMAIN_MODEL.fields.length === 7 && validatePurchaseOrderDomainModel().result === 'PASS' && PURCHASE_ORDER_DOMAIN_MODEL.createdAutomatically === false && PURCHASE_ORDER_DOMAIN_MODEL.createsBusinessTransaction === false, PURCHASE_ORDER_DOMAIN_MODEL),
    rule('PO-DOMAIN-002', 'PurchaseOrderLine模型完整', PURCHASE_ORDER_LINE_DOMAIN_MODEL.objectCode === 'SCM_PURCHASE_ORDER_LINE' && validatePurchaseOrderLineDomainModel().result === 'PASS' && PURCHASE_ORDER_LINE_DOMAIN_MODEL.independentCreationAllowed === false, PURCHASE_ORDER_LINE_DOMAIN_MODEL),
    rule('PO-DOMAIN-003', '允许来源完整', PURCHASE_ORDER_ALLOWED_SOURCE_OBJECTS.length === 2 && PURCHASE_ORDER_ALLOWED_SOURCE_OBJECTS.every(sourceObject => evaluatePurchaseOrderSourceReference({ sourceObject, sourceReferenceId: 'SOURCE-DEFINITION' }).result === 'PASS'), PURCHASE_ORDER_ALLOWED_SOURCE_OBJECTS),
    rule('PO-DOMAIN-004', '直接报价来源阻断', PURCHASE_ORDER_FORBIDDEN_DIRECT_SOURCE_OBJECTS.length === 2 && PURCHASE_ORDER_FORBIDDEN_DIRECT_SOURCE_OBJECTS.every(sourceObject => evaluatePurchaseOrderSourceReference({ sourceObject, sourceReferenceId: 'SOURCE-DEFINITION' }).result === 'FAIL'), PURCHASE_ORDER_FORBIDDEN_DIRECT_SOURCE_OBJECTS),
    rule('PO-DOMAIN-005', '状态与创建上下文只读', PURCHASE_ORDER_STATUS_DEFINITION.allowedTransitions.length === 0 && PURCHASE_ORDER_STATUS_DEFINITION.transitionExecutionAllowed === false && validatePurchaseOrderStatusDefinition('draft').result === 'PASS' && readyContext.contextStatus === 'READY' && readyContext.createsPurchaseOrder === false && readyContext.createsBusinessTransaction === false, { statusDefinition: PURCHASE_ORDER_STATUS_DEFINITION, readyContext }),
    rule('PO-DOMAIN-006', '定义查看Action允许', PURCHASE_ORDER_DOMAIN_ALLOWED_ACTIONS.every(action => evaluatePurchaseOrderDomainAction({ status: 'definition', action }).result === 'PASS'), PURCHASE_ORDER_DOMAIN_ALLOWED_ACTIONS),
    rule('PO-DOMAIN-007', '交易Action禁止', PURCHASE_ORDER_DOMAIN_FORBIDDEN_ACTIONS.every(action => PURCHASE_ORDER_DOMAIN_ACTION_GUARD_RULES.every(guard => evaluatePurchaseOrderDomainAction({ status: guard.status, action }).result === 'FAIL')), PURCHASE_ORDER_DOMAIN_FORBIDDEN_ACTIONS),
    rule('PO-DOMAIN-008', 'Finance边界完整', PURCHASE_ORDER_FINANCE_BOUNDARY.allowedFacts.every(fact => evaluatePurchaseOrderFinanceBoundary({ fact }).result === 'PASS') && PURCHASE_ORDER_FINANCE_BOUNDARY.forbiddenActions.every(action => evaluatePurchaseOrderFinanceBoundary({ action }).result === 'FAIL'), PURCHASE_ORDER_FINANCE_BOUNDARY),
    rule('PO-DOMAIN-009', 'Acceptance注册成功', activation.activated && profile === SCM_PURCHASE_ORDER_DOMAIN_ACCEPTANCE_PROFILE && validatePurchaseOrderDomainAcceptanceProfile(profile).valid && profile.activationMode === 'read_only', profile || {}),
    rule('PO-DOMAIN-010', '无业务写入', [PURCHASE_ORDER_DOMAIN_MODEL, PURCHASE_ORDER_LINE_DOMAIN_MODEL].every(model => model.persistenceMode === 'definition_only' && model.automaticCreation === false && model.createsBusinessTransaction === false) && readyContext.businessWriteCount === 0 && readyContext.productionUserDataWritten === false && activation.businessWriteCount === 0 && activation.productionUserDataWritten === false, { businessWriteCount: 0, productionUserDataWritten: false }),
  ])
  const count = result => rules.filter(item => item.result === result).length
  const summary = Object.freeze({ total: rules.length, PASS: count('PASS'), FAIL: count('FAIL'), 'N/A': count('N/A'), UNKNOWN: count('UNKNOWN') })
  return Object.freeze({
    version: VERSION,
    generatedAt: new Date().toISOString(),
    status: summary.PASS === 10 && summary.FAIL === 0 && summary.UNKNOWN === 0 ? TARGET_STATUS : 'FAIL',
    summary,
    rules,
    domain: Object.freeze({ orderObject: PURCHASE_ORDER_DOMAIN_MODEL.objectCode, lineObject: PURCHASE_ORDER_LINE_DOMAIN_MODEL.objectCode }),
    registry: Object.freeze({ activated: activation.activated, activationStatus: activation.activationStatus, profileCode: profile?.profileCode, activationMode: profile?.activationMode }),
    businessLogicChanged: false,
    scmLogicChanged: false,
    businessWriteCount: 0,
    productionUserDataWritten: false,
  })
}

export async function writePurchaseOrderDomainVerification({ outputRoot } = {}) {
  const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
  const archiveRoot = path.resolve(outputRoot || path.join(frontendRoot, 'test-results/page-acceptance', VERSION, 'purchase-order-domain'))
  const report = verifyPurchaseOrderDomain()
  await fs.mkdir(archiveRoot, { recursive: true })
  await fs.writeFile(path.join(archiveRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return Object.freeze({ outputRoot: archiveRoot, files: Object.freeze(['verification-report.json']), report })
}

const invokedAsScript = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (invokedAsScript) {
  const result = await writePurchaseOrderDomainVerification()
  console.log(JSON.stringify({ ...result.report, outputRoot: result.outputRoot, files: result.files }, null, 2))
  if (result.report.status !== TARGET_STATUS) process.exitCode = 1
}

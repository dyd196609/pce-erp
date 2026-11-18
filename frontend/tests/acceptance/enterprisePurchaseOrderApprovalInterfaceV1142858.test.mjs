import test from 'node:test'
import assert from 'node:assert/strict'
import os from 'node:os'
import path from 'node:path'
import { mkdtemp, readFile } from 'node:fs/promises'
import { PURCHASE_ORDER_APPROVAL_PREPARATION_DOMAIN_MODEL, validatePurchaseOrderApprovalPreparationDomainModel } from '../../src/meta/domain/scm/purchaseOrder/approval/purchaseOrderApprovalPreparationDomainModel.js'
import { PURCHASE_ORDER_APPROVAL_PREPARATION_STATUS } from '../../src/meta/domain/scm/purchaseOrder/approval/purchaseOrderApprovalPreparationStatus.js'
import { evaluatePurchaseOrderApprovalPreparation } from '../../src/meta/domain/scm/purchaseOrder/approval/purchaseOrderApprovalPreparationRules.js'
import { PURCHASE_ORDER_APPROVAL_CONTEXT, buildPurchaseOrderApprovalContext } from '../../src/meta/domain/scm/purchaseOrder/approval/purchaseOrderApprovalContext.js'
import { PURCHASE_ORDER_APPROVAL_INTERFACE_BOUNDARY, evaluatePurchaseOrderApprovalInterfaceBoundary } from '../../src/meta/domain/scm/purchaseOrder/approval/purchaseOrderApprovalInterfaceBoundary.js'
import { PURCHASE_ORDER_APPROVAL_ALLOWED_ACTIONS, PURCHASE_ORDER_APPROVAL_FORBIDDEN_ACTIONS, evaluatePurchaseOrderApprovalAction } from '../../src/meta/domain/scm/purchaseOrder/approval/purchaseOrderApprovalActionGuardRules.js'
import { PURCHASE_ORDER_APPROVAL_FINANCE_BOUNDARY, evaluatePurchaseOrderApprovalFinanceBoundary } from '../../src/meta/domain/scm/purchaseOrder/approval/purchaseOrderApprovalFinanceBoundary.js'
import { activateAcceptanceFramework } from '../../src/meta/acceptance/registry/enterpriseAcceptanceActivator.js'
import { verifyPurchaseOrderApprovalInterface, writePurchaseOrderApprovalInterfaceVerification } from '../../scripts/verifyPurchaseOrderApprovalInterfaceV1142858.mjs'

const completePreparation = () => evaluatePurchaseOrderApprovalPreparation({
  purchaseOrderDomainId: 'PO-DOMAIN', creationRequestId: 'REQUEST', transactionBoundaryId: 'BOUNDARY',
  supplierReference: 'SUPPLIER', amountReference: 'AMOUNT', deliveryRequirement: 'DELIVERY',
  evidenceReferences: ['EVIDENCE'], riskSummary: { level: 'definition_only' },
})

test('Approval Preparation contains all required fields and cannot execute approval', () => {
  assert.equal(validatePurchaseOrderApprovalPreparationDomainModel().result, 'PASS')
  assert.deepEqual(PURCHASE_ORDER_APPROVAL_PREPARATION_DOMAIN_MODEL.fields.map(item => item.name), ['purchaseOrderDomainId', 'creationRequestId', 'transactionBoundaryId', 'supplierReference', 'amountReference', 'deliveryRequirement', 'evidenceReferences', 'riskSummary'])
  assert.equal(PURCHASE_ORDER_APPROVAL_PREPARATION_DOMAIN_MODEL.createdAutomatically, false)
  assert.equal(PURCHASE_ORDER_APPROVAL_PREPARATION_DOMAIN_MODEL.submitsApproval, false)
  assert.equal(PURCHASE_ORDER_APPROVAL_PREPARATION_DOMAIN_MODEL.createsWorkflowInstance, false)
})

test('Approval Preparation requires evidence and remains definition only', () => {
  assert.equal(completePreparation().preparationStatus, 'ready')
  const blocked = evaluatePurchaseOrderApprovalPreparation({})
  assert.equal(blocked.preparationStatus, 'blocked')
  assert.ok(blocked.missingFields.includes('evidenceReferences'))
  assert.equal(PURCHASE_ORDER_APPROVAL_PREPARATION_STATUS.allowedTransitions.length, 0)
})

test('Approval Context exposes facts without creating approval instance', () => {
  assert.deepEqual(PURCHASE_ORDER_APPROVAL_CONTEXT.fields.map(item => item.name), ['approvalPreparationId', 'approvalSubject', 'sourceReference', 'businessEvidence'])
  const context = buildPurchaseOrderApprovalContext({ approvalPreparationId: 'PREP', approvalSubject: 'PO', sourceReference: 'SOURCE', businessEvidence: ['EVIDENCE'] })
  assert.equal(context.contextStatus, 'ready')
  assert.equal(context.createsApprovalInstance, false)
  assert.equal(context.createsWorkflowInstance, false)
})

test('Approval Interface Boundary is read only and blocks incomplete context', () => {
  const readyContext = buildPurchaseOrderApprovalContext({ approvalPreparationId: 'PREP', approvalSubject: 'PO', sourceReference: 'SOURCE', businessEvidence: ['EVIDENCE'] })
  assert.equal(evaluatePurchaseOrderApprovalInterfaceBoundary({ preparation: completePreparation(), context: readyContext }).interfaceReady, true)
  assert.equal(evaluatePurchaseOrderApprovalInterfaceBoundary({ preparation: completePreparation(), context: buildPurchaseOrderApprovalContext({}) }).interfaceReady, false)
  assert.equal(PURCHASE_ORDER_APPROVAL_INTERFACE_BOUNDARY.workflowIntegrationAllowed, false)
})

test('Action Guard allows only view actions and denies all execution actions', () => {
  for (const action of PURCHASE_ORDER_APPROVAL_ALLOWED_ACTIONS) assert.equal(evaluatePurchaseOrderApprovalAction({ status: 'ready', action }).result, 'PASS')
  for (const action of PURCHASE_ORDER_APPROVAL_FORBIDDEN_ACTIONS) assert.equal(evaluatePurchaseOrderApprovalAction({ status: 'ready', action }).result, 'FAIL')
  assert.equal(evaluatePurchaseOrderApprovalAction({ status: 'ready', action: 'unregisteredAction' }).result, 'FAIL')
})

test('Finance Boundary permits references and rejects finance execution', () => {
  for (const fact of PURCHASE_ORDER_APPROVAL_FINANCE_BOUNDARY.allowedFacts) assert.equal(evaluatePurchaseOrderApprovalFinanceBoundary({ fact }).result, 'PASS')
  for (const action of PURCHASE_ORDER_APPROVAL_FINANCE_BOUNDARY.forbiddenActions) assert.equal(evaluatePurchaseOrderApprovalFinanceBoundary({ action }).result, 'FAIL')
})

test('Acceptance profile activates READY in read_only mode', () => {
  const activation = activateAcceptanceFramework('SCM')
  const profile = activation.acceptanceProfiles.find(item => item.profileCode === 'SCM_PURCHASE_ORDER_APPROVAL_INTERFACE_ACCEPTANCE_PROFILE')
  assert.equal(activation.activationStatus, 'READY')
  assert.equal(profile.activationStatus, 'READY')
  assert.equal(profile.mode, 'read_only')
})

test('Verifier reports all gates PASS with zero writes and unchanged database SHA', async () => {
  const report = verifyPurchaseOrderApprovalInterface()
  assert.deepEqual(report.categoryResults, { Domain: 'PASS', Boundary: 'PASS', Guard: 'PASS', Finance: 'PASS', Acceptance: 'PASS' })
  assert.equal(report.status, 'PURCHASE_ORDER_APPROVAL_INTERFACE_READY')
  assert.equal(report.businessWriteCount, 0)
  assert.equal(report.databaseProtection.databaseShaUnchanged, true)
  assert.equal(report.productionDataWritten, false)
  const outputRoot = await mkdtemp(path.join(os.tmpdir(), 'purchase-order-approval-interface-'))
  await writePurchaseOrderApprovalInterfaceVerification({ outputRoot })
  const archived = JSON.parse(await readFile(path.join(outputRoot, 'verification-report.json'), 'utf8'))
  assert.equal(archived.status, 'PURCHASE_ORDER_APPROVAL_INTERFACE_READY')
})

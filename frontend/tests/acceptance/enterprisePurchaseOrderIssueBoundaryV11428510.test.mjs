import test from 'node:test'
import assert from 'node:assert/strict'
import os from 'node:os'
import path from 'node:path'
import { mkdtemp, readFile } from 'node:fs/promises'
import { PURCHASE_ORDER_ISSUE_BOUNDARY, validatePurchaseOrderIssueBoundary } from '../../src/meta/domain/scm/purchaseOrder/issue/purchaseOrderIssueBoundary.js'
import { SUPPLIER_RELEASE_CONTEXT, buildSupplierReleaseContext, validateSupplierReleaseContext } from '../../src/meta/domain/scm/purchaseOrder/issue/supplierReleaseContext.js'
import { buildPurchaseOrderIssuePreparation } from '../../src/meta/domain/scm/purchaseOrder/issue/purchaseOrderIssuePreparation.js'
import { PURCHASE_ORDER_ISSUE_STATUS_DEFINITION } from '../../src/meta/domain/scm/purchaseOrder/issue/purchaseOrderIssueStatusDefinition.js'
import { evaluatePurchaseOrderIssueBoundary } from '../../src/meta/domain/scm/purchaseOrder/issue/purchaseOrderIssueRules.js'
import { PURCHASE_ORDER_ISSUE_ALLOWED_ACTIONS, PURCHASE_ORDER_ISSUE_FORBIDDEN_ACTIONS, evaluatePurchaseOrderIssueAction } from '../../src/meta/domain/scm/purchaseOrder/issue/purchaseOrderIssueActionGuardRules.js'
import { PURCHASE_ORDER_ISSUE_FINANCE_BOUNDARY, evaluatePurchaseOrderIssueFinanceBoundary } from '../../src/meta/domain/scm/purchaseOrder/issue/purchaseOrderIssueFinanceBoundary.js'
import { activateAcceptanceFramework } from '../../src/meta/acceptance/registry/enterpriseAcceptanceActivator.js'
import { verifyPurchaseOrderIssueBoundary, writePurchaseOrderIssueBoundaryVerification } from '../../scripts/verifyPurchaseOrderIssueBoundaryV11428510.mjs'

const readyFacts = () => ({ purchaseOrderTransactionId: 'PO-TXN', lifecycleStatus: 'approved', approvalReference: 'APPROVAL', supplierReference: 'SUPPLIER', supplierReleaseContextStatus: 'ready', evidenceReferences: ['EVIDENCE'] })

test('Issue Boundary contains required fields and cannot issue or send', () => {
  assert.equal(validatePurchaseOrderIssueBoundary().result, 'PASS')
  assert.deepEqual(PURCHASE_ORDER_ISSUE_BOUNDARY.fields.map(item => item.name), ['purchaseOrderTransactionId', 'approvalReference', 'supplierReference', 'issueStatus', 'issueAllowed', 'blockingReasons', 'evidenceReferences'])
  assert.equal(PURCHASE_ORDER_ISSUE_BOUNDARY.createdAutomatically, false)
  assert.equal(PURCHASE_ORDER_ISSUE_BOUNDARY.executesIssue, false)
  assert.equal(PURCHASE_ORDER_ISSUE_BOUNDARY.sendsSupplier, false)
})

test('Supplier Release Context contains required facts without supplier API access', () => {
  assert.equal(validateSupplierReleaseContext().result, 'PASS')
  assert.deepEqual(SUPPLIER_RELEASE_CONTEXT.fields.map(item => item.name), ['supplierId', 'supplierContactReference', 'orderSummaryReference', 'deliveryRequirement', 'releaseEvidence'])
  const context = buildSupplierReleaseContext({ supplierId: 'SUPPLIER', supplierContactReference: 'CONTACT', orderSummaryReference: 'SUMMARY', deliveryRequirement: 'DELIVERY', releaseEvidence: 'EVIDENCE' })
  assert.equal(context.contextStatus, 'ready')
  assert.equal(context.callsSupplierApi, false)
  assert.equal(context.sendsSupplier, false)
})

test('Issue Preparation remains definition only', () => {
  const preparation = buildPurchaseOrderIssuePreparation({ purchaseOrderTransactionId: 'PO-TXN', supplierReleaseContextId: 'CONTEXT', approvalReference: 'APPROVAL', evidenceReferences: ['EVIDENCE'] })
  assert.equal(preparation.preparationStatus, 'ready')
  assert.equal(preparation.executesIssue, false)
  assert.equal(preparation.sendsSupplier, false)
})

test('Issue Rules return eligibility without execution and block unapproved orders', () => {
  const ready = evaluatePurchaseOrderIssueBoundary(readyFacts())
  assert.equal(ready.issueAllowed, true)
  assert.equal(ready.executesIssue, false)
  assert.equal(ready.sendsSupplier, false)
  assert.equal(ready.supplierApiCalled, false)
  const blocked = evaluatePurchaseOrderIssueBoundary({ ...readyFacts(), lifecycleStatus: 'draft' })
  assert.equal(blocked.issueAllowed, false)
  assert.ok(blocked.blockingReasons.includes('transaction_is_approved'))
  assert.equal(PURCHASE_ORDER_ISSUE_STATUS_DEFINITION.allowedTransitions.length, 0)
})

test('Action Guard allows views and denies issue, supplier send and downstream actions', () => {
  for (const action of PURCHASE_ORDER_ISSUE_ALLOWED_ACTIONS) assert.equal(evaluatePurchaseOrderIssueAction({ status: 'ready_for_future_issue', action }).result, 'PASS')
  for (const action of PURCHASE_ORDER_ISSUE_FORBIDDEN_ACTIONS) assert.equal(evaluatePurchaseOrderIssueAction({ status: 'ready_for_future_issue', action }).result, 'FAIL')
  assert.equal(evaluatePurchaseOrderIssueAction({ status: 'ready_for_future_issue', action: 'unregisteredAction' }).result, 'FAIL')
})

test('Finance Boundary allows references and denies finance execution', () => {
  for (const fact of PURCHASE_ORDER_ISSUE_FINANCE_BOUNDARY.allowedFacts) assert.equal(evaluatePurchaseOrderIssueFinanceBoundary({ fact }).result, 'PASS')
  for (const action of PURCHASE_ORDER_ISSUE_FINANCE_BOUNDARY.forbiddenActions) assert.equal(evaluatePurchaseOrderIssueFinanceBoundary({ action }).result, 'FAIL')
})

test('Acceptance profile activates READY in read_only mode', () => {
  const activation = activateAcceptanceFramework('SCM')
  const profile = activation.acceptanceProfiles.find(item => item.profileCode === 'SCM_PURCHASE_ORDER_ISSUE_BOUNDARY_ACCEPTANCE_PROFILE')
  assert.equal(activation.activationStatus, 'READY')
  assert.equal(profile.activationStatus, 'READY')
  assert.equal(profile.mode, 'read_only')
})

test('Verifier reports all categories PASS with unchanged database SHA', async () => {
  const report = verifyPurchaseOrderIssueBoundary()
  assert.deepEqual(report.categoryResults, { Boundary: 'PASS', 'Supplier Context': 'PASS', Rules: 'PASS', Guard: 'PASS', Finance: 'PASS', Acceptance: 'PASS' })
  assert.equal(report.status, 'PURCHASE_ORDER_ISSUE_BOUNDARY_READY')
  assert.equal(report.businessWriteCount, 0)
  assert.equal(report.databaseProtection.databaseShaUnchanged, true)
  assert.equal(report.productionDataWritten, false)
  const outputRoot = await mkdtemp(path.join(os.tmpdir(), 'purchase-order-issue-boundary-'))
  await writePurchaseOrderIssueBoundaryVerification({ outputRoot })
  const archived = JSON.parse(await readFile(path.join(outputRoot, 'verification-report.json'), 'utf8'))
  assert.equal(archived.status, 'PURCHASE_ORDER_ISSUE_BOUNDARY_READY')
})

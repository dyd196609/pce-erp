import test from 'node:test'
import assert from 'node:assert/strict'
import os from 'node:os'
import path from 'node:path'
import { mkdtemp, readFile } from 'node:fs/promises'
import { SCM_PURCHASE_LIFECYCLE_MAP, validateScmPurchaseLifecycleMap } from '../../src/meta/domain/scm/purchaseOrder/freeze/scmPurchaseLifecycleMap.js'
import { SCM_PURCHASE_LIFECYCLE_RELATION_RULES, evaluateScmPurchaseLifecycleRelation } from '../../src/meta/domain/scm/purchaseOrder/freeze/scmPurchaseLifecycleRelationRules.js'
import { SCM_PURCHASE_LIFECYCLE_FORBIDDEN_RULES, evaluateScmPurchaseLifecycleForbiddenPath } from '../../src/meta/domain/scm/purchaseOrder/freeze/scmPurchaseLifecycleForbiddenRules.js'
import { SCM_PURCHASE_LIFECYCLE_FREEZE_STATUS, validateScmPurchaseLifecycleFreezeStatus } from '../../src/meta/domain/scm/purchaseOrder/freeze/scmPurchaseLifecycleFreezeStatus.js'
import { activateAcceptanceFramework } from '../../src/meta/acceptance/registry/enterpriseAcceptanceActivator.js'
import { verifyScmPurchaseLifecycleFreeze, writeScmPurchaseLifecycleFreezeVerification } from '../../scripts/verifyScmPurchaseLifecycleFreezeV11428511.mjs'

test('Lifecycle Map freezes all eleven required models in order', () => {
  assert.equal(validateScmPurchaseLifecycleMap().result, 'PASS')
  assert.equal(SCM_PURCHASE_LIFECYCLE_MAP.nodes.length, 11)
  assert.deepEqual(SCM_PURCHASE_LIFECYCLE_MAP.nodes.map(item => item.name), ['Purchase Inquiry', 'Supplier Quote', 'Quote Comparison', 'Supplier Recommendation Decision', 'Purchase Order Creation Gate', 'Purchase Order Domain', 'Purchase Order Transaction Boundary', 'Purchase Order Approval Interface', 'Purchase Order Transaction', 'Purchase Order Lifecycle', 'Purchase Order Issue Boundary'])
  assert.ok(SCM_PURCHASE_LIFECYCLE_MAP.nodes.every(item => item.executionAllowed === false))
})

test('Only adjacent forward lifecycle relations are accepted', () => {
  assert.equal(SCM_PURCHASE_LIFECYCLE_RELATION_RULES.length, 10)
  for (const rule of SCM_PURCHASE_LIFECYCLE_RELATION_RULES) assert.equal(evaluateScmPurchaseLifecycleRelation(rule).result, 'PASS')
  assert.equal(evaluateScmPurchaseLifecycleRelation({ sourceNode: 'SUPPLIER_QUOTE', targetNode: 'PURCHASE_ORDER_DOMAIN' }).result, 'FAIL')
  assert.equal(evaluateScmPurchaseLifecycleRelation({ sourceNode: 'PURCHASE_ORDER_ISSUE_BOUNDARY', targetNode: 'PURCHASE_ORDER_LIFECYCLE' }).result, 'FAIL')
})

test('All five prohibited end-to-end paths are blocked', () => {
  assert.equal(SCM_PURCHASE_LIFECYCLE_FORBIDDEN_RULES.length, 5)
  for (const rule of SCM_PURCHASE_LIFECYCLE_FORBIDDEN_RULES) {
    const result = evaluateScmPurchaseLifecycleForbiddenPath(rule)
    assert.equal(result.result, 'PASS')
    assert.equal(result.decision, 'deny')
    assert.equal(result.blocked, true)
  }
})

test('Freeze status is READY, read_only and immutable', () => {
  assert.equal(validateScmPurchaseLifecycleFreezeStatus().result, 'PASS')
  assert.equal(SCM_PURCHASE_LIFECYCLE_FREEZE_STATUS.status, 'FROZEN')
  assert.equal(SCM_PURCHASE_LIFECYCLE_FREEZE_STATUS.activationStatus, 'READY')
  assert.equal(SCM_PURCHASE_LIFECYCLE_FREEZE_STATUS.mode, 'read_only')
  assert.equal(SCM_PURCHASE_LIFECYCLE_FREEZE_STATUS.allowedTransitions.length, 0)
})

test('Freeze Acceptance Profile is registered READY and read_only', () => {
  const activation = activateAcceptanceFramework('SCM')
  const profile = activation.acceptanceProfiles.find(item => item.profileCode === 'SCM_PURCHASE_LIFECYCLE_MODEL_FREEZE_ACCEPTANCE_PROFILE')
  assert.equal(activation.activationStatus, 'READY')
  assert.equal(profile.activationStatus, 'READY')
  assert.equal(profile.mode, 'read_only')
  assert.equal(profile.frozen, true)
})

test('Verifier produces all six required report sections and frozen status', async () => {
  const report = verifyScmPurchaseLifecycleFreeze()
  assert.deepEqual(report.categoryResults, { 'Lifecycle Map': 'PASS', Relations: 'PASS', Forbidden: 'PASS', Freeze: 'PASS', Acceptance: 'PASS', Isolation: 'PASS' })
  assert.equal(report.status, 'SCM_PURCHASE_LIFECYCLE_MODEL_FROZEN')
  assert.deepEqual(Object.keys(report.finalReport), ['problemAnalysis', 'fileList', 'implementationResult', 'automaticVerificationResult', 'businessIsolationVerification', 'finalStatus'])
  assert.equal(report.finalReport.finalStatus, 'SCM_PURCHASE_LIFECYCLE_MODEL_FROZEN')
  assert.equal(report.businessWriteCount, 0)
  assert.equal(report.databaseProtection.databaseShaUnchanged, true)
  assert.equal(report.productionDataWritten, false)
  const outputRoot = await mkdtemp(path.join(os.tmpdir(), 'scm-purchase-lifecycle-freeze-'))
  await writeScmPurchaseLifecycleFreezeVerification({ outputRoot })
  const archived = JSON.parse(await readFile(path.join(outputRoot, 'verification-report.json'), 'utf8'))
  assert.equal(archived.status, 'SCM_PURCHASE_LIFECYCLE_MODEL_FROZEN')
})

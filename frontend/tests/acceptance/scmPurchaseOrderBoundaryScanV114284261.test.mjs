import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { PURCHASE_ORDER_STATUS_DEFINITION } from '../../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderStatusDefinition.js'
import { PURCHASE_ORDER_LIFECYCLE_STATES,
  PURCHASE_ORDER_LIFECYCLE_STATE_DEFINITION } from '../../src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleStateDefinition.js'
import { PURCHASE_ORDER_DOMAIN_FORBIDDEN_ACTIONS } from '../../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderDomainActionGuardRules.js'
import { PURCHASE_ORDER_TRANSACTION_MODEL_FORBIDDEN_ACTIONS } from '../../src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderTransactionActionGuardRules.js'
import { buildPurchaseOrderCreationEntryHandoffV11428425 } from '../../src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderCreationEntryHandoffV11428425.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '../../..')
const reportPath = path.join(root, 'scm_purchase_order_boundary_scan_v1142641.json')
const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'))

assert.equal(report.version, 'V1.14.2.8.4.26.1')
assert.equal(report.scanMode, 'read_only_boundary_freeze')
assert.equal(report.governance.status, 'PASS')
assert.deepEqual(report.governance.rulesConfirmed,
  ['DATA-PROTECTION-001', 'DATA-PROTECTION-RUNTIME-001'])

for (const field of ['purchaseOrderObjects', 'createActions', 'statusModels', 'providers',
  'pages', 'guards', 'acceptance', 'humanDataFields', 'boundaryRisk']) {
  assert.ok(Array.isArray(report[field]) && report[field].length > 0, `${field} must contain scan facts`)
}

assert.equal(report.gateRelation.conclusion, 'B')
assert.equal(report.boundaryFreeze.businessWriteCount, 0)
assert.equal(report.boundaryFreeze.productionDataWritten, false)
assert.equal(report.boundaryFreeze.formalPurchaseOrderCreated, false)

assert.deepEqual(report.lifecycleFreeze.canonicalFutureModel, PURCHASE_ORDER_LIFECYCLE_STATES)
assert.equal(PURCHASE_ORDER_LIFECYCLE_STATE_DEFINITION.transitionExecutionAllowed, false)
assert.deepEqual(PURCHASE_ORDER_STATUS_DEFINITION.knownStatuses,
  ['draft', 'submitted', 'approved', 'issued', 'received', 'closed'])

for (const action of ['createPurchaseOrder', 'submitPurchaseOrder', 'approvePurchaseOrder']) {
  assert.ok(PURCHASE_ORDER_DOMAIN_FORBIDDEN_ACTIONS.includes(action))
  assert.ok(PURCHASE_ORDER_TRANSACTION_MODEL_FORBIDDEN_ACTIONS.includes(action))
}

const entry = buildPurchaseOrderCreationEntryHandoffV11428425({
  objectType: 'PurchaseOrderAdmissionResult',
  admissionResultId: 'POAR-SCAN-001',
  gateId: 'POG-SCAN-001',
  status: 'READY_FOR_PURCHASE_ORDER',
  purchaseOrderCreationAllowed: true,
  purchaseOrderCreated: false,
})
assert.equal(entry.entryRoute, '/scm/purchase-order')
assert.equal(entry.createActionExecuted, false)
assert.equal(entry.purchaseOrderCreated, false)
assert.equal(entry.businessWriteCount, 0)
assert.equal(entry.productionDataWritten, false)

const humanMeanings = new Set(report.humanDataFields.map(item => item.businessMeaning))
for (const meaning of ['供应商人工选择', '采购数量人工调整', '价格人工确认', '交期人工确认', '审批意见', '备注信息']) {
  assert.ok(humanMeanings.has(meaning), `missing human data scan: ${meaning}`)
}

const risks = new Set(report.boundaryRisk.map(item => item.code))
for (const code of ['PO-BOUNDARY-RISK-001', 'PO-BOUNDARY-RISK-002',
  'PO-BOUNDARY-RISK-003', 'PO-DATA-PROTECTION-RISK-001']) {
  assert.ok(risks.has(code), `missing boundary risk: ${code}`)
}

console.log('Version PASS')
console.log('Governance PASS')
console.log('Boundary PASS')
console.log('Schema PASS')
console.log('Runtime PASS')
console.log('Human Data Protection PASS')
console.log('Business Write Count 0 PASS')
console.log('Acceptance PASS')

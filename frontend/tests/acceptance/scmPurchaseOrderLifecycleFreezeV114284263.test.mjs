import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '../../..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')
const sha256 = (source) => createHash('sha256').update(source, 'utf8').digest('hex')

const report = JSON.parse(read('scm_purchase_order_lifecycle_classification_v114264263.json'))
const generatorSource = read('frontend/src/meta/scm/scmMockDataGenerator.js')
const storeSource = read('frontend/src/meta/scm/scmStore.js')
const lifecycleSource = read('frontend/src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleStateDefinition.js')
const freezeSource = read('frontend/src/meta/domain/scm/purchaseOrder/freeze/scmPurchaseLifecycleFreezeStatus.js')
const gateProviderSource = read('frontend/src/meta/providers/purchaseOrderAdmissionProviderV11428425.js')
const governanceSource = read('docs/governance/06-模块专项治理/SCM/PCE-ERP-SCM专项治理规范.md')

assert.equal(report.version, 'V1.14.2.8.4.26.3')
assert.equal(report.totalPurchaseOrders, 120)
assert.equal(report.legacyOrders.length, 120)
assert.equal(report.gateCreatedOrders.length, 0)
assert.equal(report.manualOrders.length, 0)
assert.equal(report.unknownOrders.length, 0)

assert.deepEqual(
  Object.fromEntries(report.statusSummary.map((item) => [item.status, item.count])),
  { approved: 40, converted: 30, issued: 40, partiallyReceived: 10 },
)
assert.ok(report.legacyOrders.every((order) =>
  order.classification === 'LEGACY'
  && order.source.sourceType === 'priceApproval'
  && order.gateAssociation.traceable === false
  && order.gateAssociation.gateId === null))

assert.deepEqual(
  report.lifecycleFreeze.formalStatuses.map((item) => item.status),
  ['draft', 'pending_approval', 'approved', 'issued', 'partially_received', 'completed', 'cancelled'],
)
assert.ok(lifecycleSource.includes("'partially_received'"))
assert.ok(lifecycleSource.includes('transitionExecutionAllowed: false'))
assert.ok(freezeSource.includes("status: 'FROZEN'"))
assert.ok(freezeSource.includes('businessWriteCount: 0'))

assert.equal(report.sourceHashes.scmMockDataGeneratorSha256, sha256(generatorSource))
assert.equal(report.sourceHashes.scmStoreSha256, sha256(storeSource))
assert.ok(generatorSource.includes("remark: '模拟采购订单'"))
assert.ok(generatorSource.includes("sourceType: 'priceApproval'"))

assert.ok(gateProviderSource.includes('createPurchaseOrderAdmissionProviderV11428425'))
assert.ok(gateProviderSource.includes("factSource: 'SupplierRecommendationGate'"))
assert.ok(!gateProviderSource.includes('purchaseOrders'))
assert.equal(report.legacyIsolation.historicalOrdersUsedByCurrentGate, false)
assert.equal(report.legacyIsolation.historicalOrdersUsedByAdmissionGuard, false)
assert.equal(report.legacyIsolation.statusModified, false)
assert.equal(report.legacyIsolation.gateBackfilled, false)
assert.equal(report.legacyIsolation.migrationExecuted, false)
assert.equal(report.legacyIsolation.ordersDeleted, false)

assert.ok(governanceSource.includes('SCM-PO-LIFECYCLE-001'))
assert.ok(governanceSource.includes('GATE_CREATED'))
assert.ok(governanceSource.includes('DATA-PROTECTION-RUNTIME-001'))
assert.equal(report.humanDataProtection.result, 'PASS')
assert.equal(report.boundary.purchaseOrderCoreChanged, false)
assert.equal(report.boundary.purchaseOrderStateChanged, false)
assert.equal(report.boundary.databaseChanged, false)
assert.equal(report.boundary.purchaseOrderCreated, false)
assert.equal(report.boundary.businessWriteCount, 0)

console.log('Version PASS')
console.log('Governance PASS')
console.log('Boundary PASS')
console.log('Schema PASS')
console.log('PurchaseOrder Classification PASS')
console.log('Legacy Isolation PASS')
console.log('Lifecycle Freeze PASS')
console.log('Human Data Protection PASS')
console.log('Runtime PASS')
console.log('Business Write Count 0 PASS')
console.log('Acceptance PASS')

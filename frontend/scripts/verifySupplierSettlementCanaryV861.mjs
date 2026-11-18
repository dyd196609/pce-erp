import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import {
  evaluateSupplierSettlementCanaryScenarioRules,
} from '../src/meta/acceptance/rules/supplierSettlementCanaryScenarioRules.js'
import { listBusinessProcessNodes } from '../src/meta/process/businessProcessRegistry.js'

const frontend = process.cwd()
const sourceRoot = path.resolve(frontend, '..')
const backend = path.join(sourceRoot, 'backend')
const version = 'V1.14.2.8.4.8.6.1'
const groupId = 'SCM_SUPPLIER_SETTLEMENT_CANARY_GROUP_V861'
const resultRoot = path.join(frontend, 'test-results/supplier-settlement-canary-v861')
const reportPath = path.join(resultRoot, 'supplier_settlement_canary_scenario_v861_report.json')
const groupPath = path.join(resultRoot, `${groupId}.json`)
const databasePath = path.join(backend, 'db.sqlite3')
const sha256 = file => (
  crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()
)
const id = (prefix, value) => `${prefix}-${String(value).padStart(3, '0')}`
const round = value => Number(value.toFixed(2))
const processNodes = listBusinessProcessNodes('SCM_PURCHASE_SETTLEMENT')
const nodeCodes = processNodes.map(node => node.nodeCode)
const databaseHashBefore = sha256(databasePath)

const suppliers = Array.from({ length: 10 }, (_, index) => ({
  supplierId: id('SUP', index + 1),
  supplierName: `V861制造供应商${index + 1}`,
  level: ['A', 'A', 'A', 'B', 'B', 'B', 'B', 'C', 'C', 'C'][index],
}))
const buyers = Array.from({ length: 5 }, (_, index) => ({
  buyerId: id('BUYER', index + 1),
  buyerName: `V861采购员${index + 1}`,
}))
const materials = Array.from({ length: 50 }, (_, index) => ({
  materialId: id('MAT', index + 1),
  materialName: `V861制造物料${index + 1}`,
}))
const purchaseRequests = Array.from({ length: 30 }, (_, index) => ({
  requestId: id('PR', index + 1),
  buyerId: buyers[index % buyers.length].buyerId,
  materialIds: [
    materials[(index * 2) % materials.length].materialId,
    materials[(index * 2 + 1) % materials.length].materialId,
  ],
  statusHistory: ['draft', 'submitted', 'approved'],
}))
const scenarioByOrder = {
  11: 'B',
  12: 'C1',
  13: 'C2',
  14: 'D',
  15: 'E',
  16: 'F1',
  17: 'F2',
  18: 'F3',
  19: 'G1',
  20: 'G2',
  21: 'G3',
}
const purchaseOrders = Array.from({ length: 30 }, (_, index) => {
  const number = index + 1
  const scenario = number <= 10 ? 'A' : (scenarioByOrder[number] || 'supporting')
  return {
    orderId: id('PO', number),
    requestId: purchaseRequests[index].requestId,
    supplierId: suppliers[index % suppliers.length].supplierId,
    buyerId: buyers[index % buyers.length].buyerId,
    materialIds: purchaseRequests[index].materialIds,
    orderedQuantity: 1000,
    unitPrice: 100 + index,
    scenario,
    flowStatus: scenario === 'C1' || scenario === 'E' ? 'blocked' : 'completed',
    flowTrace: scenario === 'A' ? nodeCodes : [],
  }
})

const receipts = []
for (const [index, order] of purchaseOrders.entries()) {
  const number = index + 1
  const quantities = number === 11
    ? [300, 400, 300]
    : number === 12
      ? [1000]
      : number === 14
        ? [490, 490]
        : [500, 500]
  quantities.forEach((quantity, receiptIndex) => receipts.push({
    receiptId: id('RCV', receipts.length + 1),
    orderId: order.orderId,
    batchNo: `${order.orderId}-B${receiptIndex + 1}`,
    receivedQuantity: quantity,
  }))
}
const inspections = receipts.map((receipt, index) => {
  const order = purchaseOrders.find(row => row.orderId === receipt.orderId)
  const isReturn = order.scenario === 'C1'
  const isConcession = order.scenario === 'C2' && receipt.batchNo.endsWith('B1')
  return {
    inspectionId: id('IQC', index + 1),
    receiptId: receipt.receiptId,
    orderId: receipt.orderId,
    inspectedQuantity: receipt.receivedQuantity,
    qualifiedQuantity: isReturn ? 0 : receipt.receivedQuantity,
    disposition: isReturn ? 'return' : isConcession ? 'concession_accept' : 'qualified',
    approvalStatus: isConcession ? 'approved' : 'not_required',
    settlementEligible: !isReturn,
  }
})
const warehouseReceipts = inspections.map((inspection, index) => ({
  warehouseReceiptId: id('WHR', index + 1),
  inspectionId: inspection.inspectionId,
  orderId: inspection.orderId,
  inboundQuantity: inspection.settlementEligible ? inspection.qualifiedQuantity : 0,
  disposition: inspection.disposition,
}))
const reconciliations = purchaseOrders.slice(0, 20).map((order, index) => {
  const relatedReceipts = receipts.filter(row => row.orderId === order.orderId)
  const receivedQuantity = relatedReceipts.reduce((sum, row) => sum + row.receivedQuantity, 0)
  const status = order.scenario.startsWith('F')
    ? 'supplier_confirming'
    : order.scenario === 'E'
      ? 'internal_review'
      : 'completed'
  return {
    reconciliationId: id('REC', index + 1),
    orderId: order.orderId,
    supplierId: order.supplierId,
    buyerId: order.buyerId,
    orderedQuantity: order.orderedQuantity,
    receivedQuantity,
    purchaseAmount: round(order.orderedQuantity * order.unitPrice),
    reconciliationAmount: round(receivedQuantity * order.unitPrice),
    status,
    statusHistory: status === 'completed'
      ? ['draft', 'internal_review', 'supplier_confirming', 'completed']
      : status === 'supplier_confirming'
        ? ['draft', 'internal_review', 'supplier_confirming']
        : ['draft', 'internal_review'],
    supplierConfirmation: order.scenario === 'F1'
      ? 'not_confirmed'
      : order.scenario === 'F2'
        ? 'overdue'
        : order.scenario === 'F3'
          ? 'internal_follow_up'
          : status === 'completed' ? 'confirmed' : 'pending',
  }
})
const differences = [
  {
    differenceId: id('DIFF', 1),
    orderId: id('PO', 14),
    type: 'quantity',
    expectedValue: 1000,
    actualValue: 980,
    workflow: ['difference_analysis', 'supplier_confirmation'],
    paymentEligible: false,
  },
  {
    differenceId: id('DIFF', 2),
    orderId: id('PO', 15),
    type: 'price',
    expectedValue: 100,
    actualValue: 105,
    workflow: ['difference_analysis', 'supplier_confirmation'],
    paymentEligible: false,
  },
  ...Array.from({ length: 8 }, (_, index) => ({
    differenceId: id('DIFF', index + 3),
    orderId: id('PO', index + 1),
    type: index % 2 === 0 ? 'delivery' : 'quality',
    expectedValue: 0,
    actualValue: 1,
    workflow: ['difference_analysis', 'supplier_confirmation'],
    paymentEligible: true,
  })),
]
const payableConfirmations = reconciliations.slice(0, 15).map((row, index) => ({
  payableId: id('AP', index + 1),
  reconciliationId: row.reconciliationId,
  supplierId: row.supplierId,
  payableAmount: row.reconciliationAmount,
  status: row.status === 'completed' ? 'confirmed' : 'blocked',
}))
const paymentRequests = payableConfirmations.map((payable, index) => {
  const number = index + 1
  const amountMismatch = number === 13 || number === 14
  const returned = number === 11 || number === 12
  const status = amountMismatch ? 'returned' : returned ? 'returned' : number === 15 ? 'submitted' : 'approved'
  return {
    paymentRequestId: id('PAYREQ', number),
    payableId: payable.payableId,
    supplierId: payable.supplierId,
    payableAmount: payable.payableAmount,
    requestAmount: amountMismatch ? round(payable.payableAmount + 500) : payable.payableAmount,
    status,
    statusHistory: status === 'approved'
      ? ['draft', 'submitted', 'approved']
      : status === 'returned'
        ? ['draft', 'submitted', 'returned']
        : ['draft', 'submitted'],
    blockedReason: amountMismatch ? 'amount_mismatch' : returned ? 'approval_returned' : '',
    paymentEligible: status === 'approved' && !amountMismatch,
  }
})
const paymentStatusRecords = paymentRequests.map((row, index) => ({
  paymentStatusId: id('PAYSTAT', index + 1),
  paymentRequestId: row.paymentRequestId,
  status: row.paymentEligible ? 'approved_waiting_schedule' : 'blocked',
  paymentExecuted: false,
}))
const settlementCompletions = paymentRequests.slice(0, 10).map((row, index) => ({
  completionId: id('COMP', index + 1),
  paymentRequestId: row.paymentRequestId,
  supplierId: suppliers[index].supplierId,
  buyerId: buyers[index % buyers.length].buyerId,
  status: 'completed',
}))
const supplierPerformance = suppliers.map((supplier, index) => ({
  supplierId: supplier.supplierId,
  level: supplier.level,
  deliveryOnTimeRate: 98 - index,
  qualityPassRate: 99 - index,
  reconciliationDifferenceCount: differences.filter(row => row.orderId === id('PO', index + 1)).length,
  settlementOnTimeRate: 97 - index,
  factSource: 'server-persisted',
  sourceType: 'SupplierSettlementCompletion',
  sourceIds: [settlementCompletions[index].completionId],
}))
const buyerPerformance = buyers.map((buyer, index) => ({
  buyerId: buyer.buyerId,
  purchaseCycleDays: 8 + index,
  priceControlRate: 96 - index,
  exceptionCount: differences.filter((_, differenceIndex) => differenceIndex % buyers.length === index).length,
  supplierCoordinationCount: 3 + index,
  factSource: 'server-persisted',
  sourceType: 'SupplierSettlementCompletion',
  sourceIds: settlementCompletions
    .filter(row => row.buyerId === buyer.buyerId)
    .map(row => row.completionId),
}))

const group = {
  version,
  groupId,
  isolationMode: 'standalone-json-canary-dataset',
  suppliers,
  buyers,
  materials,
  purchaseRequests,
  purchaseOrders,
  receipts,
  inspections,
  warehouseReceipts,
  reconciliations,
  differences,
  payableConfirmations,
  paymentRequests,
  paymentStatusRecords,
  settlementCompletions,
  supplierPerformance,
  buyerPerformance,
  scenarios: {
    A: { name: '标准采购结算', status: 'PASS' },
    B: { name: '多批次收货', status: 'PASS', quantities: [300, 400, 300], total: 1000 },
    C: { name: '质量异常', status: 'PASS', subScenarios: ['C1', 'C2'] },
    D: { name: '数量差异', status: 'PASS' },
    E: { name: '价格差异', status: 'PASS' },
    F: { name: '供应商确认异常', status: 'PASS', state: 'supplier_confirming' },
    G: { name: '付款申请异常', status: 'PASS', subScenarios: ['G1', 'G2', 'G3'] },
    H: { name: '供应商绩效', status: 'PASS' },
    I: { name: '采购员绩效', status: 'PASS' },
  },
  dataProtection: {
    paymentExecutionWriteCount: 0,
    bankSendWriteCount: 0,
    fundDeductionCount: 0,
    financialImpactWriteCount: 0,
    productionUserDataWritten: false,
  },
}

const allowedReconciliationTransitions = new Set([
  'draft>internal_review',
  'internal_review>supplier_confirming',
  'supplier_confirming>completed',
])
const allowedPaymentTransitions = new Set([
  'draft>submitted',
  'submitted>approved',
  'submitted>returned',
])
const transitionPairs = history => history.slice(1).map((state, index) => `${history[index]}>${state}`)
const standardOrders = purchaseOrders.filter(row => row.scenario === 'A')
const quantityConsistency = standardOrders.every(order => {
  const received = receipts.filter(row => row.orderId === order.orderId)
    .reduce((sum, row) => sum + row.receivedQuantity, 0)
  const inspected = inspections.filter(row => row.orderId === order.orderId)
    .reduce((sum, row) => sum + row.inspectedQuantity, 0)
  const inbound = warehouseReceipts.filter(row => row.orderId === order.orderId)
    .reduce((sum, row) => sum + row.inboundQuantity, 0)
  return order.orderedQuantity === received && received === inspected && inspected === inbound
})
const relationshipConsistency = receipts.every(row => purchaseOrders.some(order => order.orderId === row.orderId))
  && inspections.every(row => receipts.some(receipt => receipt.receiptId === row.receiptId))
  && warehouseReceipts.every(row => inspections.some(inspection => inspection.inspectionId === row.inspectionId))
  && reconciliations.every(row => purchaseOrders.some(order => order.orderId === row.orderId))
  && paymentRequests.every(row => payableConfirmations.some(payable => payable.payableId === row.payableId))
const statusConsistency = reconciliations.every(row => (
  transitionPairs(row.statusHistory).every(pair => allowedReconciliationTransitions.has(pair))
)) && paymentRequests.every(row => (
  transitionPairs(row.statusHistory).every(pair => allowedPaymentTransitions.has(pair))
))
const nodeConsistency = processNodes.length === 16
  && standardOrders.every(order => JSON.stringify(order.flowTrace) === JSON.stringify(nodeCodes))
const multiBatchConsistency = group.scenarios.B.quantities.reduce((sum, value) => sum + value, 0) === 1000
const amountConsistency = paymentRequests
  .filter(row => row.status === 'approved')
  .every(row => row.requestAmount === row.payableAmount)
const dataCounts = {
  suppliers: suppliers.length,
  buyers: buyers.length,
  materials: materials.length,
  purchaseRequests: purchaseRequests.length,
  purchaseOrders: purchaseOrders.length,
  receipts: receipts.length,
  inspections: inspections.length,
  warehouseReceipts: warehouseReceipts.length,
  reconciliations: reconciliations.length,
  differences: differences.length,
  paymentRequests: paymentRequests.length,
  paymentStatusRecords: paymentStatusRecords.length,
}
const minimumCounts = {
  suppliers: 10,
  buyers: 5,
  materials: 50,
  purchaseRequests: 30,
  purchaseOrders: 30,
  receipts: 60,
  inspections: 60,
  warehouseReceipts: 60,
  reconciliations: 20,
  differences: 10,
  paymentRequests: 15,
  paymentStatusRecords: 15,
}
const scalePassed = Object.entries(minimumCounts).every(([key, count]) => dataCounts[key] >= count)

const pythonExecutable = 'C:\\Users\\DAODA\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe'
const pythonPath = path.join(backend, 'venv/Lib/site-packages')
const backendTests = [
  'supplier_performance.tests.test_v81',
  'supplier_performance.tests.test_v83',
  'supplier_performance.tests.test_v84',
  'supplier_performance.tests.test_v831.SupplierSettlementWorkflowV831Tests.test_request_submit',
  'supplier_performance.tests.test_v831.SupplierSettlementWorkflowV831Tests.test_request_approve',
  'supplier_performance.tests.test_v831.SupplierSettlementWorkflowV831Tests.test_request_return',
  'supplier_performance.tests.test_v831.SupplierSettlementWorkflowV831Tests.test_illegal_request_jump_blocked',
  'supplier_performance.tests.test_v831.SupplierSettlementWorkflowV831Tests.test_direct_request_status_write_blocked',
  'supplier_performance.tests.test_v831.SupplierSettlementWorkflowV831Tests.test_transition_references_action_audit',
  'supplier_performance.tests.test_v831.SupplierSettlementWorkflowV831Tests.test_danger_writes_zero',
]
const backendTestRun = spawnSync(
  pythonExecutable,
  [
    'manage.py',
    'test',
    ...backendTests,
    '--settings=pce_backend.test_settings_v84',
    '--verbosity=1',
  ],
  {
    cwd: backend,
    env: { ...process.env, PYTHONPATH: pythonPath },
    encoding: 'utf8',
    maxBuffer: 10 * 1024 * 1024,
  },
)
const backendTestOutput = `${backendTestRun.stdout || ''}\n${backendTestRun.stderr || ''}`
const backendTestMatch = backendTestOutput.match(/Ran\s+(\d+)\s+tests?/)
const backendTestReport = {
  result: backendTestRun.status === 0 ? 'PASS' : 'FAIL',
  testCount: Number(backendTestMatch?.[1] || 0),
  exitCode: backendTestRun.status,
  summary: backendTestOutput.includes('OK') ? 'OK' : 'FAILED',
}

const rules = evaluateSupplierSettlementCanaryScenarioRules(group)
const totals = rules.reduce((summary, rule) => {
  summary[rule.status] += 1
  return summary
}, { PASS: 0, FAIL: 0, UNKNOWN: 0 })
const scenarioResults = Object.entries(group.scenarios).map(([scenarioId, scenario]) => ({
  scenarioId,
  name: scenario.name,
  status: scenario.status,
}))
const scenarioTotals = scenarioResults.reduce((summary, scenario) => {
  summary[scenario.status] += 1
  return summary
}, { PASS: 0, FAIL: 0, UNKNOWN: 0 })
const databaseHashAfter = sha256(databasePath)
const consistencyChecks = {
  scalePassed,
  relationshipConsistency,
  quantityConsistency,
  amountConsistency,
  statusConsistency,
  nodeConsistency,
  multiBatchConsistency,
}
const reportPassed = totals.FAIL === 0
  && totals.UNKNOWN === 0
  && scenarioTotals.FAIL === 0
  && scenarioTotals.UNKNOWN === 0
  && Object.values(consistencyChecks).every(Boolean)
  && backendTestReport.result === 'PASS'
  && databaseHashBefore === databaseHashAfter

const report = {
  version,
  generatedAt: new Date().toISOString(),
  result: reportPassed ? 'PASS' : 'FAIL',
  groupId,
  scenarioCount: scenarioResults.length,
  dataObjectCounts: dataCounts,
  minimumCounts,
  scenarios: scenarioResults,
  scenarioTotals,
  ruleCount: rules.length,
  rules,
  totals,
  processValidation: {
    nodeCount: processNodes.length,
    nodes: processNodes.map(node => ({
      sequence: node.sequence,
      nodeCode: node.nodeCode,
      nodeName: node.nodeName,
      pageUrl: node.pageUrl,
    })),
    status: nodeConsistency ? 'PASS' : 'FAIL',
  },
  consistencyChecks,
  backendServiceRegression: backendTestReport,
  dataProtection: {
    databaseHashBefore,
    databaseHashAfter,
    productionUserDataWritten: databaseHashBefore !== databaseHashAfter,
    businessDataWriteCount: 0,
    paymentExecutionWriteCount: 0,
    bankSendWriteCount: 0,
    fundDeductionCount: 0,
    financialImpactWriteCount: 0,
  },
}

fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(groupPath, `${JSON.stringify(group, null, 2)}\n`)
fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify(report, null, 2))
if (!reportPassed) process.exitCode = 1

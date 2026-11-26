import { listAccountPayableDrafts } from '../finance/accountPayableDraftStore.js'
import { listFormalPaymentVouchers } from '../finance/formalPaymentVoucherStore.js'
import { listInvoicePrepares } from '../finance/invoicePrepareStore.js'
import { listPayableChecks } from '../finance/payableCheckStore.js'
import { listPayablePrepares } from '../finance/payablePrepareStore.js'
import { listPaymentExecutions } from '../finance/paymentExecutionStore.js'
import { listPaymentExecutionRiskReviews } from '../finance/paymentExecutionRiskReviewStore.js'
import { listPaymentOrderDrafts } from '../finance/paymentOrderDraftStore.js'
import { listPaymentOrderPrepares } from '../finance/paymentOrderPrepareStore.js'
import { listPaymentRecordReviews } from '../finance/paymentRecordReviewStore.js'
import { listPaymentVoucherDrafts } from '../finance/paymentVoucherDraftStore.js'
import { listPaymentVoucherReviews } from '../finance/paymentVoucherReviewStore.js'
import { listSupplierPaymentDrafts } from '../finance/supplierPaymentDraftStore.js'
import { resolveP2PTraceNodeStatuses } from '../pages/p2pTraceResolver.js'

export function createFinanceTraceSnapshot() {
  return {
    payablePrepares: listPayablePrepares(),
    payableChecks: listPayableChecks(),
    invoicePrepares: listInvoicePrepares(),
    accountPayableDrafts: listAccountPayableDrafts(),
    supplierPaymentDrafts: listSupplierPaymentDrafts(),
    paymentOrderPrepares: listPaymentOrderPrepares(),
    paymentOrderDrafts: listPaymentOrderDrafts(),
    paymentExecutionRiskReviews: listPaymentExecutionRiskReviews(),
    paymentExecutions: listPaymentExecutions(),
    paymentRecordReviews: listPaymentRecordReviews(),
    paymentVoucherDrafts: listPaymentVoucherDrafts(),
    paymentVoucherReviews: listPaymentVoucherReviews(),
    formalPaymentVouchers: listFormalPaymentVouchers(),
  }
}

export function resolveP2PTraceData(sourceNo, snapshot = {}) {
  const poNo = clean(sourceNo)
  const scm = snapshot.scm || {}
  const receive = snapshot.receive || {}
  const qms = snapshot.qms || {}
  const wms = snapshot.wms || {}
  const finance = snapshot.finance || createFinanceTraceSnapshot()
  const purchaseOrders = scm.purchaseOrders || []
  const purchaseItems = scm.purchaseOrderItems || []
  const fieldProbe = {}
  const purchaseOrderMatch = findMatchedRecord(purchaseOrders, [poNo], purchaseOrderMatchFields)
  const purchaseOrder = purchaseOrderMatch?.record
    || (hasText(poNo) ? { poNo } : null)
  fieldProbe.purchaseOrderMatchedBy = purchaseOrderMatch?.matchedBy || (purchaseOrder ? 'input' : '')
  const purchaseOrderId = purchaseOrder?.id || ''
  const sourceKeys = uniqueList([poNo, purchaseOrderId])
  const lines = purchaseItems.filter((line) => (
    recordMatches(line, [purchaseOrderId], ['poId', 'purchaseOrderId', 'sourceOrderId'])
    || recordMatches(line, [poNo], purchaseOrderMatchFields)
  ))

  const existingP2P = resolveFromExistingP2PNodeStatuses(poNo, finance)
  if (existingP2P.fieldProbe.purchaseOrderMatchedBy) fieldProbe.purchaseOrderMatchedBy = existingP2P.fieldProbe.purchaseOrderMatchedBy

  const receiptMatch = filterMatchedRecords(receive.purchaseReceives || [], sourceKeys, receiptMatchFields)
  const receipts = receiptMatch.records
  fieldProbe.receiptMatchedBy = firstText(existingP2P.fieldProbe.receiptMatchedBy, receiptMatch.matchedBy)
  const receiptNos = uniqueList([...collectNos(receipts, ['receiveNo', 'receiptNo', 'sourceReceiveNo', 'no']), ...existingP2P.receiptNos])

  const inspectionMatch = filterMatchedRecords(qms.incomingInspections || [], [...sourceKeys, ...receiptNos], inspectionMatchFields)
  const inspections = inspectionMatch.records
  fieldProbe.inspectionMatchedBy = firstText(existingP2P.fieldProbe.inspectionMatchedBy, inspectionMatch.matchedBy)
  const inspectionNos = uniqueList([...collectNos(inspections, ['inspectionNo', 'iqcNo', 'sourceInspectionNo', 'no']), ...existingP2P.inspectionNos])
  const inspectionInventoryPosted = inspections.some(isInventoryPostedInspection)

  const inventoryMatch = filterMatchedRecords(wms.inventoryTransactions || [], [...sourceKeys, ...receiptNos, ...inspectionNos], inventoryMatchFields)
  const transactions = inventoryMatch.records
  fieldProbe.inventoryMatchedBy = firstText(existingP2P.fieldProbe.inventoryMatchedBy, inventoryMatch.matchedBy)
  const transactionNos = uniqueList([...collectNos(transactions, ['transactionNo', 'txnNo', 'inventoryTransactionNo', 'no', 'id']), ...existingP2P.transactionNos])

  const payableCollections = [
    ...tagRecords(finance.payablePrepares, 'payablePrepare'),
    ...tagRecords(finance.payableChecks, 'payableCheck'),
    ...tagRecords(finance.invoicePrepares, 'invoicePrepare'),
    ...tagRecords(finance.accountPayableDrafts, 'accountPayableDraft'),
  ]
  const payableMatch = filterMatchedRecords(payableCollections, [...sourceKeys, ...receiptNos, ...inspectionNos, ...transactionNos], financeMatchFields)
  const payableRecords = payableMatch.records
  fieldProbe.payableMatchedBy = firstText(existingP2P.fieldProbe.payableMatchedBy, payableMatch.matchedBy)
  const payableNos = uniqueList([...collectNos(payableRecords, [
    'payablePrepareNo',
    'sourcePayablePrepareNo',
    'payableCheckNo',
    'sourcePayableCheckNo',
    'invoicePrepareNo',
    'sourceInvoicePrepareNo',
    'apDraftNo',
    'sourceApDraftNo',
    'accountPayableNo',
    'payableNo',
    'sourcePayableNo',
  ]), ...existingP2P.payableNos])

  const paymentCollections = [
    ...tagRecords(finance.supplierPaymentDrafts, 'supplierPaymentDraft'),
    ...tagRecords(finance.paymentOrderPrepares, 'paymentOrderPrepare'),
    ...tagRecords(finance.paymentOrderDrafts, 'paymentOrderDraft'),
    ...tagRecords(finance.paymentExecutionRiskReviews, 'paymentExecutionRiskReview'),
    ...tagRecords(finance.paymentExecutions, 'paymentExecution'),
    ...tagRecords(finance.paymentRecordReviews, 'paymentRecordReview'),
    ...tagRecords(finance.paymentVoucherDrafts, 'paymentVoucherDraft'),
    ...tagRecords(finance.paymentVoucherReviews, 'paymentVoucherReview'),
    ...tagRecords(finance.formalPaymentVouchers, 'formalPaymentVoucher'),
  ]
  const paymentMatch = filterMatchedRecords(paymentCollections, [...sourceKeys, ...receiptNos, ...inspectionNos, ...transactionNos, ...payableNos], paymentMatchFields)
  const paymentRecords = paymentMatch.records
  fieldProbe.paymentMatchedBy = firstText(existingP2P.fieldProbe.paymentMatchedBy, paymentMatch.matchedBy)
  const paymentVoucherNos = uniqueList([...collectNos(paymentRecords, [
    'paymentDraftNo',
    'sourcePaymentDraftNo',
    'paymentPrepareNo',
    'sourcePaymentPrepareNo',
    'paymentOrderDraftNo',
    'sourcePaymentOrderDraftNo',
    'riskReviewNo',
    'sourceRiskReviewNo',
    'paymentExecutionNo',
    'sourcePaymentExecutionNo',
    'paymentRecordReviewNo',
    'sourcePaymentRecordReviewNo',
    'voucherDraftNo',
    'sourceVoucherDraftNo',
    'voucherReviewNo',
    'formalVoucherNo',
    'voucherNo',
    'paymentVoucherNo',
    'sourcePaymentNo',
  ]), ...existingP2P.paymentVoucherNos])

  const supplierList = collectSuppliers(purchaseOrder, lines, payableRecords, paymentRecords)
  const purchaseAmount = amount(lines.reduce((sum, line) => sum + lineAmount(line), 0)
    || purchaseOrder?.totalAmount
    || purchaseOrder?.amount
    || purchaseOrder?.planAmount
    || payableRecords.reduce((sum, item) => sum + amount(item.totalPayableAmount || item.payableAmount || item.totalInvoiceAmount), 0)
    || paymentRecords.reduce((sum, item) => sum + amount(item.executionAmount || item.paymentAmount || item.amount), 0))
  const matchedRecords = {
    purchaseOrder: purchaseOrder && hasText(poNo) ? 1 : 0,
    purchaseLines: lines.length,
    receipts: receipts.length,
    inspections: inspections.length,
    warehouseEntry: inspectionInventoryPosted || transactionNos.length > 0 || existingP2P.warehouseEntryNormal ? 1 : 0,
    inventoryTransactions: transactionNos.length,
    payables: payableRecords.length,
    payments: paymentRecords.length,
  }
  const missingNodes = Object.entries({
    purchaseOrder: !purchaseOrder,
    receipt: receipts.length === 0,
    inspection: inspections.length === 0,
    warehouseEntry: !inspectionInventoryPosted && transactionNos.length === 0 && !existingP2P.warehouseEntryNormal,
    inventoryTransaction: transactionNos.length === 0,
    payable: payableNos.length === 0,
    payment: paymentVoucherNos.length === 0,
  }).filter(([, missing]) => missing).map(([key]) => key)

  return {
    sourceModule: 'P2P',
    sourceNo: poNo,
    poNo,
    purchaseOrder,
    lines,
    supplierList,
    purchaseAmount,
    receipts,
    receiptNos,
    inspections,
    inspectionNos,
    inspectionInventoryPosted,
    transactions,
    transactionNos,
    payableRecords,
    payableNos,
    paymentRecords,
    paymentVoucherNos,
    existingP2PNodeStatuses: existingP2P.p2pNodeStatuses,
    reusedTraceTarget: existingP2P.traceTarget,
    reusedEvidenceSource: existingP2P.reusedEvidenceSource,
    formalVouchers: finance.formalPaymentVouchers || [],
    resolverDiagnostic: {
      sourceModule: 'P2P',
      resolverSource: existingP2P.reusedP2PNodeStatusCount ? 'existingP2PNodeStatuses' : resolverSourceFromFieldProbe(fieldProbe),
      matchedRecords,
      missingNodes,
      fieldProbe,
      reusedP2PNodeStatusCount: existingP2P.reusedP2PNodeStatusCount,
      reusedTraceTarget: existingP2P.traceTarget,
      reusedEvidenceSource: existingP2P.reusedEvidenceSource,
      resolverWarnings: missingNodes.length ? [`仍有未解析节点：${missingNodes.join('、')}`] : [],
    },
  }
}

export function resolveFromExistingP2PNodeStatuses(poNo, finance = {}) {
  const candidates = [
    ...tagRecords(finance.formalPaymentVouchers, 'formalPaymentVoucher'),
    ...tagRecords(finance.paymentVoucherReviews, 'paymentVoucherReview'),
    ...tagRecords(finance.paymentVoucherDrafts, 'paymentVoucherDraft'),
    ...tagRecords(finance.paymentRecordReviews, 'paymentRecordReview'),
    ...tagRecords(finance.paymentExecutions, 'paymentExecution'),
    ...tagRecords(finance.paymentExecutionRiskReviews, 'paymentExecutionRiskReview'),
    ...tagRecords(finance.paymentOrderDrafts, 'paymentOrderDraft'),
    ...tagRecords(finance.paymentOrderPrepares, 'paymentOrderPrepare'),
    ...tagRecords(finance.supplierPaymentDrafts, 'supplierPaymentDraft'),
    ...tagRecords(finance.accountPayableDrafts, 'accountPayableDraft'),
  ]
  const matched = candidates.filter((item) => recordMatches(item, [poNo], [
    ...purchaseOrderMatchFields,
    'rootRequestNo',
  ]))
  const receiptNos = collectNos(matched, ['sourceReceiveNo', 'receiveNo', 'receiptNo'])
  const inspectionNos = collectNos(matched, ['sourceInspectionNo', 'inspectionNo', 'iqcNo'])
  const transactionNos = collectNos(matched, ['sourceInventoryTransactionNos', 'sourceInventoryTransactionNo', 'transactionNo', 'txnNo'])
  const payableNos = collectNos(matched, [
    'sourceApDraftNo',
    'apDraftNo',
    'sourcePayableNo',
    'payableNo',
    'sourcePayableCheckNo',
    'payableCheckNo',
    'sourcePayablePrepareNo',
    'payablePrepareNo',
  ])
  const paymentVoucherNos = collectNos(matched, [
    'formalVoucherNo',
    'voucherNo',
    'paymentVoucherNo',
    'sourcePaymentNo',
    'paymentNo',
    'sourcePaymentExecutionNo',
    'paymentExecutionNo',
    'sourcePaymentRecordReviewNo',
    'paymentRecordReviewNo',
  ])
  const p2pNodeStatuses = resolveP2PTraceNodeStatuses({
    purchaseOrderNo: poNo,
    receiveNo: receiptNos.join('、'),
    inspectionNo: inspectionNos.join('、'),
    inventoryTransaction: transactionNos.join('、'),
    inventoryTransactionNos: transactionNos,
    payable: payableNos.join('、'),
    paymentVoucher: paymentVoucherNos.join('、'),
  })
  const normalStatuses = p2pNodeStatuses.filter((item) => item.status === 'normal')
  return {
    receiptNos,
    inspectionNos,
    transactionNos,
    payableNos,
    paymentVoucherNos,
    p2pNodeStatuses,
    warehouseEntryNormal: p2pNodeStatuses.some((item) => item.node === 'warehouseEntry' && item.status === 'normal'),
    reusedP2PNodeStatusCount: normalStatuses.length,
    reusedEvidenceSource: matched.map((item) => item.traceRecordType).filter(Boolean).join('、') || '',
    traceTarget: {
      purchaseOrder: poNo,
      receipt: receiptNos.join('、'),
      inspection: inspectionNos.join('、'),
      warehouseEntry: p2pNodeStatuses.find((item) => item.node === 'warehouseEntry')?.sourceNo || '',
      inventoryTransaction: transactionNos.join('、'),
      payable: payableNos.join('、'),
      paymentVoucher: paymentVoucherNos.join('、'),
    },
    fieldProbe: {
      purchaseOrderMatchedBy: matched.length ? 'existingP2PNodeStatuses' : '',
      receiptMatchedBy: receiptNos.length ? 'existingP2PNodeStatuses' : '',
      inspectionMatchedBy: inspectionNos.length ? 'existingP2PNodeStatuses' : '',
      inventoryMatchedBy: transactionNos.length ? 'existingP2PNodeStatuses' : '',
      payableMatchedBy: payableNos.length ? 'existingP2PNodeStatuses' : '',
      paymentMatchedBy: paymentVoucherNos.length ? 'existingP2PNodeStatuses' : '',
    },
  }
}

const purchaseOrderMatchFields = [
  'sourcePurchaseOrderNo',
  'purchaseOrderNo',
  'poNo',
  'sourcePoNo',
  'orderNo',
  'sourceOrderNo',
  'no',
]

const receiptMatchFields = [
  ...purchaseOrderMatchFields,
  'sourceOrderId',
]

const inspectionMatchFields = [
  ...purchaseOrderMatchFields,
  'sourceReceiveNo',
  'receiveNo',
  'receiptNo',
]

const inventoryMatchFields = [
  ...purchaseOrderMatchFields,
  'sourceReceiptNo',
  'sourceReceiveNo',
  'receiptNo',
  'sourceInspectionNo',
  'inspectionNo',
  'inspectionNo',
  'transactionNo',
  'txnNo',
]

const financeMatchFields = [
  'sourcePurchaseOrderNo',
  'purchaseOrderNo',
  'poNo',
  'sourcePoNo',
  'orderNo',
  'sourceOrderNo',
  'rootRequestNo',
  'sourceReceiveNo',
  'receiveNo',
  'receiptNo',
  'sourceInspectionNo',
  'inspectionNo',
  'sourceInventoryTransactionNo',
  'sourceInventoryTransactionNos',
  'transactionNo',
  'txnNo',
  'sourcePayablePrepareNo',
  'payablePrepareNo',
  'sourcePayableCheckNo',
  'payableCheckNo',
  'sourceInvoicePrepareNo',
  'invoicePrepareNo',
  'sourceApDraftNo',
  'apDraftNo',
  'sourcePayableNo',
  'payableNo',
  'sourcePaymentNo',
  'paymentNo',
  'voucherNo',
  'formalVoucherNo',
]

const paymentMatchFields = [
  ...financeMatchFields,
  'sourcePaymentDraftNo',
  'paymentDraftNo',
  'sourcePaymentPrepareNo',
  'paymentPrepareNo',
  'sourcePaymentOrderDraftNo',
  'paymentOrderDraftNo',
  'sourcePaymentExecutionNo',
  'paymentExecutionNo',
  'sourcePaymentRecordReviewNo',
  'paymentRecordReviewNo',
  'paymentVoucherNo',
]

function filterMatchedRecords(records = [], values = [], fields = []) {
  const matched = []
  const matchedBy = []
  records.forEach((record) => {
    const result = matchRecord(record, values, fields)
    if (result.matched) {
      matched.push(record)
      matchedBy.push(result.matchedBy)
    }
  })
  return {
    records: matched,
    matchedBy: uniqueList(matchedBy).join('、') || '',
  }
}

function findMatchedRecord(records = [], values = [], fields = []) {
  for (const record of records) {
    const result = matchRecord(record, values, fields)
    if (result.matched) return { record, matchedBy: result.matchedBy }
  }
  return null
}

function recordMatches(record = {}, values = [], fields = []) {
  return matchRecord(record, values, fields).matched
}

function matchRecord(record = {}, values = [], fields = []) {
  const keys = uniqueList(values).filter(hasText)
  if (!keys.length) return { matched: false, matchedBy: '' }
  for (const field of fields) {
    const valuesFromField = asArray(record?.[field])
    if (valuesFromField.some((value) => keys.includes(String(value || '')))) {
      return { matched: true, matchedBy: field }
    }
  }
  const text = JSON.stringify(record || {})
  return keys.some((key) => text.includes(key))
    ? { matched: true, matchedBy: 'text' }
    : { matched: false, matchedBy: '' }
}

function collectNos(records = [], fields = []) {
  return uniqueList(records.flatMap((record) => fields.flatMap((field) => asArray(record?.[field]))))
}

function tagRecords(records = [], traceRecordType) {
  return (records || []).map((record) => ({ ...record, traceRecordType }))
}

function collectSuppliers(...groups) {
  return uniqueList(groups.flatMap((group) => {
    if (Array.isArray(group)) return group.flatMap((item) => [item?.supplierName, item?.supplierId])
    return [group?.supplierName, group?.supplierId]
  }))
}

function resolverSourceFromFieldProbe(fieldProbe = {}) {
  const values = Object.values(fieldProbe).filter(Boolean)
  if (values.includes('text')) return 'textFallback'
  return values.length ? 'fieldScan' : 'fieldScan'
}

function lineAmount(line = {}) {
  return amount(line.amount || line.totalAmount || (Number(line.quantity || 0) * Number(line.price || line.unitPrice || 0)))
}

function firstText(...values) {
  return values.find((value) => hasText(value)) || ''
}

function isInventoryPostedInspection(record = {}) {
  const statusText = [
    record.status,
    record.statusText,
    record.warehouseStatus,
    record.warehouseStatusText,
    record.inventoryStatus,
    record.inventoryStatusText,
    record.inventoryPostStatus,
    record.inventoryPostStatusText,
    record.postStatus,
    record.postStatusText,
  ].map((item) => String(item || '')).join(' ')
  return Boolean(record.inventoryPosted || record.warehousePosted || record.posted)
    || /已入库|入库完成|posted|inInventory|inventoryPosted|completed|success/i.test(statusText)
}

function amount(value) {
  const number = Number(value || 0)
  if (!Number.isFinite(number)) return 0
  return Math.round(number * 100) / 100
}

function asArray(value) {
  if (Array.isArray(value)) return value.filter(Boolean)
  return String(value || '').split(/[、,，;；\s]+/).map((item) => item.trim()).filter(Boolean)
}

function uniqueList(items = []) {
  return Array.from(new Set(items.map((item) => String(item || '').trim()).filter(Boolean)))
}

function hasText(value) {
  return String(value || '').trim().length > 0
}

function clean(value) {
  return String(value || '').trim()
}

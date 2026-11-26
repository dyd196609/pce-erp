import { listFormalPaymentVouchers } from '../finance/formalPaymentVoucherStore.js'
import { getScmState } from '../scm/scmStore.js'
import { getPurchaseReceiveState } from '../wms/purchaseReceiveStore.js'
import { getQmsState } from '../qms/qmsStore.js'
import { getWmsState } from '../wms/wmsStore.js'
import { createFinanceTraceSnapshot, resolveP2PTraceData } from './businessTraceResolver.js'

export function createBusinessTraceSnapshot() {
  return {
    scm: getScmState(),
    receive: getPurchaseReceiveState(),
    qms: getQmsState(),
    wms: getWmsState(),
    finance: createFinanceTraceSnapshot(),
    formalVouchers: listFormalPaymentVouchers(),
  }
}

export function listP2PBusinessTraces(options = {}, snapshot = createBusinessTraceSnapshot()) {
  const sourceNo = clean(options.documentNo || options.sourceNo || options.queryValue)
  const documentType = options.documentType || options.queryType || 'purchaseOrder'
  const purchaseOrders = snapshot.scm?.purchaseOrders || []
  const shouldPrefilterPurchaseOrder = sourceNo && documentType === 'purchaseOrder'
  const sourceOrders = shouldPrefilterPurchaseOrder
    ? ensureFallbackOrder(purchaseOrders.filter((item) => matchKeyword(orderNo(item), sourceNo)), sourceNo)
    : purchaseOrders

  return sourceOrders
    .map((order) => resolveP2PBusinessTrace(orderNo(order) || sourceNo, snapshot, order))
    .filter((trace) => !sourceNo || businessTraceSearchText(trace).includes(normalize(sourceNo)))
}

export function resolveP2PBusinessTrace(sourceNo, snapshot = createBusinessTraceSnapshot(), sourceOrder = null) {
  const resolverData = resolveP2PTraceData(sourceNo, {
    ...snapshot,
    scm: {
      ...(snapshot.scm || {}),
      purchaseOrders: sourceOrder ? uniqueBy([sourceOrder, ...(snapshot.scm?.purchaseOrders || [])], 'id') : (snapshot.scm?.purchaseOrders || []),
    },
  })
  const {
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
    resolverDiagnostic,
  } = resolverData
  const inventoryDisplay = buildInventoryDisplay(transactionNos, transactions)
  const inventoryTransactionDetails = inventoryDisplay.displayedTxnNos.map((no) => {
    const record = transactions.find((item) => firstText(item.transactionNo, item.txnNo, item.inventoryTransactionNo, item.no, item.id) === no) || {}
    return {
      transactionNo: no,
      transactionType: firstText(record.transactionTypeText, record.transactionType, record.typeText, record.type, '采购入库类库存流水'),
      sourceInspectionNo: firstText(record.sourceInspectionNo, inspectionNos.join('、')),
      sourceReceiptNo: firstText(record.sourceReceiptNo, record.sourceReceiveNo, receiptNos.join('、')),
      sourcePurchaseOrderNo: firstText(record.sourcePurchaseOrderNo, record.sourceOrderNo, poNo),
    }
  })
  const documentGroups = buildDocumentGroups(payableRecords, paymentRecords)
  const amountSummary = buildAmountSummary({ purchaseAmount, payableRecords, paymentRecords })
  const amountReconciliation = amountSummary.amountReconciliation

  const traceNodes = buildP2PNodes({
    purchaseOrder,
    lines,
    supplierList,
    purchaseAmount,
    amountSummary,
    receipts,
    receiptNos,
    inspections,
    inspectionNos,
    inspectionInventoryPosted,
    transactions,
    transactionNos: inventoryDisplay.displayedTxnNos,
    payableRecords,
    payableNos,
    paymentRecords,
    paymentVoucherNos,
    documentGroups,
    inventoryDisplay,
    inventoryTransactionDetails,
  })
  const requiredNodes = traceNodes.filter((node) => !['purchaseRequest', 'inquiry', 'pricing'].includes(node.key))
  const missingRequired = requiredNodes.filter((node) => node.status !== 'normal')
  const riskStatus = missingRequired.length ? 'risk' : amountReconciliation.amountStatus === 'difference' ? 'amount_check' : 'normal'
  const businessStatus = resolveBusinessStatus({ receipts, inspections, transactions, payableNos, paymentVoucherNos })

  return {
    id: String(purchaseOrder?.id || poNo),
    sourceNo,
    poNo,
    purchaseOrderNo: poNo || '-',
    purchaseOrder,
    lines,
    supplierList,
    supplierText: supplierList.join('、') || '-',
    purchaseAmount,
    amount: purchaseAmount,
    amountText: formatCurrency(purchaseAmount),
    receipts,
    receiptNos,
    inspections,
    inspectionNos,
    transactions,
    transactionNos: inventoryDisplay.displayedTxnNos,
    rawTransactionNos: transactionNos,
    inventoryDisplay,
    inventoryTransactionDetails,
    documentGroups,
    amountSummary,
    amountReconciliation,
    payableRecords,
    payableNos,
    paymentRecords,
    paymentVoucherNos,
    businessTraceResolverDiagnostic: resolverDiagnostic,
    traceNodes,
    nodes: traceNodes,
    riskStatus,
    riskStatusText: riskStatus === 'normal' ? '正常' : riskStatus === 'amount_check' ? '金额待核对' : '有风险',
    businessStatus,
    businessStatusText: businessStatusText(businessStatus),
    nodeSummary: traceNodes.map((node) => `${node.title}:${node.statusText}`).join(' / '),
    sourceDate: firstText(purchaseOrder?.orderDate, purchaseOrder?.createdAt, purchaseOrder?.date),
    documentNos: uniqueList(traceNodes.flatMap((node) => asArray(node.documentNo))),
  }
}

export function buildBusinessTraceDiagnostic({ page = 'BusinessTraceCenter', version = 'V1.13.28.1', queryType = 'purchaseOrder', queryValue = '', traces = [], selectedTrace = null, warnings = [] } = {}) {
  return {
    page,
    version,
    queryType,
    queryValue,
    matchedCount: traces.length,
    traceNodes: selectedTrace?.traceNodes || selectedTrace?.nodes || [],
    businessTraceResolverDiagnostic: selectedTrace?.businessTraceResolverDiagnostic || null,
    amountSummary: selectedTrace?.amountSummary || null,
    amountReconciliation: selectedTrace?.amountReconciliation || null,
    documentGroups: selectedTrace?.documentGroups || null,
    inventoryDisplay: selectedTrace?.inventoryDisplay || null,
    warnings,
    timestamp: new Date().toISOString(),
  }
}

export function businessTraceSearchText(trace = {}) {
  return normalize([
    trace.purchaseOrderNo,
    trace.supplierText,
    ...(trace.documentNos || []),
  ].join(' '))
}

function buildP2PNodes(data = {}) {
  const requestNo = firstText(data.purchaseOrder?.rootRequestNo, data.purchaseOrder?.sourceRequestNo, data.purchaseOrder?.requestNo)
  const inquiryNo = firstText(data.purchaseOrder?.sourceInquiryNo, data.purchaseOrder?.inquiryNo)
  const pricingNo = firstText(data.purchaseOrder?.sourcePriceApprovalNo, data.purchaseOrder?.priceApprovalNo, data.purchaseOrder?.sourceOrderNo)
  const poNo = orderNo(data.purchaseOrder || {})
  const supplier = data.supplierList.join('、')
  return [
    buildNode('purchaseRequest', '请购', requestNo, requestNo ? '已追踪到请购来源。' : '当前采购订单未提供请购来源字段。', [
      { label: '入口状态', value: requestNo ? '已追踪' : '设计预留' },
    ], requestNo ? 'normal' : 'placeholder'),
    buildNode('inquiry', '询价', inquiryNo, inquiryNo ? '已追踪到询价来源。' : '当前采购订单未提供询价来源字段。', [
      { label: '入口状态', value: inquiryNo ? '已追踪' : '设计预留' },
    ], inquiryNo ? 'normal' : 'placeholder'),
    buildNode('pricing', '核价', pricingNo, pricingNo ? '已追踪到核价来源。' : '当前采购订单未提供核价来源字段。', [
      { label: '入口状态', value: pricingNo ? '已追踪' : '设计预留' },
    ], pricingNo ? 'normal' : 'placeholder'),
    buildNode('purchaseOrder', '采购订单', poNo, '采购订单作为当前业务追踪入口。', [
      { label: '供应商', value: supplier },
      { label: '金额', value: formatCurrency(data.purchaseAmount) },
      { label: '明细行数', value: data.lines.length },
    ]),
    buildNode('receipt', '收货', data.receiptNos.join('、'), '找到采购订单对应收货记录。', [
      { label: '收货数量', value: data.receipts.length },
    ]),
    buildNode('inspection', '检验', data.inspectionNos.join('、'), '找到收货或采购订单对应检验记录。', [
      { label: '检验数量', value: data.inspections.length },
    ]),
    buildNode('warehouseEntry', '入库', data.transactionNos.length || data.inspectionInventoryPosted ? warehouseEntryEvidence(data) : '', '库存流水或检验入库状态可作为入库完成依据。', [
      { label: '入库来源', value: data.transactionNos.length ? '库存流水' : data.inspectionInventoryPosted ? '检验状态' : '' },
    ]),
    buildNode('inventoryTransaction', '库存流水', data.transactionNos.join('、'), '库存流水编号已按同一订单去重。', [
      { label: '业务流水数量', value: data.inventoryDisplay.businessTxnCount },
    ]),
    buildNode('payable', '应付', data.documentGroups.accountPayable.join('、'), '应付节点按流程证据分组展示，金额只取最终应付对象。', [
      { label: '应付预备', value: data.documentGroups.payablePrepare.join('、') || '-' },
      { label: '应付核对', value: data.documentGroups.payableCheck.join('、') || '-' },
      { label: '发票预备', value: data.documentGroups.invoicePrepare.join('、') || '-' },
      { label: '应付草稿 / 应付对象', value: data.documentGroups.accountPayable.join('、') || '-' },
      { label: '应付金额', value: data.amountSummary.payableAmountText },
      { label: '金额依据', value: data.amountSummary.payableAmountSource },
    ]),
    buildNode('payment', '付款', paymentDisplayNos(data.documentGroups).join('、'), '付款节点按流程证据分组展示，金额只取最终付款结果。', [
      { label: '付款草稿', value: data.documentGroups.paymentDraft.join('、') || '-' },
      { label: '付款指令', value: data.documentGroups.paymentOrder.join('、') || '-' },
      { label: '付款执行', value: data.documentGroups.paymentExecution.join('、') || '-' },
      { label: '付款记录', value: data.documentGroups.paymentRecord.join('、') || '-' },
      { label: '付款凭证', value: [...data.documentGroups.paymentVoucher, ...data.documentGroups.formalPaymentVoucher].join('、') || '-' },
      { label: '付款金额', value: data.amountSummary.paymentAmountText },
      { label: '金额依据', value: data.amountSummary.paymentAmountSource },
    ]),
  ]
}

function buildInventoryDisplay(transactionNos = [], transactions = []) {
  const rawNos = uniqueList(transactionNos)
  const businessTxnNos = uniqueList([
    ...rawNos.filter(isBusinessTxnNo),
    ...transactions.flatMap((record) => [
      record.transactionNo,
      record.txnNo,
      record.inventoryTransactionNo,
      record.no,
    ]).filter(isBusinessTxnNo),
  ])
  const displayedTxnNos = businessTxnNos
  return {
    businessTxnCount: displayedTxnNos.length,
    internalTxnCount: rawNos.filter((no) => !displayedTxnNos.includes(no)).length,
    displayedTxnNos,
    hiddenInternalTxnIds: rawNos.filter((no) => !displayedTxnNos.includes(no)),
  }
}

function buildDocumentGroups(payableRecords = [], paymentRecords = []) {
  const byType = (records, type, fields) => collectRecordNos(records.filter((record) => record.traceRecordType === type), fields)
  return {
    payablePrepare: byType(payableRecords, 'payablePrepare', ['payablePrepareNo', 'sourcePayablePrepareNo', 'no']),
    payableCheck: byType(payableRecords, 'payableCheck', ['payableCheckNo', 'sourcePayableCheckNo', 'no']),
    invoicePrepare: byType(payableRecords, 'invoicePrepare', ['invoicePrepareNo', 'sourceInvoicePrepareNo', 'no']),
    accountPayable: byType(payableRecords, 'accountPayableDraft', ['apDraftNo', 'sourceApDraftNo', 'accountPayableNo', 'payableNo', 'sourcePayableNo', 'no']),
    paymentDraft: byType(paymentRecords, 'supplierPaymentDraft', ['paymentDraftNo', 'sourcePaymentDraftNo', 'supplierPaymentDraftNo', 'no']),
    paymentOrder: uniqueList([
      ...byType(paymentRecords, 'paymentOrderPrepare', ['paymentPrepareNo', 'sourcePaymentPrepareNo', 'paymentOrderPrepareNo', 'no']),
      ...byType(paymentRecords, 'paymentOrderDraft', ['paymentOrderDraftNo', 'sourcePaymentOrderDraftNo', 'paymentOrderNo', 'no']),
    ]),
    paymentExecution: byType(paymentRecords, 'paymentExecution', ['paymentExecutionNo', 'sourcePaymentExecutionNo', 'executionNo', 'no']),
    paymentRecord: byType(paymentRecords, 'paymentRecordReview', ['paymentRecordReviewNo', 'sourcePaymentRecordReviewNo', 'paymentRecordNo', 'no']),
    paymentVoucher: uniqueList([
      ...byType(paymentRecords, 'paymentVoucherDraft', ['voucherDraftNo', 'sourceVoucherDraftNo', 'paymentVoucherDraftNo', 'no']),
      ...byType(paymentRecords, 'paymentVoucherReview', ['voucherReviewNo', 'paymentVoucherNo', 'voucherNo', 'no']),
    ]),
    formalPaymentVoucher: byType(paymentRecords, 'formalPaymentVoucher', ['formalVoucherNo', 'voucherNo', 'paymentVoucherNo', 'no']),
  }
}

function buildAmountSummary({ purchaseAmount = 0, payableRecords = [], paymentRecords = [] } = {}) {
  const payableAmountInfo = resolveAmountFromRecords(payableRecords.filter((record) => record.traceRecordType === 'accountPayableDraft'), [
    'totalPayableAmount',
    'payableAmount',
    'amount',
    'totalAmount',
  ])
  const paymentAmountInfo = resolvePaymentAmount(paymentRecords)
  const purchase = amount(purchaseAmount)
  const payable = payableAmountInfo.confirmed ? payableAmountInfo.amount : null
  const payment = paymentAmountInfo.confirmed ? paymentAmountInfo.amount : null
  const amountReconciliation = buildAmountReconciliation({
    purchaseAmount: purchase,
    payableAmount: payable,
    paymentAmount: payment,
    payableAmountInfo,
    paymentAmountInfo,
  })
  return {
    purchaseAmount: purchase,
    payableAmount: payable,
    paymentAmount: payment,
    purchaseAmountText: formatCurrency(purchase),
    payableAmountText: payableAmountInfo.confirmed ? formatCurrency(payable) : '应付金额待确认',
    paymentAmountText: paymentAmountInfo.confirmed ? formatCurrency(payment) : '付款金额待确认',
    purchaseAmountSource: amountReconciliation.purchaseAmountSource,
    payableAmountSource: amountReconciliation.payableAmountSourceDocuments.join('、') || '应付金额待确认',
    paymentAmountSource: amountReconciliation.paymentAmountSourceDocuments.join('、') || '付款金额待确认',
    amountDifferenceWarning: amountReconciliation.amountConclusion,
    amountReconciliation,
  }
}

function resolvePaymentAmount(paymentRecords = []) {
  const formal = resolveAmountFromRecords(paymentRecords.filter((record) => record.traceRecordType === 'formalPaymentVoucher'), [
    'totalVoucherAmount',
    'paymentAmount',
    'executionAmount',
    'amount',
  ])
  if (formal.confirmed) return { ...formal, source: 'formalPaymentVoucher' }
  const execution = resolveAmountFromRecords(paymentRecords.filter((record) => record.traceRecordType === 'paymentExecution' && isCompletedPaymentRecord(record)), [
    'executionAmount',
    'paymentAmount',
    'amount',
  ])
  if (execution.confirmed) return { ...execution, source: 'paymentExecution completed' }
  const record = resolveAmountFromRecords(paymentRecords.filter((item) => item.traceRecordType === 'paymentRecordReview' && isPassedPaymentRecord(item)), [
    'paymentAmount',
    'recordAmount',
    'amount',
  ])
  if (record.confirmed) return { ...record, source: 'paymentRecordReview passed' }
  return { confirmed: false, amount: null, source: '' }
}

function resolveAmountFromRecords(records = [], fields = []) {
  const amountRecords = uniqueBy(records.map((record) => ({
    sourceNo: amountSourceNo(record),
    amount: firstAmount(record, fields),
  })).filter((item) => item.amount > 0), 'sourceNo')
  if (!amountRecords.length) return { confirmed: false, amount: null, source: '', sourceDocuments: [] }
  return {
    confirmed: true,
    amount: amount(amountRecords.reduce((total, item) => total + item.amount, 0)),
    source: amountRecords.map((item) => item.sourceNo).join('、'),
    sourceDocuments: amountRecords.map((item) => item.sourceNo),
  }
}

function buildAmountReconciliation({
  purchaseAmount = 0,
  payableAmount = null,
  paymentAmount = null,
  payableAmountInfo = {},
  paymentAmountInfo = {},
} = {}) {
  const purchaseToPayableDifference = payableAmount === null ? null : amount(purchaseAmount - payableAmount)
  const payableToPaymentDifference = payableAmount === null || paymentAmount === null ? null : amount(payableAmount - paymentAmount)
  const hasPending = payableAmount === null || paymentAmount === null
  const hasDifference = !hasPending && (Math.abs(purchaseToPayableDifference) > 0.009 || Math.abs(payableToPaymentDifference) > 0.009)
  const amountStatus = hasPending ? 'pending' : hasDifference ? 'difference' : 'matched'
  const conclusionParts = []
  if (payableAmount === null) conclusionParts.push('最终应付金额待确认')
  if (paymentAmount === null) conclusionParts.push('最终付款金额待确认')
  if (purchaseToPayableDifference !== null && Math.abs(purchaseToPayableDifference) > 0.009) {
    conclusionParts.push(`采购金额与应付金额差异 ${formatCurrency(Math.abs(purchaseToPayableDifference))}`)
  }
  if (payableToPaymentDifference !== null && Math.abs(payableToPaymentDifference) > 0.009) {
    conclusionParts.push(paymentAmount > payableAmount
      ? `付款金额大于应付金额 ${formatCurrency(Math.abs(payableToPaymentDifference))}`
      : `应付金额与付款金额差异 ${formatCurrency(Math.abs(payableToPaymentDifference))}`)
  }
  if (amountStatus === 'matched') conclusionParts.push('采购、应付、付款金额基本一致')
  if (amountStatus === 'difference') conclusionParts.push('请核对应付对象、正式付款凭证、部分付款、多供应商拆分、扣款或税额差异')
  return {
    purchaseAmount,
    payableAmount,
    paymentAmount,
    purchaseToPayableDifference,
    payableToPaymentDifference,
    amountStatus,
    amountConclusion: conclusionParts.join('；'),
    purchaseAmountSource: '采购订单金额',
    payableAmountSourceDocuments: payableAmountInfo.sourceDocuments || [],
    paymentAmountSourceDocuments: paymentAmountInfo.sourceDocuments || [],
  }
}

function paymentDisplayNos(documentGroups = {}) {
  return uniqueList([
    ...(documentGroups.formalPaymentVoucher || []),
    ...(documentGroups.paymentVoucher || []),
    ...(documentGroups.paymentRecord || []),
    ...(documentGroups.paymentExecution || []),
    ...(documentGroups.paymentOrder || []),
    ...(documentGroups.paymentDraft || []),
  ])
}

function collectRecordNos(records = [], fields = []) {
  return uniqueList(records.flatMap((record) => fields.flatMap((field) => asArray(record?.[field]))))
}

function isBusinessTxnNo(value) {
  return /^TXN\d/i.test(String(value || '').trim())
}

function amountSourceNo(record = {}) {
  return firstText(
    record.formalVoucherNo,
    record.voucherNo,
    record.paymentVoucherNo,
    record.sourcePaymentNo,
    record.apDraftNo,
    record.sourceApDraftNo,
    record.accountPayableNo,
    record.payableNo,
    record.sourcePayableNo,
    record.paymentExecutionNo,
    record.sourcePaymentExecutionNo,
    record.paymentRecordReviewNo,
    record.sourcePaymentRecordReviewNo,
    record.id,
  )
}

function firstAmount(record = {}, fields = []) {
  for (const field of fields) {
    const value = amount(record?.[field])
    if (value > 0) return value
  }
  return 0
}

function isCompletedPaymentRecord(record = {}) {
  const statusText = [
    record.status,
    record.statusText,
    record.executionStatus,
    record.executionStatusText,
    record.paymentStatus,
    record.paymentStatusText,
  ].map((item) => String(item || '')).join(' ')
  return Boolean(record.completed || record.executed || record.paid)
    || /completed|success|paid|executed|passed/i.test(statusText)
}

function isPassedPaymentRecord(record = {}) {
  const statusText = [
    record.status,
    record.statusText,
    record.reviewStatus,
    record.reviewStatusText,
    record.approvalStatus,
    record.approvalStatusText,
  ].map((item) => String(item || '')).join(' ')
  return Boolean(record.passed || record.approved)
    || /passed|approved|success|completed/i.test(statusText)
}

function buildNode(key, title, documentNo, description, details = [], forcedStatus = '') {
  const normal = hasText(documentNo)
  const status = forcedStatus || (normal ? 'normal' : 'missing')
  return {
    key,
    title,
    status,
    statusText: status === 'normal' ? '正常' : status === 'placeholder' ? '预留' : '缺失',
    documentNo,
    description: normal || status === 'placeholder' ? description : '当前未找到对应来源，仅用于只读定位。',
    details,
  }
}

function warehouseEntryEvidence(data = {}) {
  if (data.transactionNos.length) return data.transactionNos.join('、')
  return data.inspectionInventoryPosted ? '检验状态显示已入库' : ''
}

function ensureFallbackOrder(orders = [], sourceNo = '') {
  if (orders.length || !hasText(sourceNo)) return orders
  return [{ poNo: sourceNo }]
}

function resolveBusinessStatus({ receipts, inspections, transactions, payableNos, paymentVoucherNos }) {
  if (!receipts.length) return 'pendingReceipt'
  if (!inspections.length) return 'inspection'
  if (!transactions.length) return 'pendingInventory'
  if (!payableNos.length || !paymentVoucherNos.length) return 'pendingPayment'
  return 'paid'
}

function businessStatusText(status) {
  const map = {
    purchasing: '采购中',
    pendingReceipt: '待收货',
    inspection: '检验中',
    pendingInventory: '待入库',
    inInventory: '已入库',
    pendingPayment: '待付款',
    paid: '已付款',
    abnormal: '异常',
  }
  return map[status] || '待确认'
}

function orderNo(order = {}) {
  return firstText(order.poNo, order.purchaseOrderNo, order.orderNo, order.no)
}

function lineAmount(line = {}) {
  return amount(line.amount || line.totalAmount || (Number(line.quantity || 0) * Number(line.price || line.unitPrice || 0)))
}

function voucherAmount(voucher = {}) {
  return amount(voucher.totalVoucherAmount || voucher.executionAmount || voucher.paymentAmount || voucher.totalPayableAmount || voucher.amount || voucher.debitAmount || voucher.creditAmount)
}

function amount(value) {
  const number = Number(value || 0)
  if (!Number.isFinite(number)) return 0
  return Math.round(number * 100) / 100
}

function formatCurrency(value) {
  return amount(value).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function matches(value, targets = []) {
  const text = String(value || '')
  return targets.some((target) => hasText(target) && text === String(target))
}

function matchKeyword(value, keyword) {
  return normalize(value).includes(normalize(keyword))
}

function intersects(left = [], right = []) {
  const rightSet = new Set(right.map((item) => String(item || '')))
  return left.some((item) => rightSet.has(String(item || '')))
}

function asArray(value) {
  if (Array.isArray(value)) return value.filter(Boolean)
  return String(value || '').split(/[、,，;；\s]+/).map((item) => item.trim()).filter(Boolean)
}

function uniqueList(items = []) {
  return Array.from(new Set(items.map((item) => String(item || '').trim()).filter(Boolean)))
}

function uniqueBy(items = [], key) {
  const seen = new Set()
  return items.filter((item) => {
    const value = item?.[key]
    if (!hasText(value) || seen.has(value)) return false
    seen.add(value)
    return true
  })
}

function firstText(...values) {
  return values.find((value) => hasText(value)) || ''
}

function hasText(value) {
  return String(value || '').trim().length > 0
}

function clean(value) {
  return String(value || '').trim()
}

function normalize(value) {
  return clean(value).toLowerCase()
}

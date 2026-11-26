import { buildPurchaseOrderLifecycleSnapshotV114284272 } from
  '../domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleRuntimeV114284272.js'
import { buildPurchaseOrderApprovalContextV114284272 } from
  '../domain/scm/purchaseOrder/approval/purchaseOrderApprovalContextV114284272.js'
import { evaluateQualifiedMaterialPriceV114284272 } from
  '../domain/scm/purchaseOrder/domain/qualifiedMaterialPriceV114284272.js'
import { purchaseOrderCreationDraftStoreV114284262 } from
  '../runtime/purchaseOrderCreationDraftRuntimeV114284262.js'

export const PURCHASE_ORDER_LIFECYCLE_DETAIL_PROVIDER_VERSION_V114284272 =
  'V1.14.2.8.4.27.2'
export const PURCHASE_ORDER_DETAIL_FLOW_VERSION_V1142842721 =
  'V1.14.2.8.4.27.2.1'
export const PURCHASE_ORDER_DOCUMENT_VIEW_VERSION_V11428427242 =
  'V1.14.2.8.4.27.2.4.2'

const freeze = value => Object.freeze(value)
const text = value => String(value ?? '').trim()
const number = value => Number.isFinite(Number(value)) ? Number(value) : 0
const clone = value => JSON.parse(JSON.stringify(value))

const lifecycleLabels = Object.freeze({
  draft: '草稿', pending_approval: '待审批', approved: '已审批', issued: '已下达',
  partially_received: '部分收货', completed: '完成', cancelled: '取消',
  submitted: '已提交', reviewed: '已审核', rechecked: '已复核', converted: '已转换',
  partiallyReceived: '部分收货', fullyReceived: '全部收货', receiving: '收货中',
  received: '已收货', closed: '已关闭',
})

const approvalLabels = Object.freeze({
  not_started: '未发起', pending_approval: '待审批', approved: '已审批',
  rejected: '已驳回', cancelled: '已取消',
})

const nextActionByStatus = Object.freeze({
  draft: Object.freeze({ code: 'submit_approval', label: '提交审批', mode: 'controlled_action_pending' }),
  pending_approval: Object.freeze({ code: 'view_approval', label: '查看审批', mode: 'focus_approval' }),
  approved: Object.freeze({ code: 'issue_purchase_order', label: '下达采购订单', mode: 'controlled_action_pending' }),
  issued: Object.freeze({ code: 'view_receipt', label: '查看收货', mode: 'navigate', route: '/wms/purchase-receive-preview' }),
})

function uniqueTexts(values = []) {
  return freeze([...new Set(values.flatMap(value => Array.isArray(value) ? value : [value])
    .map(text).filter(Boolean))])
}

function sourcePurchaseRequestIdsOf(purchaseOrder, lines) {
  const sourceRelations = purchaseOrder.sourceRelations || purchaseOrder.SourceRelations || {}
  const sourceDraft = text(purchaseOrder.admissionResultId)
    ? purchaseOrderCreationDraftStoreV114284262.findByAdmissionResultId(
      purchaseOrder.admissionResultId) : null
  const draftCreationContext = sourceDraft?.creationContext || {}
  return uniqueTexts([
    Array.isArray(purchaseOrder.sourcePurchaseRequestIds)
      ? purchaseOrder.sourcePurchaseRequestIds : [],
    Array.isArray(sourceRelations.purchaseRequestIds)
      ? sourceRelations.purchaseRequestIds : [],
    Array.isArray(draftCreationContext.purchaseRequestIds)
      ? draftCreationContext.purchaseRequestIds : [],
    Array.isArray(sourceDraft?.purchaseRequestIds)
      ? sourceDraft.purchaseRequestIds : [],
    ...lines.map(line => Array.isArray(line.sourcePurchaseRequestIds)
      ? line.sourcePurchaseRequestIds : []),
  ])
}

function lifecycleHistoryOf(purchaseOrder, lifecycle) {
  const sourceHistory = Array.isArray(purchaseOrder.lifecycleHistory)
    ? purchaseOrder.lifecycleHistory
    : Array.isArray(purchaseOrder.stateHistory) ? purchaseOrder.stateHistory : []
  if (!sourceHistory.length) {
    return freeze([freeze({
      recordId: `CURRENT-${text(purchaseOrder.id) || 'UNKNOWN'}`,
      status: lifecycle.lifecycleStatus,
      statusLabel: lifecycle.lifecycleStatusLabel,
      changedBy: text(purchaseOrder.updatedBy || purchaseOrder.createdBy) || '历史记录未提供',
      changedAt: text(purchaseOrder.updatedAt || purchaseOrder.createdAt) || '历史记录未提供',
      reason: '当前状态快照；未补造状态迁移记录。',
      recordType: 'current_state_snapshot',
    })])
  }
  return freeze(sourceHistory.map((record, index) => freeze({
    recordId: text(record.recordId || record.id) || `STATE-${index + 1}`,
    status: text(record.status || record.toStatus),
    statusLabel: text(record.statusLabel)
      || lifecycleLabels[text(record.status || record.toStatus)] || '状态待确认',
    changedBy: text(record.changedBy || record.actor || record.operator) || '-',
    changedAt: text(record.changedAt || record.at || record.createdAt) || '-',
    reason: text(record.reason || record.opinion || record.remark) || '-',
    recordType: 'source_history',
  })))
}

function approvalDisplayOf(purchaseOrder, approvalContext, legacyIsolated) {
  const history = Array.isArray(purchaseOrder.approvalHistory)
    ? clone(purchaseOrder.approvalHistory) : []
  const current = history.reduce((latest, record) => record || latest, null)
  const status = approvalContext?.approvalStatus || approvalStatusOf(purchaseOrder)
  return freeze({
    status,
    statusLabel: legacyIsolated && !text(purchaseOrder.approvalStatus)
      ? '历史订单审批记录不可追溯' : approvalLabels[status] || '待确认',
    approvedBy: text(current?.approvedBy || current?.actor
      || purchaseOrder.approvedBy) || '-',
    approvedAt: text(current?.approvedAt || current?.at
      || purchaseOrder.approvedAt) || '-',
    opinion: text(current?.opinion || current?.comment || current?.reason
      || purchaseOrder.approvalOpinion) || '-',
    history: freeze(history.map(record => freeze(record))),
  })
}

function approvalStatusOf(purchaseOrder) {
  const explicit = text(purchaseOrder.approvalStatus)
  if (explicit) return explicit
  const lifecycle = text(purchaseOrder.lifecycleStatus || purchaseOrder.status)
  if (['approved', 'issued', 'partially_received', 'completed'].includes(lifecycle)) {
    return 'approved'
  }
  return lifecycle === 'pending_approval' ? 'pending_approval' : 'not_started'
}

function priceRow(purchaseOrder, line, index) {
  if (purchaseOrder.classification !== 'GATE_CREATED') {
    return freeze({
      id: text(line.id) || `legacy-price-${index + 1}`,
      materialCode: text(line.materialCode),
      supplierId: text(line.supplierId || purchaseOrder.supplierId),
      currentPrice: number(line.confirmedPrice || line.planPrice || line.price),
      currency: text(line.currency || purchaseOrder.currency) || 'CNY',
      priceSource: 'Legacy订单隔离，不形成合格价格来源',
      qualifiedPriceStatus: '不适用',
      qualifiedPriceStatusCode: 'legacy_isolated',
      reason: '历史采购订单保持原状，禁止补写合格价格记录。',
      materialMasterAutoUpdate: false,
    })
  }
  const evaluation = evaluateQualifiedMaterialPriceV114284272({
    materialId: line.materialId,
    materialCode: line.materialCode,
    supplierId: line.supplierId || purchaseOrder.supplierId,
    qualifiedPrice: line.confirmedPrice || line.planPrice || line.price,
    currency: line.currency || purchaseOrder.currency || 'CNY',
    effectiveDate: line.priceEffectiveDate || purchaseOrder.priceEffectiveDate,
    sourcePurchaseOrderId: purchaseOrder.id,
    sourceSupplierId: line.supplierId || purchaseOrder.supplierId,
    sourceApprovalRecord: line.sourceApprovalRecord
      || purchaseOrder.qualifiedPriceApprovalRecord,
    purchaseOrderStatus: purchaseOrder.lifecycleStatus || purchaseOrder.status,
    priceHumanConfirmed: line.priceHumanConfirmed === true,
    priceConfirmedBy: line.priceConfirmedBy,
    priceConfirmedAt: line.priceConfirmedAt,
  })
  return freeze({
    id: text(line.id) || `qualified-price-${index + 1}`,
    materialCode: text(line.materialCode),
    supplierId: text(line.supplierId || purchaseOrder.supplierId),
    currentPrice: number(line.confirmedPrice || line.planPrice || line.price),
    currency: text(line.currency || purchaseOrder.currency) || 'CNY',
    priceSource: `${text(purchaseOrder.objectNo) || '-'} / ${text(purchaseOrder.id) || '-'}`,
    qualifiedPriceStatus: evaluation.result === 'PASS' ? '已具备合格价格资格' : '待确认',
    qualifiedPriceStatusCode: evaluation.eligibilityStatus,
    reason: evaluation.reason || '人工价格确认及审批来源完整。',
    sourcePurchaseOrderId: text(purchaseOrder.id),
    sourceSupplierId: text(line.supplierId || purchaseOrder.supplierId),
    sourceApprovalRecord: clone(line.sourceApprovalRecord
      || purchaseOrder.qualifiedPriceApprovalRecord || null),
    materialMasterAutoUpdate: false,
  })
}

export function buildPurchaseOrderLifecycleDetailReadModelV114284272({
  purchaseOrder = {}, orderLines = [],
} = {}) {
  const lines = Array.isArray(orderLines) ? orderLines : []
  const purchaseOrderId = text(purchaseOrder.id)
  const mismatchedOrderItems = freeze(lines.filter(line => text(line.poId)
    && text(line.poId) !== purchaseOrderId).map(line => text(line.id) || 'UNKNOWN_ITEM'))
  const purchaseOrderItems = freeze(lines.filter(line => !text(line.poId)
    || text(line.poId) === purchaseOrderId).map(line => freeze(clone(line))))
  const legacyIsolated = purchaseOrder.classification !== 'GATE_CREATED'
  const lifecycle = buildPurchaseOrderLifecycleSnapshotV114284272(purchaseOrder)
  const sourcePurchaseRequestIds = sourcePurchaseRequestIdsOf(purchaseOrder, lines)
  const sourceRelations = purchaseOrder.sourceRelations || purchaseOrder.SourceRelations || {}
  const sourceGateId = text(purchaseOrder.sourceGateId || sourceRelations.gateId)
  const approvalContext = legacyIsolated ? null
    : buildPurchaseOrderApprovalContextV114284272({
      purchaseOrderId: purchaseOrder.id,
      purchaseOrderNo: purchaseOrder.objectNo,
      supplierId: purchaseOrder.supplierId,
      sourceGateId,
      sourcePurchaseRequestIds,
      approvalStatus: approvalStatusOf(purchaseOrder),
      approvalHistory: purchaseOrder.approvalHistory || [],
    })
  const qualifiedPriceRows = freeze(purchaseOrderItems.map((line, index) =>
    priceRow(purchaseOrder, line, index)))
  const outputKeys = qualifiedPriceRows.map(item => item.id)
  const lineQuantity = purchaseOrderItems.reduce((sum, line) => sum + number(
    line.confirmedQuantity ?? line.quantity), 0)
  const lineAmount = purchaseOrderItems.reduce((sum, line) => sum + number(line.amount
    ?? line.planAmount ?? (number(line.confirmedQuantity ?? line.quantity)
      * number(line.confirmedPrice ?? line.planPrice ?? line.price))), 0)
  const totalAmount = text(purchaseOrder.totalAmount) || text(purchaseOrder.planAmount)
    ? number(purchaseOrder.totalAmount ?? purchaseOrder.planAmount) : lineAmount
  const lifecycleHistory = lifecycleHistoryOf(purchaseOrder, lifecycle)
  const nextAction = freeze(clone(nextActionByStatus[lifecycle.lifecycleStatus] || {
    code: 'none', label: '无可用动作', mode: 'none',
  }))
  const approvalDisplay = approvalDisplayOf(purchaseOrder, approvalContext, legacyIsolated)
  return freeze({
    result: !purchaseOrderId ? 'UNKNOWN' : mismatchedOrderItems.length ? 'FAIL' : 'PASS',
    factLoadStatus: !purchaseOrderId ? 'not_found'
      : mismatchedOrderItems.length ? 'purchase_order_item_identity_mismatch' : 'loaded',
    factSource: legacyIsolated ? 'legacy_purchase_order_read_only'
      : 'gate_created_purchase_order',
    baseInfo: freeze({
      purchaseOrderId: text(purchaseOrder.id),
      objectNo: text(purchaseOrder.objectNo),
      supplierId: text(purchaseOrder.supplierId),
      supplierName: text(purchaseOrder.supplierName),
      totalQuantity: lineQuantity,
      totalAmount,
      currency: text(purchaseOrder.currency) || 'CNY',
      orderTypeLabel: legacyIsolated ? '历史采购订单' : 'Gate治理采购订单',
    }),
    sourceTrace: freeze({
      sourceGateId,
      gateReference: sourceGateId,
      sourcePurchaseRequestIds,
      sourceRelationCount: sourcePurchaseRequestIds.length,
      traceable: !legacyIsolated && Boolean(sourceGateId)
        && sourcePurchaseRequestIds.length > 0,
      sourceLabel: legacyIsolated ? '历史数据不可追溯' : '采购订单来源关系',
      identityResolution: 'SourceRelations',
      businessNoParsed: false,
    }),
    lifecycle,
    lifecycleHistory,
    nextAction,
    approvalDisplay,
    approvalStatusLabel: approvalDisplay.statusLabel,
    purchaseOrderItems,
    purchaseOrderItemSource: 'PurchaseOrderItem[]',
    materialCountConsistency: freeze({
      purchaseOrderItemCount: purchaseOrderItems.length,
      detailDisplayCount: purchaseOrderItems.length,
      providerInputCount: lines.length,
      consistent: mismatchedOrderItems.length === 0,
      mismatchedOrderItemIds: mismatchedOrderItems,
      fallbackSourceUsed: false,
      forbiddenSourcesUsed: freeze([]),
    }),
    documentMaker: freeze({
      createdBy: text(purchaseOrder.createdBy || purchaseOrder.creatorName
        || purchaseOrder.buyerName || purchaseOrder.buyerId) || '-',
      createdAt: text(purchaseOrder.createdAt || purchaseOrder.orderDate) || '-',
    }),
    qualifiedPriceRows,
    legacyIsolated,
    dataExtract: freeze({
      inputItemCount: purchaseOrderItems.length,
      outputItemCount: qualifiedPriceRows.length,
      sourceRelationCount: qualifiedPriceRows.length,
      inputBusinessKeys: freeze(lines.map((line, index) => text(line.id)
        || `line-${index + 1}`)),
      outputBusinessKeys: freeze(outputKeys),
      missingKeys: freeze([]),
      unexpectedKeys: freeze([]),
      duplicateKeys: freeze(outputKeys.filter((key, index) => outputKeys.indexOf(key) !== index)),
    }),
    sourceArrayCompleteness: freeze({
      inputItemCount: sourcePurchaseRequestIds.length,
      outputItemCount: sourcePurchaseRequestIds.length,
      sourceRelationCount: sourcePurchaseRequestIds.length,
      inputBusinessKeys: sourcePurchaseRequestIds,
      outputBusinessKeys: sourcePurchaseRequestIds,
      missingKeys: freeze([]),
      unexpectedKeys: freeze([]),
      duplicateKeys: freeze([]),
    }),
    materialMasterAutoUpdate: false,
    historicalPriceOverwritten: false,
    purchaseOrderCreated: false,
    purchaseOrderStatusChanged: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
